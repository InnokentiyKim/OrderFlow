import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger(__name__)


_CREATE_ROLES = text("""
    DO $$
    BEGIN
        -- app_user: regular user, sees only own orders via RLS
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
            CREATE ROLE app_user;
        END IF;

        -- app_admin: full visibility over all orders
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_admin') THEN
            CREATE ROLE app_admin;
        END IF;
    END$$;
""")

# Grant both roles to the service DB user so it can SET LOCAL ROLE at runtime.
# Uses current_user — works regardless of which account the service connects with.
_GRANT_ROLES_TO_SERVICE = text("""
    DO $$
    DECLARE svc TEXT := current_user;
    BEGIN
        EXECUTE format('GRANT app_user  TO %I', svc);
        EXECUTE format('GRANT app_admin TO %I', svc);
    END$$;
""")

_GRANT_TABLE_PRIVILEGES_USER = text(
    "GRANT SELECT, INSERT, UPDATE ON TABLE orders TO app_user"
)
_GRANT_TABLE_PRIVILEGES_ADMIN = text(
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE orders TO app_admin"
)

_ENABLE_RLS = text("ALTER TABLE orders ENABLE ROW LEVEL SECURITY")

# FORCE RLS applies policies even to the table owner.
# Without FORCE the owner bypasses all policies.
_FORCE_RLS = text("ALTER TABLE orders FORCE ROW LEVEL SECURITY")

_CREATE_POLICIES = text("""
    -- ── app_user policies ───────────────────────────────────────────────
    -- USING   → filters rows on SELECT / UPDATE / DELETE
    -- WITH CHECK → validates rows on INSERT / UPDATE

    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = 'orders' AND policyname = 'orders_user_select'
        ) THEN
            CREATE POLICY orders_user_select
                ON orders FOR SELECT TO app_user
                USING (user_id = current_setting('app.current_user_id')::uuid);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = 'orders' AND policyname = 'orders_user_insert'
        ) THEN
            CREATE POLICY orders_user_insert
                ON orders FOR INSERT TO app_user
                WITH CHECK (user_id = current_setting('app.current_user_id')::uuid);
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = 'orders' AND policyname = 'orders_user_update'
        ) THEN
            CREATE POLICY orders_user_update
                ON orders FOR UPDATE TO app_user
                USING     (user_id = current_setting('app.current_user_id')::uuid)
                WITH CHECK (user_id = current_setting('app.current_user_id')::uuid);
        END IF;

        -- ── app_admin policy ────────────────────────────────────────────────────
        -- Admins see and modify every row — no ownership restriction.
        IF NOT EXISTS (
            SELECT 1 FROM pg_policies
            WHERE tablename = 'orders' AND policyname = 'orders_admin_all'
        ) THEN
            CREATE POLICY orders_admin_all
                ON orders FOR ALL TO app_admin
                USING (true)
                WITH CHECK (true);
        END IF;
    END$$;
""")


async def apply_rls_setup(engine: AsyncEngine) -> None:
    """Bootstrap RLS roles and policies idempotently.

    Safe to call on every application startup:
    all DDL is guarded by ``IF NOT EXISTS`` so repeated calls are no-ops.

    Args:
        engine: The shared ``AsyncEngine`` instance from ``database.py``.
    """
    await logger.ainfo("RLS setup: starting")

    async with engine.begin() as conn:
        await logger.adebug("RLS setup: creating roles app_user / app_admin")
        await conn.execute(_CREATE_ROLES)

        await logger.adebug("RLS setup: granting roles to service account")
        await conn.execute(_GRANT_ROLES_TO_SERVICE)

        await logger.adebug("RLS setup: granting table privileges")
        await conn.execute(_GRANT_TABLE_PRIVILEGES_USER)
        await conn.execute(_GRANT_TABLE_PRIVILEGES_ADMIN)

        await logger.adebug("RLS setup: enabling RLS + FORCE on orders")
        await conn.execute(_ENABLE_RLS)
        await conn.execute(_FORCE_RLS)

        await logger.adebug("RLS setup: creating / verifying RLS policies")
        await conn.execute(_CREATE_POLICIES)

    await logger.ainfo("RLS setup: done")

"""ContextVars that carry the RLS identity of the current HTTP request.

These vars are set by ``RLSContextMiddleware`` after JWT authentication
and are read by ``provide_rls_session`` to inject SET LOCAL into the
PostgreSQL transaction before any SQL is executed.

Usage:
    # Write (middleware):
    rls_user_id.set(uuid.UUID("..."))
    rls_db_role.set("app_customer")

    # Read (db session provider):
    user_id = rls_user_id.get()   # None if not authenticated
    role    = rls_db_role.get()   # None if not authenticated
"""

import uuid
from contextvars import ContextVar

rls_user_id: ContextVar[uuid.UUID | None] = ContextVar("rls_user_id", default=None)
rls_db_role: ContextVar[str | None] = ContextVar("rls_db_role", default=None)

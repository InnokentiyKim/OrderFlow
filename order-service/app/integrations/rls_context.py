import uuid
from contextvars import ContextVar

rls_user_id: ContextVar[uuid.UUID | None] = ContextVar("rls_user_id", default=None)
rls_db_role: ContextVar[str | None] = ContextVar("rls_db_role", default=None)

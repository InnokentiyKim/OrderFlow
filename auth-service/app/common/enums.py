from enum import StrEnum


class UserRoleEnum(StrEnum):
    USER = "user"
    ADMIN = "admin"


class AuthTokenTypeEnum(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"

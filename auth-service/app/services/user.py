from typing import TypeAlias, Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Configs, app_config
from app.core.logger import get_logger
from app.core.security.adapter import SecurityDependency, SecurityAdapter
from app.integrations.dao.user import UserDAO
from app.integrations.database import SessionDependency
from app.models.users import User
from app.schemas import command as commands
from app.schemas import fetch as fetches
from app.schemas import result as results
from app.services.exceptions import InvalidCredentialsError, UserNotFoundError
from fastapi import Depends


class UserService:
    def __init__(
        self,
        session: AsyncSession,
        security_adapter: SecurityAdapter,
        user_dao: UserDAO = UserDAO(),
        config: Configs = app_config,
    ) -> None:
        self._session = session
        self._user = user_dao
        self._security = security_adapter
        self._logger = get_logger("AuthenticationService")
        self._config = config

    async def create_new_user(
        self, cmd: commands.CreateUserCommand
    ) -> results.UserInfo:
        """
        Create a new user in the system.

        This method creates a new user in the system after ensuring that no user with the same
        email already exists. It hashes the provided password before storing it.

        Args:
            cmd (commands.CreateUserCommand): Command object containing user details.

        Returns:
            UserInfo: The created user object.

        Raises:
            UserAlreadyExistsError: If a user with the given email already exists.
        """

        hashed_password = await self._security.hash_password(
            plain_password=cmd.password.get_secret_value()
        )

        new_user = User(
            email=cmd.email,
            hashed_password=hashed_password,
            role=cmd.role,
            is_active=cmd.is_active,
        )
        await self._user.add_user(session=self._session, user=new_user)
        await self._logger.ainfo("Created new user", user_id=new_user.id)

        return results.UserInfo.from_model(new_user)

    async def verify_user_credentials(
        self, cmd: commands.VerifyUserCredentialsCommand
    ) -> results.UserInfo:
        """
        Validates password authentication credentials and returns the user ID.

        Args:
            cmd (commands.ValidatePasswordCredentials): The command containing the credentials to validate.

        Returns:
            results.UserID: A data structure containing the ID of the successfully authenticated user.

        Raises:
            InvalidCredentialsError: If no user is found for the provided email, or if the password verification fails.
        """
        user = await self._user.get_user_by_email(
            session=self._session, email=cmd.email
        )

        if not user:
            raise UserNotFoundError

        if not await self._security.verify_hashed_password(
            plain_password=cmd.password.get_secret_value(),
            hashed_password=user.hashed_password,
        ):
            await self._logger.awarning("Incorrect password for user", user_id=user.id)
            raise InvalidCredentialsError

        return results.UserInfo.from_model(user)

    async def get_user_info(self, fetch: fetches.GetUserInfo) -> results.UserInfo:
        """
        Retrieve user information by user ID.

        Args:
            fetch (GetUserInfo): Object containing the user ID to fetch.

        Returns:
            UserInfo: The user object corresponding to the provided user ID.

        Raises:
            UserIsNotFoundError: If the user does not exist.
        """
        user = await self._user.get_user_by_id(
            session=self._session, user_id=fetch.user_id
        )
        if not user:
            raise UserNotFoundError

        return results.UserInfo.from_model(user)


def provide_user_service(
    session: SessionDependency,
    security_adapter: SecurityDependency,
) -> UserService:
    return UserService(session=session, security_adapter=security_adapter) # type: ignore


UserServiceDependency: TypeAlias = Annotated[UserService, Depends(provide_user_service)]

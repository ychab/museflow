from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm

from museflow.application.inputs.user import UserCreateInput
from museflow.application.inputs.user import UserUpdateInput
from museflow.application.ports.security import AccessTokenManagerPort
from museflow.application.ports.security import PasswordHasherPort
from museflow.application.ports.unit_of_work import UnitOfWorkPort
from museflow.application.use_cases.user_authenticate import authenticate_user
from museflow.application.use_cases.user_create import create_user
from museflow.application.use_cases.user_delete import delete_user
from museflow.application.use_cases.user_update import update_user
from museflow.domain.entities.user import User
from museflow.domain.exceptions import UserAlreadyExistsException
from museflow.domain.exceptions import UserEmailAlreadyExistsException
from museflow.domain.exceptions import UserInactive
from museflow.domain.exceptions import UserInvalidCredentials
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.api.dependencies import get_access_token_manager
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.api.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.api.schemas import UserResponse
from museflow.infrastructure.entrypoints.api.schemas import UserWithToken

router = APIRouter()


@router.post("/register", name="user_register", status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreateInput,
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> UserWithToken:
    try:
        user = await create_user(
            user_data=user_data,
            uow=uow,
            password_hasher=password_hasher,
        )
    except UserAlreadyExistsException as e:
        # Accepted risk (#102): this answer reveals that the email has an account. A neutral one needs a full user
        # workflow with email verification, not worth building for a local, single-user app still in development.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered") from e

    access_token = access_token_manager.create(data={"sub": str(user.id)})

    return UserWithToken(user=UserResponse.model_validate(user), access_token=access_token)


@router.post("/login", name="user_login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> UserWithToken:
    try:
        user = await authenticate_user(
            email=form_data.username,
            password=form_data.password,
            uow=uow,
            password_hasher=password_hasher,
        )
    except (UserNotFound, UserInvalidCredentials) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except UserInactive as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive") from e

    access_token = access_token_manager.create(data={"sub": str(user.id)})

    return UserWithToken(user=UserResponse.model_validate(user), access_token=access_token)


@router.get("/me", name="user_me")
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", name="user_me")
async def update_current_user(
    user_data: UserUpdateInput,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
) -> UserResponse:
    try:
        updated_user = await update_user(
            user=current_user,
            user_data=user_data,
            uow=uow,
            password_hasher=password_hasher,
        )
    except UserEmailAlreadyExistsException as e:
        # Accepted risk (#102): see `register`.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered") from e

    return UserResponse.model_validate(updated_user)


@router.delete("/me", name="user", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
) -> None:
    await delete_user(user_id=current_user.id, uow=uow)
    return None

from fastapi import APIRouter
from fastapi import Depends
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
from museflow.infrastructure.entrypoints.api.dependencies import get_access_token_manager
from museflow.infrastructure.entrypoints.api.dependencies import get_current_user
from museflow.infrastructure.entrypoints.api.dependencies import get_password_hasher
from museflow.infrastructure.entrypoints.api.dependencies import get_unit_of_work
from museflow.infrastructure.entrypoints.api.schemas import UserResponse
from museflow.infrastructure.entrypoints.api.schemas import UserWithToken

router = APIRouter()


@router.post("/register", name="user_register", status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreateInput,
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> UserWithToken:
    user = await create_user(
        user_in=user_in,
        uow=uow,
        password_hasher=password_hasher,
    )

    access_token = access_token_manager.create(data={"sub": str(user.id)})

    return UserWithToken(user=UserResponse.model_validate(user), access_token=access_token)


@router.post("/login", name="user_login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> UserWithToken:
    user = await authenticate_user(
        email=form_data.username,
        password=form_data.password,
        uow=uow,
        password_hasher=password_hasher,
    )

    access_token = access_token_manager.create(data={"sub": str(user.id)})

    return UserWithToken(user=UserResponse.model_validate(user), access_token=access_token)


@router.get("/me", name="user_me")
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", name="user_me")
async def update_current_user(
    user_in: UserUpdateInput,
    current_user: User = Depends(get_current_user),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
) -> UserResponse:
    updated_user = await update_user(
        user=current_user,
        user_in=user_in,
        uow=uow,
        password_hasher=password_hasher,
    )

    return UserResponse.model_validate(updated_user)


@router.delete("/me", name="user", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    uow: UnitOfWorkPort = Depends(get_unit_of_work),
) -> None:
    await delete_user(user_id=current_user.id, uow=uow)
    return None

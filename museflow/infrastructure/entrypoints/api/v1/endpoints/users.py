from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm

from museflow.application.inputs.user import UserCreateInput
from museflow.application.inputs.user import UserUpdateInput
from museflow.application.use_cases.user_authenticate import authenticate_user
from museflow.application.use_cases.user_create import create_user
from museflow.application.use_cases.user_delete import delete_user
from museflow.application.use_cases.user_update import update_user
from museflow.infrastructure.entrypoints.api.dependencies import AccessTokenManagerDep
from museflow.infrastructure.entrypoints.api.dependencies import CurrentUserDep
from museflow.infrastructure.entrypoints.api.dependencies import PasswordHasherDep
from museflow.infrastructure.entrypoints.api.dependencies import UnitOfWorkDep
from museflow.infrastructure.entrypoints.api.schemas.users import UserResponse
from museflow.infrastructure.entrypoints.api.schemas.users import UserWithToken

router = APIRouter()


@router.post("/register", name="user_register", status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreateInput,
    uow: UnitOfWorkDep,
    password_hasher: PasswordHasherDep,
    access_token_manager: AccessTokenManagerDep,
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
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    uow: UnitOfWorkDep,
    password_hasher: PasswordHasherDep,
    access_token_manager: AccessTokenManagerDep,
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
async def get_current_user_info(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", name="user_me")
async def update_current_user(
    user_in: UserUpdateInput,
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
    password_hasher: PasswordHasherDep,
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
    current_user: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> None:
    await delete_user(user_id=current_user.id, uow=uow)
    return None

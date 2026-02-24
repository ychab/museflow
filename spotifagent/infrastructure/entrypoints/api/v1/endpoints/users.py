from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm

from spotifagent.application.use_cases.user_authenticate import user_authenticate
from spotifagent.application.use_cases.user_create import user_create
from spotifagent.application.use_cases.user_update import user_update
from spotifagent.domain.entities.users import User
from spotifagent.domain.entities.users import UserCreate
from spotifagent.domain.entities.users import UserUpdate
from spotifagent.domain.exceptions import UserAlreadyExistsException
from spotifagent.domain.exceptions import UserEmailAlreadyExistsException
from spotifagent.domain.exceptions import UserInactive
from spotifagent.domain.exceptions import UserInvalidCredentials
from spotifagent.domain.exceptions import UserNotFound
from spotifagent.domain.ports.repositories.users import UserRepositoryPort
from spotifagent.domain.ports.security import AccessTokenManagerPort
from spotifagent.domain.ports.security import PasswordHasherPort
from spotifagent.infrastructure.entrypoints.api.dependencies import get_access_token_manager
from spotifagent.infrastructure.entrypoints.api.dependencies import get_current_user
from spotifagent.infrastructure.entrypoints.api.dependencies import get_password_hasher
from spotifagent.infrastructure.entrypoints.api.dependencies import get_user_repository
from spotifagent.infrastructure.entrypoints.api.schemas import UserResponse
from spotifagent.infrastructure.entrypoints.api.schemas import UserWithToken

router = APIRouter()


@router.post("/register", name="user_register", status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    user_repository: UserRepositoryPort = Depends(get_user_repository),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> UserWithToken:
    try:
        user = await user_create(
            user_data=user_data,
            user_repository=user_repository,
            password_hasher=password_hasher,
        )
    except UserAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    access_token = access_token_manager.create(data={"sub": str(user.id)})

    return UserWithToken(user=UserResponse.model_validate(user), access_token=access_token)


@router.post("/login", name="user_login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
    access_token_manager: AccessTokenManagerPort = Depends(get_access_token_manager),
) -> UserWithToken:
    try:
        user = await user_authenticate(
            email=form_data.username,
            password=form_data.password,
            user_repository=user_repository,
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
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
    password_hasher: PasswordHasherPort = Depends(get_password_hasher),
) -> UserResponse:
    try:
        updated_user = await user_update(
            user=current_user,
            user_data=user_data,
            user_repository=user_repository,
            password_hasher=password_hasher,
        )
    except UserEmailAlreadyExistsException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered") from e

    return UserResponse.model_validate(updated_user)


@router.delete("/me", name="user", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(
    current_user: User = Depends(get_current_user),
    user_repository: UserRepositoryPort = Depends(get_user_repository),
) -> None:
    await user_repository.delete(current_user.id)
    return None

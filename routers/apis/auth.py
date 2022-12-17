import sys

sys.path.append("..")

from fastapi import Depends, HTTPException, status, APIRouter
from pydantic import BaseModel
from typing import Optional
import models
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import get_db
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import datetime, timedelta
from jose import jwt
from dotenv import load_dotenv
import os

load_dotenv()


# SECRET_KEY = os.getenv("SECRET_KEY")
AUTH_ACCESS_TOKEN_KEY = os.getenv("AUTH_ACCESS_TOKEN_KEY")
AUTH_REFRESH_TOKEN_KEY = os.getenv("AUTH_REFRESH_TOKEN_KEY")
ALGORITHM = "HS256"


class CreateUser(BaseModel):
    username: str
    email: Optional[str]
    first_name: str
    last_name: str
    password: str
    phone_number: Optional[str]


bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "user": "Not authorized",
        },
    },
)


def get_password_hash(password):
    return bcrypt_context.hash(password)


def verify_password(plain_password, hashed_password):
    return bcrypt_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(models.Users).filter(models.Users.username == username).first()

    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False

    return user


def create_access_and_refresh_token(
    username: str, user_id: int, expires_delta: Optional[timedelta] = None
):
    accessEncode = {
        "sub": username,
        "id": user_id,
    }
    refreshEncode = {
        "sub": username,
        "id": user_id,
        "exp": datetime.utcnow() + timedelta(days=(30 * 6)),
    }

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    accessEncode.update(
        {
            "exp": expire,
        }
    )

    access_token = jwt.encode(accessEncode, AUTH_ACCESS_TOKEN_KEY, algorithm=ALGORITHM)
    refresh_token = jwt.encode(
        refreshEncode, AUTH_REFRESH_TOKEN_KEY, algorithm=ALGORITHM
    )

    # return jwt.encode(accessEncode, AUTH_ACCESS_TOKEN_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "refresh_token": refresh_token}


def create_access_token(
    username: str, user_id: int, expires_delta: Optional[timedelta] = None
):
    accessEncode = {
        "sub": username,
        "id": user_id,
    }

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    accessEncode.update(
        {
            "exp": expire,
        }
    )

    access_token = jwt.encode(accessEncode, AUTH_ACCESS_TOKEN_KEY, algorithm=ALGORITHM)

    # return jwt.encode(accessEncode, AUTH_ACCESS_TOKEN_KEY, algorithm=ALGORITHM)
    return access_token


async def get_current_user(token: str = Depends(oauth2_bearer)):
    try:
        payload = jwt.decode(token, AUTH_ACCESS_TOKEN_KEY, algorithms=ALGORITHM)
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        if username is None or user_id is None:
            raise get_user_exception()

        return {
            "username": username,
            "id": user_id,
        }
    except:
        raise get_user_exception()


async def get_access_token(token: str = Depends(oauth2_bearer)):
    try:
        payload = jwt.decode(token, AUTH_REFRESH_TOKEN_KEY, algorithms=ALGORITHM)
        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        print(user_id)
        if username is None or user_id is None:
            raise get_user_exception()

        access_token = create_access_token(username, user_id)

        print(access_token)

        return access_token
    except:
        raise get_user_exception()


@router.post("/signup")
async def create_new_user(create_user: CreateUser, db: Session = Depends(get_db)):
    create_user_model = models.Users()
    create_user_model.email = create_user.email
    create_user_model.username = create_user.username
    create_user_model.first_name = create_user.first_name
    create_user_model.last_name = create_user.last_name
    create_user_model.phone_number = create_user.phone_number

    hash_password = get_password_hash(create_user.password)

    create_user_model.hashed_password = hash_password
    create_user_model.is_active = True

    db.add(create_user_model)
    db.commit()


@router.post("/login")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    user = authenticate_user(form_data.username, form_data.password, db)

    if not user:
        raise token_exception()

    token_expires = timedelta(minutes=20)
    token = create_access_and_refresh_token(
        user.username, user.id, expires_delta=token_expires
    )

    return {
        "access_token": token.get("access_token"),
        "refresh_token": token.get("refresh_token"),
    }


@router.post("/refresh")
async def refresh_token(access_token: str = Depends(get_access_token)):
    return {"access_token": access_token, "hi": "by"}


# Exceptions
def get_user_exception():
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    return credentials_exception


def token_exception():
    token_exception_response = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    return token_exception_response

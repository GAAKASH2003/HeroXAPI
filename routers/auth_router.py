from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional
import jwt
import bcrypt
from datetime import datetime, timedelta
from database import db
from auth import get_current_user
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from utils.activity_logger import ActivityLogger
import os
import dotenv
from authlib.integrations.starlette_client import OAuth
from fastapi.responses import RedirectResponse
from starlette.config import Config
from starlette.middleware.sessions import SessionMiddleware
dotenv.load_dotenv()
# app.add_middleware(SessionMiddleware, secret_key="super-secret-session-key")

router = APIRouter()

# Pydantic models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    role:Optional[bool] = False
    # is_admin:Optional[bool] = False
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    ai_model:Optional[str] = None
    ai_provider:Optional[str] = None
    ai_max_tokens:Optional[int] = None
    ai_temperature:Optional[float] = None
    ai_is_active:Optional[bool] = None


    class Config:
        from_attributes = True

class SignupResponse(BaseModel):
    user: UserResponse
    access_token: str
    token_type: str
    expires_in: int

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID") 
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET") 
REDIRECT_URI = f"{os.getenv('BACKEND_URL')}/api/v1/auth/google/callback"


config = Config(environ={
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET
})
oauth = OAuth(config)
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

@router.get("/auth/google")
async def auth_google(request: Request):
    """Redirect to Google OAuth login page"""
    redirect_uri = REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google/callback")
async def auth_google_callback(request: Request):
    """Handle Google OAuth callback"""
    try:
        # Step 1: Get token safely
        token: Optional[dict] = await oauth.google.authorize_access_token(request)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve token from Google"
            )

        # Step 2: Extract user info
        user_info: Optional[dict] = token.get("userinfo")
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google login failed: missing user info"
            )

        email = user_info.get("email")
        name = user_info.get("name", "Unknown User")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account did not return an email"
            )

        # Step 3: Check if user exists in DB
        user = db(db.users.email == email).select().first()

        if not user:
            try:
                user_id = db.users.insert(
                    username=name,
                    email=email,
                    password=None,   # No password for Google users
                    is_admin=False,
                    full_name=name
                )
                db.commit()
                user = db.users(user_id)
            except Exception as e:
                # logger.error(f"Error creating user: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user"
                )

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User creation/retrieval failed"
            )

        # Step 4: Create JWT token
        try:
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.email, "user_id": user.id},
                expires_delta=access_token_expires
            )
        except Exception as e:
            # logger.error(f"JWT creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate access token"
            )

        # Step 5: Redirect to frontend
        frontend_url = f"{os.getenv('FRONTEND_URL')}/oauth/callback?token={access_token}"
        return RedirectResponse(url=frontend_url)

    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Unexpected error in Google OAuth callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected server error during Google login,{e}"
        )

@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, request: Request):
    """Create a new user account"""
    origin = request.headers.get("origin")
    # Check if user already exists
    existing_user = db(
        (db.users.email == user_data.email) | 
        (db.users.username == user_data.username)
    ).select().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    hashed_password = hash_password(user_data.password)
    print("Hashed password:", hashed_password)
    # Create user
    print("origin:", origin)
    if("https://hero-x-admin.vercel.app" in origin):
        user_id = db.users.insert(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            is_admin=True,
            full_name=user_data.full_name
        )
    else:
        user_id = db.users.insert(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            is_admin=False,
            full_name=user_data.full_name
        )
    
    db.commit()
    
    # Get the created user
    user = db.users(user_id)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id,"role":user.is_admin}, 
        expires_delta=access_token_expires
    )
    
    return SignupResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            # is_admin=user.is_admin,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at
        ),
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    


@router.post("/super_signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, request: Request):
    """Create a new user account"""
    origin = request.headers.get("origin")
    # Check if user already exists
    existing_user = db(
        (db.users.email == user_data.email) | 
        (db.users.username == user_data.username)
    ).select().first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )
    
    hashed_password = hash_password(user_data.password)
    print("Hashed password:", hashed_password)
    # Create user
    print("origin:",origin)
    if("https://hero-x-admin.vercel.app" in origin):
        user_id = db.users.insert(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            is_admin=True,
            full_name=user_data.full_name
        )
    else:
        user_id = db.users.insert(
            username=user_data.username,
            email=user_data.email,
            password=hashed_password,
            is_admin=False,
            full_name=user_data.full_name
        )
    
    db.commit()
    
    # Get the created user
    user = db.users(user_id)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id,"role":user.is_admin}, 
        expires_delta=access_token_expires
    )
    
    return SignupResponse(
        user=UserResponse(
            id=user.id,
            username=user.username,
            # is_admin=user.is_admin,
            email=user.email,
            full_name=user.full_name,
            created_at=user.created_at
        ),
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    

    

@router.post("/login", response_model=LoginResponse)
async def login(user_credentials: UserLogin, request: Request):
    """Login user and return access token"""
    origin = request.headers.get("origin")
    # Find user by email
    user = db(db.users.email == user_credentials.email).select().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if(user.password is None):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please login using Google OAuth"
        )
    if not user or not verify_password(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if("3001" in origin and not user.is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}, 
        expires_delta=access_token_expires
    )
    
    # Log login activity
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    # ActivityLogger.log_login(user.id, client_ip, user_agent)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role = current_user.is_admin,
        # is_admin=current_user.is_admin
        full_name=current_user.full_name,
        created_at=current_user.created_at,
        ai_model=current_user.ai_model,
        ai_provider=current_user.ai_provider,
        ai_max_tokens=current_user.ai_max_tokens,
        ai_temperature=current_user.ai_temperature,
        ai_is_active=current_user.ai_is_active
    )

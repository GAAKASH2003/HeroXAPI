from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
import bcrypt
from datetime import datetime
from database import db
from auth import get_current_user

router = APIRouter()

# Pydantic models
class UserProfileUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class AISettings(BaseModel):
    ai_model: str  # e.g., "gpt-4", "gpt-3.5-turbo", "claude-3", etc.
    api_key: str
    provider: str  # e.g., "openai", "anthropic", "google", etc.
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7
    is_active: bool = True

class UserSettingsResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    ai_model: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_max_tokens: Optional[int] = None
    ai_temperature: Optional[float] = None
    ai_is_active: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

@router.get("/profile", response_model=UserSettingsResponse)
async def get_user_profile(current_user = Depends(get_current_user)):
    """Get current user profile and settings"""
    
    return UserSettingsResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        ai_model=getattr(current_user, 'ai_model', None),
        ai_provider=getattr(current_user, 'ai_provider', None),
        ai_max_tokens=getattr(current_user, 'ai_max_tokens', None),
        ai_temperature=getattr(current_user, 'ai_temperature', None),
        ai_is_active=getattr(current_user, 'ai_is_active', None),
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@router.put("/profile", response_model=UserSettingsResponse)
async def update_user_profile(
    profile_data: UserProfileUpdate,
    current_user = Depends(get_current_user)
):
    """Update user profile (username, email, full_name)"""
    
    update_data = {}
    
    if profile_data.username is not None:
        # Check if username already exists
        existing_user = db(
            (db.users.username == profile_data.username) & 
            (db.users.id != current_user.id)
        ).select().first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        update_data['username'] = profile_data.username
    
    if profile_data.email is not None:
        # Check if email already exists
        existing_user = db(
            (db.users.email == profile_data.email) & 
            (db.users.id != current_user.id)
        ).select().first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        update_data['email'] = profile_data.email
    
    if profile_data.full_name is not None:
        update_data['full_name'] = profile_data.full_name
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update the user
    db(db.users.id == current_user.id).update(**update_data)
    db.commit()
    
    # Get the updated user
    updated_user = db.users(current_user.id)
    
    return UserSettingsResponse(
        id=updated_user.id,
        username=updated_user.username,
        email=updated_user.email,
        full_name=updated_user.full_name,
        ai_model=getattr(updated_user, 'ai_model', None),
        ai_provider=getattr(updated_user, 'ai_provider', None),
        ai_max_tokens=getattr(updated_user, 'ai_max_tokens', None),
        ai_temperature=getattr(updated_user, 'ai_temperature', None),
        ai_is_active=getattr(updated_user, 'ai_is_active', None),
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at
    )

@router.put("/password", status_code=status.HTTP_200_OK)
async def change_password(
    password_data: PasswordChange,
    current_user = Depends(get_current_user)
):
    """Change user password"""
    
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Hash new password
    hashed_new_password = hash_password(password_data.new_password)
    
    # Update password
    db(db.users.id == current_user.id).update(
        password=hashed_new_password,
        updated_at=datetime.utcnow()
    )
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.put("/ai-settings", response_model=UserSettingsResponse)
async def update_ai_settings(
    ai_settings: AISettings,
    current_user = Depends(get_current_user)
):
    """Update AI model settings and API key"""
    
    # Validate AI model and provider
    valid_providers = ["openai", "anthropic", "google", "azure", "custom","deepseek"]
    if ai_settings.provider.lower() not in valid_providers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid provider. Must be one of: {', '.join(valid_providers)}"
        )
    
    # Validate temperature range
    if ai_settings.temperature is not None and (ai_settings.temperature < 0 or ai_settings.temperature > 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Temperature must be between 0 and 2"
        )
    
    # Validate max_tokens
    if ai_settings.max_tokens is not None and ai_settings.max_tokens <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max tokens must be greater than 0"
        )
    
    # Update AI settings
    update_data = {
        'ai_model': ai_settings.ai_model,
        'ai_provider': ai_settings.provider.lower(),
        'ai_api_key': ai_settings.api_key,
        'ai_max_tokens': ai_settings.max_tokens,
        'ai_temperature': ai_settings.temperature,
        'ai_is_active': ai_settings.is_active,
        'updated_at': datetime.utcnow()
    }
    
    db(db.users.id == current_user.id).update(**update_data)
    db.commit()
    
    # Get the updated user
    updated_user = db.users(current_user.id)
    
    return UserSettingsResponse(
        id=updated_user.id,
        username=updated_user.username,
        email=updated_user.email,
        full_name=updated_user.full_name,
        ai_model=updated_user.ai_model,
        ai_provider=updated_user.ai_provider,
        ai_max_tokens=updated_user.ai_max_tokens,
        ai_temperature=updated_user.ai_temperature,
        ai_is_active=updated_user.ai_is_active,
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at
    )

@router.get("/ai-settings")
async def get_ai_settings(current_user = Depends(get_current_user)):
    """Get current AI settings (without API key for security)"""
    api_key_exists = getattr(current_user,'ai_api_key',None) is not None

    # return ai_models or {
    #      "ai_model":  'ai_model',
    #      "provider":  'ai_provider',
    #      "max_tokens":  'ai_max_tokens',
    #      "temperature":  'ai_temperature',
    #      "is_active":  'ai_is_active'
    #  }
    
    return {
        "ai_model": getattr(current_user, 'ai_model', None),
        "provider": getattr(current_user, 'ai_provider', None),
        "max_tokens": getattr(current_user, 'ai_max_tokens', None),
        "api_key": api_key_exists,
        "temperature": getattr(current_user, 'ai_temperature', None),
        "is_active": getattr(current_user, 'ai_is_active', None)
    }

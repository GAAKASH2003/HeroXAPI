from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from database import db
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from auth import get_current_user
from utils.activity_logger import ActivityLogger

router = APIRouter()

# Pydantic models
class SenderProfileBase(BaseModel):
    name: str
    auth_type: str  # 'smtp' or 'oauth'
    from_address: EmailStr
    from_name: Optional[str] = None
    is_active: bool = True

class SMTPSenderProfile(SenderProfileBase):
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str

class OAuthSenderProfile(SenderProfileBase):
    oauth_client_id: str
    oauth_client_secret: str
    oauth_refresh_token: str

class SenderProfileCreate(BaseModel):
    name: str
    auth_type: str
    from_address: EmailStr
    from_name: Optional[str] = None
    # SMTP fields
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    # OAuth fields
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    is_active: bool = True

class SenderProfileUpdate(BaseModel):
    name: Optional[str] = None
    from_address: Optional[EmailStr] = None
    from_name: Optional[str] = None
    # SMTP fields
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    # OAuth fields
    oauth_client_id: Optional[str] = None
    oauth_client_secret: Optional[str] = None
    oauth_refresh_token: Optional[str] = None
    is_active: Optional[bool] = None

class SenderProfileResponse(BaseModel):
    id: int
    name: str
    auth_type: str
    from_address: str
    from_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    oauth_client_id: Optional[str] = None
    is_active: bool
    is_admin: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

def checkIfAdmin(user_id: int) -> bool:
    """Check if a user is admin"""
    user = db(db.users.id == user_id).select().first()
    return user.is_admin if user else False


@router.post("/", response_model=SenderProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_sender_profile(
    profile_data: SenderProfileCreate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Create a new sender profile"""
    
    # Validate auth_type
    if profile_data.auth_type not in ['smtp', 'oauth']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="auth_type must be either 'smtp' or 'oauth'"
        )
    
    # Validate required fields based on auth_type
    if profile_data.auth_type == 'smtp':
        if not all([profile_data.smtp_host, profile_data.smtp_port, 
                   profile_data.smtp_username, profile_data.smtp_password]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SMTP configuration requires host, port, username, and password"
            )
    elif profile_data.auth_type == 'oauth':
        if not all([profile_data.oauth_client_id, profile_data.oauth_client_secret, 
                   profile_data.oauth_refresh_token]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth configuration requires client_id, client_secret, and refresh_token"
            )
    
    # Check if profile name already exists for this user
    existing_profile = db(
        (db.sender_profiles.user_id == current_user.id) & 
        (db.sender_profiles.name == profile_data.name)
    ).select().first()
    
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A sender profile with this name already exists"
        )
    
    # Create profile data
    profile_dict = {
        'name': profile_data.name,
        'user_id': current_user.id,
        'auth_type': profile_data.auth_type,
        'from_address': profile_data.from_address,
        'from_name': profile_data.from_name,
        'is_active': profile_data.is_active
    }
    
    # Add SMTP fields if provided
    if profile_data.auth_type == 'smtp':
        profile_dict.update({
            'smtp_host': profile_data.smtp_host,
            'smtp_port': profile_data.smtp_port,
            'smtp_username': profile_data.smtp_username,
            'smtp_password': profile_data.smtp_password
        })
    
    # Add OAuth fields if provided
    if profile_data.auth_type == 'oauth':
        profile_dict.update({
            'oauth_client_id': profile_data.oauth_client_id,
            'oauth_client_secret': profile_data.oauth_client_secret,
            'oauth_refresh_token': profile_data.oauth_refresh_token
        })
    
    # Insert the profile
    profile_id = db.sender_profiles.insert(**profile_dict)
    db.commit()
    
    # Get the created profile
    new_profile = db.sender_profiles(profile_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_activity(
            user_id=current_user.id,
            activity_type="sender_profile_created",
            resource_type="sender_profile",
            resource_id=profile_id,
            resource_name=profile_data.name,
            description=f"Created sender profile: {profile_data.name} ({profile_data.auth_type})",
            ip_address=client_ip,
            user_agent=user_agent
        )
    
    return SenderProfileResponse(
        id=new_profile.id,
        name=new_profile.name,
        auth_type=new_profile.auth_type,
        from_address=new_profile.from_address,
        from_name=new_profile.from_name,
        smtp_host=new_profile.smtp_host,
        smtp_port=new_profile.smtp_port,
        smtp_username=new_profile.smtp_username,
        oauth_client_id=new_profile.oauth_client_id,
        is_active=new_profile.is_active,
        is_admin=checkIfAdmin(new_profile.user_id),
        created_at=new_profile.created_at,
        updated_at=new_profile.updated_at
    )

@router.get("/", response_model=List[SenderProfileResponse])
async def list_sender_profiles(current_user = Depends(get_current_user)):
    """List all sender profiles for the current user"""
    
    # profiles = db(db.sender_profiles.user_id == current_user.id).select()
    query= (db.sender_profiles.user_id == current_user.id)
    if not current_user.is_admin:
        admin_ids = [user.id for user in db(db.users.is_admin == True).select(db.users.id)]
        query |= db.sender_profiles.user_id.belongs(admin_ids)
        profiles = db(query).select()
    else:
        profiles = db(db.sender_profiles).select()  
    
    return [
        SenderProfileResponse(
            id=profile.id,
            name=profile.name,
            auth_type=profile.auth_type,
            from_address=profile.from_address,
            from_name=profile.from_name,
            smtp_host=profile.smtp_host,
            smtp_port=profile.smtp_port,
            smtp_username=profile.smtp_username,
            oauth_client_id=profile.oauth_client_id,
            is_active=profile.is_active,
            is_admin=checkIfAdmin(profile.user_id),
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )
        for profile in profiles
    ]

@router.get("/{profile_id}", response_model=SenderProfileResponse)
async def get_sender_profile(
    profile_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific sender profile"""
    
    profile = db(
        (db.sender_profiles.id == profile_id) & 
        ((db.sender_profiles.user_id == current_user.id)| (current_user.is_admin))
    ).select().first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender profile not found"
        )
    
    return SenderProfileResponse(
        id=profile.id,
        name=profile.name,
        auth_type=profile.auth_type,
        from_address=profile.from_address,
        from_name=profile.from_name,
        smtp_host=profile.smtp_host,
        smtp_port=profile.smtp_port,
        smtp_username=profile.smtp_username,
        oauth_client_id=profile.oauth_client_id,
        is_admin=checkIfAdmin(profile.user_id),
        is_active=profile.is_active,
        created_at=profile.created_at,
        updated_at=profile.updated_at
    )

@router.put("/{profile_id}", response_model=SenderProfileResponse)
async def update_sender_profile(
    profile_id: int,
    profile_data: SenderProfileUpdate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Update a sender profile"""
    
    profile = db(
        (db.sender_profiles.id == profile_id) & 
        ((db.sender_profiles.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender profile not found"
        )
    
    # Prepare update data
    update_data = {}
    changes = {}
    
    if profile_data.name is not None:
        # Check if name already exists for this user
        existing_profile = db(
            (db.sender_profiles.user_id == current_user.id) & 
            (db.sender_profiles.name == profile_data.name) &
            (db.sender_profiles.id != profile_id)
        ).select().first()
        
        if existing_profile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A sender profile with this name already exists"
            )
        update_data['name'] = profile_data.name
        changes['name'] = profile_data.name
    
    if profile_data.from_address is not None:
        update_data['from_address'] = profile_data.from_address
        changes['from_address'] = profile_data.from_address
    
    if profile_data.from_name is not None:
        update_data['from_name'] = profile_data.from_name
        changes['from_name'] = profile_data.from_name
    
    if profile_data.is_active is not None:
        update_data['is_active'] = profile_data.is_active
        changes['is_active'] = profile_data.is_active
    
    # Update SMTP fields if provided
    if profile.auth_type == 'smtp':
        if profile_data.smtp_host is not None:
            update_data['smtp_host'] = profile_data.smtp_host
            changes['smtp_host'] = profile_data.smtp_host
        if profile_data.smtp_port is not None:
            update_data['smtp_port'] = profile_data.smtp_port
            changes['smtp_port'] = profile_data.smtp_port
        if profile_data.smtp_username is not None:
            update_data['smtp_username'] = profile_data.smtp_username
            changes['smtp_username'] = profile_data.smtp_username
        if profile_data.smtp_password is not None:
            update_data['smtp_password'] = profile_data.smtp_password
            changes['smtp_password'] = "***"  # Don't log actual password
    
    # Update OAuth fields if provided
    if profile.auth_type == 'oauth':
        if profile_data.oauth_client_id is not None:
            update_data['oauth_client_id'] = profile_data.oauth_client_id
            changes['oauth_client_id'] = profile_data.oauth_client_id
        if profile_data.oauth_client_secret is not None:
            update_data['oauth_client_secret'] = profile_data.oauth_client_secret
            changes['oauth_client_secret'] = "***"  # Don't log actual secret
        if profile_data.oauth_refresh_token is not None:
            update_data['oauth_refresh_token'] = profile_data.oauth_refresh_token
            changes['oauth_refresh_token'] = "***"  # Don't log actual token
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update the profile
    db(db.sender_profiles.id == profile_id).update(**update_data)
    db.commit()
    
    # Get the updated profile
    updated_profile = db.sender_profiles(profile_id)
    
    # Log activity
    if request and changes:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_activity(
            user_id=current_user.id,
            activity_type="sender_profile_updated",
            resource_type="sender_profile",
            resource_id=profile_id,
            resource_name=updated_profile.name,
            description=f"Updated sender profile: {updated_profile.name}",
            ip_address=client_ip,
            user_agent=user_agent,
            metadata={"changes": changes}
        )
    
    return SenderProfileResponse(
        id=updated_profile.id,
        name=updated_profile.name,
        auth_type=updated_profile.auth_type,
        from_address=updated_profile.from_address,
        from_name=updated_profile.from_name,
        smtp_host=updated_profile.smtp_host,
        smtp_port=updated_profile.smtp_port,
        smtp_username=updated_profile.smtp_username,
        oauth_client_id=updated_profile.oauth_client_id,
        is_active=updated_profile.is_active,
        is_admin=checkIfAdmin(updated_profile.user_id),
        created_at=updated_profile.created_at,
        updated_at=updated_profile.updated_at
    )

@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sender_profile(
    profile_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Delete a sender profile"""
    
    profile = db(
        (db.sender_profiles.id == profile_id) & 
        ((db.sender_profiles.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender profile not found"
        )
    
    # Log activity before deletion
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_activity(
            user_id=current_user.id,
            activity_type="sender_profile_deleted",
            resource_type="sender_profile",
            resource_id=profile_id,
            resource_name=profile.name,
            description=f"Deleted sender profile: {profile.name}",
            ip_address=client_ip,
            user_agent=user_agent
        )
    
    # Delete the profile
    db(db.sender_profiles.id == profile_id).delete()
    db.commit()
    
    return None

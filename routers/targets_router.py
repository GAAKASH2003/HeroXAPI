from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Union
from datetime import datetime
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger

router = APIRouter()

# Pydantic models
class TargetCreate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    position: Optional[str] = None
    group_id: Optional[int] = None
    is_active: bool = True

class TargetUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    position: Optional[str] = None
    group_id: Optional[int] = None
    is_active: Optional[bool] = None

class TargetResponse(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str
    position: Optional[str] = None
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    is_active: bool
    is_admin: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

def checkIfAdmin(user_id: int) -> bool:
    """Check if a user is admin"""
    user = db(db.users.id == user_id).select().first()
    return user.is_admin if user else False

@router.post("/", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    target_data: TargetCreate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Create a new target (employee)"""
    
    # Check if email already exists for this user
    existing_target = db(
        (db.targets.user_id == current_user.id) & 
        (db.targets.email == target_data.email)
    ).select().first()
    
    if existing_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A target with this email already exists"
        )
    
    # Validate group_id if provided
    if target_data.group_id:
        group = db(
            (db.groups.id == target_data.group_id) & 
            ((db.groups.user_id == current_user.id) | (current_user.is_admin))
        ).select().first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid group_id: group not found or not owned by user"
            )
    
    # Create the target
    target_id = db.targets.insert(
        first_name=target_data.first_name,
        last_name=target_data.last_name,
        email=target_data.email,
        position=target_data.position,
        group_id=target_data.group_id,
        user_id=current_user.id,
        is_active=target_data.is_active
    )
    db.commit()
    
    # Get the created target with group info
    new_target = db.targets(target_id)
    group_name = None
    if new_target.group_id:
        group = db.groups(new_target.group_id)
        group_name = group.name if group else None
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_target_added(
            current_user.id, 
            target_id, 
            target_data.email, 
            client_ip, 
            user_agent
        )
    
    return TargetResponse(
        id=new_target.id,
        first_name=new_target.first_name,
        last_name=new_target.last_name,
        email=new_target.email,
        position=new_target.position,
        group_id=new_target.group_id,
        group_name=group_name,
        is_active=new_target.is_active,
        is_admin=checkIfAdmin(new_target.user_id),
        created_at=new_target.created_at,
        updated_at=new_target.updated_at
    )



@router.get("/", response_model=List[TargetResponse])
async def list_targets(
    group_id: Optional[int] = None,
    current_user = Depends(get_current_user)
):
    """List all targets for the current user, optionally filtered by group"""

    query = (db.targets.user_id == current_user.id) | (current_user.is_admin)

    if group_id:
        # Validate group_id belongs to user
        group = db(
            (db.groups.id == group_id) & 
            ((db.groups.user_id == current_user.id) | (current_user.is_admin))
        ).select().first()
        
        if not group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid group_id: group not found or not owned by user"
            )
        query &= db.targets.group_id == group_id
    
    targets = db(query).select()
    
    # Get group names for all targets
    group_ids = [target.group_id for target in targets if target.group_id]
    groups = {}
    if group_ids:
        groups_data = db(db.groups.id.belongs(group_ids)).select()
        groups = {group.id: group.name for group in groups_data}
    
    return [
        TargetResponse(
            id=target.id,
            first_name=target.first_name,
            last_name=target.last_name,
            email=target.email,
            position=target.position,
            group_id=target.group_id,
            group_name=groups.get(target.group_id) if target.group_id else None,
            is_active=target.is_active,
            is_admin=checkIfAdmin(target.user_id),
            created_at=target.created_at,
            updated_at=target.updated_at
        )
        for target in targets
    ]

@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific target"""
    
    target = db(
        (db.targets.id == target_id) & 
        ((db.targets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )
    
    # Get group name if target has a group
    group_name = None
    if target.group_id:
        group = db.groups(target.group_id)
        group_name = group.name if group else None
    
    return TargetResponse(
        id=target.id,
        first_name=target.first_name,
        last_name=target.last_name,
        email=target.email,
        position=target.position,
        group_id=target.group_id,
        group_name=group_name,
        is_active=target.is_active,
        is_admin=checkIfAdmin(target.user_id),
        created_at=target.created_at,
        updated_at=target.updated_at
    )

@router.put("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: int,
    target_data: TargetUpdate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Update a target"""
    
    target = db(
        (db.targets.id == target_id) & 
        ((db.targets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )
    
    # Prepare update data
    update_data = {}
    
    # For first_name and last_name, we allow explicit None values
    # Check if the field was provided in the request (even if it's None)
    if 'first_name' in target_data.model_fields_set:
        update_data['first_name'] = target_data.first_name
    
    if 'last_name' in target_data.model_fields_set:
        update_data['last_name'] = target_data.last_name
    
    if target_data.email is not None:
        # Check if email already exists for this user
        existing_target = db(
            (db.targets.user_id == current_user.id) & 
            (db.targets.email == target_data.email) &
            (db.targets.id != target_id)
        ).select().first()
        
        if existing_target:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A target with this email already exists"
            )
        update_data['email'] = target_data.email
    
    if target_data.position is not None:
        update_data['position'] = target_data.position
    
    if target_data.group_id is not None:
        if target_data.group_id:
            # Validate group_id belongs to user
            group = db(
                (db.groups.id == target_data.group_id) & 
                ((db.groups.user_id == current_user.id) | (current_user.is_admin))
            ).select().first()
            
            if not group:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid group_id: group not found or not owned by user"
                )
        update_data['group_id'] = target_data.group_id
    
    if target_data.is_active is not None:
        update_data['is_active'] = target_data.is_active
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update the target
    db(db.targets.id == target_id).update(**update_data)
    db.commit()
    
    # Get the updated target
    updated_target = db.targets(target_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_target_updated(
            current_user.id, 
            target_id, 
            updated_target.email, 
            client_ip, 
            user_agent
        )
    
    # Get group name if target has a group
    group_name = None
    if updated_target.group_id:
        group = db.groups(updated_target.group_id)
        group_name = group.name if group else None
    
    return TargetResponse(
        id=updated_target.id,
        first_name=updated_target.first_name,
        last_name=updated_target.last_name,
        email=updated_target.email,
        position=updated_target.position,
        group_id=updated_target.group_id,
        group_name=group_name,
        is_active=updated_target.is_active,
        is_admin=checkIfAdmin(updated_target.user_id),
        created_at=updated_target.created_at,
        updated_at=updated_target.updated_at
    )

@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Delete a target"""
    
    target = db(
        (db.targets.id == target_id) & 
        ((db.targets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )
    
    # Log activity before deletion
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_target_deleted(
            current_user.id, 
            target_id, 
            target.email, 
            client_ip, 
            user_agent
        )
    
    # Delete the target
    db(db.targets.id == target_id).delete()
    db.commit()
    
    return None

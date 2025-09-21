from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger

router = APIRouter()

# Pydantic models
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_active: bool = True

class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
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

@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Create a new group (department)"""
    
    # Check if group name already exists for this user
    existing_group = db(
        (db.groups.user_id == current_user.id) & 
        (db.groups.name == group_data.name)
    ).select().first()
    
    if existing_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A group with this name already exists"
        )
    
    # Create the group
    group_id = db.groups.insert(
        name=group_data.name,
        description=group_data.description,
        user_id=current_user.id,
        is_active=group_data.is_active
    )
    db.commit()
    
    # Get the created group
    new_group = db.groups(group_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_group_created(
            current_user.id, 
            group_id, 
            group_data.name, 
            client_ip, 
            user_agent
        )
    
    return GroupResponse(
        id=new_group.id,
        name=new_group.name,
        description=new_group.description,
        is_active=new_group.is_active,
        is_admin=checkIfAdmin(new_group.user_id),
        created_at=new_group.created_at,
        updated_at=new_group.updated_at
    )

@router.get("/", response_model=List[GroupResponse])
async def list_groups(current_user = Depends(get_current_user)):
    """List all groups for the current user"""
    
    groups = db(db.groups.user_id == current_user.id).select()
    if(current_user.is_admin):
        groups = db().select(db.groups.ALL)
    
    return [
        GroupResponse(
            id=group.id,
            name=group.name,
            description=group.description,
            is_active=group.is_active,
            created_at=group.created_at,
            is_admin=checkIfAdmin(group.user_id),
            updated_at=group.updated_at
        )
        for group in groups
    ]

@router.get("/{group_id}", response_model=GroupResponse)
async def get_group(
    group_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific group"""
    
    group = db(
        (db.groups.id == group_id) & 
        ((db.groups.user_id == current_user.id)| (current_user.is_admin))
    ).select().first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        is_active=group.is_active,
        is_admin=checkIfAdmin(group.user_id),
        created_at=group.created_at,
        updated_at=group.updated_at
    )

@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group_data: GroupUpdate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Update a group"""
    
    group = db(
        (db.groups.id == group_id) & 
        ((db.groups.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Prepare update data
    update_data = {}
    
    if group_data.name is not None:
        # Check if name already exists for this user
        existing_group = db(
            ((db.groups.user_id == current_user.id) | (current_user.is_admin)) & 
            (db.groups.name == group_data.name) &
            (db.groups.id != group_id)
        ).select().first()
        
        if existing_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A group with this name already exists"
            )
        update_data['name'] = group_data.name
    
    if group_data.description is not None:
        update_data['description'] = group_data.description
    
    if group_data.is_active is not None:
        update_data['is_active'] = group_data.is_active
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update the group
    db(db.groups.id == group_id).update(**update_data)
    db.commit()
    
    # Get the updated group
    updated_group = db.groups(group_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_group_updated(
            current_user.id, 
            group_id, 
            updated_group.name, 
            client_ip, 
            user_agent
        )
    
    return GroupResponse(
        id=updated_group.id,
        name=updated_group.name,
        description=updated_group.description,
        is_active=updated_group.is_active,
        is_admin=checkIfAdmin(updated_group.user_id),
        created_at=updated_group.created_at,
        updated_at=updated_group.updated_at
    )

@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Delete a group"""
    
    group = db(
        (db.groups.id == group_id) & 
        ((db.groups.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found"
        )
    
    # Check if any targets are using this group
    targets_in_group = db(db.targets.group_id == group_id).select()
    if targets_in_group:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete group: targets are assigned to this group"
        )
    
    # Log activity before deletion
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_group_deleted(
            current_user.id, 
            group_id, 
            group.name, 
            client_ip, 
            user_agent
        )
    
    # Delete the group
    db(db.groups.id == group_id).delete()
    db.commit()
    
    return None

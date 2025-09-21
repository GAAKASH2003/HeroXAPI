from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import openai
import requests
from fastapi.responses import StreamingResponse
import io
from datetime import datetime
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger
import base64
import mimetypes

import os
from datetime import datetime
from fastapi.responses import FileResponse
from typing import List, Optional

router = APIRouter()

class AttachmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    isDemo: Optional[bool] = False
    user_id: int


class AttachmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    isDemo: Optional[bool] = None
    


class AttachmentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    isDemo: Optional[bool] = False
    user_id: int
    created_at: datetime
    updated_at: datetime
    file_type:Optional[str] = None
    # Instead of exposing file path, return a download link
    download_url: Optional[str] = None

    is_admin: Optional[bool] = False  # If you need admin info in response

    class Config:
        from_attributes = True


class AttachmentImportRequest(BaseModel):
    name: str
    description: Optional[str] = None
    isDemo: Optional[bool] = False
    user_id: int
    




UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)  # Ensure folder exists


def checkIfAdmin(user_id: int) -> bool:
    """Check if a user is admin"""
    user = db(db.users.id == user_id).select().first()
    return user.is_admin if user else False

@router.post("/", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def create_attachment(
    name: str = Form(...),
    description: str = Form(None),
    isDemo: bool = Form(False),
    attachmentFile: UploadFile = File(...),
    current_user=Depends(get_current_user),
    request: Request = None
):
    # Check for existing attachment
    existing_attachment = db(
        (db.attachments.user_id == current_user.id) & 
        (db.attachments.name == name)
    ).select().first()
    
    if existing_attachment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An attachment with this name already exists"
        )

    # Save file to uploads folder
    file_path = os.path.join(UPLOAD_DIR, f"{datetime.utcnow().timestamp()}_{attachmentFile.filename}")
    file_type, _ = mimetypes.guess_type(file_path)
    with open(file_path, "wb") as f:
        f.write(await attachmentFile.read())

    # Insert into DB (store relative path)
    attachment_id = db.attachments.insert(
        name=name,
        description=description,
        user_id=current_user.id,
        attachmentFile=file_path,
        file_type=file_type,
        isDemo=isDemo,
    )
    db.commit()

    new_attachment = db.attachments(attachment_id)

    return AttachmentResponse(
        id=new_attachment.id,
        name=new_attachment.name,
        description=new_attachment.description,
        isDemo=new_attachment.isDemo,
        user_id=new_attachment.user_id,
        created_at=new_attachment.created_at,
        updated_at=new_attachment.updated_at,
        file_type=file_type or "application/octet-stream"
    )


@router.get("/", response_model=List[AttachmentResponse])
async def list_attachments(current_user=Depends(get_current_user)):
    """List all attachments for the current user"""

    query = (db.attachments.user_id == current_user.id) | (db.attachments.isDemo == True)

    if not checkIfAdmin(current_user.id):
        admin_ids = [user.id for user in db(db.users.is_admin == True).select(db.users.id)]
        query |= db.attachments.user_id.belongs(admin_ids)
        attachments = db(query).select()
    else:
        attachments = db(db.attachments).select()

    if not attachments:
        attachments = db(db.attachments.isDemo == True).select()

    return [
        AttachmentResponse(
            id=attachment.id,
            name=attachment.name,
            description=attachment.description,
            isDemo=attachment.isDemo,
            user_id=attachment.user_id,
            file_type=attachment.file_type,
            is_admin=checkIfAdmin(attachment.user_id),
            created_at=attachment.created_at,
            updated_at=attachment.updated_at,
        )
        for attachment in attachments
    ]


# @router.get("/{attachment_id}/download")
# async def download_attachment(
#     attachment_id: int,
#     current_user=Depends(get_current_user)
# ):
#     """Download an attachment"""
#     attachment = db(
#         (db.attachments.id == attachment_id) &
#         ((db.attachments.user_id == current_user.id) | (current_user.is_admin))
#     ).select().first()

#     if not attachment:
#         raise HTTPException(status_code=404, detail="Attachment not found")

#     file_path = attachment.attachmentFile
#     if not os.path.exists(file_path):
#         raise HTTPException(status_code=404, detail="File not found on server")

#     return FileResponse(
#         path=file_path,
#         filename=os.path.basename(file_path),
#         media_type="application/octet-stream"
#     )


@router.put("/{attachment_id}", response_model=AttachmentResponse)
async def update_attachment(
    attachment_id: int,
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    isDemo: Optional[bool] = Form(None),
    # attachmentFile: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user)
):
    """Update attachment metadata or replace file"""
    attachment = db(
        (db.attachments.id == attachment_id) &
        ((db.attachments.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()

    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    update_data = {}

    if name is not None:
        existing_attachment = db(
            (db.attachments.user_id == current_user.id) &
            (db.attachments.name == name) &
            (db.attachments.id != attachment_id)
        ).select().first()
        if existing_attachment:
            raise HTTPException(status_code=400, detail="Attachment with this name already exists")
        update_data["name"] = name

    if description is not None:
        update_data["description"] = description

    if isDemo is not None:
        update_data["isDemo"] = isDemo

    # if attachmentFile is not None:
    #     # Delete old file if it exists
    #     if os.path.exists(attachment.attachmentFile):
    #         os.remove(attachment.attachmentFile)

    #     # Save new file
    #     new_file_path = os.path.join(UPLOAD_DIR, f"{datetime.utcnow().timestamp()}_{attachmentFile.filename}")
    #     with open(new_file_path, "wb") as f:
    #         f.write(await attachmentFile.read())
    #     update_data["attachmentFile"] = new_file_path

    update_data["updated_at"] = datetime.utcnow()
    db(db.attachments.id == attachment_id).update(**update_data)
    db.commit()

    updated_attachment = db.attachments(attachment_id)

    return AttachmentResponse(
        id=updated_attachment.id,
        name=updated_attachment.name,
        description=updated_attachment.description,
        isDemo=updated_attachment.isDemo,
        user_id=updated_attachment.user_id,
        created_at=updated_attachment.created_at,
        updated_at=updated_attachment.updated_at
    )


import os

@router.get("/{attachment_id}/download")
async def download_attachment(
    attachment_id: int,
    current_user=Depends(get_current_user)
):
    attachment = db(db.attachments.id == attachment_id).select().first()
    if not checkIfAdmin(attachment.user_id):
        if not attachment.is_admin:
           if (attachment.user_id != current_user.id) and not current_user.is_admin:
               raise HTTPException(status_code=403, detail="Not authorized to access this file")

    file_path = attachment.attachmentFile
    print("filepath",file_path)

    normalized_path = file_path.replace("\\", "/")
    
    if not os.path.exists(normalized_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    file_like = open(normalized_path, "rb")
    
    real_filename = os.path.basename(normalized_path)
    # print(real_filename)
    return StreamingResponse(
        file_like,
        media_type=attachment.file_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{real_filename}"'
        }
    )
    
    

@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    attachment_id: int,
    current_user=Depends(get_current_user)
):
    """Delete an attachment (both DB record and physical file)"""

    # Fetch attachment
    attachment = db(db.attachments.id == attachment_id).select().first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    # Check permissions
    if attachment.user_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to delete this file")

    # Delete the file from uploads folder
    file_path = os.path.join(UPLOAD_DIR, f"{attachment.name}")
    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete DB record
    db(db.attachments.id == attachment_id).delete()
    db.commit()

    return {"detail": "Attachment deleted successfully"}
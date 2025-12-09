from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone, tzinfo
from typing import Optional
from database import db
from auth import get_current_user
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from utils.activity_logger import ActivityLogger
import requests
import pytz
from datetime import timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
dotenv_path = '.env'
import os
import httpx
import base64
router = APIRouter()

# Pydantic models
class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    sender_profile_id: int
    email_template_id: int
    phishlet_id: Optional[int] = None
    attachment_id:Optional[int] = None
    target_type: str  # 'group' or 'individual'
    target_group_id: Optional[int] = None
    target_individuals: Optional[List[int]] = None
    scheduled_at: Optional[datetime] = None
    launch_now: bool = False

class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sender_profile_id: Optional[int] = None
    email_template_id: Optional[int] = None
    phishlet_id: Optional[int] = None
    attachment_id: Optional[int] = None
    target_type: Optional[str] = None
    target_group_id: Optional[int] = None
    target_individuals: Optional[List[int]] = None
    scheduled_at: Optional[datetime] = None
    launch_now: Optional[bool] = None
    status: Optional[str] = None
    is_active: Optional[bool] = None

class CampaignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    sender_profile_id: int
    email_template_id: int
    phishlet_id: Optional[int] = None
    attachment_id: Optional[int] = None
    target_type: str
    target_group_id: Optional[int] = None
    target_individuals: Optional[List[int]] = None
    scheduled_at: Optional[datetime] = None
    status: str
    is_active: bool
    is_admin: Optional[bool] = None
    created_at: datetime
    user_name:Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


def checkIfAdmin(user_id: int) -> bool:
    """Check if a user is admin"""
    user = db(db.users.id == user_id).select().first()
    return user.is_admin if user else False


@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    campaign_data: CampaignCreate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Create a new campaign"""
    print(campaign_data)
    # Check if campaign name already exists for this user
    existing_campaign = db(
        (db.campaigns.user_id == current_user.id) & 
        (db.campaigns.name == campaign_data.name)
    ).select().first()
    
    if existing_campaign:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A campaign with this name already exists"
        )
    
    # Determine initial status based on launch_now and scheduled_at
    if campaign_data.launch_now:
        initial_status = 'running'
        scheduled_at = None
    elif campaign_data.scheduled_at:
        initial_status = 'scheduled'
        scheduled_at = campaign_data.scheduled_at
    else:
        initial_status = 'scheduled'  # Default to scheduled if no launch_now and no scheduled_at
        scheduled_at = None
    if scheduled_at is None:
        scheduled_at = datetime.now(pytz.timezone('Asia/Kolkata'))
    print("scheduled_at:", scheduled_at)
    # Validate required fields
    if not campaign_data.sender_profile_id  :
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender profile is required"
        )
    # sender_profiles=db(db.sender_profile.user_id== current_user.id & db.sender_profile.is_active)
    
    if not campaign_data.email_template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email template is required"
        )
    
    if not (campaign_data.phishlet_id):
        if not (campaign_data.attachment_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phishlet or attachment is required"
            )
  
    # Create the campaign
    campaign_id = db.campaigns.insert(
        name=campaign_data.name,
        description=campaign_data.description,
        user_id=current_user.id,
        sender_profile_id=campaign_data.sender_profile_id,
        email_template_id=campaign_data.email_template_id,
        phishlet_id=campaign_data.phishlet_id,
        attachment_id=campaign_data.attachment_id,
        target_type=campaign_data.target_type,
        target_group_id=campaign_data.target_group_id,
        target_individuals=json.dumps(campaign_data.target_individuals) if campaign_data.target_individuals else None,
        scheduled_at=scheduled_at,
        status=initial_status,
        is_active=True
    )
    db.commit()
    if campaign_data.launch_now:
        scheduled_at = scheduled_at + timedelta(minutes=2)

    m   = scheduled_at.minute
    h   = scheduled_at.hour
    d   = scheduled_at.day
    mon = scheduled_at.month
    year = scheduled_at.year
    week = scheduled_at.weekday()

    new_campaign = db.campaigns(campaign_id)
    # print("cron_expression", f"{m} {h} {d} {mon} {week}")
    BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
    # BACKEND_URL = "https://m7zfbszf-8000.inc1.devtunnels.ms"
    url= BACKEND_URL + "/api/v1/campaigns/send_email",
    cronexpression=f"{m} {h} {d} {mon} *"
    payload = {
    "cron_expression": cronexpression,   
    "url": url[0],
    "http_method": "POST",
    "http_headers": "Content-Type: application/json",
    "http_message_body": json.dumps({
        "id":new_campaign.id
    }),
    "timezone_from":1,
    }
    print("payload",payload)
    resp = requests.post(
        "https://api.easycron.com/v1/cron-jobs",
        headers={
            "Content-Type": "application/json",
            "X-API-Key": os.getenv("EASY_CRON_API_KEY")
        },
        json=payload
    )
    print("resp",resp.json())
        
     
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_campaign_created(
            current_user.id, 
            campaign_id, 
            campaign_data.name, 
            client_ip, 
            user_agent
        )
    
    return CampaignResponse(
        id=new_campaign.id,
        name=new_campaign.name,
        description=new_campaign.description,
        sender_profile_id=new_campaign.sender_profile_id,
        email_template_id=new_campaign.email_template_id,
        phishlet_id=new_campaign.phishlet_id,
        target_type=new_campaign.target_type,
        target_group_id=new_campaign.target_group_id,
        target_individuals=json.loads(new_campaign.target_individuals) if new_campaign.target_individuals else None,
        scheduled_at=new_campaign.scheduled_at,
        status=new_campaign.status,
        is_active=new_campaign.is_active,
        created_at=new_campaign.created_at,
        updated_at=new_campaign.updated_at,
        is_admin=checkIfAdmin(new_campaign.user_id)
    )

@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(current_user = Depends(get_current_user)):
    """List all campaigns for the current user"""
    
    # campaigns = db(db.campaigns.user_id == current_user.id).select()
    query = db.campaigns.user_id == current_user.id
    # campaign_user = db(db.users.id == campaigns.user_id).select().first()
    if not current_user.is_admin:
        campaigns = db(query).select()
    else:
        campaigns = db().select(db.campaigns.ALL)
    return [
        CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            sender_profile_id=campaign.sender_profile_id,
            email_template_id=campaign.email_template_id,
            phishlet_id=campaign.phishlet_id,
            attachment_id=campaign.attachment_id,
            target_type=campaign.target_type,
            target_group_id=campaign.target_group_id,
            target_individuals=json.loads(campaign.target_individuals) if campaign.target_individuals else None,
            scheduled_at=campaign.scheduled_at,
            status=campaign.status,
            is_active=campaign.is_active,
            user_name = db(db.users.id == campaign.user_id).select().first().full_name,
            is_admin=checkIfAdmin(campaign.user_id),
            created_at=campaign.created_at,
            updated_at=campaign.updated_at
        )
        for campaign in campaigns
    ]

@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific campaign"""
    
    campaign = db(
        (db.campaigns.id == campaign_id) & 
        ((db.campaigns.user_id == current_user.id)|(current_user.is_admin))
    ).select().first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    campaign_user = db(db.users.id == campaign.user_id).select().first()
    
    return CampaignResponse(
        id=campaign.id,
        name=campaign.name,
        description=campaign.description,
        sender_profile_id=campaign.sender_profile_id,
        email_template_id=campaign.email_template_id,
        phishlet_id=campaign.phishlet_id,
        attachment_id=campaign.attachment_id,
        target_type=campaign.target_type,
        target_group_id=campaign.target_group_id,
        target_individuals=json.loads(campaign.target_individuals) if campaign.target_individuals else None,
        scheduled_at=campaign.scheduled_at,
        status=campaign.status,
        is_active=campaign.is_active,
        user_name = campaign_user.full_name if campaign_user else "User",
        created_at=campaign.created_at,
        updated_at=campaign.updated_at
    )
    
    
@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    campaign_data: CampaignUpdate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Update a campaign"""
    print(campaign_data)
    campaign = db(
        (db.campaigns.id == campaign_id) & 
        ((db.campaigns.user_id == current_user.id)|(current_user.is_admin))
    ).select().first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Prepare update data
    update_data = {}
    changes = {}

    if campaign_data.name is not None:
        update_data['name'] = campaign_data.name
        changes['name'] = campaign_data.name
    
    if campaign_data.description is not None:
        update_data['description'] = campaign_data.description
        changes['description'] = campaign_data.description
    
    if campaign_data.sender_profile_id is not None:
        update_data['sender_profile_id'] = campaign_data.sender_profile_id
        changes['sender_profile_id'] = campaign_data.sender_profile_id
    
    if campaign_data.email_template_id is not None:
        update_data['email_template_id'] = campaign_data.email_template_id
        changes['email_template_id'] = campaign_data.email_template_id
    
    # ✅ Handle phishlet OR attachment
    if campaign_data.phishlet_id is not None:
        update_data['phishlet_id'] = campaign_data.phishlet_id
        changes['phishlet_id'] = campaign_data.phishlet_id

    if campaign_data.attachment_id is not None:
        update_data['attachment_id'] = campaign_data.attachment_id
        changes['attachment_id'] = campaign_data.attachment_id
    
    if campaign_data.target_type is not None:
        update_data['target_type'] = campaign_data.target_type
        changes['target_type'] = campaign_data.target_type
    
    if campaign_data.target_group_id is not None:
        update_data['target_group_id'] = campaign_data.target_group_id
        changes['target_group_id'] = campaign_data.target_group_id
    
    if campaign_data.target_individuals is not None:
        update_data['target_individuals'] = json.dumps(campaign_data.target_individuals)
        changes['target_individuals'] = campaign_data.target_individuals
    
    if campaign_data.launch_now is not None:
        if campaign_data.launch_now:
            update_data['status'] = 'running'
            update_data['scheduled_at'] = None
            changes['status'] = 'running'
            changes['scheduled_at'] = None
        else:
            # If launch_now is false, keep current status but ensure scheduled_at is set
            if not campaign_data.scheduled_at:
                update_data['status'] = 'scheduled'
                changes['status'] = 'scheduled'
    
    if campaign_data.scheduled_at is not None:
        update_data['scheduled_at'] = campaign_data.scheduled_at
        changes['scheduled_at'] = campaign_data.scheduled_at.isoformat()
    
    if campaign_data.status is not None:
        update_data['status'] = campaign_data.status
        changes['status'] = campaign_data.status
    
    if campaign_data.is_active is not None:
        update_data['is_active'] = campaign_data.is_active
        changes['is_active'] = campaign_data.is_active
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Validate: require either phishlet or attachment (at least one after update)
    final_phishlet_id = update_data.get("phishlet_id", campaign.phishlet_id)
    final_attachment_id = update_data.get("attachment_id", getattr(campaign, "attachment_id", None))
    
    if not (final_phishlet_id or final_attachment_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either phishlet or attachment is required"
        )

    # Update the campaign
    db(db.campaigns.id == campaign_id).update(**update_data)
    db.commit()
    
    # Get the updated campaign
    updated_campaign = db.campaigns(campaign_id)
    
    # Log activity
    if request and changes:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_campaign_updated(
            current_user.id, 
            campaign_id, 
            updated_campaign.name, 
            changes, 
            client_ip, 
            user_agent
        )
    
    return CampaignResponse(
        id=updated_campaign.id,
        name=updated_campaign.name,
        description=updated_campaign.description,
        sender_profile_id=updated_campaign.sender_profile_id,
        email_template_id=updated_campaign.email_template_id,
        phishlet_id=updated_campaign.phishlet_id,
        attachment_id=getattr(updated_campaign, "attachment_id", None),  # ✅ return attachment too
        target_type=updated_campaign.target_type,
        target_group_id=updated_campaign.target_group_id,
        target_individuals=json.loads(updated_campaign.target_individuals) if updated_campaign.target_individuals else None,
        scheduled_at=updated_campaign.scheduled_at,
        status=updated_campaign.status,
        is_active=updated_campaign.is_active,
        created_at=updated_campaign.created_at,
        updated_at=updated_campaign.updated_at
    )

@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Delete a campaign"""
    
    campaign = db(
        (db.campaigns.id == campaign_id) & 
        ((db.campaigns.user_id == current_user.id)|(current_user.is_admin))
    ).select().first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Log activity before deletion
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_campaign_deleted(
            current_user.id, 
            campaign_id, 
            campaign.name, 
            client_ip, 
            user_agent
        )
    
    # Delete the campaign
    db(db.campaigns.id == campaign_id).delete()
    db.commit()
    
    return None

@router.post("/{campaign_id}/run", status_code=status.HTTP_200_OK)
async def run_campaign(
    campaign_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Run a campaign"""
    
    campaign = db(
        (db.campaigns.id == campaign_id) & 
        ((db.campaigns.user_id == current_user.id)|(current_user.is_admin))
    ).select().first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    if campaign.status not in ['scheduled', 'paused']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign can only be run when scheduled or paused"
        )
    
    # Update campaign status to running
    db(db.campaigns.id == campaign_id).update(
        status='running',
        updated_at=datetime.utcnow()
    )
    db.commit()
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_campaign_updated(
            current_user.id, 
            campaign_id, 
            campaign.name, 
            {"status": "running"}, 
            client_ip, 
            user_agent
        )
    
    return {"message": "Campaign started successfully"}

@router.post("/{campaign_id}/pause", status_code=status.HTTP_200_OK)
async def pause_campaign(
    campaign_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Pause a campaign"""
    
    campaign = db(
        (db.campaigns.id == campaign_id) & 
        ((db.campaigns.user_id == current_user.id)|(current_user.is_admin))
    ).select().first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    if campaign.status != 'running':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign can only be paused when running"
        )
    
    # Update campaign status to paused
    db(db.campaigns.id == campaign_id).update(
        status='paused',
        updated_at=datetime.utcnow()
    )
    db.commit()
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_campaign_updated(
            current_user.id, 
            campaign_id, 
            campaign.name, 
            {"status": "paused"}, 
            client_ip, 
            user_agent
        )
    
    return {"message": "Campaign paused successfully"}


def parse_captured_data(captured_data: str) -> List[List[str]]:
        raw_data_fixed = "[" + captured_data.replace("}\n{", "},{") + "]"
        parsed_list = json.loads(raw_data_fixed)
        creds_list = []
        for parsed in parsed_list:
            fields = parsed.get("fields", {})
            creds = []
            for key, field in fields.items():
                value = field.get("value")
                if value not in [None, "", "null"]:
                    creds.append(f"{key}: {value}")
            # creds_list.append(" | ".join(creds))
            creds_list.append(creds)
        
        # print({"credentials": creds_list})
        return {"credentials": creds_list}

@router.get("/{campaign_id}/results", response_model=List[dict])
async def get_campaign_results(
    campaign_id: int,
    current_user = Depends(get_current_user)
):
    """Get campaign results"""
    
    campaign = db(
        (db.campaigns.id == campaign_id) & 
        ((db.campaigns.user_id == current_user.id)|(current_user.is_admin))
    ).select().first()
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    # Get campaign results
    results = db(db.campaign_results.campaign_id == campaign_id).select()

    for result in results:
      target_individual = db(db.targets.id == result.target_id).select().first()
      result.target_email = target_individual.email if target_individual else None
    

    return [
    {
        "id": result.id,
        "target_email": result.target_email,
        "email_sent": result.email_sent,
        "email_opened": result.email_opened,
        "link_clicked": result.link_clicked,
        "form_submitted": result.form_submitted,
        "captured_data": parse_captured_data(result.captured_data) if result.captured_data else None,
        "timestamp": result.created_at if result.created_at else None
    }
    for result in results
    ]

class EmailRequest(BaseModel):
    id: Optional[int] = None


@router.post("/send_email", status_code=status.HTTP_200_OK)
async def send_email(email_req: EmailRequest):
    """Send phishing or campaign emails with validations"""
    if not email_req.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign ID is required"
        )

    # Validate campaign
    campaign = db(db.campaigns.id == email_req.id).select().first()
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # Validate sender profile
    sender = db(campaign.sender_profile_id == db.sender_profiles.id).select().first()
    if not sender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sender profile not found"
        )

    # Validate email template
    email_temp = db(campaign.email_template_id == db.email_templates.id).select().first()
    if not email_temp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found"
        )

    # Optional: phishlet & attachment
    phishlet = db(campaign.phishlet_id == db.phishlets.id).select().first() if campaign.phishlet_id else None
    attachment = db(campaign.attachment_id == db.attachments.id).select().first() if campaign.attachment_id else None

    # Collect targets
    targets_list = []
    if campaign.target_type == "individual":
        try:
            targets = json.loads(campaign.target_individuals or "[]")
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid target individuals format"
            )
        for target in targets:
            t = db(db.targets.id == target).select().first()
            if t and t.is_active:
                targets_list.append(t)
    else:
        group = db(campaign.target_group_id == db.groups.id).select().first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target group not found"
            )
        targets = db(db.targets.group_id == group.id).select()
        targets_list.extend([t for t in targets if t.is_active])

    if not targets_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active targets found"
        )

    # SMTP credentials
    EMAIL_USER = sender.smtp_username
    EMAIL_PASSWORD = sender.smtp_password
    if not EMAIL_USER or not EMAIL_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid SMTP credentials"
        )

    # ---- Send emails ----
    errors = []
    for target in targets_list:
        msg = MIMEMultipart("alternative")
        msg["From"] = sender.from_address
        msg["To"] = target.email
        msg["Subject"] = email_temp.subject or "No Subject"

        # Attachment
        if attachment:
            try:
                file_path = attachment.attachmentFile.replace("\\", "/")
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                maintype, subtype = attachment.file_type.split("/", 1)
                part = MIMEBase(maintype, subtype)
                part.set_payload(file_bytes)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{attachment.name}"')
                msg.attach(part)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to attach file: {str(e)}"
                )
            plain_body = email_temp.text_content
            html_body = email_temp.html_content

        # Phishlet
        elif phishlet:
            plain_body = f"{email_temp.text_content}\n\nClick here: {phishlet.clone_url}"
            phishlet_url = f"{phishlet.clone_url}*{campaign.id}*{target.id}"
            html_body = email_temp.html_content.replace("{{PHISHLET_URL}}", phishlet_url)

        else:
            plain_body = email_temp.text_content
            html_body = email_temp.html_content

        # Tracking pixel
        image_src = os.getenv("BACKEND_URL", "")
        html_body = f"""
            {html_body}
            <br>
            <img width="1" height="1" src="{image_src}/api/v1/track/f1/{campaign.id}*{target.id}">
        """

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # ---- Send via SMTP ----
        # Build attachments payload (base64 encoded) if there's an attachment
        attachments_payload = []
        if attachment:
            try:
                file_path = attachment.attachmentFile.replace("\\", "/")
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                encoded = base64.b64encode(file_bytes).decode()
                attachments_payload.append({
                    "filename": attachment.name,
                    "content_base64": encoded,
                    "mime_type": attachment.file_type,
                })
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to read attachment file: {str(e)}"
                )

        # Send mail via external mailer API (configurable via MAILER_API_URL)
        MAILER_API_URL = os.getenv("EMAIL_API_URL", "http://localhost:8001/send")
        mailer_payload = {
            "smtp_host": sender.smtp_host,
            "smtp_port": sender.smtp_port,
            "smtp_username": EMAIL_USER,
            "smtp_password": EMAIL_PASSWORD,
            "from_address": sender.from_address,
            "to": target.email,
            "subject": email_temp.subject or "No Subject",
            "plain_body": plain_body,
            "html_body": html_body,
            "attachments": attachments_payload,
        }

        try:
            resp = httpx.post(MAILER_API_URL, json=mailer_payload, timeout=60)
            if resp.status_code != 200:
                errors.append({"email": target.email, "error": f"Mailer API error: {resp.status_code} {resp.text}"})
                continue

            now = datetime.utcnow()

            # Log email events
            db.email_events.insert(
                campaign_id=campaign.id,
                target_id=target.id,
                event_type="sent",
                event_data=json.dumps({
                    "subject": email_temp.subject,
                    "from": sender.from_address,
                    "to": target.email
                })
            )

            # Update campaign results
            db.campaign_results.update_or_insert(
                (db.campaign_results.campaign_id == campaign.id) &
                (db.campaign_results.target_id == target.id),
                campaign_id=campaign.id,
                target_id=target.id,
                email_sent=True,
                email_sent_at=now,
                updated_at=now
            )
            db.commit()

        except httpx.RequestError as e:
            errors.append({"email": target.email, "error": f"Mailer request error: {str(e)}"})
        except Exception as e:
            errors.append({"email": target.email, "error": f"Unexpected error: {str(e)}"})

    if errors:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Some emails failed", "errors": errors}
        )

    return {"message": "✅ Emails sent successfully!", "count": len(targets_list)}

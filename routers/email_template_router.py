from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import openai
import requests
import email
import email.policy
from email import message_from_bytes
from datetime import datetime
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger

router = APIRouter()

# Pydantic models
class EmailTemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    isDemo: Optional[bool] = False
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    template_type: str = "custom"  # 'custom', 'ai_generated', 'predefined'
    variables: Optional[Dict[str, Any]] = None
    is_active: bool = True

class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    isDemo:Optional[bool] = None
    subject: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class AITemplateGenerateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: str
    subject_line: Optional[str] = None
    template_type: Optional[str] = None  # 'phishing', 'marketing', 'notification', 'custom'
    tone:  Optional[str] = None # 'professional', 'casual', 'urgent', 'friendly'
    target_audience: Optional[str] = None
    include_html: Optional[bool] = True
    include_text: Optional[bool] = True
    # variables: Optional[Dict[str, Any]] = None

class AITemplate(BaseModel):
    name: str
    description: Optional[str] = None
    prompt: str
    subject_line: Optional[str] = None
    template_type: str = "phishing"  # 'phishing', 'marketing', 'notification', 'custom'
    tone: str = "professional"  # 'professional', 'casual', 'urgent', 'friendly'
    target_audience: Optional[str] = None
    include_html: bool = True
    include_text: bool = True
    variables: Optional[Dict[str, Any]] = None

class EMLImportRequest(BaseModel):
    name: str
    description: Optional[str] = None
    template_type: str = "custom"
    is_active: bool = True

class EmailTemplateResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    isDemo:Optional[bool] = False
    template_type: str
    ai_prompt: Optional[str] = None
    ai_model_used: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
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


def generate_ai_template(user, prompt: str, subject_line: Optional[str] = None, 
                        template_type: str = "phishing", tone: str = "professional",
                        target_audience: Optional[str] = None, include_html: bool = True,
                        include_text: bool = True) -> Dict[str, str]:
    """Generate email template using AI"""
    
    # Check if user has AI settings configured
    if not user.ai_is_active or not user.ai_api_key or not user.ai_model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI settings not configured. Please configure AI settings in user settings."
        )
    
    # Build the AI prompt
    ai_prompt = f"""
Generate a {template_type} email template with a {tone} tone.
"""
    
    if target_audience:
        ai_prompt += f"Target audience: {target_audience}\n"
    
    if subject_line:
        ai_prompt += f"Subject line: {subject_line}\n"
    
    ai_prompt += f"""
User request: {prompt}

Please generate:
1. A compelling subject line
2. An HTML version of the email (if HTML is requested)
3. A plain text version of the email (if text is requested)

Make sure the email is professional, engaging, and appropriate for the specified type and tone.
"""
    
    try:
        if user.ai_provider.lower() == "openai":
            return generate_openai_template(user, ai_prompt, include_html, include_text)
        elif user.ai_provider.lower() == "anthropic":
            return generate_anthropic_template(user, ai_prompt, include_html, include_text)
        elif user.ai_provider.lower() == "deepseek":
            return generate_deepseek_template(user, ai_prompt, include_html, include_text)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported AI provider: {user.ai_provider}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI template: {str(e)}"
        )

def generate_openai_template(user, prompt: str, include_html: bool, include_text: bool) -> Dict[str, str]:
    """Generate template using OpenAI"""
    openai.api_key = user.ai_api_key
    
    messages = [
        {"role": "system", "content": "You are an expert email template writer. Generate professional email templates based on user requirements."},
        {"role": "user", "content": prompt}
    ]
    
    response = openai.ChatCompletion.create(
        model=user.ai_model,
        messages=messages,
        max_tokens=user.ai_max_tokens or 1000,
        temperature=user.ai_temperature or 0.7
    )
    
    content = response.choices[0].message.content
    
    # Parse the response to extract subject, HTML, and text
    lines = content.split('\n')
    subject = ""
    html_content = ""
    text_content = ""
    
    current_section = None
    for line in lines:
        line = line.strip()
        if line.lower().startswith('subject:'):
            subject = line.split(':', 1)[1].strip()
        elif line.lower().startswith('html:'):
            current_section = 'html'
        elif line.lower().startswith('text:'):
            current_section = 'text'
        elif line and current_section == 'html':
            html_content += line + '\n'
        elif line and current_section == 'text':
            text_content += line + '\n'
    
    # If no structured response, use the entire content
    if not subject and not html_content and not text_content:
        if include_html:
            html_content = content
        if include_text:
            text_content = content
    
    return {
        'subject': subject or "Important Message",
        'html_content': html_content if include_html else None,
        'text_content': text_content if include_text else None,
        'ai_model_used': user.ai_model
    }

def generate_anthropic_template(user, prompt: str, include_html: bool, include_text: bool) -> Dict[str, str]:
    """Generate template using Anthropic Claude"""
    headers = {
        "x-api-key": user.ai_api_key,
        "content-type": "application/json"
    }
    
    data = {
        "model": user.ai_model,
        "max_tokens": user.ai_max_tokens or 1000,
        "temperature": user.ai_temperature or 0.7,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=data,
        timeout=60
    )
    
    if response.status_code != 200:
        raise Exception(f"Anthropic API error: {response.text}")
    
    content = response.json()['content'][0]['text']
    
    # Parse response similar to OpenAI
    lines = content.split('\n')
    subject = ""
    html_content = ""
    text_content = ""
    
    current_section = None
    for line in lines:
        line = line.strip()
        if line.lower().startswith('subject:'):
            subject = line.split(':', 1)[1].strip()
        elif line.lower().startswith('html:'):
            current_section = 'html'
        elif line.lower().startswith('text:'):
            current_section = 'text'
        elif line and current_section == 'html':
            html_content += line + '\n'
        elif line and current_section == 'text':
            text_content += line + '\n'
    
    if not subject and not html_content and not text_content:
        if include_html:
            html_content = content
        if include_text:
            text_content = content
    
    return {
        'subject': subject or "Important Message",
        'html_content': html_content if include_html else None,
        'text_content': text_content if include_text else None,
        'ai_model_used': user.ai_model
    }



def generate_deepseek_template(user, prompt: str, include_html: bool, include_text: bool) -> Dict[str, str]:
    """Generate template using DeepSeek (OpenAI-compatible Chat Completions API)"""
    headers = {
        "Authorization": f"Bearer {user.ai_api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "model": user.ai_model or "deepseek-chat",  # default to deepseek-chat
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert email template writer.\n"
                    "Always respond in the following format:\n\n"
                    "Subject: <subject line>\n\n"
                    "HTML:\n<html>...</html>\n\n"
                    "Text:\nPlain text version here."
                    "All anchor tags (<a>) or buttons in the HTML must use '{{PHISHLET_URL}}' as the href target.\n"
                    "Do not insert any real or placeholder URLs—always use the variable '{{PHISHLET_URL}}'."
                )
            },
            {"role": "user", "content": prompt}
        ],
        "max_tokens": user.ai_max_tokens or 1000,
        "temperature": user.ai_temperature or 0.7
    }

    response = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers,
        json=data,
        timeout=60
    )

    if response.status_code != 200:
        raise Exception(f"DeepSeek API error: {response.text}")

    json_resp = response.json()

    # Safely extract content
    content = (
        json_resp.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )

    subject = ""
    html_content = ""
    text_content = ""
    current_section = None

    for line in content.splitlines():
        line = line.strip()
        if line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip()
        elif line.lower().startswith("html:"):
            current_section = "html"
        elif line.lower().startswith("text:"):
            current_section = "text"
        elif line:
            if current_section == "html":
                html_content += line + "\n"
            elif current_section == "text":
                text_content += line + "\n"

    # Fallback if model didn’t follow structure
    if not subject:
        subject = "Important Message"
    if not html_content and include_html:
        html_content = content
    if not text_content and include_text:
        text_content = content

    return {
        "subject": subject,
        "html_content": html_content if include_html else None,
        "text_content": text_content if include_text else None,
        "ai_model_used": user.ai_model
    }




@router.post("/", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_email_template(
    template_data: EmailTemplateCreate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Create a new email template"""
    
    # Check if template name already exists for this user
    if not template_data.name or not template_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Template name is required"
        )
    
    # if not template_data.subject or not template_data.subject.strip():
    #     raise HTTPException(
    #         status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    #         detail="Template subject is required"
    #     )    
    
    if not (template_data.html_content and template_data.html_content.strip()) and \
       not (template_data.text_content and template_data.text_content.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either HTML content or plain text content is required"
        )
    
    existing_template = db(
        (db.email_templates.user_id == current_user.id) & 
        (db.email_templates.name == template_data.name)
    ).select().first()
    
    if existing_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An email template with this name already exists"
        )
    
    # Create the template
    template_id = db.email_templates.insert(
        name=template_data.name,
        description=template_data.description,
        user_id=current_user.id,
        subject=template_data.subject,
        html_content=template_data.html_content,
        text_content=template_data.text_content,
        isDemo=template_data.isDemo,
        template_type=template_data.template_type,
        variables=json.dumps(template_data.variables) if template_data.variables else None,
        is_active=template_data.is_active
    )
    db.commit()
    
    # Get the created template
    new_template = db.email_templates(template_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_template_created(
            current_user.id, 
            template_id, 
            template_data.name, 
            client_ip, 
            user_agent
        )
    
    return EmailTemplateResponse(
        id=new_template.id,
        name=new_template.name,
        isDemo=new_template.isDemo,
        description=new_template.description,
        subject=new_template.subject,
        html_content=new_template.html_content,
        text_content=new_template.text_content,
        template_type=new_template.template_type,
        ai_prompt=new_template.ai_prompt,
        ai_model_used=new_template.ai_model_used,
        variables=json.loads(new_template.variables) if new_template.variables else None,
        is_active=new_template.is_active,
        created_at=new_template.created_at,
        updated_at=new_template.updated_at
    )

@router.post("/generate", response_model=EmailTemplateResponse, status_code=status.HTTP_201_CREATED)
async def generate_ai_email_template(
    generate_data: AITemplate,
    current_user = Depends(get_current_user)
):
    """Generate an email template using AI"""
    
    # Check if template name already exists for this user
    if not generate_data.name or not generate_data.name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Template name is required"
        )

    # if not generate_data.subject_line or not generate_data.subject_line.strip():
    #     raise HTTPException(
    #         status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    #         detail="Template subject is required"
    #     )    
    
    if not generate_data.prompt or not generate_data.prompt.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI prompt is required"
        )
    existing_template = db(
        (db.email_templates.user_id == current_user.id) & 
        (db.email_templates.name == generate_data.name)
    ).select().first()
    
    if existing_template:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An email template with this name already exists"
        )
    
    # Generate the template using AI
    ai_result = generate_ai_template(
        user=current_user,
        prompt=generate_data.prompt,
        subject_line=generate_data.subject_line,
        template_type=generate_data.template_type,
        tone=generate_data.tone,
        target_audience=generate_data.target_audience,
        include_html= generate_data.include_html,
        include_text= generate_data.include_text
    )
    
    # Create the template
    template_id = db.email_templates.insert(
        name=generate_data.name,
        description=generate_data.description,
        user_id=current_user.id,
        subject=ai_result['subject'],
        html_content=ai_result['html_content'],
        text_content=ai_result['text_content'],
        template_type='ai_generated',
        ai_prompt=generate_data.prompt,
        ai_model_used=ai_result['ai_model_used'],
        variables=json.dumps(generate_data.variables) if generate_data.variables else None,
        is_active=True
    )
    db.commit()
    
    # Get the created template
    new_template = db.email_templates(template_id)
    
    return EmailTemplateResponse(
        id=new_template.id,
        name=new_template.name,
        description=new_template.description,
        subject=new_template.subject,
        html_content=new_template.html_content,
        text_content=new_template.text_content,
        template_type=new_template.template_type,
        ai_prompt=new_template.ai_prompt,
        ai_model_used=new_template.ai_model_used,
        variables=json.loads(new_template.variables) if new_template.variables else None,
        is_active=new_template.is_active,
        created_at=new_template.created_at,
        updated_at=new_template.updated_at
    )
    
@router.get("/admin", response_model=List[EmailTemplateResponse])
async def list_email_templates(current_user = Depends(get_current_user)):
    """List all email templates for the current user"""

    admin_ids = [user.id for user in db(db.users.is_admin == True).select(db.users.id)]
    query = (db.email_templates.user_id.belongs(admin_ids)) | (db.email_templates.isDemo == True)
    templates = db(query).select() 
    # if not checkIfAdmin(current_user.id):
    #     query |= db.email_templates.user_id.belongs(admin_ids)
    # templates = db(query).select()
    # else:
    #     # Admin sees all templates
    #     templates = db(db.email_templates).select()
    
    # If nothing found, fallback to demo templates
    if not templates:
        templates = db(db.email_templates.isDemo == True).select()

    return [
        EmailTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            subject=template.subject,
            html_content=template.html_content,
            text_content=template.text_content,
            template_type=template.template_type,
            ai_prompt=template.ai_prompt,
            ai_model_used=template.ai_model_used,
            variables=json.loads(template.variables) if template.variables else None,
            is_active=template.is_active,
            isDemo=template.isDemo,
            is_admin=checkIfAdmin(current_user.id),
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
        for template in templates
    ]
@router.get("/", response_model=List[EmailTemplateResponse])
async def list_email_templates(current_user = Depends(get_current_user)):
    """List all email templates for the current user"""
    
    # Base query
    query = (db.email_templates.user_id == current_user.id) | (db.email_templates.isDemo == True)
    
    # If user is not admin, also include admin templates
    # templates = db(query).select()
    if not checkIfAdmin(current_user.id):
        admin_ids = [user.id for user in db(db.users.is_admin == True).select(db.users.id)]
        query |= db.email_templates.user_id.belongs(admin_ids)
        templates = db(query).select()
    else:
        # Admin sees all templates
        templates = db(db.email_templates).select()
    
    # If nothing found, fallback to demo templates
    if not templates:
        templates = db(db.email_templates.isDemo == True).select()

    return [
        EmailTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            subject=template.subject,
            html_content=template.html_content,
            text_content=template.text_content,
            template_type=template.template_type,
            ai_prompt=template.ai_prompt,
            ai_model_used=template.ai_model_used,
            variables=json.loads(template.variables) if template.variables else None,
            is_active=template.is_active,
            isDemo=template.isDemo,
            is_admin=checkIfAdmin(template.user_id),
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
        for template in templates
    ]

@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: int,
    current_user = Depends(get_current_user)
):
    """Get a specific email template"""

    template = db(
        (db.email_templates.id == template_id) & 
        ((db.email_templates.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found"
        )
    
    return EmailTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        template_type=template.template_type,
        ai_prompt=template.ai_prompt,
        isDemo=template.isDemo,
        ai_model_used=template.ai_model_used,
        variables=json.loads(template.variables) if template.variables else None,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at
    )

@router.put("/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: int,
    template_data: EmailTemplateUpdate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Update an email template"""
    
    template = db(
        (db.email_templates.id == template_id) & 
        ((db.email_templates.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found"
        )
    
    # Prepare update data
    update_data = {}
    
    if template_data.name is not None:
        # Check if name already exists for this user
        existing_template = db(
            (db.email_templates.user_id == current_user.id) & 
            (db.email_templates.name == template_data.name) &
            (db.email_templates.id != template_id)
        ).select().first()
        
        if existing_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An email template with this name already exists"
            )
        update_data['name'] = template_data.name
    
    if template_data.description is not None:
        update_data['description'] = template_data.description
    
    if template_data.subject is not None:
        update_data['subject'] = template_data.subject
    
    if template_data.html_content is not None:
        update_data['html_content'] = template_data.html_content
    
    if template_data.text_content is not None:
        update_data['text_content'] = template_data.text_content
    
    if template_data.variables is not None:
        update_data['variables'] = json.dumps(template_data.variables)
    
    if template_data.is_active is not None:
        update_data['is_active'] = template_data.is_active
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update the template
    db(db.email_templates.id == template_id).update(**update_data)
    db.commit()
    
    # Get the updated template
    updated_template = db.email_templates(template_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_template_updated(
            current_user.id, 
            template_id, 
            updated_template.name, 
            client_ip, 
            user_agent
        )
    
    return EmailTemplateResponse(
        id=updated_template.id,
        name=updated_template.name,
        description=updated_template.description,
        subject=updated_template.subject,
        isDemo = updated_template.isDemo,
        html_content=updated_template.html_content,
        text_content=updated_template.text_content,
        template_type=updated_template.template_type,
        ai_prompt=updated_template.ai_prompt,
        ai_model_used=updated_template.ai_model_used,
        variables=json.loads(updated_template.variables) if updated_template.variables else None,
        is_active=updated_template.is_active,
        created_at=updated_template.created_at,
        updated_at=updated_template.updated_at
    )

@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_email_template(
    template_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Delete an email template"""
    
    template = db(
        (db.email_templates.id == template_id) & 
        ((db.email_templates.user_id == current_user.id)| (current_user.is_admin))
    ).select().first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found"
        )
    
    # Log activity before deletion
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_template_deleted(
            current_user.id, 
            template_id, 
            template.name, 
            client_ip, 
            user_agent
        )
    
    # Delete the template
    db(db.email_templates.id == template_id).delete()
    db.commit()
    
    return None

@router.post("/{template_id}/regenerate", response_model=EmailTemplateResponse)
async def regenerate_ai_template(
    template_id: int,
    current_user = Depends(get_current_user)
):
    """Regenerate an AI-generated email template"""
    
    template = db(
        (db.email_templates.id == template_id) & 
        ((db.email_templates.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email template not found"
        )
    
    if template.template_type != 'ai_generated':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only AI-generated templates can be regenerated"
        )
    
    if not template.ai_prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No AI prompt found for this template"
        )
    
    # Regenerate the template using AI
    ai_result = generate_ai_template(
        user=current_user,
        prompt=template.ai_prompt,
        include_html=bool(template.html_content),
        include_text=bool(template.text_content)
    )
    
    # Update the template
    update_data = {
        'subject': ai_result['subject'],
        'html_content': ai_result['html_content'],
        'text_content': ai_result['text_content'],
        'ai_model_used': ai_result['ai_model_used'],
        'updated_at': datetime.utcnow()
    }
    
    db(db.email_templates.id == template_id).update(**update_data)
    db.commit()
    
    # Get the updated template
    updated_template = db.email_templates(template_id)
    
    return EmailTemplateResponse(
        id=updated_template.id,
        name=updated_template.name,
        description=updated_template.description,
        subject=updated_template.subject,
        html_content=updated_template.html_content,
        text_content=updated_template.text_content,
        template_type=updated_template.template_type,
        ai_prompt=updated_template.ai_prompt,
        ai_model_used=updated_template.ai_model_used,
        variables=json.loads(updated_template.variables) if updated_template.variables else None,
        is_active=updated_template.is_active,
        created_at=updated_template.created_at,
        updated_at=updated_template.updated_at
    )
    




@router.post("/import/eml", response_model=EmailTemplateResponse)
async def import_eml_template(
    eml_file: UploadFile = File(...),
    name: str = None,
    description: str = None,
    template_type: str = "custom",
    isDemo:bool = False,
    is_active: bool = True,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Import email template from .eml file"""
    
    # Validate file type
    if not eml_file.filename.lower().endswith('.eml'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .eml files are supported"
        )
    
    # Check file size (max 10MB)
    if eml_file.size and eml_file.size > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size too large. Maximum size is 10MB"
        )
    
    try:
        # Read the .eml file content
        eml_content = await eml_file.read()
        print("eml_content:", eml_content)
        # Parse the .eml file
        msg = message_from_bytes(eml_content, policy=email.policy.default)
        
        # Extract subject
        subject = msg.get('Subject', '')
        if not subject:
            subject = 'Imported Email Template'
        
        # Extract HTML content
        html_content = None
        text_content = None
        
        if msg.is_multipart():
            # Handle multipart messages
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/html':
                    html_content = part.get_content()
                    break
                elif content_type == 'text/plain' and not text_content:
                    text_content = part.get_content()
        else:
            # Handle single part messages
            content_type = msg.get_content_type()
            if content_type == 'text/html':
                html_content = msg.get_content()
            elif content_type == 'text/plain':
                text_content = msg.get_content()
        
        # If no HTML content found, try to convert text to HTML
        if not html_content and text_content:
            html_content = f"<html><body><pre>{text_content}</pre></body></html>"
        
        # If no text content found, try to extract from HTML
        if not text_content and html_content:
            # Better HTML to text conversion
            import re
            # Remove HTML tags but preserve line breaks
            text_content = re.sub(r'<br\s*/?>', '\n', html_content)
            text_content = re.sub(r'</p>', '\n\n', text_content)
            text_content = re.sub(r'<[^>]+>', '', text_content)
            # Clean up whitespace
            text_content = re.sub(r'\n\s*\n', '\n\n', text_content)
            text_content = re.sub(r' +', ' ', text_content)
            text_content = text_content.strip()
        
        # Use provided name or filename as name
        template_name = name if name else eml_file.filename.replace('.eml', '')
        print("text_content:", text_content)
        print("html_content:", html_content)
        
        # Check if template name already exists for this user
        existing_template = db(
            (db.email_templates.user_id == current_user.id) & 
            (db.email_templates.name == template_name)
        ).select().first()
        
        if existing_template:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A template with this name already exists"
            )
        
        # Create the template
        
        template_id = db.email_templates.insert(
            name=template_name,
            description=description if description else f"Imported from {eml_file.filename}",
            subject=subject,
            html_content=html_content,
            isDemo = isDemo,
            text_content=text_content,
            user_id=current_user.id,
            template_type=template_type,
            is_active=is_active
        )
        db.commit()
        
        # Get the created template
        new_template = db.email_templates(template_id)
        
        # Log activity
        if request:
            client_ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")
            ActivityLogger.log_template_created(
                current_user.id, 
                template_id, 
                template_name, 
                client_ip, 
                user_agent
            )
        
        # Prepare import summary
        import_summary = {
            "subject_extracted": bool(subject),
            "html_content_extracted": bool(html_content),
            "text_content_extracted": bool(text_content),
            "content_types_found": []
        }
        
        if html_content:
            import_summary["content_types_found"].append("HTML")
        if text_content:
            import_summary["content_types_found"].append("Plain Text")
        
        response_data = EmailTemplateResponse(
            id=new_template.id,
            name=new_template.name,
            description=new_template.description,
            subject=new_template.subject,
            html_content=new_template.html_content,
            text_content=new_template.text_content,
            template_type=new_template.template_type,
            ai_prompt=new_template.ai_prompt,
            ai_model_used=new_template.ai_model_used,
            variables=json.loads(new_template.variables) if new_template.variables else None,
            is_active=new_template.is_active,
            isDemo = False,
            created_at=new_template.created_at,
            updated_at=new_template.updated_at
        )
        
        # Add import summary to response
        response_dict = response_data.dict()
        response_dict["import_summary"] = import_summary
        
        return response_dict
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse .eml file: {str(e)}"
        )

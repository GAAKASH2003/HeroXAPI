import os
from fastapi import FastAPI,Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from typing import Optional
from contextlib import asynccontextmanager
from routers import auth_router, sender_profile_router, groups_router, targets_router, user_settings_router, phishlet_router, email_template_router, campaigns_router, analytics_router, dashboard_router, attachment_router, tracker_router
from database import db
import requests
from requests.auth import HTTPBasicAuth
import json
import requests, json
from fastapi import FastAPI
from pydantic import BaseModel, EmailStr
from starlette.middleware.sessions import SessionMiddleware
import dotenv
from database import db
from auth import get_current_user
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv
dotenv_path = '.env'
import os
from database import db
from fastapi import FastAPI
import requests
from datetime import datetime
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
dotenv.load_dotenv()
# Security scheme for Swagger UI
security = HTTPBearer()
# print("GLITCH_TIP_DSN", os.getenv("GLITCH_TIP_DSN"))
sentry_sdk.init(
    dsn=os.getenv("GLITCH_TIP_DSN"),
    integrations=[FastApiIntegration()],
    traces_sample_rate=0.0,   # optional: performance monitoring
    send_default_pii=True     # optional: captures user info
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")
    yield
    # Shutdown
    print("Shutting down...")
    db.close()

app = FastAPI(
    title="HeroX API",
    description="A comprehensive phishing simulation platform API",
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication and authorization endpoints"
        },
        {
            "name": "Sender Profiles",
            "description": "Email sender profile management (SMTP/OAuth)"
        },
        {
            "name": "Groups",
            "description": "Department/group management for organizing targets"
        },
        {
            "name": "Targets",
            "description": "Employee/target management for phishing campaigns"
        },
        {
            "name": "User Settings",
            "description": "User profile and AI settings management"
        },
        {
            "name": "Phishlets",
            "description": "Phishing page templates and website cloning"
        },
        {
            "name": "Email Templates",
            "description": "Email template management with AI generation"
        },
        {
            "name": "Campaigns",
            "description": "Phishing campaign management and scheduling"
        },
        {
            "name": "Analytics",
            "description": "Campaign performance analytics and reporting"
        },
        {
            "name": "Dashboard",
            "description": "Dashboard statistics and activity monitoring"
        }
    ]
)

# CORS middleware
app.add_middleware(SessionMiddleware, secret_key="super-secret-session-key")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    try:
        # Test database connection
        db.executesql("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}


class EmailPayload(BaseModel):
    sender: EmailStr
    password: str
    recipient: EmailStr
    subject: str
    body: str

# class CronRequest(BaseModel):
#     email_payload: EmailPayload
#     hour: int
#     minute: int
#     day: int
#     month: int


# @app.get("/cron-proxy")
# async def cron_proxy(sender: str, recipient: str, subject: str, message: str):
#     payload = {
#         "sender": sender,
#         "recipient": recipient,
#         "subject": subject,
#         "message": message
#     }
#     print("payload", payload)
#     resp = requests.post("http://localhost:8001/send_email", json=payload)
#     return {"forwarded": resp.status_code}


# @app.post("/cron")
# async def run_cron_jobs(req: Request):
#     cron_req = await req.json()
#     payload = {
#         "job": {
#             "url": "http://localhost:8000/cron-proxy?sender=gopuaakash751@gmail.com&recipient=shivarkcodes@gmail.com&subject=Hello&message=Test email",
#             "enabled": True,
#             "saveResponses": True,
#             "body":"{\"name\": \"Apple MacBook Pro 16\",\"data\": {\"year\": 2019,\"price\": 1849.99,\"CPU model\": \"Intel Core i9\",\"Hard disk size\": \"1 TB\"}}",
#             "schedule": {
#                 "timezone": "Asia/Kolkata",
#                 "expiresAt": 0,
#                 "hours": [-1],
#                 "mdays": [-1],
#                 "minutes": [25],
#                 "months": [9],
#                 "wdays": [5]
#             }
#         }
#     }

#     resp = requests.put(
#         "https://api.cron-job.org/jobs",
#         headers={
#             "Content-Type": "application/json",
#             "Authorization": "Bearer jR4HjNtvytphSNCd4tB/7h/cs4RGLqmcMfc9WvKoLlE="
#         },
#         json=payload
#     )
#     return {"status": "Cron job created", "response": resp.json()}

# class EmailRequest(BaseModel):
#     id: Optional[int] = None
    
    
# @app.post("/send_email", status_code=status.HTTP_200_OK)
# async def send_email(email_req: EmailRequest):
#     print("email_req", email_req.dict())
    
#     campaign = db(db.campaigns.id == email_req.id).select().first()
#     if not campaign:
#         return {"error": "Campaign not found"}
    
#     sender = db(campaign.sender_profile_id == db.sender_profiles.id).select().first()
#     email_temp = db(campaign.email_template_id == db.email_templates.id).select().first()

#     phishlet = None
#     attachment = None
#     print(campaign)
#     if  campaign.phishlet_id:
#         phishlet = db(campaign.phishlet_id == db.phishlets.id).select().first()

#     if campaign.attachment_id:
#         attachment = db(campaign.attachment_id == db.attachments.id).select().first()

#     # Collect targets
#     targets_list = []
#     if campaign.target_type == "individual":
#         targets = json.loads(campaign.target_individuals)
        
#         for target in targets:
#             t = db(db.targets.id == target).select().first()
#             if t.is_active:
#                 targets_list.append(t)
                
#     else:
#         group = db(campaign.target_group_id == db.groups.id).select().first()
#         if group is None:
#             return {"error": "Group not found"}
#         targets = db(db.targets.group_id == group.id).select()
#         for t in targets:
#             if t.is_active:
#                 targets_list.append(t)

#     EMAIL_USER = sender.smtp_username    
#     EMAIL_PASSWORD = sender.smtp_password 

#     for target in targets_list:
#         msg = MIMEMultipart("alternative")
#         msg["From"] = sender.from_address 
#         msg["To"] = target.email
#         msg["Subject"] = email_temp.subject
#         if attachment:
#             # Read the file
#             file_path = attachment.attachmentFile.replace("\\", "/")
#             with open(file_path, "rb") as f:
#                 file_bytes = f.read()
#             print(attachment)
#             maintype, subtype = attachment.file_type.split("/", 1)
#             part = MIMEBase(maintype, subtype)
#             part.set_payload(file_bytes)
#             encoders.encode_base64(part)
#             part.add_header(
#                 "Content-Disposition",
#                 f'attachment; filename="{attachment.name}"'
#             )
#             msg.attach(part)

#             # Body (no phishlet link here)
#             plain_body = email_temp.text_content
#             html_body = email_temp.html_content

#         # ---- CASE 2: Phishlet ----
#         elif phishlet:
#             plain_body = f"{email_temp.text_content}\n\nClick here: {phishlet.clone_url}"            
#             phishlet_url = phishlet.clone_url + '*' + str(campaign.id) + '*' + str(target.id)
#             html_body = email_temp.html_content.replace('{{PHISHLET_URL}}',phishlet_url)

#         else:
#             plain_body = email_temp.text_content
#             html_body = email_temp.html_content
            
#         image_src = os.getenv("BACKEND_URL")
#         html_body = f"""
#             {html_body}
#             <br>
#             <img width="1" height="1" src="{image_src}/api/v1/track/f1/{campaign.id}*{target.id}">
#         """

#         msg.attach(MIMEText(plain_body, "plain"))
#         msg.attach(MIMEText(html_body, "html"))
#         msg.attach(MIMEText(html_body, "html"))

#         try:
#             with smtplib.SMTP(sender.smtp_host, sender.smtp_port) as server:
#                 server.starttls()
#                 server.login(EMAIL_USER, EMAIL_PASSWORD)
#                 server.sendmail(EMAIL_USER, msg["To"], msg.as_string())
#             now = datetime.utcnow()

#             # for target_email in targets_list:
            
                
#                     # Email events log (history)
#             db.email_events.insert(
#                 campaign_id=campaign.id,
#                 target_id=target.id,
#                 event_type="sent",
#                 event_data=json.dumps({
#                     "subject": email_temp.subject,
#                     "from": sender.from_address,
#                     "to": target.email
#                 }),
#                 # timestamp=now
#             )

#             # Campaign results (status tracker)
#             db.campaign_results.update_or_insert(
#                 (db.campaign_results.campaign_id == campaign.id) &
#                 (db.campaign_results.target_id == target.id),
#                 campaign_id=campaign.id,
#                 target_id=target.id,
#                 email_sent=True,
#                 email_sent_at=now,
#                 updated_at=now
#             )

#             db.commit()
#         except Exception as err:
#             return {"message":err}
            

#     return {"message": "✅ Email sent successfully!"}

    



# Include routers
app.include_router(
    auth_router.router,
    prefix="/api/v1",
    tags=["Authentication"]
)

app.include_router(
    sender_profile_router.router,
    prefix="/api/v1/sender-profiles",
    tags=["Sender Profiles"]
)

app.include_router(
    groups_router.router,
    prefix="/api/v1/groups",
    tags=["Groups"]
)

app.include_router(
    targets_router.router,
    prefix="/api/v1/targets",
    tags=["Targets"]
)

app.include_router(
    user_settings_router.router,
    prefix="/api/v1/user-settings",
    tags=["User Settings"]
)

app.include_router(
    phishlet_router.router,
    prefix="/api/v1/phishlets",
    tags=["Phishlets"]
)

app.include_router(
    email_template_router.router,
    prefix="/api/v1/email-templates",
    tags=["Email Templates"]
)

app.include_router(
    tracker_router.router,
    prefix="/api/v1/track",
    tags=["Tracks"]
)

app.include_router(
    attachment_router.router,
    prefix="/api/v1/attachments",
    tags=["Attachments"]
)

app.include_router(
    campaigns_router.router,
    prefix="/api/v1/campaigns",
    tags=["Campaigns"]
)

app.include_router(
    analytics_router.router,
    prefix="/api/v1/analytics",
    tags=["Analytics"]
)

app.include_router(
    dashboard_router.router,
    prefix="/api/v1/dashboard",
    tags=["Dashboard"]
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

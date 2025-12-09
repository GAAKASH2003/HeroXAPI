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
import requests
from datetime import datetime
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
dotenv.load_dotenv()
# Security scheme for Swagger UI
security = HTTPBearer()
# print("GLITCH_TIP_DSN", os.getenv("GLITCH_TIP_DSN"))
# sentry_sdk.init(
#     dsn=os.getenv("GLITCH_TIP_DSN"),
#     integrations=[FastApiIntegration()],
#     traces_sample_rate=0.0,   # optional: performance monitoring
#     send_default_pii=True     # optional: captures user info
# )


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
app.add_middleware(
    SessionMiddleware, 
    secret_key="super-secret-session-key",
    session_cookie="my_session",  # Give it a unique name
    max_age=3600,                 # Session lifespan (optional)
    same_site="None",             # CRITICAL: Allows cross-site requests
    secure=True                   # CRITICAL: Must be True if same_site="None"
)
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

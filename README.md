# HeroX API

A FastAPI application with authentication endpoints using PyDAL and SQLite for data persistence.

## Features

- User registration (signup)
- User authentication (login)
- JWT token-based authentication
- Password hashing with bcrypt
- User profile retrieval
- SQLite database with PyDAL ORM
- Automatic database schema migration

## Project Structure

```
api/
├── main.py              # Main FastAPI application
├── database.py          # Database configuration with PyDAL
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── storage.db          # SQLite database file (created automatically)
├── database/           # PyDAL database files (created automatically)
└── routers/
    ├── __init__.py     # Package initialization
    └── auth_router.py  # Authentication endpoints
```

## Installation

1. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

Start the server:

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

**Note**: The SQLite database (`storage.db`) and PyDAL files will be created automatically on first run.

## API Documentation

Once the server is running, you can access:

- Interactive API docs: `http://localhost:8000/docs`
- ReDoc documentation: `http://localhost:8000/redoc`

## API Endpoints

All authenticated endpoints require a Bearer token (see login/signup) unless noted. Base prefix: `/api/v1`.

### General

- `GET /health` — Health check with database status

Examples

Request

```bash
curl -s http://localhost:8000/health
```

Response

```json
{
  "status": "healthy",
  "database": "connected"
}
```

### Authentication (`routers/auth_router.py`)

- `GET /api/v1/auth/google` — Redirect to Google OAuth login
- `GET /api/v1/auth/google/callback` — Google OAuth callback, issues JWT and redirects to frontend
- `POST /api/v1/signup` — Create a new user account and return JWT
- `POST /api/v1/login` — Login with email/password and return JWT
- `GET /api/v1/me` — Get current user information

Examples

Signup

```bash
curl -X POST http://localhost:8000/api/v1/signup \
  -H "Content-Type: application/json" \
  -d '{
    "username":"john", "email":"john@example.com", "password":"Passw0rd!", "is_admin": false,
    "full_name":"John Doe"
  }'
```

Login

```bash
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email":"john@example.com","password":"Passw0rd!"}'
```

Me

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/me
```

### Sender Profiles (`/api/v1/sender-profiles`, `routers/sender_profile_router.py`)

- `POST /api/v1/sender-profiles/` — Create sender profile (SMTP or OAuth)
- `GET /api/v1/sender-profiles/` — List sender profiles (user’s and admins’ when applicable)
- `GET /api/v1/sender-profiles/{profile_id}` — Get a sender profile
- `PUT /api/v1/sender-profiles/{profile_id}` — Update a sender profile
- `DELETE /api/v1/sender-profiles/{profile_id}` — Delete a sender profile

Examples

Create (SMTP)

```bash
curl -X POST http://localhost:8000/api/v1/sender-profiles/ \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "name":"Corp SMTP","auth_type":"smtp","from_address":"it@example.com",
    "from_name":"IT","smtp_host":"smtp.example.com","smtp_port":587,
    "smtp_username":"it@example.com","smtp_password":"app-password"
  }'
```

List

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/sender-profiles/
```

### Groups (`/api/v1/groups`, `routers/groups_router.py`)

- `POST /api/v1/groups/` — Create group/department
- `GET /api/v1/groups/` — List groups for current user (admins see all)
- `GET /api/v1/groups/{group_id}` — Get group by id
- `PUT /api/v1/groups/{group_id}` — Update group
- `DELETE /api/v1/groups/{group_id}` — Delete group (blocked if targets attached)

Examples

Create

```bash
curl -X POST http://localhost:8000/api/v1/groups/ \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"name":"Finance","description":"Finance Dept"}'
```

List

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/groups/
```

### Targets (`/api/v1/targets`, `routers/targets_router.py`)

- `POST /api/v1/targets/` — Create target (employee)
- `GET /api/v1/targets/` — List targets (optional `group_id` filter)
- `GET /api/v1/targets/{target_id}` — Get target by id
- `PUT /api/v1/targets/{target_id}` — Update target
- `DELETE /api/v1/targets/{target_id}` — Delete target

Examples

Create

```bash
curl -X POST http://localhost:8000/api/v1/targets/ \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{"first_name":"Alice","last_name":"Lee","email":"alice@corp.com","group_id":1}'
```

List by group

```bash
curl -H "Authorization: Bearer <JWT>" "http://localhost:8000/api/v1/targets/?group_id=1"
```

### User Settings (`/api/v1/user-settings`, `routers/user_settings_router.py`)

- `GET /api/v1/user-settings/profile` — Get user profile and AI settings (no API key leaked)
- `PUT /api/v1/user-settings/profile` — Update username, email, full name
- `PUT /api/v1/user-settings/password` — Change password
- `PUT /api/v1/user-settings/ai-settings` — Update AI provider/model/settings and API key
- `GET /api/v1/user-settings/ai-settings` — Get AI settings (API key presence only)

Examples

Get profile

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/user-settings/profile
```

Update AI settings

```bash
curl -X PUT http://localhost:8000/api/v1/user-settings/ai-settings \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "ai_model":"gpt-4o","api_key":"sk-...","provider":"openai",
    "max_tokens":800,"temperature":0.7,"is_active":true
  }'
```

### Phishlets (`/api/v1/phishlets`, `routers/phishlet_router.py`)

- `POST /api/v1/phishlets/` — Create phishlet (optionally with provided HTML)
- `POST /api/v1/phishlets/clone` — Clone a website and create a phishlet
- `GET /api/v1/phishlets/` — List phishlets (user and admins’ where applicable)
- `POST /api/v1/phishlets/upload-html` — Upload an HTML file and extract fields
- `POST /api/v1/phishlets/preview` — Preview phishlet and detected form fields
- `POST /api/v1/phishlets/save` — Save a phishlet after preview/edit
- `POST /api/v1/phishlets/clone-preview` — Clone website and return preview payload
- `GET /api/v1/phishlets/{phishlet_id}` — Get phishlet by id
- `PUT /api/v1/phishlets/{phishlet_id}` — Update phishlet
- `DELETE /api/v1/phishlets/{phishlet_id}` — Delete phishlet
- `GET /api/v1/phishlets/{phishlet_id}/content` — Get HTML content and fields
- `GET /api/v1/phishlets/serve/{url_id}` — Public endpoint to serve cloned page and (when adorned with campaign/target) inject tracking

Examples

Create

```bash
curl -X POST http://localhost:8000/api/v1/phishlets/ \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "name":"Office365 Login","description":"O365 clone",
    "original_url":"https://login.microsoftonline.com/",
    "html_content":"<html>...</html>",
    "capture_credentials":true
  }'
```

Clone

```bash
curl -X POST http://localhost:8000/api/v1/phishlets/clone \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "original_url":"https://example.com","name":"Example Clone"
  }'
```

Upload HTML

```bash
curl -X POST http://localhost:8000/api/v1/phishlets/upload-html \
  -H "Authorization: Bearer <JWT>" \
  -F file=@page.html
```

Serve (public; no auth)

```bash
curl "http://localhost:8000/api/v1/phishlets/serve/<url_id>"
```

### Email Templates (`/api/v1/email-templates`, `routers/email_template_router.py`)

- `POST /api/v1/email-templates/` — Create email template
- `POST /api/v1/email-templates/generate` — Generate template using configured AI
- `GET /api/v1/email-templates/` — List email templates (falls back to demos if empty)
- `GET /api/v1/email-templates/{template_id}` — Get template by id
- `PUT /api/v1/email-templates/{template_id}` — Update template
- `DELETE /api/v1/email-templates/{template_id}` — Delete template
- `POST /api/v1/email-templates/{template_id}/regenerate` — Regenerate an AI-generated template
- `POST /api/v1/email-templates/import/eml` — Import template from .eml file

Examples

Create

```bash
curl -X POST http://localhost:8000/api/v1/email-templates/ \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "name":"Password Reset","subject":"Action Required",
    "html_content":"<html>...","text_content":"Plain text","isDemo": false
  }'
```

Generate with AI

```bash
curl -X POST http://localhost:8000/api/v1/email-templates/generate \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "name":"Urgent HR Notice","prompt":"Draft a phishing style email",
    "template_type":"phishing","tone":"urgent","include_html":true,"include_text":true
  }'
```

Import .eml

```bash
curl -X POST http://localhost:8000/api/v1/email-templates/import/eml \
  -H "Authorization: Bearer <JWT>" \
  -F eml_file=@sample.eml -F name="Imported"
```

### Campaigns (`/api/v1/campaigns`, `routers/campaigns_router.py`)

- `POST /api/v1/campaigns/` — Create campaign (schedule or run now; requires phishlet or attachment)
- `GET /api/v1/campaigns/` — List campaigns (admins see all)
- `GET /api/v1/campaigns/{campaign_id}` — Get campaign by id
- `PUT /api/v1/campaigns/{campaign_id}` — Update campaign
- `DELETE /api/v1/campaigns/{campaign_id}` — Delete campaign
- `POST /api/v1/campaigns/{campaign_id}/run` — Start a scheduled/paused campaign
- `POST /api/v1/campaigns/{campaign_id}/pause` — Pause a running campaign
- `GET /api/v1/campaigns/{campaign_id}/results` — Get campaign results with captured data summary
- `POST /api/v1/campaigns/send_email` — Utility endpoint to send a test email

Examples

Create

```bash
curl -X POST http://localhost:8000/api/v1/campaigns/ \
  -H "Authorization: Bearer <JWT>" -H "Content-Type: application/json" \
  -d '{
    "name":"Feb Campaign","sender_profile_id":1,
    "email_template_id":2,
    "phishlet_id":3,
    "target_type":"group","target_group_id":1,
    "launch_now": true
  }'
```

Run

```bash
curl -X POST -H "Authorization: Bearer <JWT>" \
  http://localhost:8000/api/v1/campaigns/1/run
```

Results

```bash
curl -H "Authorization: Bearer <JWT>" \
  http://localhost:8000/api/v1/campaigns/1/results
```

### Analytics (`/api/v1/analytics`, `routers/analytics_router.py`)

- `GET /api/v1/analytics/dashboard` — High-level dashboard metrics
- `GET /api/v1/analytics/campaigns` — Stats for all campaigns
- `GET /api/v1/analytics/campaigns/{campaign_id}` — Detailed stats for a campaign
- `GET /api/v1/analytics/activity` — User activity log (paged)
- `GET /api/v1/analytics/targets/performance` — Target performance scores
- `GET /api/v1/analytics/timeseries?days=30` — Time series data for charts

Examples

Dashboard summary

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/analytics/dashboard
```

Targets performance

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/analytics/targets/performance
```

### Dashboard (`/api/v1/dashboard`, `routers/dashboard_router.py`)

- `GET /api/v1/dashboard/stats` — Comprehensive dashboard stats
- `GET /api/v1/dashboard/recent-activity` — Recent activities summary
- `GET /api/v1/dashboard/email-events` — Email events summary
- `GET /api/v1/dashboard/activity-breakdown` — Breakdown of activities by type/date
- `GET /api/v1/dashboard/campaign-performance` — Campaign performance summary
- `GET /api/v1/dashboard/quick-stats` — Quick counts for widgets

Examples

Stats

```bash
curl -H "Authorization: Bearer <JWT>" http://localhost:8000/api/v1/dashboard/stats
```

Recent activity

```bash
curl -H "Authorization: Bearer <JWT>" "http://localhost:8000/api/v1/dashboard/recent-activity?days=7&limit=50"
```

### Attachments (`/api/v1/attachments`, `routers/attachment_router.py`)

- `POST /api/v1/attachments/` — Upload attachment (stored on disk; path in DB)
- `GET /api/v1/attachments/` — List attachments (user’s, admins’, and demos)
- `PUT /api/v1/attachments/{attachment_id}` — Update attachment metadata
- `GET /api/v1/attachments/{attachment_id}/download` — Download attachment file
- `DELETE /api/v1/attachments/{attachment_id}` — Delete attachment and file

Examples

Upload

```bash
curl -X POST http://localhost:8000/api/v1/attachments/ \
  -H "Authorization: Bearer <JWT>" \
  -F name="Policy PDF" -F description="HR Policy" -F isDemo=false \
  -F attachmentFile=@policy.pdf
```

Download

```bash
curl -L -H "Authorization: Bearer <JWT>" \
  http://localhost:8000/api/v1/attachments/10/download -o policy.pdf
```

### Tracking (`/api/v1/track`, `routers/tracker_router.py`)

- `GET /api/v1/track/f1/{campaignId*targetId}` — Track email opens (pixel)
- `POST /api/v1/track/f2/{campaignId*targetId}` — Track form interactions/submissions on served phishlets
- `GET /api/v1/track/credentials/{campaign_id}/{user_id}` — Fetch captured credentials for a target

Examples

Open tracking (pixel)

```bash
curl "http://localhost:8000/api/v1/track/f1/1*42"
```

Form tracking

```bash
curl -X POST "http://localhost:8000/api/v1/track/f2/1*42" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "email": {"type": "input", "value": "user@example.com"},
      "password": {"type": "input", "value": "secret"},
      "remember": {"type": "checkbox", "value": true}
    }
  }'
```

## Example Usage

### Signup

```bash
curl -X POST "http://localhost:8000/api/v1/signup" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "john_doe",
       "email": "john@example.com",
       "password": "securepassword123",
       "full_name": "John Doe"
     }'
```

### Login

```bash
curl -X POST "http://localhost:8000/api/v1/login" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "john@example.com",
       "password": "securepassword123"
     }'
```

### Get User Profile

```bash
curl -X GET "http://localhost:8000/api/v1/me?token=YOUR_JWT_TOKEN"
```

## Database

The application uses:

- **PyDAL**: Python Database Abstraction Layer for ORM functionality
- **SQLite**: Lightweight, serverless database
- **Automatic migrations**: Database schema is created automatically

### Database Schema

The `users` table includes:

- `id`: Primary key (auto-increment)
- `username`: Unique username
- `email`: Unique email address
- `password`: Hashed password
- `full_name`: Optional full name
- `created_at`: Timestamp of account creation

## Security Notes

- Passwords are hashed using bcrypt
- JWT tokens are used for authentication
- SQLite database provides data persistence
- For production, consider:
  - Using a more robust database (PostgreSQL, MySQL)
  - Changing the SECRET_KEY in auth_router.py
  - Implementing proper password validation
  - Adding rate limiting and additional security measures
  - Using environment variables for sensitive configuration

import os

from uuid import uuid4
from pydal import DAL, Field
from datetime import datetime

# Ensure database directory exists with proper permissions
database_dir = os.path.join(os.path.dirname(__file__), 'database')
os.makedirs(database_dir, exist_ok=True)

# Initialize database with absolute path
db_path = os.path.join(database_dir, 'app.db')
db = DAL(f'sqlite://{db_path}', folder=database_dir)

# Define users table
# print(db.tables)
if 'users' not in db.tables:
    
    db.define_table('users',
        Field('id', 'id'),
        Field('username', 'string', required=True, unique=True),
        Field('email', 'string', required=True, unique=True),
        Field('password', 'string', required=True),
        Field('full_name', 'string'),
        Field('is_admin','boolean',required=True,default=False),
        # AI Settings fields
        Field('ai_model', 'string'),
        Field('ai_provider', 'string'),
        Field('ai_api_key', 'string'),
        Field('ai_max_tokens', 'integer'),
        Field('ai_temperature', 'double'),
        Field('ai_is_active', 'boolean', default=False),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define sender_profiles table
if 'sender_profiles' not in db.tables:
    db.define_table('sender_profiles',
        Field('id', 'id'),
        Field('name', 'string', required=True),
        Field('user_id', 'reference users', required=True),
        Field('auth_type', 'string', required=True),  # 'smtp' or 'oauth'
        Field('smtp_host', 'string'),
        Field('smtp_port', 'integer'),
        Field('smtp_username', 'string'),
        Field('smtp_password', 'string'),
        Field('from_address', 'string', required=True),
        Field('from_name', 'string'),
        Field('oauth_client_id', 'string'),
        Field('oauth_client_secret', 'string'),
        Field('oauth_refresh_token', 'string'),
        Field('oauth_access_token', 'string'),
        Field('oauth_token_expiry', 'datetime'),
        Field('is_active', 'boolean', default=True),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define groups table
if 'groups' not in db.tables:
    db.define_table('groups',
        Field('id', 'id'),
        Field('name', 'string', required=True),
        Field('description', 'text'),
        Field('user_id', 'reference users', required=True),  # Owner of the group
        Field('is_active', 'boolean', default=True),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define targets table
if 'targets' not in db.tables:
    db.define_table('targets',
        Field('id', 'id'),
        Field('first_name', 'string'),  # Optional
        Field('last_name', 'string'),   # Optional
        Field('email', 'string', required=True),
        Field('position', 'string'),  # Optional
        Field('group_id', 'reference groups'),  # Optional - can be in multiple groups
        Field('user_id', 'reference users', required=True),  # Owner of the target
        Field('is_active', 'boolean', default=True),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define phishlets table
if 'phishlets' not in db.tables:
    db.define_table('phishlets',
        Field('id', 'id'),
        Field('name', 'string', required=True),
        Field('url_id', 'text'),
        Field('description', 'text'),
        Field('user_id', 'reference users', required=True),  # Owner of the phishlet
        Field('original_url', 'string', required=True),  # Original website URL
        Field('clone_url', 'string'),  # Cloned website URL
        Field('html_content', 'text'),  # HTML content of the cloned page
        Field('form_fields', 'text'),  # JSON string of form fields to capture
        Field('capture_credentials', 'boolean', default=True),  # Whether to capture credentials
        Field('capture_other_data', 'boolean', default=True),  # Whether to capture other form data
        Field('redirect_url', 'string'),  # Where to redirect after form submission
        Field('is_active', 'boolean', default=True),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define email_templates table
if 'email_templates' not in db.tables:
    db.define_table('email_templates',
        Field('id', 'id'),
        Field('name', 'string', required=True),
        Field('description', 'text'),
        Field('isDemo', 'boolean', default=False),
        Field('user_id', 'reference users', required=True),  # Owner of the template
        Field('subject', 'string', required=True),  # Email subject line
        Field('html_content', 'text'),  # HTML version of the email
        Field('text_content', 'text'),  # Plain text version of the email
        Field('template_type', 'string', default='custom'),  # 'custom', 'ai_generated', 'predefined'
        Field('ai_prompt', 'text'),  # The prompt used to generate the template
        Field('ai_model_used', 'string'),  # Which AI model was used
        Field('variables', 'text'),  # JSON string of template variables
        Field('is_active', 'boolean', default=True),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Attachments
if 'attachments' not in db.tables:
    db.define_table('attachments',
        Field('id', 'id'),
        Field('name', 'string', required=True),
        Field('description', 'text'),
        Field('isDemo', 'boolean', default=False),
        Field('user_id', 'reference users', required=True),
        Field('file_type', 'string'),  # e.g., image/jpeg, application/pdf
        Field('attachmentFile', 'string', required=True),  # store file path or filename
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
    )


# Define campaigns table
if 'campaigns' not in db.tables:
    db.define_table('campaigns',
        Field('id', 'id'),
        Field('name', 'string', required=True),
        Field('description', 'text'),
        Field('user_id', 'reference users', required=True),  # Owner of the campaign
        Field('sender_profile_id', 'reference sender_profiles', required=True),
        Field('email_template_id', 'reference email_templates', required=True),
        Field('phishlet_id', 'reference phishlets', required=True,default=None),
        Field('target_type', 'string', required=True),  # 'group' or 'individual'
        Field('target_group_id', 'reference groups'),  # If target_type is 'group'
        Field('target_individuals', 'text'),  # JSON array of target IDs if target_type is 'individual'
        Field('attachment_id','reference attachments',required=True,default=None),
        Field('target_individuals', 'text '),  # JSON array of target IDs if target_type is 'individual'
        Field('scheduled_at', 'datetime'),  # When to send the campaign (null for immediate)
        Field('status', 'string', default='draft'),  # 'draft', 'scheduled', 'running', 'completed', 'paused', 'cancelled'
        Field('is_active', 'boolean', default=True),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define campaign_results table for analytics
if 'campaign_results' not in db.tables:
    db.define_table('campaign_results',
        Field('id', 'id'),
        Field('campaign_id', 'reference campaigns', required=True),
        Field('target_id', 'reference targets', required=True),
        Field('email_sent', 'boolean', default=False),
        Field('email_sent_at', 'datetime'),
        Field('email_opened', 'boolean', default=False),
        Field('email_opened_at', 'datetime'),
        Field('link_clicked', 'boolean', default=False),
        Field('link_clicked_at', 'datetime'),
        Field('form_submitted', 'boolean', default=False),
        Field('form_submitted_at', 'datetime'),
        Field('credentials_captured', 'boolean', default=False),
        Field('captured_data', 'text'),  # JSON string of captured form data
        Field('ip_address', 'string'),
        Field('user_agent', 'string'),
        Field('created_at', 'datetime', default=lambda: datetime.utcnow()),
        Field('updated_at', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define email_events table for detailed tracking
if 'email_events' not in db.tables:
    db.define_table('email_events',
        Field('id', 'id'),
        Field('campaign_id', 'reference campaigns', required=True),
        Field('target_id', 'reference targets', required=True),
        Field('event_type', 'string', required=True),  # 'sent', 'delivered', 'opened', 'clicked', 'bounced', 'complained'
        Field('event_data', 'text'),  # JSON string of additional event data
        Field('timestamp', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# Define user_activities table for comprehensive activity logging
if 'user_activities' not in db.tables:
    db.define_table('user_activities',
        Field('id', 'id'),
        Field('user_id', 'reference users', required=True),
        Field('activity_type', 'string', required=True),  # 'login', 'logout', 'campaign_created', 'campaign_updated', 'campaign_deleted', 'target_added', 'template_created', 'phishlet_created', 'email_sent', 'form_submitted', etc.
        Field('resource_type', 'string'),  # 'campaign', 'target', 'template', 'phishlet', 'sender_profile', 'group', 'user_settings'
        Field('resource_id', 'integer'),  # ID of the affected resource
        Field('resource_name', 'string'),  # Name of the affected resource
        Field('description', 'text'),  # Human-readable description of the activity
        Field('ip_address', 'string'),  # IP address of the user
        Field('user_agent', 'string'),  # User agent string
        Field('metadata', 'text'),  # JSON string of additional metadata
        Field('timestamp', 'datetime', default=lambda: datetime.utcnow()),
        migrate=True
    )

# if "ai_models" not in db.tables:
#     db.define_table("ai_models",
#         Field("id", "id"),
#         Field("name", "string", required=True),
#         Field("api_key", "string", required=True),
#         Field("user", "reference users", required=True),
#         Field("provider", "string", required=True),  # e.g., 'OpenAI', 'Anthropic'
#         Field("max_tokens", "integer", required=True, default=1000),
#         Field("temperature", "double", required=True, default=0.7),
#         Field("is_active", "boolean", default=True),
#         Field("created_at", "datetime", default=lambda: datetime.utcnow()),
#         Field("updated_at", "datetime", default=lambda: datetime.utcnow()),
#         migrate=True,
#     )
# Commit the database schema
db.commit()

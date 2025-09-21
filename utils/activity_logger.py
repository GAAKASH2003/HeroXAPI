import json
from datetime import datetime
from typing import Optional, Dict, Any
from database import db

class ActivityLogger:
    """Utility class for logging user activities"""
    
    @staticmethod
    def log_activity(
        user_id: int,
        activity_type: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        resource_name: Optional[str] = None,
        description: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a user activity"""
        try:
            metadata_json = json.dumps(metadata) if metadata else None
            
            db.user_activities.insert(
                user_id=user_id,
                activity_type=activity_type,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=metadata_json,
                timestamp=datetime.utcnow()
            )
            db.commit()
        except Exception as e:
            # Log error but don't fail the main operation
            print(f"Error logging activity: {e}")
            
    @staticmethod
    def checkIfAdmin(user_id: int) -> bool:
        """Check if a user is admin"""
        user = db(db.users.id == user_id).select().first()
        return user.is_admin if user else False
    
    @staticmethod
    def log_login(user_id: int, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log user login"""
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="login",
            description="User logged in",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_logout(user_id: int, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log user logout"""
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="logout",
            description="User logged out",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_campaign_created(user_id: int, campaign_id: int, campaign_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log campaign creation"""
        if ActivityLogger.checkIfAdmin(user_id):
              ActivityLogger.log_activity(
                  user_id=user_id,
                  activity_type="campaign_created",
                  resource_type="campaign",
                  resource_id=campaign_id,
                  resource_name=campaign_name,
                  description=f"Created campaign: {campaign_name} by admin",
                  ip_address=ip_address,
                  user_agent=user_agent
              )
        else:
              ActivityLogger.log_activity(
                  user_id=user_id,
                  activity_type="campaign_created",
                  resource_type="campaign",
                  resource_id=campaign_id,
                  resource_name=campaign_name,
                  description=f"Created campaign: {campaign_name} by you",
                  ip_address=ip_address,
                  user_agent=user_agent
              )
    
    @staticmethod
    def log_campaign_updated(user_id: int, campaign_id: int, campaign_name: str, changes: Dict[str, Any], ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log campaign update"""
        if ActivityLogger.checkIfAdmin(user_id):
              ActivityLogger.log_activity(
                  user_id=user_id,
                  activity_type="campaign_updated",
                  resource_type="campaign",
                  resource_id=campaign_id,
                  resource_name=campaign_name,
                  description=f"Updated campaign: {campaign_name} by admin",
                  ip_address=ip_address,
                  user_agent=user_agent,
                  metadata={"changes": changes}
        )
        else:
              ActivityLogger.log_activity(
                  user_id=user_id,
                  activity_type="campaign_updated",
                  resource_type="campaign",
                  resource_id=campaign_id,
                  resource_name=campaign_name,
                  description=f"Updated campaign: {campaign_name} by you",
                  ip_address=ip_address,
                  user_agent=user_agent,
                  metadata={"changes": changes}
        )
    
    @staticmethod
    def log_campaign_deleted(user_id: int, campaign_id: int, campaign_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log campaign deletion"""
        if ActivityLogger.checkIfAdmin(user_id):
              ActivityLogger.log_activity(
                 user_id=user_id,
                 activity_type="campaign_deleted",
                 resource_type="campaign",
                 resource_id=campaign_id,
                 resource_name=campaign_name,
                 description=f"Deleted campaign: {campaign_name} by admin",
                 ip_address=ip_address,
                 user_agent=user_agent
             )
        else:    
             ActivityLogger.log_activity(
                 user_id=user_id,
                 activity_type="campaign_deleted",
                 resource_type="campaign",
                 resource_id=campaign_id,
                 resource_name=campaign_name,
                 description=f"Deleted campaign: {campaign_name} by you",
                 ip_address=ip_address,
                 user_agent=user_agent
             )
         
    @staticmethod
    def log_target_added(user_id: int, target_id: int, target_email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log target addition"""
        if ActivityLogger.checkIfAdmin(user_id):
             ActivityLogger.log_activity(
                 user_id=user_id,
                 activity_type="target_added",
                 resource_type="target",
                 resource_id=target_id,
                 resource_name=target_email,
                 description=f"Added target: {target_email} by admin",
                 ip_address=ip_address,
                 user_agent=user_agent
             )
        else:
            ActivityLogger.log_activity(
                 user_id=user_id,
                 activity_type="target_added",
                 resource_type="target",
                 resource_id=target_id,
                 resource_name=target_email,
                 description=f"Added target: {target_email} by you",
                 ip_address=ip_address,
                 user_agent=user_agent
             )
    
    @staticmethod
    def log_target_updated(user_id: int, target_id: int, target_email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log target update"""
        if ActivityLogger.checkIfAdmin(user_id):
            ActivityLogger.log_activity(
                user_id=user_id,
                activity_type="target_updated",
                resource_type="target",
                resource_id=target_id,
                resource_name=target_email,
                description=f"Updated target: {target_email} by admin",
                ip_address=ip_address,
                user_agent=user_agent
            )
        else:
            ActivityLogger.log_activity(
                user_id=user_id,
                activity_type="target_updated",
                resource_type="target",
                resource_id=target_id,
                resource_name=target_email,
                description=f"Updated target: {target_email} by you",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
    
    @staticmethod
    def log_target_deleted(user_id: int, target_id: int, target_email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log target deletion"""
        if ActivityLogger.checkIfAdmin(user_id):
            ActivityLogger.log_activity(
                user_id=user_id,
                activity_type="target_deleted",
                resource_type="target",
                resource_id=target_id,
                resource_name=target_email,
                description=f"Deleted target: {target_email} by admin",
                ip_address=ip_address,
                user_agent=user_agent
            )
        else: 
            ActivityLogger.log_activity(
                user_id=user_id,
                activity_type="target_deleted",
                resource_type="target",
                resource_id=target_id,
                resource_name=target_email,
                description=f"Deleted target: {target_email} by admin",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
    
    @staticmethod
    def log_group_created(user_id: int, group_id: int, group_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log group creation"""
        if ActivityLogger.checkIfAdmin(user_id):
            ActivityLogger.log_activity(
                user_id=user_id,
                activity_type="group_created",
                resource_type="group",
                resource_id=group_id,
                resource_name=group_name,
                description=f"Created group: {group_name} by admin",
                ip_address=ip_address,
                user_agent=user_agent
            )
        else:
             ActivityLogger.log_activity(
                user_id=user_id,
                activity_type="group_created",
                resource_type="group",
                resource_id=group_id,
                resource_name=group_name,
                description=f"Created group: {group_name} by you",
                ip_address=ip_address,
                user_agent=user_agent
            )
            
    
    @staticmethod
    def log_group_updated(user_id: int, group_id: int, group_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log group update"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Updated group:{group_name} by admin"
        else:
            description = f"Updated group:{group_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="group_updated",
            resource_type="group",
            resource_id=group_id,
            resource_name=group_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_group_deleted(user_id: int, group_id: int, group_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log group deletion"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Deleted group: {group_name} by admin"
        else:
            description = f"Deleted group: {group_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="group_deleted",
            resource_type="group",
            resource_id=group_id,
            resource_name=group_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_template_created(user_id: int, template_id: int, template_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log template creation"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Created email template: {template_name} by admin"
        else:
            description = f"Created email template: {template_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="template_created",
            resource_type="template",
            resource_id=template_id,
            resource_name=template_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_template_updated(user_id: int, template_id: int, template_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log template update"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Updated email template: {template_name} by admin"
        else:
            description = f"Updated email template: {template_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="template_updated",
            resource_type="template",
            resource_id=template_id,
            resource_name=template_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_template_deleted(user_id: int, template_id: int, template_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log template deletion"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Deleted email template: {template_name} by admin"
        else:
            description = f"Deleted email template: {template_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="template_deleted",
            resource_type="template",
            resource_id=template_id,
            resource_name=template_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_phishlet_created(user_id: int, phishlet_id: int, phishlet_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log phishlet creation"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Created phishlet: {phishlet_name} by admin"
        else:
            description = f"Created phishlet: {phishlet_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="phishlet_created",
            resource_type="phishlet",
            resource_id=phishlet_id,
            resource_name=phishlet_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_phishlet_updated(user_id: int, phishlet_id: int, phishlet_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log phishlet update"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Updated phishlet: {phishlet_name} by admin"
        else:
            description = f"Updated phishlet: {phishlet_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="phishlet_updated",
            resource_type="phishlet",
            resource_id=phishlet_id,
            resource_name=phishlet_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_phishlet_deleted(user_id: int, phishlet_id: int, phishlet_name: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log phishlet deletion"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Deleted phishlet: {phishlet_name} by admin"
        else:
            description = f"Deleted phishlet: {phishlet_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="phishlet_deleted",
            resource_type="phishlet",
            resource_id=phishlet_id,
            resource_name=phishlet_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_email_sent(user_id: int, campaign_id: int, campaign_name: str, target_email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log email sent"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Sent email to {target_email} from campaign: {campaign_name} by admin"
        else:
            description = f"Sent email to {target_email} from campaign: {campaign_name} by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="email_sent",
            resource_type="campaign",
            resource_id=campaign_id,
            resource_name=campaign_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_form_submitted(user_id: int, campaign_id: int, campaign_name: str, target_email: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log form submission"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Form submitted by {target_email} from campaign: {campaign_name} (recorded by admin)"
        else:
            description = f"Form submitted by {target_email} from campaign: {campaign_name} (recorded by you)"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="form_submitted",
            resource_type="campaign",
            resource_id=campaign_id,
            resource_name=campaign_name,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

    @staticmethod
    def log_settings_updated(user_id: int, setting_type: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log settings update"""
        if ActivityLogger.checkIfAdmin(user_id):
            description = f"Updated {setting_type} settings by admin"
        else:
            description = f"Updated {setting_type} settings by you"
        ActivityLogger.log_activity(
            user_id=user_id,
            activity_type="settings_updated",
            resource_type="user_settings",
            resource_name=setting_type,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent
        )

from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timedelta
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger

router = APIRouter()

# Pydantic models
class DashboardStatsResponse(BaseModel):
    total_campaigns: int
    active_campaigns: int
    total_targets: int
    total_templates: int
    total_phishlets: int
    total_sender_profiles: int
    total_groups: int
    total_emails_sent: int
    total_emails_opened: int
    total_links_clicked: int
    total_forms_submitted: int
    total_credentials_captured: int
    overall_open_rate: float
    overall_click_rate: float
    overall_submission_rate: float
    overall_capture_rate: float

class RecentActivityResponse(BaseModel):
    id: int
    activity_type: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    resource_name: Optional[str] = None
    description: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime

class DashboardActivitySummary(BaseModel):
    period: str
    total_activities: int
    activities_by_type: Dict[str, int]
    recent_activities: List[RecentActivityResponse]

class EmailEventSummary(BaseModel):
    total_events: int
    events_by_type: Dict[str, int]
    events_by_campaign: Dict[str, int]
    recent_events: List[Dict[str, Any]]

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(current_user = Depends(get_current_user)):
    """Get comprehensive dashboard statistics"""
    
    # Get all campaigns for the user
    campaigns = db(db.campaigns.user_id == current_user.id).select()
    campaign_ids = [campaign.id for campaign in campaigns]
    
    # Get campaign results
    results = db(db.campaign_results.campaign_id.belongs(campaign_ids)).select() if campaign_ids else []
    
    # Calculate campaign stats
    total_campaigns = len(campaigns)
    active_campaigns = len([c for c in campaigns if c.status in ['running', 'scheduled']])
    
    # Calculate resource counts
    total_targets = len(db(db.targets.user_id == current_user.id).select())
    total_templates = len(db(db.email_templates.user_id == current_user.id).select())
    total_phishlets = len(db(db.phishlets.user_id == current_user.id).select())
    total_sender_profiles = len(db(db.sender_profiles.user_id == current_user.id).select())
    total_groups = len(db(db.groups.user_id == current_user.id).select())
    
    # Calculate email stats
    total_emails_sent = len([r for r in results if r.email_sent])
    total_emails_opened = len([r for r in results if r.email_opened])
    total_links_clicked = len([r for r in results if r.link_clicked])
    total_forms_submitted = len([r for r in results if r.form_submitted])
    total_credentials_captured = len([r for r in results if r.credentials_captured])
    
    # Calculate rates
    overall_open_rate = (total_emails_opened / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    overall_click_rate = (total_links_clicked / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    overall_submission_rate = (total_forms_submitted / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    overall_capture_rate = (total_credentials_captured / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
    
    return DashboardStatsResponse(
        total_campaigns=total_campaigns,
        active_campaigns=active_campaigns,
        total_targets=total_targets,
        total_templates=total_templates,
        total_phishlets=total_phishlets,
        total_sender_profiles=total_sender_profiles,
        total_groups=total_groups,
        total_emails_sent=total_emails_sent,
        total_emails_opened=total_emails_opened,
        total_links_clicked=total_links_clicked,
        total_forms_submitted=total_forms_submitted,
        total_credentials_captured=total_credentials_captured,
        overall_open_rate=round(overall_open_rate, 2),
        overall_click_rate=round(overall_click_rate, 2),
        overall_submission_rate=round(overall_submission_rate, 2),
        overall_capture_rate=round(overall_capture_rate, 2)
    )

@router.get("/recent-activity", response_model=DashboardActivitySummary)
async def get_recent_activity(
    days: int = 7,
    limit: int = 50,
    current_user = Depends(get_current_user)
):
    """Get recent user activities with comprehensive logging"""
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get recent activities
    activities = db(
        (db.user_activities.user_id == current_user.id) &
        (db.user_activities.timestamp >= start_date) &
        (db.user_activities.timestamp <= end_date)
    ).select(orderby=~db.user_activities.timestamp, limitby=(0, limit))
    
    # Count activities by type
    activities_by_type = {}
    for activity in activities:
        activity_type = activity.activity_type
        activities_by_type[activity_type] = activities_by_type.get(activity_type, 0) + 1
    
    # Convert to response format
    recent_activities = []
    for activity in activities:
        metadata = None
        if activity.metadata:
            try:
                metadata = json.loads(activity.metadata)
            except:
                metadata = None
        
        recent_activities.append(RecentActivityResponse(
            id=activity.id,
            activity_type=activity.activity_type,
            resource_type=activity.resource_type,
            resource_id=activity.resource_id,
            resource_name=activity.resource_name,
            description=activity.description,
            ip_address=activity.ip_address,
            user_agent=activity.user_agent,
            metadata=metadata,
            timestamp=activity.timestamp
        ))
    
    return DashboardActivitySummary(
        period=f"Last {days} days",
        total_activities=len(activities),
        activities_by_type=activities_by_type,
        recent_activities=recent_activities
    )

@router.get("/email-events", response_model=EmailEventSummary)
async def get_email_events_summary(
    days: int = 7,
    current_user = Depends(get_current_user)
):
    """Get comprehensive email events summary"""
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get user's campaigns
    campaigns = db(db.campaigns.user_id == current_user.id).select()
    campaign_ids = [campaign.id for campaign in campaigns]
    
    if not campaign_ids:
        return EmailEventSummary(
            total_events=0,
            events_by_type={},
            events_by_campaign={},
            recent_events=[]
        )
    
    # Get email events
    events = db(
        (db.email_events.campaign_id.belongs(campaign_ids)) &
        (db.email_events.timestamp >= start_date) &
        (db.email_events.timestamp <= end_date)
    ).select(
        db.email_events.ALL,
        db.campaigns.name
    )
    
    # Count events by type
    events_by_type = {}
    events_by_campaign = {}
    
    recent_events = []
    for event in events:
        # Count by type
        event_type = event.email_events.event_type
        events_by_type[event_type] = events_by_type.get(event_type, 0) + 1
        
        # Count by campaign
        campaign_name = event.campaigns.name
        events_by_campaign[campaign_name] = events_by_campaign.get(campaign_name, 0) + 1
        
        # Add to recent events
        event_data = None
        if event.email_events.event_data:
            try:
                event_data = json.loads(event.email_events.event_data)
            except:
                event_data = None
        
        recent_events.append({
            "campaign_name": campaign_name,
            "event_type": event_type,
            "timestamp": event.email_events.timestamp.isoformat(),
            "event_data": event_data
        })
    
    return EmailEventSummary(
        total_events=len(events),
        events_by_type=events_by_type,
        events_by_campaign=events_by_campaign,
        recent_events=recent_events
    )

@router.get("/activity-breakdown")
async def get_activity_breakdown(
    days: int = 30,
    current_user = Depends(get_current_user)
):
    """Get detailed activity breakdown by type and date"""
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get activities
    activities = db(
        (db.user_activities.user_id == current_user.id) &
        (db.user_activities.timestamp >= start_date) &
        (db.user_activities.timestamp <= end_date)
    ).select()
    
    # Group by activity type
    activity_breakdown = {}
    for activity in activities:
        activity_type = activity.activity_type
        if activity_type not in activity_breakdown:
            activity_breakdown[activity_type] = {
                "count": 0,
                "resources": {},
                "timeline": {}
            }
        
        activity_breakdown[activity_type]["count"] += 1
        
        # Group by resource type
        resource_type = activity.resource_type or "general"
        if resource_type not in activity_breakdown[activity_type]["resources"]:
            activity_breakdown[activity_type]["resources"][resource_type] = 0
        activity_breakdown[activity_type]["resources"][resource_type] += 1
        
        # Group by date
        date_key = activity.timestamp.strftime("%Y-%m-%d")
        if date_key not in activity_breakdown[activity_type]["timeline"]:
            activity_breakdown[activity_type]["timeline"][date_key] = 0
        activity_breakdown[activity_type]["timeline"][date_key] += 1
    
    return {
        "period": f"Last {days} days",
        "total_activities": len(activities),
        "activity_breakdown": activity_breakdown
    }

@router.get("/campaign-performance")
async def get_campaign_performance_summary(current_user = Depends(get_current_user)):
    """Get campaign performance summary for dashboard"""
    
    # Get all campaigns
    campaigns = db(db.campaigns.user_id == current_user.id).select()
    
    campaign_performance = []
    for campaign in campaigns:
        # Get campaign results
        results = db(db.campaign_results.campaign_id == campaign.id).select()
        
        # Calculate metrics
        total_targets = len(results)
        emails_sent = len([r for r in results if r.email_sent])
        emails_opened = len([r for r in results if r.email_opened])
        links_clicked = len([r for r in results if r.link_clicked])
        forms_submitted = len([r for r in results if r.form_submitted])
        credentials_captured = len([r for r in results if r.credentials_captured])
        
        # Calculate rates
        open_rate = (emails_opened / emails_sent * 100) if emails_sent > 0 else 0.0
        click_rate = (links_clicked / emails_sent * 100) if emails_sent > 0 else 0.0
        submission_rate = (forms_submitted / emails_sent * 100) if emails_sent > 0 else 0.0
        capture_rate = (credentials_captured / emails_sent * 100) if emails_sent > 0 else 0.0
        
        campaign_performance.append({
            "campaign_id": campaign.id,
            "campaign_name": campaign.name,
            "status": campaign.status,
            "total_targets": total_targets,
            "emails_sent": emails_sent,
            "emails_opened": emails_opened,
            "links_clicked": links_clicked,
            "forms_submitted": forms_submitted,
            "credentials_captured": credentials_captured,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "submission_rate": round(submission_rate, 2),
            "capture_rate": round(capture_rate, 2),
            "created_at": campaign.created_at.isoformat(),
            "updated_at": campaign.updated_at.isoformat()
        })
    
    return {
        "total_campaigns": len(campaigns),
        "campaigns": campaign_performance
    }

@router.get("/quick-stats")
async def get_quick_stats(current_user = Depends(get_current_user)):
    """Get quick stats for dashboard widgets"""
    
    # Get counts for different resources
    campaigns_count = db(db.campaigns.user_id == current_user.id).count()
    targets_count = db(db.targets.user_id == current_user.id).count()
    templates_count = db(db.email_templates.user_id == current_user.id).count()
    phishlets_count = db(db.phishlets.user_id == current_user.id).count()
    
    # Get recent activity count (last 24 hours)
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_activities_count = db(
        (db.user_activities.user_id == current_user.id) &
        (db.user_activities.timestamp >= yesterday)
    ).count()
    
    # Get email events count (last 24 hours)
    recent_email_events_count = 0
    if campaigns_count > 0:
        campaign_ids = [c.id for c in db(db.campaigns.user_id == current_user.id).select()]
        recent_email_events_count = db(
            (db.email_events.campaign_id.belongs(campaign_ids)) &
            (db.email_events.timestamp >= yesterday)
        ).count()
    
    return {
        "campaigns": campaigns_count,
        "targets": targets_count,
        "templates": templates_count,
        "phishlets": phishlets_count,
        "recent_activities": recent_activities_count,
        "recent_email_events": recent_email_events_count
    }

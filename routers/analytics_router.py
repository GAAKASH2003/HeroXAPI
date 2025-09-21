from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from database import db
from auth import get_current_user
import json

router = APIRouter()


# Pydantic models
class DashboardStats(BaseModel):
    total_campaigns: int
    active_campaigns: int
    total_targets: int
    total_templates: int
    total_phishlets: int
    total_sender_profiles: int
    total_emails_sent: int
    total_emails_opened: int
    total_clicks: int
    total_form_submissions: int
    success_rate: float
    recent_activity_count: int

class CampaignStats(BaseModel):
    campaign_id: int
    campaign_name: str
    status: str
    total_targets: int
    emails_sent: int
    emails_opened: int
    clicks: int
    form_submissions: int
    success_rate: float
    created_at: datetime

class ActivityLog(BaseModel):
    id: int
    activity_type: str
    resource_type: Optional[str]
    resource_name: Optional[str]
    description: str
    timestamp: datetime

class TimeSeriesData(BaseModel):
    date: str
    emails_sent: int
    emails_opened: int
    clicks: int
    form_submissions: int

class TargetPerformance(BaseModel):
    target_id: int
    target_name: str
    target_email: str
    campaigns_participated: int
    emails_received: int
    emails_opened: int
    clicks: int
    form_submissions: int
    risk_score: float

@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(current_user = Depends(get_current_user)):
    """Get comprehensive dashboard statistics"""
    
    try:
        # Get counts from various tables
        total_campaigns = db(db.campaigns.user_id == current_user.id).count()
        if(current_user.is_admin):
            total_campaigns = db(db.campaigns).count()
        # Fix the status query - use OR condition instead of in_
        active_campaigns = db((db.campaigns.user_id == current_user.id)|(current_user.is_admin) & 
                             ((db.campaigns.status == 'running') | (db.campaigns.status == 'scheduled'))).count()
        
        
        total_targets = db(db.targets.user_id == current_user.id).count()
        if(current_user.is_admin):
            total_targets = db(db.targets).count()
        total_templates = db(db.email_templates.user_id == current_user.id).count()
        if(current_user.is_admin):
            total_templates = db(db.email_templates).count()
        total_phishlets = db(db.phishlets.user_id == current_user.id).count()
        if(current_user.is_admin):
            total_phishlets = db(db.phishlets).count()
        total_sender_profiles = db(db.sender_profiles.user_id == current_user.id).count()
        if(current_user.is_admin):
            total_sender_profiles = db(db.sender_profiles).count()

        # Get campaign results statistics
        campaign_ids = [c.id for c in db((db.campaigns.user_id == current_user.id)|(current_user.is_admin)).select(db.campaigns.id)]
        
        if campaign_ids:
            total_emails_sent = db(db.campaign_results.campaign_id.belongs(campaign_ids) & 
                                 (db.campaign_results.email_sent == True)).count()
            total_emails_opened = db(db.campaign_results.campaign_id.belongs(campaign_ids) & 
                                   (db.campaign_results.email_opened == True)).count()
            total_clicks = db(db.campaign_results.campaign_id.belongs(campaign_ids) & 
                            (db.campaign_results.link_clicked == True)).count()
            total_form_submissions = db(db.campaign_results.campaign_id.belongs(campaign_ids) & 
                                      (db.campaign_results.form_submitted == True)).count()
        else:
            total_emails_sent = 0
            total_emails_opened = 0
            total_clicks = 0
            total_form_submissions = 0
        
        # Calculate success rate
        if total_emails_sent > 0:
            success_rate = (total_form_submissions / total_emails_sent) * 100
        else:
            success_rate = 0.0
        
        # Get recent activity count (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_activity_count = db((db.user_activities.user_id == current_user.id) & 
                                  (db.user_activities.timestamp >= week_ago)).count()
        
        return DashboardStats(
            total_campaigns=total_campaigns,
            active_campaigns=active_campaigns,
            total_targets=total_targets,
            total_templates=total_templates,
            total_phishlets=total_phishlets,
            total_sender_profiles=total_sender_profiles,
            total_emails_sent=total_emails_sent,
            total_emails_opened=total_emails_opened,
            total_clicks=total_clicks,
            total_form_submissions=total_form_submissions,
            success_rate=round(success_rate, 2),
            recent_activity_count=recent_activity_count
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dashboard stats: {str(e)}"
        )

@router.get("/campaigns", response_model=List[CampaignStats])
async def get_campaign_stats(current_user = Depends(get_current_user)):
    """Get statistics for all campaigns"""
    
    try:
        campaigns = db(db.campaigns.user_id == current_user.id).select()
        if(current_user.is_admin):
             campaigns = db().select(db.campaigns.ALL)
        campaign_stats = []
        
        for campaign in campaigns:
            # Get results for this campaign
            results = db(db.campaign_results.campaign_id == campaign.id).select()
            
            total_targets = len(results)
            emails_sent = len([r for r in results if r.email_sent])
            emails_opened = len([r for r in results if r.email_opened])
            clicks = len([r for r in results if r.link_clicked])
            form_submissions = len([r for r in results if r.form_submitted])
            
            # Calculate success rate
            if emails_sent > 0:
                success_rate = (form_submissions / emails_sent) * 100
            else:
                success_rate = 0.0
            
            campaign_stats.append(CampaignStats(
                campaign_id=campaign.id,
                campaign_name=campaign.name,
                status=campaign.status,
                total_targets=total_targets,
                emails_sent=emails_sent,
                emails_opened=emails_opened,
                clicks=clicks,
                form_submissions=form_submissions,
                success_rate=round(success_rate, 2),
                created_at=campaign.created_at
            ))
        
        return campaign_stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign stats: {str(e)}"
        )

@router.get("/campaigns/{campaign_id}", response_model=Dict[str, Any])
async def get_campaign_detail_stats(
    campaign_id: int,
    current_user = Depends(get_current_user)
):
    """Get detailed statistics for a specific campaign"""
    
    try:
        # Verify campaign belongs to user
        campaign = db((db.campaigns.id == campaign_id) & 
                     (db.campaigns.user_id == current_user.id)).select().first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Get all results for this campaign
        results = db(db.campaign_results.campaign_id == campaign_id).select()
        
        # Calculate statistics
        total_targets = len(results)
        emails_sent = len([r for r in results if r.email_sent])
        emails_opened = len([r for r in results if r.email_opened])
        clicks = len([r for r in results if r.link_clicked])
        form_submissions = len([r for r in results if r.form_submitted])
        credentials_captured = len([r for r in results if r.credentials_captured])
        
        # Calculate rates
        open_rate = (emails_opened / emails_sent * 100) if emails_sent > 0 else 0
        click_rate = (clicks / emails_sent * 100) if emails_sent > 0 else 0
        submission_rate = (form_submissions / emails_sent * 100) if emails_sent > 0 else 0
        
        # Get time series data (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        daily_stats = {}
        
        for result in results:
            if result.email_sent_at and result.email_sent_at >= thirty_days_ago:
                date_str = result.email_sent_at.strftime('%Y-%m-%d')
                if date_str not in daily_stats:
                    daily_stats[date_str] = {
                        'emails_sent': 0,
                        'emails_opened': 0,
                        'clicks': 0,
                        'form_submissions': 0
                    }
                
                daily_stats[date_str]['emails_sent'] += 1
                if result.email_opened:
                    daily_stats[date_str]['emails_opened'] += 1
                if result.link_clicked:
                    daily_stats[date_str]['clicks'] += 1
                if result.form_submitted:
                    daily_stats[date_str]['form_submissions'] += 1
        
        return {
            'campaign': {
                'id': campaign.id,
                'name': campaign.name,
                'status': campaign.status,
                'created_at': campaign.created_at
            },
            'statistics': {
                'total_targets': total_targets,
                'emails_sent': emails_sent,
                'emails_opened': emails_opened,
                'clicks': clicks,
                'form_submissions': form_submissions,
                'credentials_captured': credentials_captured,
                'open_rate': round(open_rate, 2),
                'click_rate': round(click_rate, 2),
                'submission_rate': round(submission_rate, 2)
            },
            'daily_stats': daily_stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get campaign detail stats: {str(e)}"
        )

@router.get("/activity", response_model=List[ActivityLog])
async def get_activity_log(
    limit: int = 50,
    offset: int = 0,
    current_user = Depends(get_current_user)
):
    """Get user activity log"""
    
    try:
        #  replaced db.user.is_admin with db.users.is_admin
        admin_list = [row.id for row in db(db.users.is_admin == True).select(db.users.id)]
        # print('Admin List:', admin_list)
        if current_user.id in admin_list:
            query = (db.user_activities.user_id == current_user.id)
        else:
    # Show current user's + all admin activities
            query = (db.user_activities.user_id == current_user.id) | (db.user_activities.user_id.belongs(admin_list))

# Now fetch combined activities in a single query
        activities = db(query).select(
             orderby=~db.user_activities.timestamp,
             limitby=(offset, offset + limit)
         )
        return [
            ActivityLog(
                id=activity.id,
                activity_type=activity.activity_type,
                resource_type=activity.resource_type,
                resource_name=activity.resource_name,
                description=activity.description,
                timestamp=activity.timestamp
            )
            for activity in activities
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity log: {str(e)}"
        )

@router.get("/targets/performance", response_model=List[TargetPerformance])
async def get_target_performance(current_user = Depends(get_current_user)):
    """Get performance statistics for all targets"""
    
    try:
        targets = db((db.targets.user_id == current_user.id)|(current_user.is_admin)).select()
        target_performance = []
        
        for target in targets:
            # Get all campaign results for this target
            results = db(db.campaign_results.target_id == target.id).select()
            
            campaigns_participated = len(set(r.campaign_id for r in results))
            emails_received = len([r for r in results if r.email_sent])
            emails_opened = len([r for r in results if r.email_opened])
            clicks = len([r for r in results if r.link_clicked])
            form_submissions = len([r for r in results if r.form_submitted])
            
            # Calculate risk score (higher score = higher risk)
            if emails_received > 0:
                open_rate = emails_opened / emails_received
                click_rate = clicks / emails_received
                submission_rate = form_submissions / emails_received
                risk_score = (open_rate * 0.3 + click_rate * 0.4 + submission_rate * 0.3) * 100
            else:
                risk_score = 0.0
            
            target_performance.append(TargetPerformance(
                target_id=target.id,
                target_name=f"{target.first_name or ''} {target.last_name or ''}".strip() or target.email,
                target_email=target.email,
                campaigns_participated=campaigns_participated,
                emails_received=emails_received,
                emails_opened=emails_opened,
                clicks=clicks,
                form_submissions=form_submissions,
                risk_score=round(risk_score, 2)
            ))
        
        # Sort by risk score (highest first)
        target_performance.sort(key=lambda x: x.risk_score, reverse=True)
        return target_performance
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get target performance: {str(e)}"
        )

@router.get("/timeseries", response_model=List[TimeSeriesData])
async def get_time_series_data(
    days: int = 30,
    current_user = Depends(get_current_user)
):
    """Get time series data for analytics charts"""
    
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get campaign IDs for this user
        campaign_ids = [c.id for c in db((db.campaigns.user_id == current_user.id)|(current_user.is_admin)).select(db.campaigns.id)]

        if not campaign_ids:
            return []
        
        # Get results within date range
        results = db((db.campaign_results.campaign_id.belongs(campaign_ids)) & 
                    (db.campaign_results.email_sent_at >= start_date)).select()
        
        # Group by date
        daily_stats = {}
        
        for result in results:
            date_str = result.email_sent_at.strftime('%Y-%m-%d')
            if date_str not in daily_stats:
                daily_stats[date_str] = {
                    'emails_sent': 0,
                    'emails_opened': 0,
                    'clicks': 0,
                    'form_submissions': 0
                }
            
            daily_stats[date_str]['emails_sent'] += 1
            if result.email_opened:
                daily_stats[date_str]['emails_opened'] += 1
            if result.link_clicked:
                daily_stats[date_str]['clicks'] += 1
            if result.form_submitted:
                daily_stats[date_str]['form_submissions'] += 1
        
        # Convert to list format
        time_series_data = []
        for date_str, stats in daily_stats.items():
            time_series_data.append(TimeSeriesData(
                date=date_str,
                emails_sent=stats['emails_sent'],
                emails_opened=stats['emails_opened'],
                clicks=stats['clicks'],
                form_submissions=stats['form_submissions']
            ))
        
        # Sort by date
        time_series_data.sort(key=lambda x: x.date)
        return time_series_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get time series data: {str(e)}"
        )

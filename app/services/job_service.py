import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.job import Job, JobStatus
from app.models.meeting import Meeting
from .base_service import BaseService

logging = logging.getLogger(__name__)


class JobService(BaseService):
    """
    Service class for all job-related database operations and processing workflows.
    """
    model = Job
    
    @classmethod
    def create_job(cls, meeting_id: str, s3_audio_url: str, **kwargs) -> Job:
        """
        Create a new job for processing a meeting.
        
        Args:
            meeting_id: Meeting UUID this job processes
            s3_audio_url: S3 URL of the audio file
            **kwargs: Additional job fields
            
        Returns:
            Created Job instance
        """
        try:
            job_data = {
                'meeting_id': meeting_id,
                's3_audio_url': s3_audio_url,
                'status': kwargs.get('status', JobStatus.INIT),
                'start_time': kwargs.get('start_time', datetime.now(ZoneInfo("Asia/Kolkata"))),
                **kwargs
            }
            
            job = cls.create(**job_data)
            logging.info(f"Created job for meeting {meeting_id} with ID: {job.id}")
            return job
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to create job for meeting {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def get_by_meeting(cls, meeting_id: str) -> Optional[Job]:
        """
        Get job by its associated meeting ID.
        
        Args:
            meeting_id: Meeting UUID
            
        Returns:
            Job instance or None if not found
        """
        return cls.get_by_field('meeting_id', meeting_id)
    
    @classmethod
    def get_running_jobs(cls) -> List[Job]:
        """
        Get all currently running jobs.
        
        Returns:
            List of Job instances with IN_PROGRESS status
        """
        try:
            jobs = cls.model.query.filter_by(status=JobStatus.IN_PROGRESS).all()
            logging.info(f"Found {len(jobs)} running jobs")
            return jobs
        except SQLAlchemyError as e:
            logging.error(f"Failed to get running jobs: {str(e)}")
            raise
    
    @classmethod
    def get_pending_jobs(cls) -> List[Job]:
        """
        Get all pending jobs (INIT status).
        
        Returns:
            List of Job instances with INIT status
        """
        try:
            jobs = cls.model.query.filter_by(status=JobStatus.INIT).all()
            logging.info(f"Found {len(jobs)} pending jobs")
            return jobs
        except SQLAlchemyError as e:
            logging.error(f"Failed to get pending jobs: {str(e)}")
            raise
    
    @classmethod
    def get_failed_jobs(cls) -> List[Job]:
        """
        Get all failed jobs.
        
        Returns:
            List of Job instances with FAILURE status
        """
        try:
            jobs = cls.model.query.filter_by(status=JobStatus.FAILURE).all()
            logging.info(f"Found {len(jobs)} failed jobs")
            return jobs
        except SQLAlchemyError as e:
            logging.error(f"Failed to get failed jobs: {str(e)}")
            raise
    
    @classmethod
    def mark_in_progress(cls, job_id: str) -> Optional[Job]:
        """
        Mark a job as in progress.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Updated Job instance or None if not found
        """
        try:
            job = cls.update(
                job_id, 
                status=JobStatus.IN_PROGRESS,
                start_time=datetime.now(ZoneInfo("Asia/Kolkata"))
            )
            if job:
                logging.info(f"Marked job {job_id} as in progress")
            return job
        except SQLAlchemyError as e:
            logging.error(f"Failed to mark job {job_id} as in progress: {str(e)}")
            raise
    
    @classmethod
    def mark_completed(cls, job_id: str, **completion_data) -> Optional[Job]:
        """
        Mark a job as completed with optional completion data.
        
        Args:
            job_id: Job UUID
            **completion_data: Additional data to store on completion
            
        Returns:
            Updated Job instance or None if not found
        """
        try:
            update_data = {
                'status': JobStatus.COMPLETED,
                'end_time': datetime.now(ZoneInfo("Asia/Kolkata")),
                **completion_data
            }
            
            job = cls.update(job_id, **update_data)
            if job:
                logging.info(f"Marked job {job_id} as completed")
            return job
        except SQLAlchemyError as e:
            logging.error(f"Failed to mark job {job_id} as completed: {str(e)}")
            raise
    
    @classmethod
    def mark_failed(cls, job_id: str, error_message: str = None) -> Optional[Job]:
        """
        Mark a job as failed with optional error message.
        
        Args:
            job_id: Job UUID
            error_message: Optional error message to store
            
        Returns:
            Updated Job instance or None if not found
        """
        try:
            update_data = {
                'status': JobStatus.FAILURE,
                'end_time': datetime.now(ZoneInfo("Asia/Kolkata"))
            }
            
            if error_message:
                # Store error message in a field if the model has one
                # This would require adding an error_message field to the Job model
                pass  # For now, just log it
                
            job = cls.update(job_id, **update_data)
            if job:
                logging.error(f"Marked job {job_id} as failed: {error_message}")
            return job
        except SQLAlchemyError as e:
            logging.error(f"Failed to mark job {job_id} as failed: {str(e)}")
            raise
    
    @classmethod
    def update_status(cls, job_id: str, status: JobStatus) -> Optional[Job]:
        """
        Update job status.
        
        Args:
            job_id: Job UUID
            status: New JobStatus
            
        Returns:
            Updated Job instance or None if not found
        """
        try:
            update_data = {'status': status}
            
            # Set end_time for terminal states
            if status in [JobStatus.COMPLETED, JobStatus.FAILURE]:
                update_data['end_time'] = datetime.now(ZoneInfo("Asia/Kolkata"))
            # Set start_time for in-progress state
            elif status == JobStatus.IN_PROGRESS:
                update_data['start_time'] = datetime.now(ZoneInfo("Asia/Kolkata"))
            
            job = cls.update(job_id, **update_data)
            if job:
                logging.info(f"Updated job {job_id} status to {status.value}")
            return job
        except SQLAlchemyError as e:
            logging.error(f"Failed to update job {job_id} status: {str(e)}")
            raise
    
    @classmethod
    def get_job_with_meeting(cls, job_id: str) -> Optional[Job]:
        """
        Get job with its associated meeting.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Job instance with meeting relationship loaded
        """
        try:
            job = cls.model.query.filter_by(id=job_id).first()
            if job:
                # Accessing meeting attribute loads the relationship
                _ = job.meeting
                logging.info(f"Found job with meeting: {job_id}")
            else:
                logging.warning(f"Job not found: {job_id}")
            return job
        except SQLAlchemyError as e:
            logging.error(f"Failed to get job with meeting {job_id}: {str(e)}")
            raise
    
    @classmethod
    def get_jobs_by_status(cls, status: JobStatus, limit: int = None) -> List[Job]:
        """
        Get jobs by status with optional limit.
        
        Args:
            status: JobStatus to filter by
            limit: Optional limit on number of results
            
        Returns:
            List of Job instances
        """
        try:
            query = cls.model.query.filter_by(status=status).order_by(cls.model.start_time.desc())
            
            if limit:
                query = query.limit(limit)
                
            jobs = query.all()
            logging.info(f"Found {len(jobs)} jobs with status {status.value}")
            return jobs
        except SQLAlchemyError as e:
            logging.error(f"Failed to get jobs by status {status.value}: {str(e)}")
            raise
    
    @classmethod
    def get_jobs_for_meeting_ids(cls, meeting_ids: List[str]) -> List[Job]:
        """
        Get jobs for multiple meeting IDs.
        
        Args:
            meeting_ids: List of meeting UUIDs
            
        Returns:
            List of Job instances
        """
        try:
            jobs = cls.model.query.filter(cls.model.meeting_id.in_(meeting_ids)).all()
            logging.info(f"Found {len(jobs)} jobs for {len(meeting_ids)} meetings")
            return jobs
        except SQLAlchemyError as e:
            logging.error(f"Failed to get jobs for meeting IDs: {str(e)}")
            raise
    
    @classmethod
    def get_job_statistics(cls, date_range: Dict[str, datetime] = None) -> Dict[str, Any]:
        """
        Get job processing statistics.
        
        Args:
            date_range: Optional date range filter
            
        Returns:
            Dictionary with job statistics
        """
        try:
            query = cls.model.query
            
            if date_range:
                query = query.filter(
                    cls.model.start_time >= date_range['start'],
                    cls.model.start_time <= date_range['end']
                )
            
            jobs = query.all()
            
            # Calculate statistics
            total_jobs = len(jobs)
            completed_jobs = len([j for j in jobs if j.status == JobStatus.COMPLETED])
            failed_jobs = len([j for j in jobs if j.status == JobStatus.FAILURE])
            in_progress_jobs = len([j for j in jobs if j.status == JobStatus.IN_PROGRESS])
            pending_jobs = len([j for j in jobs if j.status == JobStatus.INIT])
            
            # Calculate average processing time for completed jobs
            completed_with_times = [j for j in jobs if j.status == JobStatus.COMPLETED and j.start_time and j.end_time]
            avg_processing_time = None
            if completed_with_times:
                total_seconds = sum([(j.end_time - j.start_time).total_seconds() for j in completed_with_times])
                avg_processing_time = total_seconds / len(completed_with_times)
            
            statistics = {
                'total_jobs': total_jobs,
                'completed_jobs': completed_jobs,
                'failed_jobs': failed_jobs,
                'in_progress_jobs': in_progress_jobs,
                'pending_jobs': pending_jobs,
                'success_rate': (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                'failure_rate': (failed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                'average_processing_time_seconds': avg_processing_time
            }
            
            logging.info(f"Generated job statistics: {statistics}")
            return statistics
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to get job statistics: {str(e)}")
            raise
    
    @classmethod
    def retry_failed_job(cls, job_id: str) -> Optional[Job]:
        """
        Reset a failed job to INIT status for retry.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Updated Job instance or None if not found
        """
        try:
            job = cls.get_by_id(job_id)
            if not job:
                return None
                
            if job.status != JobStatus.FAILURE:
                logging.warning(f"Job {job_id} is not in failed state, cannot retry")
                return job
                
            job = cls.update(
                job_id,
                status=JobStatus.INIT,
                end_time=None  # Clear end time for retry
            )
            
            if job:
                logging.info(f"Reset job {job_id} for retry")
            return job
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to retry job {job_id}: {str(e)}")
            raise
    
    @classmethod
    def cleanup_old_completed_jobs(cls, days_old: int = 30) -> int:
        """
        Clean up old completed jobs older than specified days.
        
        Args:
            days_old: Number of days to keep completed jobs
            
        Returns:
            Number of jobs deleted
        """
        try:
            cutoff_date = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(days=days_old)
            
            old_jobs = cls.model.query.filter(
                cls.model.status == JobStatus.COMPLETED,
                cls.model.end_time < cutoff_date
            ).all()
            
            count = len(old_jobs)
            for job in old_jobs:
                db.session.delete(job)
            
            logging.info(f"Cleaned up {count} old completed jobs")
            return count
            
        except SQLAlchemyError as e:
            logging.error(f"Failed to cleanup old jobs: {str(e)}")
            raise 
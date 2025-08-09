import logging
from typing import Optional, Dict, Any
from datetime import datetime, date
from zoneinfo import ZoneInfo
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import and_

from app import db
from app.models.call_performance import CallPerformance
from app.models.meeting import Meeting
from app.models.seller import Seller
from .base_service import BaseService

logging = logging.getLogger(__name__)


class CallPerformanceService(BaseService):
    """
    Service class for all call performance-related database operations and business logic.
    """
    model = CallPerformance
    
    @classmethod
    def create_or_update_call_performance(cls, meeting_id: str, performance_data: Dict[str, Any]) -> CallPerformance:
        """
        Create or update call performance metrics for a meeting.
        
        Args:
            meeting_id: UUID of the meeting
            performance_data: Dictionary containing performance metrics
            
        Returns:
            The created or updated CallPerformance instance
            
        Raises:
            ValueError: If validation fails
            SQLAlchemyError: If database operation fails
        """
        try:
            # Validate that meeting exists
            meeting = Meeting.query.get(meeting_id)
            if not meeting:
                raise ValueError(f"Meeting with ID {meeting_id} not found")
            
            # Validate performance data
            validated_data = cls._validate_performance_data(performance_data)
            
            # Check if call performance already exists
            existing_performance = CallPerformance.query.filter_by(meeting_id=meeting_id).first()
            
            if existing_performance:
                # Update existing record
                for metric, value in validated_data.items():
                    if hasattr(existing_performance, metric):
                        setattr(existing_performance, metric, value)
                
                # Update timestamps
                existing_performance.updated_at = datetime.now(ZoneInfo("Asia/Kolkata"))
                if 'analyzed_at' in performance_data:
                    existing_performance.analyzed_at = performance_data['analyzed_at']
                
                # Recalculate overall score
                existing_performance.calculate_overall_score()
                
                db.session.commit()
                logging.info(f"Updated CallPerformance for meeting ID: {meeting_id}")
                return existing_performance
            else:
                # Create new record
                validated_data['meeting_id'] = meeting_id
                
                # Set analyzed_at if provided, otherwise use current time
                if 'analyzed_at' not in validated_data:
                    validated_data['analyzed_at'] = datetime.now(ZoneInfo("Asia/Kolkata"))
                
                instance = CallPerformance(**validated_data)
                instance.calculate_overall_score()
                
                db.session.add(instance)
                db.session.commit()
                logging.info(f"Created CallPerformance for meeting ID: {meeting_id}")
                return instance
                
        except SQLAlchemyError as e:
            logging.error(f"Database error in create_or_update_call_performance: {str(e)}")
            db.session.rollback()
            raise
        except Exception as e:
            logging.error(f"Error in create_or_update_call_performance: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def get_by_meeting_id(cls, meeting_id: str) -> Optional[CallPerformance]:
        """
        Get call performance by meeting ID.
        
        Args:
            meeting_id: UUID of the meeting
            
        Returns:
            CallPerformance instance or None if not found
        """
        try:
            performance = CallPerformance.query.filter_by(meeting_id=meeting_id).first()
            if performance:
                logging.info(f"Found CallPerformance for meeting ID: {meeting_id}")
            else:
                logging.warning(f"CallPerformance not found for meeting ID: {meeting_id}")
            return performance
        except SQLAlchemyError as e:
            logging.error(f"Failed to get CallPerformance by meeting ID {meeting_id}: {str(e)}")
            raise
    
    @classmethod
    def delete_by_meeting_id(cls, meeting_id: str) -> bool:
        """
        Delete call performance by meeting ID.
        
        Args:
            meeting_id: UUID of the meeting
            
        Returns:
            True if deleted, False if not found
        """
        try:
            performance = CallPerformance.query.filter_by(meeting_id=meeting_id).first()
            if performance:
                db.session.delete(performance)
                db.session.commit()
                logging.info(f"Deleted CallPerformance for meeting ID: {meeting_id}")
                return True
            else:
                logging.warning(f"CallPerformance not found for meeting ID: {meeting_id}")
                return False
        except SQLAlchemyError as e:
            logging.error(f"Failed to delete CallPerformance for meeting ID {meeting_id}: {str(e)}")
            db.session.rollback()
            raise
    
    @classmethod
    def _validate_performance_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate performance metrics data.
        
        Args:
            data: Dictionary containing performance metrics
            
        Returns:
            Validated data dictionary
            
        Raises:
            ValueError: If validation fails
        """
        valid_metrics = [
            'intro', 'rapport_building', 'need_realization', 'script_adherance',
            'objection_handling', 'pricing_and_negotiation', 'closure_and_next_steps',
            'conversation_structure_and_flow'
        ]
        
        validated_data = {}
        
        for metric in valid_metrics:
            if metric in data and data[metric] is not None:
                metric_data = data[metric]
                validated_metric = cls._validate_metric_data(metric, metric_data)
                validated_data[metric] = validated_metric
        
        # Validate overall_score if provided
        if 'overall_score' in data:
            overall_score = data['overall_score']
            if overall_score is not None:
                try:
                    overall_score = float(overall_score)
                    if not (0 <= overall_score <= 10):
                        raise ValueError("Overall score must be between 0 and 10")
                    validated_data['overall_score'] = overall_score
                except (TypeError, ValueError):
                    raise ValueError("Overall score must be a valid number between 0 and 10")
        
        # Validate analyzed_at if provided
        if 'analyzed_at' in data:
            analyzed_at = data['analyzed_at']
            if analyzed_at:
                if isinstance(analyzed_at, str):
                    try:
                        analyzed_at = datetime.fromisoformat(analyzed_at.replace('Z', '+00:00'))
                        validated_data['analyzed_at'] = analyzed_at
                    except ValueError:
                        raise ValueError("analyzed_at must be a valid ISO datetime string")
                elif isinstance(analyzed_at, datetime):
                    validated_data['analyzed_at'] = analyzed_at
                else:
                    raise ValueError("analyzed_at must be a datetime or ISO string")
        
        return validated_data
    
    @classmethod
    def _validate_metric_data(cls, metric_name: str, metric_data: Any) -> Dict[str, Any]:
        """
        Validate individual metric data.
        
        Args:
            metric_name: Name of the metric
            metric_data: Data for the metric
            
        Returns:
            Validated metric data
            
        Raises:
            ValueError: If validation fails
        """
        if not isinstance(metric_data, dict):
            raise ValueError(f"{metric_name} must be a dictionary")
        
        required_fields = ['score']
        optional_fields = ['date', 'reason']
        
        validated_metric = {}
        
        # Validate required fields
        for field in required_fields:
            if field not in metric_data:
                raise ValueError(f"{metric_name} missing required field: {field}")
            
            if field == 'score':
                try:
                    score = float(metric_data[field])
                    if not (0 <= score <= 10):
                        raise ValueError(f"{metric_name} score must be between 0 and 10")
                    validated_metric[field] = score
                except (TypeError, ValueError):
                    raise ValueError(f"{metric_name} score must be a valid number between 0 and 10")
        
        # Validate optional fields
        for field in optional_fields:
            if field in metric_data and metric_data[field] is not None:
                if field == 'date':
                    date_value = metric_data[field]
                    if isinstance(date_value, str):
                        # Basic date validation - accept YYYY-MM-DD format
                        try:
                            datetime.strptime(date_value, '%Y-%m-%d')
                            validated_metric[field] = date_value
                        except ValueError:
                            raise ValueError(f"{metric_name} date must be in YYYY-MM-DD format")
                    else:
                        raise ValueError(f"{metric_name} date must be a string in YYYY-MM-DD format")
                elif field == 'reason':
                    if isinstance(metric_data[field], str):
                        validated_metric[field] = metric_data[field]
                    else:
                        raise ValueError(f"{metric_name} reason must be a string")
        
        return validated_metric
    
    @classmethod
    def get_performance_summary(cls, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of call performance metrics.
        
        Args:
            meeting_id: UUID of the meeting
            
        Returns:
            Dictionary containing performance summary or None if not found
        """
        performance = cls.get_by_meeting_id(meeting_id)
        if not performance:
            return None
        
        summary = {
            'meeting_id': str(performance.meeting_id),
            'overall_score': performance.overall_score,
            'analyzed_at': performance.analyzed_at.isoformat() if performance.analyzed_at else None,
            'metrics': {}
        }
        
        # Add individual metrics
        for metric in performance.get_metric_names():
            metric_data = getattr(performance, metric)
            if metric_data:
                summary['metrics'][metric] = metric_data
        
        return summary
    
    @classmethod
    def get_user_performance_metrics(cls, seller_id: str, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Get performance metrics for a user within a date range with daily averages.
        
        Args:
            seller_id: UUID of the seller
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            
        Returns:
            Dictionary containing daily metrics and period summary
            
        Raises:
            ValueError: If validation fails
            SQLAlchemyError: If database operation fails
        """
        try:
            from datetime import timedelta
            from sqlalchemy import and_, func
            
            # Validate that seller exists
            seller = db.session.query(Seller).get(seller_id)
            if not seller:
                raise ValueError(f"Seller with ID {seller_id} not found")
            
            # Initialize response structure
            daily_metrics = {}
            period_summary = {
                'total_calls': 0,
                'days_with_data': 0,
                'days_in_range': 0,
                'overall_averages': {}
            }
            
            # Calculate total days in range
            period_summary['days_in_range'] = (end_date - start_date).days + 1
            
            # Get all metric names
            metric_names = CallPerformance.get_metric_names()
            
            # Initialize accumulators for period averages
            period_totals = {metric: [] for metric in metric_names}
            period_totals['overall_score'] = []
            
            # Loop through each day in the date range
            current_date = start_date
            while current_date <= end_date:
                # Convert to datetime range for database query
                day_start = datetime.combine(current_date, datetime.min.time()).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                day_end = datetime.combine(current_date, datetime.max.time()).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                
                # Query call performances for this seller on this specific day
                call_performances = db.session.query(CallPerformance, Meeting).join(
                    Meeting, CallPerformance.meeting_id == Meeting.id
                ).filter(
                    Meeting.seller_id == seller_id,
                    Meeting.start_time.between(day_start, day_end)
                ).all()
                
                if call_performances:
                    # Calculate daily averages for each metric
                    daily_averages = {}
                    calls_count = len(call_performances)
                    
                    for metric in metric_names:
                        scores = []
                        for call_perf, meeting in call_performances:
                            metric_data = getattr(call_perf, metric)
                            if metric_data and isinstance(metric_data, dict) and 'score' in metric_data:
                                try:
                                    score = float(metric_data['score'])
                                    scores.append(score)
                                except (TypeError, ValueError):
                                    continue
                        
                        if scores:
                            avg_score = sum(scores) / len(scores)
                            daily_averages[metric] = round(avg_score, 2)
                            period_totals[metric].extend(scores)
                        else:
                            daily_averages[metric] = None
                    
                    # Calculate daily overall scores
                    overall_scores = []
                    for call_perf, meeting in call_performances:
                        if call_perf.overall_score is not None:
                            try:
                                overall_scores.append(float(call_perf.overall_score))
                            except (TypeError, ValueError):
                                continue
                    
                    if overall_scores:
                        daily_averages['overall_score'] = round(sum(overall_scores) / len(overall_scores), 2)
                        period_totals['overall_score'].extend(overall_scores)
                    else:
                        daily_averages['overall_score'] = None
                    
                    daily_averages['calls_count'] = calls_count
                    daily_metrics[current_date.strftime('%Y-%m-%d')] = daily_averages
                    
                    period_summary['total_calls'] += calls_count
                    period_summary['days_with_data'] += 1
                else:
                    # No calls on this day
                    daily_metrics[current_date.strftime('%Y-%m-%d')] = None
                
                current_date += timedelta(days=1)
            
            # Calculate period averages
            for metric in metric_names + ['overall_score']:
                if period_totals[metric]:
                    period_summary['overall_averages'][metric] = round(
                        sum(period_totals[metric]) / len(period_totals[metric]), 2
                    )
                else:
                    period_summary['overall_averages'][metric] = None
            
            return {
                'seller_id': seller_id,
                'seller_info': {
                    'name': seller.name,
                    'email': seller.email
                },
                'date_range': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d')
                },
                'daily_metrics': daily_metrics,
                'period_summary': period_summary
            }
            
        except SQLAlchemyError as e:
            logging.error(f"Database error in get_user_performance_metrics: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error in get_user_performance_metrics: {str(e)}")
            raise

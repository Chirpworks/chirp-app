import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.meeting import Meeting
from app.services.meeting_service import MeetingService
from sqlalchemy import func

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reindex_meetings(app):
    with app.app_context():
        logger.info("Starting to find meetings to re-index...")
        
        # Find meetings that have been analyzed (have qa_pairs and facts)
        meetings_to_reindex = Meeting.query.filter(
            Meeting.qa_pairs.isnot(None),
            Meeting.facts.isnot(None)
        ).all()

        if not meetings_to_reindex:
            logger.info("No meetings with new analysis data found to re-index.")
            return

        total_meetings = len(meetings_to_reindex)
        logger.info(f"Found {total_meetings} meetings to re-index.")

        for i, meeting in enumerate(meetings_to_reindex):
            try:
                logger.info(f"({i+1}/{total_meetings}) Re-indexing meeting {meeting.id}...")
                # This method contains all the logic for creating structured and nugget documents
                MeetingService._index_meeting_structured(meeting)
            except Exception as e:
                logger.error(f"Failed to re-index meeting {meeting.id}: {e}")
        
        logger.info("Completed re-indexing of analyzed meetings.")

if __name__ == "__main__":
    # Ensure SEMANTIC_INDEXING_ENABLED is set, otherwise indexing is skipped.
    if os.getenv('SEMANTIC_INDEXING_ENABLED', 'false').lower() != 'true':
        print("SEMANTIC_INDEXING_ENABLED is not set to 'true'. Skipping.")
        sys.exit(0)
    app = create_app()
    reindex_meetings(app)

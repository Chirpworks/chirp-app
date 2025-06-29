import traceback
from typing import Optional

import logging
import os
from datetime import datetime

from dotenv import load_dotenv

from app import Seller, Agency, db
from app.services.action_service import ActionService

from app.models.meeting import Meeting
from app.service.llm.open_ai.chat_gpt import OpenAIClient

# Load environment variables (for local dev or ECS fallback)
load_dotenv()

logging = logging.getLogger(__name__)


class CallAnalysis:
    def __init__(self, meeting):
        self.meeting = meeting
        self.open_ai_client = OpenAIClient()
        self.analytical_call_analysis: Optional[dict] = None
        self.descriptive_call_analysis: Optional[dict] = None
        self.agency: Optional[Agency] = None
        self.user: Optional[Seller] = None

    def get_previous_calls_context(self, meetings):
        text = "Call History Summary:\n"
        for i, meeting in enumerate(meetings):
            text += f"Call {i+1}:\n"
            text += f"{meeting.summary}\n\n"
        return text

    def analyze_meeting(self):
        try:
            self.user = Seller.query.filter_by(id=self.meeting.seller_id).first()
            if self.user:
                self.agency = Agency.query.filter_by(id=self.user.agency_id).first()

            self.process_analytical_prompt()
            self.process_descriptive_prompt()
            db.session.commit()
            logging.info("Meeting has been analysed successfully")
        except Exception as e:
            logging.error(f"Failed to analyze call for meeting with id: {self.meeting.id}")
            raise e

    def process_analytical_prompt(self):
        try:
            prompt_text = ''
            # Get meetings for this buyer-seller combination instead of deal
            related_meetings = Meeting.query.filter(
                Meeting.buyer_id == self.meeting.buyer_id,
                Meeting.seller_id == self.meeting.seller_id
            ).order_by(Meeting.start_time).all()

            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "analytical_prompt_v1_1.txt")

            with open(prompt_path, "r") as f:
                prompt_text = f.read()
                seller_name = str(self.user.name) if self.user and self.user.name else ''
                call_date = str(self.meeting.start_time.date()) if self.meeting.start_time else ''
                agency_name = str(self.agency.name) if self.agency and self.agency.name else ''
                agency_description = str(self.agency.description) if self.agency and self.agency.description else ''
                prompt_text = prompt_text.replace("<seller_name>", seller_name)
                prompt_text = prompt_text.replace("<call_date>", call_date)
                prompt_text = prompt_text.replace("<agency_name>", agency_name)
                prompt_text = prompt_text.replace("<agency_description>", agency_description)

                if len(related_meetings) > 1:
                    text = self.get_previous_calls_context(related_meetings[:-1])
                    if text:
                        prompt_text = prompt_text.replace("<additional_context>", text)
                if self.meeting.diarization:
                    prompt_text = prompt_text.replace("<call_transcript>", str(self.meeting.diarization))

            if not prompt_text:
                logging.error("Analytical prompt text not found. Failed to generate analysis")
                raise Exception("unable to generate prompt for this analysis")

            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            self.analytical_call_analysis = self.open_ai_client.send_prompt(prompt=prompt_text, model=model)
            if not self.analytical_call_analysis:
                logging.error(f"Failed to run analytical analysis as OpenAI returned empty response")
                return

            self.meeting.llm_analytical_response = self.analytical_call_analysis

            # Process actions from the analysis
            actions = self.analytical_call_analysis.get("actions")
            if actions and actions != ['Not Specified']:
                for act in actions:
                    action_name = act.get('action_name')
                    due_date = act.get('action_due_date') if (
                            act.get('action_due_date') != "Not Specified") else None
                    if due_date:
                        due_date = datetime.fromisoformat(due_date)
                    action_description = act.get("action_description")
                    action_reasoning = act.get("action_reasoning")
                    signals = act.get("action_signals")
                    
                    ActionService.create_action(
                        title=action_name,
                        meeting_id=self.meeting.id,
                        buyer_id=self.meeting.buyer_id,
                        seller_id=self.meeting.seller_id,
                        due_date=due_date,
                        description=action_description,
                        reasoning=action_reasoning,
                        signals=signals
                    )

            # Process suggested actions
            suggested_actions = self.analytical_call_analysis.get("suggested_actions")
            if suggested_actions and suggested_actions != ['Not Specified']:
                for act in suggested_actions:
                    action_name = act.get("suggested_action_name")
                    due_date = act.get("suggested_action_due_date")
                    if due_date:
                        due_date = datetime.fromisoformat(due_date)
                    action_description = act.get("suggested_action_description")
                    suggested_action_reason = act.get("suggested_action_reasoning")
                    reasoning = suggested_action_reason.get("reasoning") if suggested_action_reason else None
                    signals = suggested_action_reason.get("signals") if suggested_action_reason else None
                    
                    ActionService.create_action(
                        title=action_name,
                        meeting_id=self.meeting.id,
                        buyer_id=self.meeting.buyer_id,
                        seller_id=self.meeting.seller_id,
                        due_date=due_date,
                        description=action_description,
                        reasoning=reasoning,
                        signals=signals
                    )
            db.session.flush()
        except Exception as e:
            logging.error(f"Failed to run analytical analysis with error {e}: {traceback.format_exc()}")
            raise e

    def process_descriptive_prompt(self):
        try:
            prompt_text = ''
            # Get related meetings for this buyer-seller combination
            related_meetings = Meeting.query.filter(
                Meeting.buyer_id == self.meeting.buyer_id,
                Meeting.seller_id == self.meeting.seller_id
            ).order_by(Meeting.start_time).all()

            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "descriptive_prompt_v1_1.txt")

            with open(prompt_path, "r") as f:
                prompt_text = f.read()
                if not prompt_text:
                    logging.error("No descriptive prompt loaded")
                    raise Exception("No descriptive prompt found. Check file.")
                seller_name = str(self.user.name) if self.user and self.user.name else ''
                call_date = str(self.meeting.start_time.date()) if self.meeting.start_time else ''
                agency_name = str(self.agency.name) if self.agency and self.agency.name else ''
                agency_description = str(self.agency.description) if self.agency and self.agency.description else ''
                if prompt_text:
                    prompt_text = prompt_text.replace("<seller_name>", seller_name)
                    prompt_text = prompt_text.replace("<call_date>", call_date)
                    prompt_text = prompt_text.replace("<agency_name>", agency_name)
                    prompt_text = prompt_text.replace("<agency_description>", agency_description)

                if len(related_meetings) > 1:
                    text = self.get_previous_calls_context(related_meetings[:-1])
                    if text and prompt_text:
                        prompt_text = prompt_text.replace("<additional_context>", str(text))
                if self.meeting.diarization and prompt_text:
                    prompt_text = prompt_text.replace("<call_transcript>", str(self.meeting.diarization))

            if not prompt_text:
                logging.error("Descriptive Prompt text not generated. Failed to generate analysis")
                raise Exception("unable to generate prompt for this analysis")

            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            self.descriptive_call_analysis = self.open_ai_client.send_prompt(prompt=prompt_text, model=model)
            if not self.descriptive_call_analysis:
                logging.error(f"Failed to run descriptive analysis as OpenAI returned empty response")
                return

            self.meeting.llm_descriptive_response = self.descriptive_call_analysis
            db.session.flush()
        except Exception as e:
            logging.error(f"Failed to run descriptive analysis with error {e}: {traceback.format_exc()}")
            raise e

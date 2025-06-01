import json
from zoneinfo import ZoneInfo

import logging
import os
from datetime import datetime

from dotenv import load_dotenv

from app import User, Agency, Deal, Action, db
from app.models.action import ActionType

from app.models.meeting import Meeting, ProcessingStatus
from app.service.llm.open_ai.chat_gpt import OpenAIClient
from app.utils.call_recording_utils import denormalize_phone_number

# Load environment variables (for local dev or ECS fallback)
load_dotenv()

logging = logging.getLogger(__name__)


class CallAnalysis:
    def __init__(self, meeting):
        self.meeting = meeting
        self.open_ai_client = OpenAIClient()
        self.analytical_call_analysis = None
        self.descriptive_call_analysis = None
        self.deal = None
        self.agency = None
        self.user = None

    def get_previous_calls_context(self, meetings):
        text = "Call History Summary:\n"
        for i, meeting in enumerate(meetings):
            text += f"Call {i+1}:\n"
            text += f"{meeting.summary}\n\n"
        return text

    def analyze_meeting(self):
        try:
            seller_number = self.meeting.seller_number
            self.user = User.query.filter_by(phone=seller_number).first()
            self.agency = Agency.query.filter_by(id=self.user.agency_id).first()
            self.deal = Deal.query.filter_by(id=self.meeting.deal_id).first()

            self.process_analytical_prompt()
            self.process_descriptive_prompt()
            self.meeting.status = ProcessingStatus.COMPLETE
            db.session.commit()
            logging.info("Meeting has been analysed successfully")
        except Exception as e:
            logging.error(f"Failed to analyze call for meeting with id: {self.meeting.id}")
            raise e

    def process_analytical_prompt(self):
        try:
            prompt_text = ''
            deal_meetings = self.deal.meetings
            deal_meetings = sorted(deal_meetings, key=lambda x: x.start_time)

            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "analytical_prompt_v1_1.txt")

            with open(prompt_path, "r") as f:
                prompt_text = f.read()
                prompt_text = prompt_text.replace("<seller_name>", self.user.name)
                prompt_text = prompt_text.replace("<call_date>", str(self.meeting.start_time.date()))
                if self.agency.name:
                    prompt_text = prompt_text.replace("<agency_name>", self.agency.name)
                else:
                    prompt_text = prompt_text.replace("<agency_name>", '')
                if self.agency.description:
                    prompt_text = prompt_text.replace("<agency_description>", self.agency.description)
                else:
                    prompt_text = prompt_text.replace("<agency_description>", '')

                if len(deal_meetings) > 1:
                    text = self.get_previous_calls_context(deal_meetings[:-1])
                    prompt_text = prompt_text.replace("<additional_context>", text)
                prompt_text = prompt_text.replace("<call_transcript>", self.meeting.diarization)

            if not prompt_text:
                logging.error("Analytical prompt text not found. Failed to generate analysis")
                raise Exception("unable to generate prompt for this analysis")

            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            self.analytical_call_analysis = self.open_ai_client.send_prompt(prompt=prompt_text, model=model)
            if not self.analytical_call_analysis:
                logging.error(f"Failed to run analytical analysis as OpenAI returned empty response")
                return

            self.meeting.llm_analytical_response = self.analytical_call_analysis

            speaker_roles = self.analytical_call_analysis.get("speaker_roles")

            deal_stage = self.analytical_call_analysis.get("deal_stage")
            stage = deal_stage.get("deal_stage")
            if not stage or stage == 'Not Specified':
                if not self.deal.stage:
                    self.deal.stage = 'Discovery & Lead Qualification'
            else:
                self.deal.stage = stage
            stage_signals = deal_stage.get("stage_signals")
            if stage_signals != ['Not Specified']:
                self.deal.stage_signals = stage_signals
            stage_reasoning = deal_stage.get("stage_reasoning")
            if stage_reasoning != ['Not Specified']:
                self.deal.stage_reasoning = stage_reasoning

            focus_areas = self.analytical_call_analysis.get("focus_areas")
            if focus_areas != ['Not Specified']:
                self.deal.focus_areas = focus_areas

            risks = self.analytical_call_analysis.get("risks")
            if risks != "Not Specified":
                self.deal.risks = risks

            actions = self.analytical_call_analysis.get("actions")
            if actions != ['Not Specified']:
                for act in actions:
                    action_name = act.get('action_name')
                    due_date = act.get('action_due_date') if (
                            act.get('action_due_date') != "Not Specified") else None
                    if due_date:
                        due_date = datetime.fromisoformat(due_date)
                    action_description = act.get("action_description")
                    action_reasoning = act.get("action_reasoning")
                    signals = act.get("action_signals")
                    action = Action(
                        title=action_name,
                        due_date=due_date,
                        description=action_description,
                        reasoning=action_reasoning,
                        meeting_id=self.meeting.id,
                        type=ActionType.CONTEXTUAL_ACTION,
                        signals=signals,
                        created_at=datetime.now(ZoneInfo("Asia/Kolkata"))
                    )
                    db.session.add(action)

            actions = self.analytical_call_analysis.get("suggested_actions")
            if actions != ['Not Specified']:
                for act in actions:
                    action_name = act.get("suggested_action_name")
                    due_date = act.get("suggested_action_due_date")
                    due_date = datetime.fromisoformat(due_date)
                    action_description = act.get("suggested_action_description")
                    suggested_action_reason = act.get("suggested_action_reasoning")
                    reasoning = suggested_action_reason.get("reasoning")
                    signals = suggested_action_reason.get("signals")
                    action = Action(
                        title=action_name,
                        due_date=due_date,
                        description=action_description,
                        reasoning=reasoning,
                        signals=signals,
                        meeting_id=self.meeting.id,
                        type=ActionType.SUGGESTED_ACTION,
                        created_at=datetime.now(ZoneInfo("Asia/Kolkata"))
                    )
                    db.session.add(action)
            db.session.flush()
        except Exception as e:
            logging.error(f"Failed to run analytical analysis with error {e}")
            raise e

    def process_descriptive_prompt(self):
        try:
            prompt_text = ''
            deal_meetings = self.deal.meetings
            deal_meetings = sorted(deal_meetings, key=lambda x: x.start_time)

            base_dir = os.path.dirname(os.path.abspath(__file__))
            prompt_path = os.path.join(base_dir, "descriptive_prompt_v1_1.txt")

            with open(prompt_path, "r") as f:
                prompt_text = f.read()
                prompt_text = prompt_text.replace("<seller_name>", self.user.name)
                prompt_text = prompt_text.replace("<call_date>", str(self.meeting.start_time.date()))
                if self.agency.name:
                    prompt_text = prompt_text.replace("<agency_name>", self.agency.name)
                else:
                    prompt_text = prompt_text.replace("<agency_name>", '')
                if self.agency.description:
                    prompt_text = prompt_text.replace("<agency_description>", self.agency.description)
                else:
                    prompt_text = prompt_text.replace("<agency_description>", '')

                if len(deal_meetings) > 1:
                    text = self.get_previous_calls_context(deal_meetings[:-1])
                    prompt_text = prompt_text.replace("<additional_context>", text)
                prompt_text = prompt_text.replace("<call_transcript>", self.meeting.diarization)

            if not prompt_text:
                logging.error("Descriptive Prompt text not generated. Failed to generate analysis")
                raise Exception("unable to generate prompt for this analysis")

            model = os.getenv("OPENAI_MODEL", "gpt-4o")
            self.descriptive_call_analysis = self.open_ai_client.send_prompt(prompt=prompt_text, model=model)
            if not self.descriptive_call_analysis:
                logging.error(f"Failed to run descriptive analysis as OpenAI returned empty response")
                return

            self.meeting.llm_descriptive_response = self.descriptive_call_analysis

            speaker_roles = self.descriptive_call_analysis.get("speaker_roles")
            if speaker_roles != 'Not Specified':
                diarization = self.meeting.diarization
                for key, value in speaker_roles.items():
                    diarization = diarization.replace(key, value)
                self.meeting.diarization = diarization

            call_title = self.descriptive_call_analysis.get("call_title")
            self.meeting.title = call_title

            call_summary = self.descriptive_call_analysis.get("call_summary")
            call_summary_string = json.dumps(call_summary)
            if speaker_roles != 'Not Specified':
                for key, value in speaker_roles.items():
                    call_summary_string = call_summary_string.replace(key, value)
            call_summary = json.loads(call_summary_string)
            self.meeting.summary = call_summary

            call_notes = self.descriptive_call_analysis.get("call_notes")
            if speaker_roles != 'Not Specified':
                call_notes_string = json.dumps(call_notes)
                for key, value in speaker_roles.items():
                    call_notes_string = call_notes_string.replace(key, value)
                call_notes = json.loads(call_notes_string)
            self.meeting.call_notes = call_notes

            deal_title = self.descriptive_call_analysis.get("deal_title")
            default_deal_title = f"Deal between {denormalize_phone_number(self.meeting.buyer_number)} and {self.user.name}"
            if not self.deal.name or self.deal.name == default_deal_title:
                if deal_title != 'Not Specified':
                    self.deal.name = deal_title

            deal_summary = self.descriptive_call_analysis.get("deal_summary")
            self.deal.overview = deal_summary.get("deal_overview")
            self.deal.pain_points = deal_summary.get("deal_problem_discovery")
            self.deal.solutions = deal_summary.get("deal_proposed_solution")

            db.session.flush()
        except Exception as e:
            logging.info(f"Failed to run descriptive analysis with error {e}")
            raise e

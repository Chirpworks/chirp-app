import json
import logging
from dotenv import load_dotenv

from app import User, Agency, Deal, Action, db
from app.models.action import ActionType

from app.models.meeting import Meeting, ProcessingStatus
from app.service.llm.open_ai.chat_gpt import OpenAIClient

# Load environment variables (for local dev or ECS fallback)
load_dotenv()

logging = logging.getLogger(__name__)

# OpenAI setup
# openai.api_key = os.getenv("OPENAI_API_KEY")
#
# JOB_ID = os.environ.get("JOB_ID")
# DATABASE_URL = os.environ.get("DATABASE_URL")  # e.g., "postgresql://user:password@host/db"
# BACKEND_API_URL = os.getenv("BACKEND_API_URL")
#
# if not DATABASE_URL:
#     logging.error("DATABASE_URL not set")
#     sys.exit(1)
#
# # Create engine and session
# engine = create_engine(DATABASE_URL)
# Session = sessionmaker(bind=engine)
# session = Session()
#
#
# def get_job_id():
#     if not JOB_ID:
#         logging.error("job_id argument is required")
#         sys.exit(1)
#     return JOB_ID
#
#
# def get_transcript(meeting):
#     return meeting.transcription or ""
#
#
# def analyze_transcript(transcript):
#     logging.info("Sending transcript to OpenAI for analysis")
#     try:
#         prompt = f"Analyze the following call transcript and extract key insights:\n\n{transcript}"
#         response = openai.ChatCompletion.create(
#             model="gpt-4",
#             messages=[{"role": "user", "content": prompt}]
#         )
#         return response['choices'][0]['message']['content']
#     except Exception as e:
#         logging.error(f"OpenAI API error: {e}")
#         return None
#
#
# def update_meeting_analysis(meeting, analysis):
#     if analysis:
#         meeting.analysis = analysis
#         session.commit()
#         print("Analysis saved to meeting record")
#     else:
#         print("No analysis to save")
#
#
# def run():
#     job_id = get_job_id()
#
#     job = session.query(Job).filter_by(id=job_id).first()
#     if not job:
#         logging.error(f"Job with id {job_id} not found")
#         sys.exit(1)
#
#     meeting = session.query(Meeting).filter_by(id=job.meeting_id).first()
#     if not meeting:
#         logging.error(f"Meeting for job {job_id} not found")
#         sys.exit(1)
#
#     transcript = get_transcript(meeting)
#     if not transcript:
#         logging.error("Call transcript is empty")
#         sys.exit(1)
#
#     analysis = analyze_transcript(transcript)
#     update_meeting_analysis(meeting, analysis)
#     # notify_backend(job_id)


class CallAnalysis:
    def __init__(self, meeting):
        self.meeting = meeting
        self.open_ai_client = OpenAIClient()
        self.analytical_call_analysis = None
        self.descriptive_call_analysis = None
        self.deal = None
        self.agency = None

    def get_previous_calls_context(self, meetings):
        text = "Additional Context:\n"
        text = "Call History Summary:\n"
        for i, meeting in enumerate(meetings):
            text += f"Call {i}:\n"
            text += f"{meeting.summary}\n\n"
        return text

    def analyze_meeting(self):
        try:
            seller_number = self.meeting.seller_number
            user = User.query.filter_by(phone=seller_number).first()
            self.agency = Agency.query.filter_by(id=user.agency_id).first()
            self.deal = Deal.query.filter_by(id=Meeting.deal_id).first()

            self.process_analytical_prompt()
            self.process_descriptive_prompt()
            self.meeting.status = ProcessingStatus.COMPLETE
            db.session.commit()
        except Exception as e:
            logging.error(f"Failed to analyze call for meeting with id: {self.meeting.id}")
            raise e

    def process_analytical_prompt(self):
        prompt_text = ''
        deal_meetings = self.deal.meetings
        deal_meetings = sorted(deal_meetings, key=lambda x: x.start_time)

        with open("analytical_prompt.txt", "r") as f:
            prompt_text = f.read()
            prompt_text = prompt_text.replace("<agency_name>", self.agency.name)
            prompt_text = prompt_text.replace("<agency_description>", self.agency.description)
            if len(deal_meetings) > 1:
                text = self.get_previous_calls_context(deal_meetings[:-1])
                prompt_text = prompt_text.replace("<additional_context>", text)
            prompt_text = prompt_text.replace("<call_transcript>", self.meeting.diarization)

        self.analytical_call_analysis = self.open_ai_client.send_prompt(prompt=prompt_text)

        if not prompt_text:
            raise Exception("unable to generate prompt for this analysis")
        self.analytical_call_analysis = json.loads(self.analytical_call_analysis)
        speaker_roles = self.analytical_call_analysis.get("speaker_roles")

        deal_stage = self.analytical_call_analysis.get("deal_stage")
        stage = deal_stage.get("deal_stage")
        if stage == 'Not Specified':
            if not self.deal.stage:
                self.deal.stage = 'Discovery & Lead Qualification'
        else:
            self.deal.stage = stage
        stage_signals = deal_stage.get("stage_signals")
        self.deal.stage_signals = stage_signals
        stage_reasoning = deal_stage.get("stage_reasoning")
        self.deal.stage_reasoning = stage_reasoning

        focus_areas = self.analytical_call_analysis.get("focus_areas")
        self.deal.focus_areas = focus_areas

        risks = self.analytical_call_analysis.get("risks")
        self.deal.risks = risks

        actions = self.analytical_call_analysis.get("suggested_actions")
        for act in actions:
            if act == 'Not Specified':
                break
            due_date = act.get('suggested_action_due_date') if (
                    act.get('suggested_action_due_date') != "Not Specified") else None
            suggested_action_reason = act.get('suggested_action_reason')
            reasoning = suggested_action_reason.get("reasoning")
            signals = suggested_action_reason.get("signals")
            action = Action(
                title=act.get("suggested_action_name"),
                due_date=due_date,
                description=act.get("suggested_action_description"),
                reasoning=reasoning,
                signals=signals,
                meeting_id=self.meeting.id,
                type=ActionType.SUGGESTED_ACTION
            )
            db.session.add(action)
            db.session.flush()

    def process_descriptive_prompt(self):
        prompt_text = ''
        deal_meetings = self.deal.meetings
        deal_meetings = sorted(deal_meetings, key=lambda x: x.start_time)

        with open("descriptive_prompt.txt", "r") as f:
            prompt_text = f.read()
            prompt_text = prompt_text.replace("<agency_name>", self.agency.name)
            prompt_text = prompt_text.replace("<agency_description>", self.agency.description)
            if len(deal_meetings) > 1:
                text = self.get_previous_calls_context(deal_meetings[:-1])
                prompt_text = prompt_text.replace("<additional_context>", text)
            prompt_text = prompt_text.replace("<call_transcript>", self.meeting.diarization)

        self.descriptive_call_analysis = self.open_ai_client.send_prompt(prompt=prompt_text)

        if not prompt_text:
            raise Exception("unable to generate prompt for this analysis")
        self.descriptive_call_analysis = json.loads(self.descriptive_call_analysis)
        speaker_roles = self.descriptive_call_analysis.get("speaker_roles")

        call_title = self.descriptive_call_analysis.get("call_title")
        self.meeting.title = call_title

        call_summary = self.descriptive_call_analysis.get("call_summary")
        self.meeting.summary = call_summary

        call_notes = self.descriptive_call_analysis.get("call_notes")
        self.meeting.key_topics = call_notes

        actions = self.descriptive_call_analysis.get("actions")
        for act in actions:
            if act == 'Not Specified':
                break
            due_date = act.get('action_due_date') if (
                    act.get('action_due_date') != "Not Specified") else None
            action_description = act.get("action_description")
            action_call_context = act.get("action_call_context")
            action = Action(
                title=act.get("action_name"),
                due_date=due_date,
                description=action_description,
                reasoning=action_call_context,
                meeting_id=self.meeting.id,
                type=ActionType.CONTEXTUAL_ACTION
            )
            db.session.add(action)
            db.session.flush()

        deal_title = self.descriptive_call_analysis.get("deal_title")
        self.deal.name = deal_title

        deal_summary = self.descriptive_call_analysis.get("deal_summary")
        self.deal.overview = deal_summary.get("deal_overview")
        self.deal.pain_points = deal_summary.get("deal_pain_points")
        self.deal.solutions = deal_summary.get("deal_proposed_solutions")

from datetime import datetime, timezone
import json

from flask import session, redirect, url_for, jsonify
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.exc import IntegrityError

from app import Meeting, db, Job
from app.models.job import JobStatus
from app.external.job_scheduler.job_scheduler import JobScheduler
from app.constants import CalendarName

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


class GoogleCalendarUserService:
    def __init__(self):
        self.job_scheduler = JobScheduler()

    def refresh_google_token(self):
        """Automatically refresh Google OAuth token or trigger re-authentication."""
        if "google_credentials" not in session:
            return redirect(url_for("auth.google_login"))  # Force login if no credentials

        credentials = Credentials.from_authorized_user_info(session["google_credentials"])

        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                session["google_credentials"] = json.loads(credentials.to_json())
            except RefreshError:
                # Refresh token is expired/revoked, force user to re-authenticate
                session.pop("google_credentials", None)
                return redirect(url_for("auth.google_login"))

        return credentials

    def get_google_calendar_events(self, user):
        """Fetch all future Google Calendar events using Google's API client."""
        credentials = self.refresh_google_token()
        if not credentials:
            return redirect(url_for("auth.google_login"))  # Force re-auth if needed

        service = build("calendar", "v3", credentials=credentials)

        events = []
        now = datetime.now(timezone.utc).isoformat()  # Current time in RFC3339 format
        page_token = None

        while True:
            events_result = (
                service.events().list(
                    calendarId="primary",
                    timeMin=now,
                    maxResults=250,  # Fetch 250 events at a time
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token  # Continue from previous page if needed
                ).execute()
            )

            events.extend(events_result.get("items", []))
            page_token = events_result.get("nextPageToken")

            if not page_token:
                break  # Stop when there are no more pages

        added_meetings = []
        for event in events:
            google_event_id = event["id"]
            meeting_id = f"google_{google_event_id}"  # Prefix Google events
            title = event.get("summary", "Untitled Meeting")
            start_time = event["start"].get("dateTime") or event["start"].get("date")  # Handle all-day events
            scheduled_at = datetime.fromisoformat(start_time) if start_time else datetime.utcnow()

            # Check if meeting already exists
            existing_meeting = Meeting.query.filter_by(id=meeting_id, user_id=user.id).first()

            if not existing_meeting:
                # Create new meeting
                new_meeting = Meeting(
                    id=meeting_id,
                    title=title,
                    scheduled_at=scheduled_at,
                    user_id=user.id
                )
                db.session.add(new_meeting)
                db.session.flush()  # Get ID before commit

                # Create corresponding job entry
                new_job = Job(
                    meeting_id=new_meeting.id,  # Link job to the meeting
                    status=JobStatus.INIT,  # Default status
                    audio_s3_path=None  # Will be updated later
                )
                db.session.add(new_job)

                event['job_id'] = new_job.id
                self.job_scheduler.schedule_agent_job(event, CalendarName.GOOGLE)
                added_meetings.append(title)

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return {"error": "Database error while saving meetings"}, 500

        # TODO: add log message
        print({"message": f"{len(added_meetings)} new meetings added", "added_meetings": added_meetings}, 200)

        return jsonify(events)

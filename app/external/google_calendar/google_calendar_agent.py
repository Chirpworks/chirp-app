from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from datetime import datetime, timedelta
import os.path
import pickle

SCOPES = ['https://www.googleapis.com/auth/calendar']


class CalenderAgent:
    def __init__(self):
        creds = self.authenticate()
        self.service = build('calendar', 'v3', credentials=creds)

    def authenticate(self):
        creds = None

        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)

            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def insert_event(self, calendar_id):
        creds = self.authenticate()
        # Feature 3: Insert an event

        event = {
            'summary': 'Python Meeting',
            'location': '800 Howard St., San Francisco, CA 94103',
            'description': 'A meeting to discuss Python projects.',
            'start': {
                'dateTime': (datetime.utcnow() + timedelta(days=1)).isoformat(),
                'timeZone': 'America/Los_Angeles',
            },
            'end': {
                'dateTime': (datetime.utcnow() + timedelta(days=1, hours=1)).isoformat(),
                'timeZone': 'America/Los_Angeles',
            },
        }
        created_event = self.service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"Created event: {created_event['id']}")

    def update_event(self, calendar_id, event_id):
        # Feature 4: Update an event
        updated_event = event_id
        updated_event['description'] = 'An updated meeting to discuss Python projects.'
        updated_event = self.service.events().update(calendarId=calendar_id, eventId=event_id,
                                                     body=updated_event).execute()
        print(f"Updated event: {updated_event['id']}")

    def delete_event(self, calendar_id, event_id):
        # Feature 5: Delete an event
        self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print(f"Deleted event: {event_id}")

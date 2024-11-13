import datetime
import os
import google.auth
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# Set the scope for Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google_account():
    """Authenticates the user and returns a Google Calendar service object."""
    creds = None
    # Check if token.json exists to save the login session.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no valid credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run.
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service


def add_test_event(service):
    """Adds a test event on Nov 16 from 12:00 to 16:00 with the label 'Test'."""
    # Define the event details
    event = {
        'summary': 'Test',
        'start': {
            'dateTime': '2024-11-16T12:00:00',
            'timeZone': 'America/Los_Angeles',  # Adjust to your timezone
        },
        'end': {
            'dateTime': '2024-11-16T16:00:00',
            'timeZone': 'America/Los_Angeles',
        },
    }

    # Insert the event
    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")


def main():
    service = authenticate_google_account()
    add_test_event(service)


if __name__ == '__main__':
    main()

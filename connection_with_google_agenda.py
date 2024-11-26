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
    """Adds a test event on Nov 18 from 12:00 to 16:00 with the label 'Test'."""
    # Define the event details
    event = {
        'summary': 'Test',
        'start': {
            'dateTime': '2024-11-18T12:00:00',
            'timeZone': 'Etc/Greenwich'  # Automatically adjusts to CET (UTC+1)
        },
        'end': {
            'dateTime': '2024-11-18T16:00:00',
            'timeZone': 'Etc/Greenwich'  # Automatically adjusts to CET (UTC+1)
        },
    }

    # Insert the event
    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")


def list_events_on_date(service, target_date):
    """
    Lists events scheduled for the given date.

    Args:
        service: The Google Calendar API service object.
        target_date: The date for which to check events, in 'YYYY-MM-DD' format.
    """
    try:
        # Parse the target date
        date = datetime.datetime.strptime(target_date, '%Y-%m-%d')

        # Define start and end of the day in ISO format
        start_of_day = date.replace(hour=0, minute=0, second=0).isoformat() + 'Z'
        end_of_day = date.replace(hour=23, minute=59, second=59).isoformat() + 'Z'

        # Call the Calendar API
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day,
            timeMax=end_of_day,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        # Display the events
        if not events:
            print(f'No events found for {target_date}.')
        else:
            print(f'Events on {target_date}:')
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))

                # Extract and format time components
                if 'T' in start:  # Handle dateTime format
                    start_time = datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z').strftime('%H:%M')
                    end_time = datetime.datetime.strptime(end, '%Y-%m-%dT%H:%M:%S%z').strftime('%H:%M')
                    print(f"{start_time} - {end_time}: {event['summary']}")
                else:  # Handle all-day events (date only)
                    print(f"All day: {event['summary']}")
    except ValueError:
        print("Invalid date format. Please use 'YYYY-MM-DD'.")


def main():
    service = authenticate_google_account()
    add_test_event(service)

    # Specify the date you want to check for events
    specific_date = "2024-11-18"
    list_events_on_date(service, specific_date)


if __name__ == '__main__':
    main()

import json
import os
import re
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from swarm_ollama import Swarm, Agent

import ollama

SCOPES = ['https://www.googleapis.com/auth/calendar']

scheduling_assistant = """
FROM llama3.1:8b

PARAMETER temperature 0.1

SYSTEM You are a scheduling helper. You are super smart. Only respond with natural language. Don't give python code. If there's a scheduling conflict please give me the date of the conflicting event and why it's conflicting. Be precise. If a event is created please summarize the event in a bullet point list. Don't talk about tool responses!
"""

ollama.create(model='scheduling_assistant', modelfile=scheduling_assistant)


def authenticate_google_account():
    """
    Authenticates the user with their Google account and returns a Google Calendar service object.

    This function handles the OAuth 2.0 authentication process to access the Google Calendar API.
    It checks for a saved `token.json` file to use existing credentials or initiates a new authentication flow
    if necessary. If credentials are expired but have a refresh token, they are refreshed automatically.
    Otherwise, the user is prompted to authenticate via a browser. The obtained credentials are saved to `token.json`
    for future use.

    Returns:
        service: An authorized Google Calendar API service object.
    """
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service



def create_recurrence_rule(freq, interval=1, count=None, until=None, byday=None):
    valid_days = {'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'}

    rule = f"RRULE:FREQ={freq.upper()};INTERVAL={interval}"

    if count:
        rule += f";COUNT={count}"
    elif until:
        try:
            parsed_date = datetime.strptime(until, '%Y-%m-%d')
            formatted_until = parsed_date.strftime('%Y%m%d')
            rule += f";UNTIL={formatted_until}"
        except ValueError:
            raise ValueError("Invalid 'until' format. Use 'YYYY-MM-DD'.")

    if byday:
        if isinstance(byday, str):
            # Use regex to extract valid two-letter day abbreviations
            byday = re.findall(r'\b(MO|TU|WE|TH|FR|SA|SU)\b', byday.upper())

        # Validate that all days in the list are valid two-letter abbreviations
        if not all(day in valid_days for day in byday):
            invalid_days = [day for day in byday if day not in valid_days]
            raise ValueError(
                f"Invalid day(s) in 'byday': {invalid_days}. Use two-letter abbreviations like 'MO', 'TU'.")

        rule += f";BYDAY={','.join(byday)}"

    return rule



def check_single_event_conflict(date, start_time, end_time, file_path='database/database.json'):
    """
    Checks if there's an existing event on the specified date and if there is a time conflict with
    any existing events, including checking for a minimum 30-minute gap between events.

    Args:
        date (str): The date of the event in `YYYY-MM-DD` format.
        start_time (str): The start time of the event in `HH:MM` format (24-hour clock).
        end_time (str): The end time of the event in `HH:MM` format (24-hour clock).
        file_path (str): The path to the local JSON file storing calendar events.

    Returns:
        str: An error message if there's a conflict, otherwise returns None.
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None

    with open(file_path, 'r') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return "Error: Failed to parse the calendar data."

    start_datetime = datetime.strptime(f"{date}T{start_time}:00", "%Y-%m-%dT%H:%M:%S")
    end_datetime = datetime.strptime(f"{date}T{end_time}:00", "%Y-%m-%dT%H:%M:%S")
    min_gap = timedelta(minutes=30)  # Minimum gap between events

    for day in data.get('calendar', []):
        if day['date'] == date:
            for event in day['events']:
                event_start = datetime.strptime(event['start']['dateTime'], "%Y-%m-%dT%H:%M:%S")
                event_end = datetime.strptime(event['end']['dateTime'], "%Y-%m-%dT%H:%M:%S")

                # Check for full overlaps (existing checks)
                if start_datetime < event_end and end_datetime > event_start:
                    # Case 1: The new event completely overlaps with an existing event
                    if start_datetime <= event_start and end_datetime >= event_end:
                        return f"Your new event completely overlaps with the event '{event['summary']}' from {event_start} to {event_end}. Please reschedule this new event another time."

                    # Case 2: The new event starts before but ends during the existing event
                    elif start_datetime < event_start < end_datetime <= event_end:
                        return f"Your new event partially overlaps with the event '{event['summary']}' that starts at {event_start}. Please reschedule this new event another time."

                    # Case 3: The new event starts during and ends after the existing event
                    elif event_start <= start_datetime < event_end < end_datetime:
                        return f"Your new event partially overlaps with the event '{event['summary']}' that ends at {event_end}. Please reschedule this new event another time."

                    # Case 4: The new event is completely after the existing event but still causes overlap
                    elif start_datetime >= event_start and end_datetime <= event_end:
                        return f"Your new event is contained within the event '{event['summary']}' from {event_start} to {event_end}. Please reschedule this new event another time."

                # Check if the events are too close together (less than 30 minutes apart)
                elif event_end + min_gap > start_datetime:
                    return f"Your new event is too close to the event '{event['summary']}' that starts at {event_start} and ends at {event_end}. Please ensure at least a 30-minute gap between events."

                # Check if the new event ends too close to the next event's start (less than 30 minutes apart)
                elif end_datetime + min_gap > event_start:
                    return f"Your new event ends too close to the event '{event['summary']}' that starts at {event_start} and ends at {event_end}. Please ensure at least a 30-minute gap between events."
def check_recurring_event_conflicts(start_date, start_time, end_time, recurrence_rule,
                                    file_path='database/database.json'):
    """
    Checks if a recurring event conflicts with existing events in the local calendar.

    Args:
        start_date (str): Start date of the recurrence (YYYY-MM-DD).
        start_time (str): Start time (HH:MM).
        end_time (str): End time (HH:MM).
        recurrence_rule (str): RRULE string for the recurrence.
        file_path (str): Path to the local JSON file.

    Returns:
        str: Conflict message, or None if no conflicts exist.
    """
    # Parse recurrence rule
    recurrence_details = re.findall(r"(FREQ|INTERVAL|UNTIL|COUNT|BYDAY)=([^;]+)", recurrence_rule)
    recurrence_params = {key: value for key, value in recurrence_details}

    occurrences = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    interval = int(recurrence_params.get('INTERVAL', 1))
    freq = recurrence_params['FREQ']
    count = int(recurrence_params.get('COUNT', 0)) if 'COUNT' in recurrence_params else None
    until = datetime.strptime(recurrence_params['UNTIL'], '%Y%m%d') if 'UNTIL' in recurrence_params else None

    while (not until or current_date <= until) and (not count or len(occurrences) < count):
        occurrences.append(current_date.strftime('%Y-%m-%d'))
        if freq == 'DAILY':
            current_date += timedelta(days=interval)
        elif freq == 'WEEKLY':
            current_date += timedelta(weeks=7 * interval)
        elif freq == 'MONTHLY':
            current_date += timedelta(days=30 * interval)  # Approximation
        elif freq == 'YEARLY':
            current_date += timedelta(days=365 * interval)  # Approximation

    for date in occurrences:
        conflict_message = check_single_event_conflict(date, start_time, end_time, file_path)
        if conflict_message:
            return conflict_message



def suggest_free_dates(start_time, end_time, file_path='database/database.json'):
    """
    Suggests dates within the next two weeks when the given event time slot is free.

    Args:
        start_time (str): Desired start time in 'HH:MM' format.
        end_time (str): Desired end time in 'HH:MM' format.
        file_path (str): Path to the local calendar JSON file.

    Returns:
        list: A list of free dates (in 'YYYY-MM-DD' format) for the given time slot.
    """
    today = datetime.now()
    free_dates = []

    for day_offset in range(14):  # Look 14 days ahead
        current_date = (today + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        conflict_message = check_single_event_conflict(current_date, start_time, end_time, file_path)

        if not conflict_message:  # If there's no conflict, the date is free
            free_dates.append(current_date)

    return free_dates



def add_single_event_local(date, title, start_time, end_time, file_path='database/database.json'):
    """
    Adds an event to a local JSON file representing a user's calendar.
    First checks for conflicts before adding the event.

    Args:
        date (str): The date of the event in `YYYY-MM-DD` format.
        title (str): The title or summary of the event.
        start_time (str): The start time of the event in `HH:MM` format (24-hour clock).
        end_time (str): The end time of the event in `HH:MM` format (24-hour clock).
        file_path (str, optional): The path to the local JSON file storing calendar events.
                                   Defaults to 'database/database.json'.

    Returns:
        str: A message indicating the result of the operation.
    """
    # Check for event conflicts
    conflict_message = check_single_event_conflict(date, start_time, end_time, file_path)
    if conflict_message:
        print()
        return conflict_message

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        data = {"calendar": []}
    else:
        with open(file_path, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {"calendar": []}

    start_datetime = f"{date}T{start_time}:00"
    end_datetime = f"{date}T{end_time}:00"
    event = {
        'summary': title,
        'start': {'dateTime': start_datetime, 'timeZone': 'Etc/Greenwich'},
        'end': {'dateTime': end_datetime, 'timeZone': 'Etc/Greenwich'},
    }

    date_exists = False
    for day in data['calendar']:
        if day['date'] == date:
            day['events'].append(event)
            date_exists = True
            break

    if not date_exists:
        new_day = {
            "date": date,
            "events": [event]
        }
        data['calendar'].append(new_day)

    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
def add_recurring_event_local(start_date, title, start_time, end_time, recurrence_rule, file_path='database/database.json'):
    """
    Adds a recurring event to the local calendar.

    Args:
        start_date (str): Start date of recurrence (YYYY-MM-DD).
        title (str): Title of the event.
        start_time (str): Start time (HH:MM).
        end_time (str): End time (HH:MM).
        recurrence_rule (str): RRULE string defining recurrence.
        file_path (str): Path to the local calendar JSON file.

    Returns:
        str: Success or conflict message.
    """
    # Parse recurrence details
    recurrence_details = re.findall(r"(FREQ|INTERVAL|UNTIL|COUNT|BYDAY)=([^;]+)", recurrence_rule)
    recurrence_params = {key: value for key, value in recurrence_details}

    occurrences = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')
    interval = int(recurrence_params.get('INTERVAL', 1))
    freq = recurrence_params['FREQ']
    count = int(recurrence_params.get('COUNT', 0)) if 'COUNT' in recurrence_params else None
    until = datetime.strptime(recurrence_params['UNTIL'], '%Y%m%d') if 'UNTIL' in recurrence_params else None

    while (not until or current_date <= until) and (not count or len(occurrences) < count):
        occurrences.append(current_date.strftime('%Y-%m-%d'))
        if freq == 'DAILY':
            current_date += timedelta(days=interval)
        elif freq == 'WEEKLY':
            current_date += timedelta(weeks=interval)
        elif freq == 'MONTHLY':
            current_date += timedelta(days=30 * interval)  # Approximation
        elif freq == 'YEARLY':
            current_date += timedelta(days=365 * interval)  # Approximation

    for date in occurrences:
        conflict_message = check_single_event_conflict(date, start_time, end_time, file_path)
        if conflict_message:
            return conflict_message

        add_single_event_local(date, title, start_time, end_time, file_path)



def add_single_google_event(service, date, title, start_time, end_time):
    """
    Adds an event to the user's Google Calendar.

    This function uses the Google Calendar API to create a new event on the user's primary calendar.
    The event is defined by its date, title, start time, and end time, and is created with the
    'Etc/Greenwich' timezone by default.

    Args:
        service: The Google Calendar API service object obtained via `authenticate_google_account`.
        date (str): The date of the event in `YYYY-MM-DD` format.
        title (str): The title or summary of the event.
        start_time (str): The start time of the event in `HH:MM` format (24-hour clock).
        end_time (str): The end time of the event in `HH:MM` format (24-hour clock).

    Returns:
        None. Prints the link to the newly created Google Calendar event.

    Side Effects:
        Creates a new event on the user's primary Google Calendar.
    """
    start_datetime = f"{date}T{start_time}:00"
    end_datetime = f"{date}T{end_time}:00"
    event = {
        'summary': title,
        'start': {'dateTime': start_datetime, 'timeZone': 'Etc/Greenwich'},
        'end': {'dateTime': end_datetime, 'timeZone': 'Etc/Greenwich'},
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")
def add_recurring_google_event(service, start_date, title, start_time, end_time, recurrence_rule):
    """
    Adds a recurring event to the user's Google Calendar.

    Args:
        service: The Google Calendar API service object.
        start_date (str): The start date of the recurring event in 'YYYY-MM-DD' format.
        title (str): The title or summary of the event.
        start_time (str): The start time of the event in 'HH:MM' format.
        end_time (str): The end time of the event in 'HH:MM' format.
        recurrence_rule (str): A recurrence rule string in the RRULE format.

    Returns:
        str: A link to the newly created Google Calendar recurring event.
    """
    start_datetime = f"{start_date}T{start_time}:00"
    end_datetime = f"{start_date}T{end_time}:00"
    event = {
        'summary': title,
        'start': {'dateTime': start_datetime, 'timeZone': 'Etc/Greenwich'},
        'end': {'dateTime': end_datetime, 'timeZone': 'Etc/Greenwich'},
        'recurrence': [recurrence_rule],
    }
    created_event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {created_event.get('htmlLink')}")



def calendar_add_event(date: str, title: str, start_time: str, end_time: str) -> str:
    """
    Adds a single event to both a local JSON calendar file and Google Calendar, ensuring no scheduling conflicts.

    This function first attempts to add the event to a local calendar file. If a conflict is detected,
    it suggests alternative free dates and times for the specified time slot within the next two weeks.
    If no conflicts are found, it proceeds to add the event to the user's Google Calendar.

    Args:
        date (str):
            The date of the event in `YYYY-MM-DD` format.
            Example: "2023-12-25" for December 25, 2023.
        title (str):
            The title or summary of the event.
            Example: "Team Meeting".
        start_time (str):
            The start time of the event in 24-hour `HH:MM` format.
            Example: "14:00" for 2:00 PM.
        end_time (str):
            The end time of the event in 24-hour `HH:MM` format.
            Example: "15:30" for 3:30 PM.

    Returns:
        str:
            A message indicating the result of the operation:
              - If the event is successfully added, the message will be "Event added successfully."
              - If a conflict occurs, the message will:
                  - Describe the conflict.
                  - Suggest alternative dates within the next two weeks if available.
                  - Indicate no free slots if no alternatives are available.

    Raises:
        ValueError:
            If the input parameters are invalid, such as incorrect date or time formats,
            or if the end time is earlier than the start time.
    """
    # First, try to add the event locally and check for conflicts
    conflict_message = add_single_event_local(date, title, start_time, end_time)
    if conflict_message:
        # Suggest alternative dates if there is a conflict
        free_dates = suggest_free_dates(start_time, end_time)
        if free_dates:
            return f"Conflict detected: {conflict_message}\nSuggested free dates for this time slot: {', '.join(free_dates)}"
        else:
            return f"Conflict detected: {conflict_message}\nNo free dates available for the specified time slot within the next two weeks."

    # If no conflict, authenticate with Google and add the event to Google Calendar
    service = authenticate_google_account()
    add_single_google_event(service, date, title, start_time, end_time)

    return "Event added successfully."
def calendar_add_recurring_event(
        start_date: str,
        title: str,
        start_time: str,
        end_time: str,
        freq: str,
        interval=1,
        count=None,
        until=None,
        byday=None
) -> str:
    """
    Adds a recurring event to both a local JSON calendar file and Google Calendar, handling potential conflicts.

    This function creates a recurring event based on the specified recurrence rule and checks for conflicts
    in the local calendar. If conflicts are found, it suggests alternative single dates for individual
    occurrences of the recurring event within the next two weeks. Once resolved, the function adds the
    recurring event to Google Calendar.

    Args:
        start_date (str):
            The start date of the recurring event in `YYYY-MM-DD` format.
            Example: "2023-12-01".
        title (str):
            The title or summary of the event.
        start_time (str):
            The start time of the event in 24-hour `HH:MM` format.
            Example: "10:00" for 10:00 AM.
        end_time (str):
            The end time of the event in 24-hour `HH:MM` format.
            Example: "11:00" for 11:00 AM.
        freq (str):
            The frequency of recurrence (e.g., "DAILY", "WEEKLY", "MONTHLY", or "YEARLY").
            Determines how often the event repeats.
        interval (int, optional):
            The interval between occurrences of the event. Defaults to 1.
            Example: For `freq="WEEKLY"` and `interval=2`, the event occurs every 2 weeks.
        count (int, optional):
            The total number of occurrences. If provided, `until` is ignored. Defaults to None.
            Example: If `count=10`, the event will occur 10 times.
        until (str, optional):
            The date when the recurrence ends, in `YYYY-MM-DD` format. Defaults to None.
            Example: "2024-06-01".
        byday (list of str, optional):
            Specifies the days of the week when the event occurs. Each day is represented as
            a two-character abbreviation:
                - "MO" (Monday), "TU" (Tuesday), "WE" (Wednesday), "TH" (Thursday), "FR" (Friday), "SA" (Saturday), "SU" (Sunday).
            Defaults to None. Example: ["MO", "WE", "FR"] for events on Monday, Wednesday, and Friday.

    Returns:
        str:
            A message indicating the result of the operation:
              - If the recurring event is successfully added, the message will be "Recurring event added successfully."
              - If a conflict occurs, the message will:
                  - Describe the conflict.
                  - Suggest alternative single dates within the next two weeks for conflicting occurrences.
                  - Indicate no free slots if no alternatives are available.

    Raises:
        ValueError:
            If the input parameters are invalid, such as incorrect date or time formats,
            or if the end time is earlier than the start time.
    """
    recurrence_rule = create_recurrence_rule(freq, interval, count, until, byday)

    conflict_message = check_recurring_event_conflicts(start_date, start_time, end_time, recurrence_rule)
    if conflict_message:
        # Suggest alternative dates if there is a conflict
        free_dates = suggest_free_dates(start_time, end_time)
        if free_dates:
            return f"Conflict detected for recurring event: {conflict_message}\nSuggested free dates for single occurrences within the next two weeks: {', '.join(free_dates)}"
        else:
            return f"Conflict detected for recurring event: {conflict_message}\nNo free dates available for single occurrences within the next two weeks."

    add_recurring_event_local(start_date, title, start_time, end_time, recurrence_rule)
    service = authenticate_google_account()

    add_recurring_google_event(service, start_date, title, start_time, end_time, recurrence_rule)
    return "Recurring event added successfully."


authenticate_google_account() # this doesn't need to be here, but just in case.

# LLM setup
client = Swarm(base_url="http://localhost:11434")
agent_a = Agent(
    name="Scheduler",
    model="scheduling_assistant",
    instructions="You are a helpful scheduling assistant, reply with natural language, you are very smart!",
    functions=[calendar_add_event, calendar_add_recurring_event],
)

# Example usage
current_date = datetime.now().strftime("%Y-%m-%d")
current_weekday = datetime.now().strftime("%A")  # Get the weekday name
request_event = input("( 0 o 0) {Give an event date, start and end time.] (press enter to confirm input): ")
response = client.run(
    agent=agent_a,
    messages=[
        {
            "role": "user",
            "content": f"Today's date is {current_weekday}, {current_date}. {request_event}"
        }
    ],
)

print(response.messages[-1]["content"])

# create a single event for 2 december 2024, from 17 till 18, meeting with my girlfriend.
# create a recurring event starting from monday 25/11/2024, meeting with dog, from 17 till 18. every monday for the next 5 times.
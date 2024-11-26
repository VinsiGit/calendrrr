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
            byday = re.findall(r'\b(MO|TU|WE|TH|FR|SA|SU)\b', byday.upper())

        if not all(day in valid_days for day in byday):
            invalid_days = [day for day in byday if day not in valid_days]
            raise ValueError(
                f"Invalid day(s) in 'byday': {invalid_days}. Use two-letter abbreviations like 'MO', 'TU'.")

        rule += f";BYDAY={','.join(byday)}"

    return rule


def check_single_event_conflict(date, start_time, end_time, file_path='database/database.json'):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None

    with open(file_path, 'r') as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            return "Error: Failed to parse the calendar data."

    start_datetime = datetime.strptime(f"{date}T{start_time}:00", "%Y-%m-%dT%H:%M:%S")
    end_datetime = datetime.strptime(f"{date}T{end_time}:00", "%Y-%m-%dT%H:%M:%S")
    min_gap = timedelta(minutes=30)

    for day in data.get('calendar', []):
        if day['date'] == date:
            for event in day['events']:
                event_start = datetime.strptime(event['start']['dateTime'], "%Y-%m-%dT%H:%M:%S")
                event_end = datetime.strptime(event['end']['dateTime'], "%Y-%m-%dT%H:%M:%S")

                if start_datetime < event_end and end_datetime > event_start:
                    if start_datetime <= event_start and end_datetime >= event_end:
                        return f"Your new event completely overlaps with the event '{event['summary']}' from {event_start} to {event_end}. Please reschedule this new event another time."
                    elif start_datetime < event_start < end_datetime <= event_end:
                        return f"Your new event partially overlaps with the event '{event['summary']}' that starts at {event_start}. Please reschedule this new event another time."
                    elif event_start <= start_datetime < event_end < end_datetime:
                        return f"Your new event partially overlaps with the event '{event['summary']}' that ends at {event_end}. Please reschedule this new event another time."
                    elif start_datetime >= event_start and end_datetime <= event_end:
                        return f"Your new event is contained within the event '{event['summary']}' from {event_start} to {event_end}. Please reschedule this new event another time."
                elif event_end + min_gap > start_datetime:
                    return f"Your new event is too close to the event '{event['summary']}' that starts at {event_start} and ends at {event_end}. Please ensure at least a 30-minute gap between events."
                elif end_datetime + min_gap > event_start:
                    return f"Your new event ends too close to the event '{event['summary']}' that starts at {event_start} and ends at {event_end}. Please ensure at least a 30-minute gap between events."


def check_recurring_event_conflicts(start_date, start_time, end_time, recurrence_rule, file_path='database/database.json'):
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
            current_date += timedelta(days=30 * interval)
        elif freq == 'YEARLY':
            current_date += timedelta(days=365 * interval)

    for date in occurrences:
        conflict_message = check_single_event_conflict(date, start_time, end_time, file_path)
        if conflict_message:
            return conflict_message


def suggest_free_dates(start_time, end_time, file_path='database/database.json'):
    today = datetime.now()
    free_dates = []

    for day_offset in range(14):
        current_date = (today + timedelta(days=day_offset)).strftime('%Y-%m-%d')
        conflict_message = check_single_event_conflict(current_date, start_time, end_time, file_path)

        if not conflict_message:
            free_dates.append(current_date)

    return free_dates


def add_single_event_local(date, title, start_time, end_time, file_path='database/database.json'):
    conflict_message = check_single_event_conflict(date, start_time, end_time, file_path)
    if conflict_message:
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
            current_date += timedelta(days=30 * interval)
        elif freq == 'YEARLY':
            current_date += timedelta(days=365 * interval)

    for date in occurrences:
        conflict_message = check_single_event_conflict(date, start_time, end_time, file_path)
        if conflict_message:
            return conflict_message

        add_single_event_local(date, title, start_time, end_time, file_path)


def add_single_google_event(service, date, title, start_time, end_time):
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
    conflict_message = add_single_event_local(date, title, start_time, end_time)
    if conflict_message:
        free_dates = suggest_free_dates(start_time, end_time)
        if free_dates:
            return f"Conflict detected: {conflict_message}\nSuggested free dates for this time slot: {', '.join(free_dates)}"
        else:
            return f"Conflict detected: {conflict_message}\nNo free dates available for the specified time slot within the next two weeks."

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
    recurrence_rule = create_recurrence_rule(freq, interval, count, until, byday)

    conflict_message = check_recurring_event_conflicts(start_date, start_time, end_time, recurrence_rule)
    if conflict_message:
        free_dates = suggest_free_dates(start_time, end_time)
        if free_dates:
            return f"Conflict detected for recurring event: {conflict_message}\nSuggested free dates for single occurrences within the next two weeks: {', '.join(free_dates)}"
        else:
            return f"Conflict detected for recurring event: {conflict_message}\nNo free dates available for single occurrences within the next two weeks."

    add_recurring_event_local(start_date, title, start_time, end_time, recurrence_rule)
    service = authenticate_google_account()

    add_recurring_google_event(service, start_date, title, start_time, end_time, recurrence_rule)
    return "Recurring event added successfully."


def main():
    authenticate_google_account()  # this doesn't need to be here, but just in case.

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


if __name__ == "__main__":
    main()
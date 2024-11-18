import json
from datetime import datetime, timedelta

def add_event(date, summary, start_time, end_time, time_zone='Europe/Brussels', file_path='database/database.json'):
    """Add an event to the calendar.
    args:
        date: str: The date of the event in the format 'YYYY-MM-DD'.
        summary: str: The title of the event.
        start_time: str: The start time of the event in the format 'HH:MM'.
        end_time: str: The end time of the event in the format 'HH:MM'.
        time_zone: str: The time zone of the event, default: Europe/Brussels.
        file_path: str: The path to the JSON file containing the calendar data, default: 'database/database.json'.
    """
    # Load the existing data
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    # Create the new event
    new_event_start = datetime.strptime(f"{date}T{start_time}", "%Y-%m-%dT%H:%M")
    new_event_end = datetime.strptime(f"{date}T{end_time}", "%Y-%m-%dT%H:%M")
    
    # Check for overlapping events
    for event in data['calendar']:
        existing_event_start = datetime.strptime(event['start']['dateTime'], "%Y-%m-%dT%H:%M:%S")
        existing_event_end = datetime.strptime(event['end']['dateTime'], "%Y-%m-%dT%H:%M:%S")
        
        if (new_event_start < existing_event_end and new_event_end > existing_event_start):
            return False, f"Event overlaps with existing event: {event['summary']} from {existing_event_start} to {existing_event_end}"
        
        if (new_event_start - existing_event_end < timedelta(minutes=30) and new_event_start > existing_event_end):
            return False, f"Event start time is less than 30 minutes after the end of existing event: {event['summary']} from {existing_event_start} to {existing_event_end}"
        
        if (existing_event_start - new_event_end < timedelta(minutes=30) and new_event_end < existing_event_start):
            return False, f"Event end time is less than 30 minutes before the start of existing event: {event['summary']} from {existing_event_start} to {existing_event_end}"
    
    # Add the new event to the calendar
    new_event = {
        "summary": summary,
        "start": {
            "dateTime": f"{date}T{start_time}:00",
            "timeZone": time_zone
        },
        "end": {
            "dateTime": f"{date}T{end_time}:00",
            "timeZone": time_zone
        }
    }
    data['calendar'].append(new_event)
    
    # Save the updated data
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)
    
    return True, f"Event added successfully."
# Example usage
# print(add_event("2024-11-16", "Test", "12:00", "16:00"))
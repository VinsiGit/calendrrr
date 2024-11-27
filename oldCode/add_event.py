import json
from datetime import datetime

def add_event(date, title, start_time, end_time, file_path='database/database.json'):
    # Load the existing data
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    # Create the new event
    new_event = {
        "title": title,
        "start_time": start_time,
        "end_time": end_time
    }
    
    # Check if the date already exists
    date_exists = False
    for day in data['calendar']:
        if day['date'] == date:
            day['events'].append(new_event)
            date_exists = True
            break
    
    # If the date does not exist, create a new entry
    if not date_exists:
        new_day = {
            "date": date,
            "events": [new_event]
        }
        data['calendar'].append(new_day)
    
    # Save the updated data
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

# # Example usage
# add_event("2023-10-01", "Meeting with Team", "09:00", "10:00")
# add_event("2023-10-01", "Lunch Break", "12:00", "13:00")
# add_event("2023-10-02", "Project Presentation", "14:00", "15:30")
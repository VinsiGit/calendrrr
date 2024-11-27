import json
from datetime import datetime

with open('database/database.json', 'r') as file:
    data = json.load(file)



# Function to create ICS format date-time
def format_datetime(date_str, time_str):
    try:
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.strftime("%Y%m%dT%H%M%S")
    except ValueError:
        return None

# Create ICS content
ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\n"

for entry in data['calendar']:
    date = entry['date']
    for event in entry['events']:
        start_datetime = format_datetime(date, event['start_time'])
        end_datetime = format_datetime(date, event['end_time'])
        if start_datetime and end_datetime:
            ics_content += "BEGIN:VEVENT\n"
            ics_content += f"SUMMARY:{event['title']}\n"
            ics_content += f"DTSTART:{start_datetime}\n"
            ics_content += f"DTEND:{end_datetime}\n"
            ics_content += "END:VEVENT\n"

ics_content += "END:VCALENDAR"

# Save to .ics file
with open("database/calendar.ics", "w") as file:
    file.write(ics_content)

print("ICS file created successfully.")
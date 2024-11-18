import json
from datetime import datetime
import pytz

with open('database/database.json', 'r') as file:
    data = json.load(file)

# Function to create ICS format date-time with timezone
def format_datetime(date_time_str, tz_str='America/Los_Angeles'):
    try:
        local_tz = pytz.timezone(tz_str)
        dt = datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S")
        local_dt = local_tz.localize(dt)
        return local_dt.strftime("%Y%m%dT%H%M%S")
    except (ValueError, pytz.UnknownTimeZoneError):
        return None

# Create ICS content
ics_content = "BEGIN:VCALENDAR\nVERSION:2.0\n"

for event in data['calendar']:
    start_datetime = format_datetime(event['start']['dateTime'], event['start']['timeZone'])
    end_datetime = format_datetime(event['end']['dateTime'], event['end']['timeZone'])
    if start_datetime and end_datetime:
        ics_content += "BEGIN:VEVENT\n"
        ics_content += f"SUMMARY:{event['summary']}\n"
        ics_content += f"DTSTART;TZID={event['start']['timeZone']}:{start_datetime}\n"
        ics_content += f"DTEND;TZID={event['end']['timeZone']}:{end_datetime}\n"
        ics_content += "END:VEVENT\n"

ics_content += "END:VCALENDAR"

# Save to .ics file
with open("database/calendar.ics", "w") as file:
    file.write(ics_content)

print("ICS file created successfully.")
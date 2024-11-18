import requests
import json
from datetime import datetime, timedelta
import ollama
# Load calendar data
def load_calendar(file_path="calendar.json"):
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"calendar": []}

# Save calendar data
def save_calendar(data, file_path="calendar.json"):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# Communicate with the LLM
def communicate_with_llm(user_prompt, calendar_data):
    
    response = ollama.generate(model="llama3.1:8b", prompt=f"""
    You are an AI scheduling assistant managing a consultant's schedule. 
    You work with a structured calendar, and your task is to process user requests to schedule or reschedule events.

    The current calendar is as follows:
    {json.dumps(calendar_data, indent=4)}

    The user has made the following request:
    {user_prompt}

    Your tasks:
    Important: return only the JSON! no extra information:
    1. Extract the required date, time, duration, and meeting details from the user's request.
    2. Check for scheduling conflicts in the current calendar. A conflict occurs if an event overlaps or does not respect a 30-minute buffer between appointments.
    3. Respond strictly in the following JSON format and only like this no extra information:
    ```json
    {{
        "action": "schedule" or "suggestion" ,
        "event": {{
            "summary": "Summary of the meeting",
            "date": "YYYY-MM-DD",
            "start_time": "HH:MM",
            "end_time": "HH:MM"
        }},
        "suggestion": {{
            "date": "YYYY-MM-DD",
            "start_time": "HH:MM",
            "end_time": "HH:MM"
        }} (omit this key if there is no conflict)
    }}```    """)["response"]
     # requests.post(url, json=data, headers=headers)
    try:
        # Print the raw response content for debugging
        print("Raw response content:", response)
        # Extract JSON from the response text
        start_index = response.find('{')
        end_index = response.rfind('}') + 1
        json_response = response[start_index:end_index]
        return json.loads(json_response)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print("Raw response content:", response)
        return {"error": "Failed to parse JSON response from LLM."}

# Schedule a task using the LLM
def schedule_task_via_llm(user_input, calendar_file="new/calendar.json"):
    # Load the current calendar
    calendar = load_calendar(calendar_file)

    # Communicate with the LLM
    llm_response = communicate_with_llm(user_input, calendar)
    print(llm_response)
    # Parse the LLM's response
    try:
        if isinstance(llm_response, str):
            llm_response = json.loads(llm_response)

        if "error" in llm_response:
            print(f"LLM Error: {llm_response['error']}")
            return

        action = llm_response.get("action")
        event = llm_response.get("event")
        suggestion = llm_response.get("suggestion")

        if action == "error":
            print(f"LLM Error: {llm_response.get('message', 'Unknown error')}")
            # return

        if suggestion:
            print(f"Conflict detected. Suggested time: {suggestion['date']} at {suggestion['start_time']} - {suggestion['end_time']}")
            user_response = input("Do you accept this suggestion? (yes/no): ")
            if user_response.lower() != "yes":
                print("Task not scheduled.")
                return

            # Update event with the suggested time
            event = suggestion

        # Add the event to the calendar
        calendar["calendar"].append({
            "summary": event["summary"],
            "start": {
                "dateTime": f"{event['date']}T{event['start_time']}:00",
                "timeZone": "Europe/Amsterdam"
            },
            "end": {
                "dateTime": f"{event['date']}T{event['end_time']}:00",
                "timeZone": "Europe/Amsterdam"
            }
        })
        save_calendar(calendar, calendar_file)
        print("Task successfully scheduled.")
    except json.JSONDecodeError:
        print("Failed to parse LLM response.")
    except Exception as e:
        print(f"An error occurred: {e}")
        
        
# Main function
def main():
    print("Welcome to the AI Planning Agent!")
    user_input = input("Enter your planning request: ")

    try:
        schedule_task_via_llm(user_input)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()

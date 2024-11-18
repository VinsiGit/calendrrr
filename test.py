from swarm_ollama import Swarm, Agent
import json
from datetime import datetime, timedelta

from add_event import add_event

client = Swarm(base_url="http://localhost:11434")

def calender_add_event(date: str, title: str, start_time: str, end_time: str) -> str:
    add_event(date, title, start_time, end_time)
    return print("Event added successfully.")

agent_a = Agent(
    name="Agent A",
    model="llama3.2",
    instructions="You are a helpful agent. Please check if the event can be added to the calendar. If not, propose a new time.",
    functions=[calender_add_event],
)

agent_b = Agent(
    name="Agent B",
    model="llama3.2",
    instructions="You are a helpful agent. Please check if the event can be added to the calendar.",
    functions=[calender_add_event],
)

current_date = datetime.now().strftime("%Y-%m-%d")
with open('database/database.json', 'r') as file:
    data = json.load(file)

response = client.run(
    agent=agent_a,
    messages=[{"role": "user", "content": f"today its {current_date}. Add an event tomorrow with title 'Meeting with Team' from 11:00 to 15:00"}],
    context_variables={"location": "Belgium", "time": "12:00", "database": data}
)


print(response.messages[-1]["content"])
from swarm_ollama import Swarm, Agent
import json
from datetime import datetime, timedelta

from add_event import add_event

client = Swarm()
## IF NEEDED, you change surcharge the base_url with the OLLAMA_URL
# client = Swarm(base_url="http://<your-ip>:11434")


def transfer_to_agent_b():
    return agent_b

def calender_add_event(date: str, title: str, start_time: str, end_time: str) -> str:
    add_event(date, title, start_time, end_time)
    return print("Event added successfully.")

agent_a = Agent(
    name="Agent A",
    model="llama3.2", # NEED a model with tool support
    #https://ollama.com/blog/tool-support
    instructions="You are a helpful agent.",
    functions=[transfer_to_agent_b, calender_add_event],
)

agent_b = Agent(
    name="Agent B",
    model="llama3.2",
    instructions="Only speak in UWU Haikus.",
)
current_date = datetime.now().strftime("%Y-%m-%d")

response = client.run(
    agent=agent_a,
    messages=[{"role": "user", "content": f"today its {current_date}. Add an event tommorowwith title 'Meeting with Team' from 09:00 to 10:00"}],
    # context_variables={"location": "Belgium","time":"12:00"}
)


#     messages=[{"role": "user", "content": f'{{"date": "{current_date}", "title": "Meeting with Internship Company", "start_time": "09:00", "end_time": "12:00"}}'}], # Example message to add an event

print(response.messages[-1]["content"])
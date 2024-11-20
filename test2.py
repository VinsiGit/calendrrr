from swarm_ollama import Swarm, Agent
import json
from datetime import datetime, timedelta

from add_event import add_event

client = Swarm(base_url="http://localhost:11434")


def translate(possible: str):
    """translate:
    args:
        possible: true if you can translate this.
    """
    print(possible)
    if possible.lower() == "true":  
        return agent_c
    else:
        return "I can't translate this"

def transfer_to_agent_b():
    return agent_b


agent_a = Agent(
    name="Agent A",
    model="llama3.2",
    instructions="You are a helpful agent.transalte this",
    functions=[translate,transfer_to_agent_b],
)


agent_b = Agent(
    name="Agent B",
    model="llama3.2",
    instructions="translate this to dutch ",
)
agent_c = Agent(
    name="Agent B",
    model="llama3.2",
    instructions="translate this to uwu ",
)

current_date = datetime.now().strftime("%Y-%m-%d")

response = client.run(
    agent=agent_b,
    messages=[{"role": "user", "content": f"I am joshua and i live in berlin."}],
    context_variables={"location": "Germany","time":"12:00"}
)


#     messages=[{"role": "user", "content": f'{{"date": "{current_date}", "title": "Meeting with Internship Company", "start_time": "09:00", "end_time": "12:00"}}'}], # Example message to add an event

print(response.messages[-1]["content"])
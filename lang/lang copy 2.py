from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from typing import Annotated, Sequence
from typing_extensions import TypedDict
import operator
import json
from datetime import datetime
from add_event import add_event
import functools
from langchain_core.messages import AIMessage

# Define the AgentState
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    sender: str

# Define the tools
repl = PythonREPL()

@tool
def calender_add_event(date: str, title: str, start_time: str, end_time: str) -> str:
    """ Add an event to your calendar. """
    result=add_event(date, title, start_time, end_time)
    return result



# Define the agents
llm = ChatOpenAI(model="llama3.2", base_url="http://localhost:11434/v1", api_key='ollama')

prompt_template = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an AI assistant that helps manage and optimize a consultant's weekly schedule."
        " You have access to the following tools: {tool_names}.\n{system_message}",
    ),
    MessagesPlaceholder(variable_name="messages")
])

def create_agent(llm, tools, system_message: str):
    prompt = prompt_template.partial(system_message=system_message)
    prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))

    return prompt | llm.bind_tools(tools)


def handle_user_input(user_input: str, state: dict):
    state["messages"].append(HumanMessage(content=user_input))
    response = agent.invoke(state).tool_calls[0]
    print(response)
    

            # Add the event to the calendar
    
    return  add_event(response["args"]["date"], response["args"]["title"], response["args"]["start_time"], response["args"]["end_time"])


# Initialize state
current_date = datetime.now().strftime("%Y-%m-%d")
initial_state = {
    "messages": [HumanMessage(content=f"Today's date is {current_date}.")],
    "sender": "user"
}

agent = create_agent(llm, [calender_add_event], system_message="You should help the user manage their schedule efficiently.")

# Example user input
user_input = "Plan a 5-hour meeting with Client X on Tuesday afternoon."
response = handle_user_input(user_input, initial_state)
print(response)
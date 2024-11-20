from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from typing import Annotated, Sequence
from typing_extensions import TypedDict
import operator
from datetime import datetime
from add_event import add_event
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel

from PIL import Image
import io
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.graph.message import add_messages


# Define the AgentState
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    sender: str

# Define the tools
repl = PythonREPL()


def make_system_prompt(suffix: str) -> str:
    return (
        "You are a helpful AI assistant, collaborating with other assistants."
        "if you fail making a event try again with a different time or provide more information about the meeting."
        f"\n{suffix}"
    )
    
class State(TypedDict):
    messages: Annotated[list, add_messages]
    selected_tools: list[str]
    


@tool
def calender_add_event(date: str, title: str, start_time: str, end_time: str) -> str:
    """ Add an event to your calendar. """
    result=add_event(date, title, start_time, end_time)
    return result

def select_tools(state: State):
    """Selects tools based on the last message in the conversation state.

    If the last message is from a human, directly uses the content of the message
    as the query. Otherwise, constructs a query using a system message and invokes
    the LLM to generate tool suggestions.
    """
    last_message = state["messages"][-1]
    hack_remove_tool_condition = False  # Simulate an error in the first tool selection

    if isinstance(last_message, HumanMessage):
        query = last_message.content
        hack_remove_tool_condition = True  # Simulate wrong tool selection
    else:
        assert isinstance(last_message, ToolMessage)
        system = SystemMessage(
            "Given this conversation, generate a query for additional tools. "
            "The query should be a short string containing what type of information "
            "is needed. If no further information is needed, "
            "set more_information_needed False and populate a blank string for the query."
        )
        input_messages = [system] + state["messages"]
        response = llm.bind_tools([calender_add_event], tool_choice=True).invoke(
            input_messages
        )
        query = response.tool_calls[0]["args"]["query"]

    return {"selected_tools": query}


@tool
def handle_failed_event(date: str, title: str, start_time: str, end_time: str) -> str:
    """ Handle the case when adding an event returns a false. """
    user_input = input("The event could not be added. Would you like to (1) Schedule the meeting at a different time, (2) Provide more information about the meeting, or (3) Cancel the meeting? Enter 1, 2, or 3: ")
    if user_input == "1":
        new_start_time = input("Enter a new start time: ")
        new_end_time = input("Enter a new end time: ")
        return add_event(date, title, start_time, end_time)
    elif user_input == "2":
        additional_info = input("Provide more information about the meeting: ")
        return f"Meeting with additional info: {additional_info}"
    elif user_input == "3":
        return "The meeting has been canceled."
    else:
        return "Invalid input. The meeting has been canceled."

@tool
def ask_ai() -> str:
    """ ask the ai. """
    return "what day is it?"


@tool
def ask_human() -> str:
    """ Ask the user for input. """
    return input("Enter username: ")     




# Define the agents
tools = [calender_add_event]
tool_node = ToolNode(tools)

llm = ChatOpenAI(model="llama3.2", base_url="http://localhost:11434/v1", api_key='ollama')
llm = llm.bind_tools(tools)


def router(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    # If there is no function call, then we finish
    if "FINAL ANSWER" in last_message.content:
        return END
    # Otherwise if there is, we continue
    else:
        return "continue"

def event_agent(state: AgentState):
	pass

def call_model(state: MessagesState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


workflow = StateGraph(MessagesState)

# Define the two nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
# workflow.add_node("ask_human", tool_node)
workflow.add_node("select_tools", select_tools)

workflow.add_edge("select_tools", "agent")
workflow.add_edge(START, "select_tools")

# workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", router,     
    {
        "continue": "tools",
        END: END,
    },)
workflow.add_conditional_edges("tools", router,     
    {
        "continue": "agent",
        END: END,
    },)
# workflow.add_edge("tools", "agent")

memory = MemorySaver()


app = workflow.compile()

# Assuming graph.get_graph(xray=True) returns an object with a method draw_mermaid_png() that provides image data
image_data = app.get_graph(xray=True).draw_mermaid_png()
try:
    # Convert the image data to a BytesIO object
    image = Image.open(io.BytesIO(image_data))
    image.show()
except Exception as e:
    print("Failed to display the graph:", e)



current_date = datetime.now().strftime("%Y-%m-%d")
initial_input = {"messages": [("human", f"Today's date is {current_date}. Plan a 5-hour meeting with Client X on Tuesday afternoon.")]}
thread = {"configurable": {"thread_id": "1"}}

# input_message = HumanMessage(content=f"ask the ai")

events = app.stream(
	initial_input,
    # Maximum number of steps to take in the graph
    stream_mode="values"
)
for chunk in events:
    chunk["messages"][-1].pretty_print()

# for chunk in app.stream(initial_input, thread, stream_mode="values"):
#     chunk["messages"][-1].pretty_print()





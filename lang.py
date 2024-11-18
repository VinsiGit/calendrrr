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


@tool
def python_repl(code: Annotated[str, "The python code to execute to generate your chart."]):
    """Use this to execute python code. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user."""

    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = f"Successfully executed:\n```python\n{code}\n```\nStdout: {result}"
    return result_str + "\n\nIf you have completed all tasks, respond with FINAL ANSWER."

# Define the agents
llm = ChatOpenAI(model="llama3.2", base_url="http://localhost:11434/v1",api_key='ollama')

def create_agent(llm, tools, system_message: str):
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful AI assistant, collaborating with other assistants."
                " Use the provided tools to progress towards answering the question."
                " If you are unable to fully answer, that's OK, another assistant with different tools "
                " will help where you left off. Execute what you can to make progress."
                " If you or any of the other assistants have the final answer or deliverable,"
                " prefix your response with FINAL ANSWER so the team knows to stop."
                " You have access to the following tools: {tool_names}.\n{system_message}",
            ),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )
    prompt = prompt.partial(system_message=system_message)
    prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
    return prompt | llm.bind_tools(tools)

# Helper function to create a node for a given agent
def agent_node(state, agent, name):
    result = agent.invoke(state)
    print('active')

    # We convert the agent output into a format that is suitable to append to the global state
    if isinstance(result, ToolMessage):
        pass
    else:
        result = AIMessage(**result.dict(exclude={"type", "name"}), name=name)
    return {
        "messages": [result],
        # Since we have a strict workflow, we can
        # track the sender so we know who to pass to next.
        "sender": name,
    }


research_agent = create_agent(
    llm,
    [calender_add_event],
    system_message="You should provide accurate data for the chart_generator to use.",
)
research_node = functools.partial(agent_node, agent=research_agent, name="Researcher")

chart_agent = create_agent(
    llm,
    [python_repl],
    system_message="Any charts you display will be visible by the user.",
)
chart_node = functools.partial(agent_node, agent=chart_agent, name="chart_generator")
tool_node = functools.partial(agent_node, agent=research_agent, name="event_generator")

from langgraph.graph import END, StateGraph, START

# Define the workflow
def calender_add_event(date: str, title: str, start_time: str, end_time: str, time_zone='Etc/Greenwich') -> str:
    """Add an event to the calendar."""
    print('active')
    event = add_event(date, title, start_time, end_time)
    return event[1]

# Initialize the state
current_date = datetime.now().strftime("%Y-%m-%d")
with open('database/database.json', 'r') as file:
    data = json.load(file)

initial_state = {
    "messages": [HumanMessage(content=f"today its {current_date}. Add an event tomorrow with title 'Meeting with Team' from 11:00 to 15:00")],
    "sender": "user",
    "context_variables": {"location": "Belgium", "time": "12:00", "database": data}
}
def router(state):
    # This is the router
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        # The previous agent is invoking a tool
        return "event_generator"
    if "FINAL ANSWER" in last_message.content:
        # Any agent decided the work is done
        return END
    return "continue"


workflow = StateGraph(AgentState)

workflow.add_node("Researcher", research_node)
workflow.add_node("chart_generator", chart_node)
workflow.add_node("event_generator", tool_node)

workflow.add_conditional_edges(
    "Researcher",
    router,
    {"continue": "chart_generator", "event_generator": "event_generator", END: END},
)
workflow.add_conditional_edges(
    "chart_generator",
    router,
    {"continue": "Researcher", "event_generator": "event_generator", END: END},
)

workflow.add_conditional_edges(
    "event_generator",
    # Each agent node updates the 'sender' field
    # the tool calling node does not, meaning
    # this edge will route back to the original agent
    # who invoked the tool
    lambda x: x["sender"],
    {
        "Researcher": "Researcher",
        "chart_generator": "chart_generator",
    },
)
workflow.add_edge(START, "Researcher")
graph = workflow.compile()

from PIL import Image
import io

# Assuming graph.get_graph(xray=True) returns an object with a method draw_mermaid_png() that provides image data
image_data = graph.get_graph(xray=True).draw_mermaid_png()

try:
    # Convert the image data to a BytesIO object
    image = Image.open(io.BytesIO(image_data))
    image.show()
except Exception as e:
    print("Failed to display the graph:", e)

# Run the workflow
response = research_agent.invoke(initial_state)
print(response)

events = graph.stream(
    {
        "messages": [
            HumanMessage(
                content="Fetch the UK's GDP over the past 5 years,"
                " then draw a line graph of it."
                " Once you code it up, finish."
            )
        ],
    },
    # Maximum number of steps to take in the graph
    {"recursion_limit": 150},
)
for s in events:
    print(s)
    print("----")
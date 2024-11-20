from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, MessagesState, START, END

from PIL import Image
import io


@tool
def check_number(number,check):
    """check if the number is equal to the check number
	Args:
		number (str): the number
		check (str): check it

	Returns:
		str: if its true or false
	"""
    if number==check:
        print("test YES")
        return "yes"
    else:
        print("test No")
        return "no"
    

@tool
def add_number(number:int,number2:int) -> str:
    """ give your number this function will add number2 to your given number. """
    number=number + number2
    print("test")
    print(number)    
    print("test")

    return str(number)



# Define the agents
tools = [add_number,check_number]
tool_node = ToolNode(tools)

llm = ChatOpenAI(model="llama3.2", temperature=0, base_url="http://localhost:11434/v1", api_key='ollama')
llm = llm.bind_tools(tools)



# tool_node.invoke({"messages": [llm.invoke("add a number like 36")]})


def should_continue(state: MessagesState):
    messages = state["messages"]
    last_message = messages[-1]
    if last_message.tool_calls:
        return "tools"
    return END


def call_model(state: MessagesState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


workflow = StateGraph(MessagesState)

# Define the two nodes we will cycle between
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, ["tools", END])
workflow.add_edge("tools", "agent")

app = workflow.compile()

# # Assuming graph.get_graph(xray=True) returns an object with a method draw_mermaid_png() that provides image data
# image_data = app.get_graph(xray=True).draw_mermaid_png()
# try:
#     # Convert the image data to a BytesIO object
#     image = Image.open(io.BytesIO(image_data))
#     image.show()
# except Exception as e:
#     print("Failed to display the graph:", e)

chat_input="you have to use all tools given. use the function add_number, input the number 36 and give me the result in one word! You have to check if you have it correct with the check_number function to see if you got it correct"
chat_input2="add a number like 157 and a number of your choise and use the function twice to get the result"

for chunk in app.stream(
    {"messages": [("human", chat_input2)]}, 
    stream_mode="values"
):
    chunk["messages"][-1].pretty_print()








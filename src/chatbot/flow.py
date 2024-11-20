from tkinter import END
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from src.chatbot.memory import memory
from src.chatbot.tools import (
    fetch_user_flight_information,
    search_flights,
    update_ticket_to_new_flight,
    cancel_ticket,
    lookup_policy,
    search_car_rentals,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
    search_hotels,
    book_hotel,
    update_hotel,
    cancel_hotel,
    search_trip_recommendations,
    book_excursion,
    update_excursion,
    cancel_excursion
)
from src.chatbot.prompts import primary_assistant_prompt
from langchain_groq import ChatGroq
from langchain_core.runnables import RunnableConfig, Runnable
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing_extensions import TypedDict
from typing import Annotated
from langgraph.graph.message import AnyMessage, add_messages
from src.chatbot.tools import create_tool_node_with_fallback
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from config.config import Config
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.checkpoint.memory import MemorySaver
from typing import Optional, Literal

def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """Push or pop the state."""
    if right is None:
        return left
    if right == "pop":
        return left[:-1]
    return left + [right]

class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: str
    dialog_state: Annotated[
        list[
            Literal[
                "assistant",
                "update_flight",
                "book_car_rental",
                "book_hotel",
                "book_excursion",
            ]
        ],
        update_dialog_stack,
    ]

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                state["messages"].append(("assistant", result.content))
                break
        return {"messages": state["messages"]}

# Initialize LLM
llm = ChatGroq(
    model="mixtral-8x7b-32768",
    temperature=0.5,
    api_key=Config.GROQ_API_KEY
)

# Make sure primary_assistant_prompt is properly defined
primary_assistant_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a helpful travel assistant. You can help with flights, hotels, car rentals, and excursions."
        "\nCurrent user flight information:\n{user_info}"
    ),
    MessagesPlaceholder(variable_name="messages"),
])

# Define tools first
primary_assistant_tools = [
    TavilySearchResults(max_results=1),
    lookup_policy,
    search_flights,
    fetch_user_flight_information,
    update_ticket_to_new_flight,
    cancel_ticket,
    search_car_rentals,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
    search_hotels,
    book_hotel,
    update_hotel,
    cancel_hotel,
    search_trip_recommendations,
    book_excursion,
    update_excursion,
    cancel_excursion,
]

# Then initialize the runnable
primary_assistant_runnable = primary_assistant_prompt | llm.bind_tools(primary_assistant_tools)

# Safe (read-only) tools
safe_tools = [
    TavilySearchResults(max_results=1),
    fetch_user_flight_information,
    search_flights,
    lookup_policy,
    search_car_rentals,
    search_hotels,
    search_trip_recommendations,
]

# Sensitive (data-modifying) tools
sensitive_tools = [
    update_ticket_to_new_flight,
    cancel_ticket,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
    book_hotel,
    update_hotel,
    cancel_hotel,
    book_excursion,
    update_excursion,
    cancel_excursion,
]

sensitive_tool_names = {t.name for t in sensitive_tools}

builder = StateGraph(State)

def user_info(state: State):
    config = state.get("config", {})
    passenger_id = config.get("configurable", {}).get("passenger_id")
    
    if not passenger_id:
        return {"user_info": "No user information available"}
        
    return {
        "user_info": fetch_user_flight_information.invoke({
            "configurable": {"passenger_id": passenger_id}
        })
    }

def route_tools(state: State):
    next_node = tools_condition(state)
    if next_node == END:
        return END
    ai_message = state["messages"][-1]
    first_tool_call = ai_message.tool_calls[0]
    if first_tool_call["name"] in sensitive_tool_names:
        return "sensitive_tools"
    return "safe_tools"

# Add nodes
builder.add_node("fetch_user_info", user_info)
builder.add_node("primary_assistant", Assistant(primary_assistant_runnable))
builder.add_node("safe_tools", create_tool_node_with_fallback(safe_tools))
builder.add_node("sensitive_tools", create_tool_node_with_fallback(sensitive_tools))
builder.add_node(
    "primary_assistant_tools", 
    create_tool_node_with_fallback(primary_assistant_tools)
)

# Add edges
builder.add_edge(START, "fetch_user_info")
builder.add_edge("fetch_user_info", "primary_assistant")
builder.add_conditional_edges(
    "primary_assistant",
    route_tools,
    ["safe_tools", "sensitive_tools", END]
)
builder.add_edge("safe_tools", "primary_assistant")
builder.add_edge("sensitive_tools", "primary_assistant")

# Assistant prompts for each specialized workflow
flight_booking_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a specialized assistant for handling flight updates. "
        "The primary assistant delegates work to you whenever the user needs help updating their bookings. "
        "Confirm the updated flight details with the customer and inform them of any additional fees. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "\n\nCurrent user flight information:\n<Flights>\n{user_info}\n</Flights>"
        "\nCurrent time: {time}."
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now)

book_hotel_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a specialized assistant for handling hotel bookings. "
        "Search for available hotels based on the user's preferences and confirm the booking details. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "\nCurrent time: {time}."
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now)

book_car_rental_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a specialized assistant for handling car rental bookings. "
        "Search for available car rentals based on the user's preferences and confirm the booking details. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "\nCurrent time: {time}."
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now)

book_excursion_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a specialized assistant for handling trip recommendations. "
        "Search for available trip recommendations based on the user's preferences and confirm the booking details. "
        "When searching, be persistent. Expand your query bounds if the first search returns no results. "
        "\nCurrent time: {time}."
    ),
    ("placeholder", "{messages}"),
]).partial(time=datetime.now)

# Create specialized runnables
update_flight_runnable = flight_booking_prompt | llm.bind_tools(safe_tools + sensitive_tools)
book_hotel_runnable = book_hotel_prompt | llm.bind_tools(safe_tools + sensitive_tools)
book_car_rental_runnable = book_car_rental_prompt | llm.bind_tools(safe_tools + sensitive_tools)
book_excursion_runnable = book_excursion_prompt | llm.bind_tools(safe_tools + sensitive_tools)

# Add specialized workflow nodes
from src.chatbot.graph_builder import (
    build_specialized_workflow,
    pop_dialog_state,
    route_to_workflow,
    route_primary_assistant
)

# Build specialized workflows
build_specialized_workflow(
    builder=builder,
    name="update_flight",
    runnable=update_flight_runnable,
    safe_tools=safe_tools,
    sensitive_tools=sensitive_tools
)

build_specialized_workflow(
    builder=builder,
    name="book_hotel",
    runnable=book_hotel_runnable,
    safe_tools=safe_tools,
    sensitive_tools=sensitive_tools
)

build_specialized_workflow(
    builder=builder,
    name="book_car_rental",
    runnable=book_car_rental_runnable,
    safe_tools=safe_tools,
    sensitive_tools=sensitive_tools
)

build_specialized_workflow(
    builder=builder,
    name="book_excursion",
    runnable=book_excursion_runnable,
    safe_tools=safe_tools,
    sensitive_tools=sensitive_tools
)

# Add leave_skill node
builder.add_node("leave_skill", pop_dialog_state)
builder.add_edge("leave_skill", "primary_assistant")

# Update routing edges
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        "enter_update_flight",
        "enter_book_car_rental",
        "enter_book_hotel",
        "enter_book_excursion",
        "primary_assistant_tools",
        "safe_tools",
        "sensitive_tools",
        END,
    ]
)

builder.add_edge("primary_assistant_tools", "primary_assistant")
builder.add_conditional_edges("fetch_user_info", route_to_workflow)

# Compile the final graph
part_4_graph = builder.compile(
    checkpointer=memory,
    interrupt_before=[
        "update_flight_sensitive_tools",
        "book_car_rental_sensitive_tools",
        "book_hotel_sensitive_tools",
        "book_excursion_sensitive_tools",
    ]
)

# Export the graph for use in the API
graph = part_4_graph

def route_primary_assistant(state: State):
    """Routes the primary assistant's actions."""
    route = tools_condition(state)
    if route == END:
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    if not tool_calls:
        return END
        
    tool_name = tool_calls[0]["name"]
    
    # Routing map for specialized assistants
    routing_map = {
        "ToFlightBookingAssistant": "enter_update_flight",
        "ToBookCarRental": "enter_book_car_rental",
        "ToHotelBookingAssistant": "enter_book_hotel",
        "ToBookExcursion": "enter_book_excursion"
    }
    
    if tool_name in routing_map:
        return routing_map[tool_name]
    
    # Check if tool is sensitive or safe
    if tool_name in sensitive_tool_names:
        return "sensitive_tools"
    return "safe_tools"

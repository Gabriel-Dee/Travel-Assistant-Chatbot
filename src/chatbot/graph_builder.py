from typing import Callable, List, Literal
from langchain_core.messages import ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import tools_condition
from src.chatbot.tools import create_tool_node_with_fallback, CompleteOrEscalate
from typing_extensions import TypedDict
from langchain_core.runnables import Runnable
from src.chatbot.flow import State, Assistant

def create_entry_node(assistant_name: str, new_dialog_state: str) -> Callable:
    """Creates an entry node for a specialized workflow."""
    def entry_node(state: State) -> dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"The assistant is now the {assistant_name}. Reflect on the above conversation between the host assistant and the user."
                    f" The user's intent is unsatisfied. Use the provided tools to assist the user. Remember, you are {assistant_name},"
                    " and the booking, update, or other action is not complete until after you have successfully invoked the appropriate tool."
                    " If the user changes their mind or needs help for other tasks, call the CompleteOrEscalate function to let the primary host assistant take control."
                    " Do not mention who you are - just act as the proxy for the assistant.",
                    tool_call_id=tool_call_id,
                )
            ],
            "dialog_state": new_dialog_state,
        }
    return entry_node

def pop_dialog_state(state: State) -> dict:
    """Pop the dialog stack and return to the main assistant."""
    messages = []
    if state["messages"][-1].tool_calls:
        messages.append(
            ToolMessage(
                content="Resuming dialog with the host assistant. Please reflect on the past conversation and assist the user as needed.",
                tool_call_id=state["messages"][-1].tool_calls[0]["id"],
            )
        )
    return {
        "dialog_state": "pop",
        "messages": messages,
    }

def create_routing_function(safe_tools: List, workflow_name: str) -> Callable:
    """Creates a routing function for a specialized workflow."""
    def route_workflow(state: State):
        route = tools_condition(state)
        if route == END:
            return END
        
        tool_calls = state["messages"][-1].tool_calls
        did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)
        
        if did_cancel:
            return "leave_skill"
            
        safe_toolnames = [t.name for t in safe_tools]
        if all(tc["name"] in safe_toolnames for tc in tool_calls):
            return f"{workflow_name}_safe_tools"
            
        return f"{workflow_name}_sensitive_tools"
    
    return route_workflow

def build_specialized_workflow(
    builder: StateGraph,
    name: str,
    runnable: Runnable,
    safe_tools: list,
    sensitive_tools: list
):
    """Builds a specialized workflow with safe and sensitive tools."""
    
    # Add entry node
    builder.add_node(
        f"enter_{name}",
        create_entry_node(f"{name.replace('_', ' ').title()} Assistant", name)
    )
    
    # Add main assistant node
    builder.add_node(name, Assistant(runnable))
    builder.add_edge(f"enter_{name}", name)
    
    # Add tool nodes
    builder.add_node(
        f"{name}_safe_tools",
        create_tool_node_with_fallback(safe_tools)
    )
    builder.add_node(
        f"{name}_sensitive_tools",
        create_tool_node_with_fallback(sensitive_tools)
    )
    
    # Add routing logic
    routing_function = create_routing_function(safe_tools, name)
    
    # Add edges
    builder.add_edge(f"{name}_sensitive_tools", name)
    builder.add_edge(f"{name}_safe_tools", name)
    builder.add_conditional_edges(
        name,
        routing_function,
        [
            f"{name}_safe_tools",
            f"{name}_sensitive_tools",
            "leave_skill",
            END
        ]
    )

def route_to_workflow(state: State) -> Literal[
    "primary_assistant",
    "update_flight",
    "book_car_rental",
    "book_hotel",
    "book_excursion"
]:
    """Routes to the appropriate workflow based on dialog state."""
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"
    return dialog_state[-1]

def route_primary_assistant(state: State):
    """Routes the primary assistant's actions."""
    route = tools_condition(state)
    if route == END:
        return END
        
    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        tool_name = tool_calls[0]["name"]
        routing_map = {
            "ToFlightBookingAssistant": "enter_update_flight",
            "ToBookCarRental": "enter_book_car_rental",
            "ToHotelBookingAssistant": "enter_book_hotel",
            "ToBookExcursion": "enter_book_excursion"
        }
        
        if tool_name in routing_map:
            return routing_map[tool_name]
            
        return "primary_assistant_tools"
        
    raise ValueError("Invalid route")
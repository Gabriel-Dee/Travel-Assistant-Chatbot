from langchain_core.messages import ToolMessage
from typing import Optional

def handle_user_interaction(graph, event, config: dict) -> Optional[dict]:
    """Handle user interaction for tool approval."""
    snapshot = graph.get_state(config)
    
    while snapshot.next:
        try:
            user_input = input(
                "Do you approve of the above actions? Type 'y' to continue; "
                "otherwise, explain your requested changes.\n\n"
            )
        except:
            user_input = "y"
            
        if user_input.strip().lower() == "y":
            result = graph.invoke(None, config)
        else:
            result = graph.invoke(
                {
                    "messages": [
                        ToolMessage(
                            tool_call_id=event["messages"][-1].tool_calls[0]["id"],
                            content=f"API call denied by user. Reasoning: '{user_input}'. "
                                   f"Continue assisting, accounting for the user's input.",
                        )
                    ]
                },
                config,
            )
        
        snapshot = graph.get_state(config)
        
    return result
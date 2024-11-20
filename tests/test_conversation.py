import uuid
from src.chatbot.flow import part_4_graph  # Changed from part_1_graph

def test_conversation_flow():
    tutorial_questions = [
        "Hi there, what time is my flight?",
        "Update my flight to next week",
    ]

    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "passenger_id": "3442 587242",
            "thread_id": thread_id,
        }
    }

    for question in tutorial_questions:
        events = part_4_graph.stream(  # Changed from part_1_graph
            {"messages": ("user", question)}, 
            config, 
            stream_mode="values"
        )
        # Verify events are generated
        assert any(event.get("messages") for event in events)

def test_specialized_workflows():
    questions = [
        "Update my flight to next week",
        "Book a hotel in Zurich",
        "I need a car rental"
    ]
    
    config = {
        "configurable": {
            "passenger_id": "3442 587242",
            "thread_id": str(uuid.uuid4()),
        }
    }

    for question in questions:
        events = part_4_graph.stream(  # Changed from graph to part_4_graph
            {"messages": ("user", question)}, 
            config,
            stream_mode="values"
        )
        assert any(event.get("messages") for event in events)
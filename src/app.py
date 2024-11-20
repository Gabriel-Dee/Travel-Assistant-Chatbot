from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from src.chatbot.flow import part_4_graph
from src.utils.logger import logger
from pydantic import BaseModel
from typing import List, Dict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from src.utils.db_init import initialize_database
import uuid
from src.chatbot.interaction import handle_user_interaction

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    config: Dict = {}

class ChatResponse(BaseModel):
    messages: List[Dict]

def serialize_message(message: BaseMessage) -> Dict:
    """Convert a LangChain message object to a serializable dictionary."""
    if not message.content and not message.additional_kwargs:
        return None
        
    return {
        "type": message.type,
        "content": message.content or "",
        "additional_kwargs": message.additional_kwargs or {}
    }

@app.get("/")
def read_root():
    return {"message": "Welcome to the Travel Assistant Chatbot"}

@app.post("/chat")
async def chat(request: ChatRequest):
    config = {
        "configurable": {
            "passenger_id": request.config.get("passenger_id", ""),
            "thread_id": str(uuid.uuid4()),
        }
    }
    
    # Initialize state with just the user's message
    initial_state = {
        "messages": [
            HumanMessage(content=request.message)
        ]
    }
    
    events = part_4_graph.stream(
        initial_state, 
        config, 
        stream_mode="values"
    )
    
    messages = []
    for event in events:
        if event.get("messages"):
            # Only add new messages that aren't already in our list
            new_messages = [
                serialize_message(msg) 
                for msg in event["messages"] 
                if isinstance(msg, (AIMessage, ToolMessage))  # Only include AI and Tool messages
            ]
            if new_messages:
                messages.extend(new_messages)
            
        # Check if we're at a sensitive tool
        snapshot = part_4_graph.get_state(config)
        if snapshot and snapshot.next == "sensitive_tools":
            result = handle_user_interaction(part_4_graph, event, config)
            if result and result.get("messages"):
                messages.extend(
                    serialize_message(msg) 
                    for msg in result["messages"]
                    if isinstance(msg, (AIMessage, ToolMessage))  # Only include AI and Tool messages
                )
    
    # If no AI messages were generated, add an error message
    if not any(msg["type"] == "ai" for msg in messages):
        messages.append({
            "type": "ai",
            "content": "I apologize, but I'm having trouble processing your request. Could you please try again?",
            "additional_kwargs": {}
        })
    
    return ChatResponse(messages=messages)

if __name__ == "__main__":
    import uvicorn
    # Initialize database before starting the app
    initialize_database()
    uvicorn.run(app, host="0.0.0.0", port=8000)

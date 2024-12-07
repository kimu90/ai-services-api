from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from ...utils.message_handler import MessageHandler
from ...utils.llm_manager import GeminiLLMManager

# Rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    timestamp: datetime

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Initialize managers
llm_manager = GeminiLLMManager()
message_handler = MessageHandler(llm_manager)

# Store last response for GET endpoint
last_response = None

@router.post("/")
@limiter.limit("5/minute")
async def chat_with_model(
    request: Request,
    chat_request: ChatRequest,
    background_tasks: BackgroundTasks
):
    """
    Handle chat requests and return responses.
    
    Args:
        request: FastAPI request object
        chat_request: The chat request containing the query
        background_tasks: FastAPI background tasks handler
    
    Returns:
        JSON response containing the chatbot's response
    """
    global last_response
    
    try:
        # Initialize response collection
        response_parts = []
        
        # Process message with streaming
        async for part in message_handler.send_message_async(
            chat_request.query,
            conversation_id=chat_request.conversation_id,
            context=chat_request.context
        ):
            if isinstance(part, bytes):
                part = part.decode('utf-8')
            response_parts.append(part)
        
        # Combine response parts
        complete_response = ''.join(response_parts)
        last_response = complete_response
        
        return ChatResponse(
            response=complete_response,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/last-response")
async def get_last_chat_response():
    """
    Retrieve the last chat response.
    
    Returns:
        JSON response containing the last chatbot response
    """
    global last_response
    
    try:
        if last_response is None:
            raise HTTPException(
                status_code=404,
                detail="No response available"
            )
            
        return ChatResponse(
            response=last_response,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/flush-cache/{conversation_id}")
async def flush_conversation_cache(conversation_id: str):
    """
    Clear the conversation history for a specific conversation.
    
    Args:
        conversation_id: The ID of the conversation to clear
        
    Returns:
        JSON response indicating success
    """
    try:
        await message_handler.flush_conversation_cache(conversation_id)
        return {"status": "success", "message": "Conversation cache cleared"}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear conversation cache: {str(e)}"
        )
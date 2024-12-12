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
    user_id: str
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None
    context: Optional[dict] = None

class ChatResponse(BaseModel):
    response: str
    timestamp: datetime
    user_id: str
    session_id: Optional[str]

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
    global last_response
    
    try:
        response_parts = []
        
        async for part in message_handler.send_message_async(
            chat_request.query,
            user_id=chat_request.user_id,
            session_id=chat_request.session_id,
            conversation_id=chat_request.conversation_id,
            context=chat_request.context
        ):
            if isinstance(part, bytes):
                part = part.decode('utf-8')
            response_parts.append(part)
        
        complete_response = ''.join(response_parts)
        last_response = {
            'response': complete_response,
            'user_id': chat_request.user_id,
            'session_id': chat_request.session_id
        }
        
        return ChatResponse(
            response=complete_response,
            timestamp=datetime.now(),
            user_id=chat_request.user_id,
            session_id=chat_request.session_id
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

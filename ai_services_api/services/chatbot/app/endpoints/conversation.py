from fastapi import APIRouter, HTTPException
from ai_services_api.services.chatbot.schemas import ChatRequest
from ai_services_api.services.chatbot.utils.message_handler import MessageHandler
from ai_services_api.services.chatbot.utils.llm_manager import GeminiLLMManager

router = APIRouter()

llm_manager = GeminiLLMManager()
message_handler = MessageHandler(llm_manager)

# Variable to store the last response
last_response = None

@router.post("/")  # This defines the POST endpoint
async def chat_with_model(chat_request: ChatRequest):
    global last_response
    try:
        # Get the user's query from the request
        message = chat_request.query

        # Initialize a list to collect response parts
        response_parts = []

        # Collect responses from the async generator
        async for part in message_handler.send_message_async(message):
            # Decode each part if it's in bytes
            if isinstance(part, bytes):
                part = part.decode('utf-8')
            response_parts.append(part)

        last_response = ''.join(response_parts)
        return {"response": last_response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")  # This defines the GET endpoint
async def get_last_chat_response():
    global last_response
    try:
        if last_response is None:
            raise HTTPException(status_code=404, detail="No response available")
        return {"response": last_response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

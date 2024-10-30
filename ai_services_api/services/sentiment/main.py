# app/services/chatbot/main.py
from fastapi import APIRouter

# Create a router for chatbot routes
sentiment_router = APIRouter()

@sentiment_router.get("/sentiment")
async def sentiment_endpoint():
    return {"message": "This is the sentiment endpoint"}

# Add more chatbot-related routes as needed
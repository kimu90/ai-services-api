from fastapi import APIRouter

# Create a router for chatbot routes
content_router = APIRouter()

@content_router.get("/content")
async def content_endpoint():
    return {"message": "This is the chatbot endpoint"}

# Add more chatbot-related routes as needed
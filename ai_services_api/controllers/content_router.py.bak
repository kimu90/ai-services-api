from fastapi import APIRouter
from ai_services_api.services.content.app.endpoints import content

api_router = APIRouter()

# Include the conversation router
api_router.include_router(
    content.router,
    prefix="/content",  # Prefix for conversation endpoints
    tags=["content"]  # Tag for documentation
)

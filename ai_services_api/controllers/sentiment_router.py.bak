# In app/controllers/sentiment_router.py

from fastapi import APIRouter
from ai_services_api.services.sentiment.app.endpoints import sentiment

api_router = APIRouter()

# Include the analyze router
api_router.include_router(
    sentiment.router,
    prefix="/sentiment",  # Prefix for sentiment analysis endpoints
    tags=["sentiment"]  # Tag for documentation
)

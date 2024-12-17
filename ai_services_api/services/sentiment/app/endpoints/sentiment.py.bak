from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
from ai_services_api.services.sentiment.utils.sentimentlogic import SentimentLogic  # Adjust this import as needed
from ai_services_api.services.sentiment.schemas import ChatRequest

# Define the FastAPI application
router = APIRouter()
# Define a Pydantic model for the input


# Instantiate the SentimentLogic class
sentiment_logic = SentimentLogic()

# Create a router for sentiment analysis
router = APIRouter()

@router.post("/sentiment")
async def analyze_sentiment(chat_request: ChatRequest):
    try:
        # Extract the text from the request
        feedback = chat_request.query

        # Call the sentiment analysis method
        sentiment_result = await sentiment_logic.analyze_sentiment(feedback)

        # Return the sentiment result as JSON
        return {"sentiment": sentiment_result}

    except Exception as e:
        # Handle any errors and return a 500 response with the error message
        raise HTTPException(status_code=500, detail=str(e))




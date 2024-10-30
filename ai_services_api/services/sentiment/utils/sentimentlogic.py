
import os
import asyncio
from pydantic import BaseModel
from typing import AsyncIterable, List
import logging
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain.memory import ConversationBufferWindowMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.callbacks import AsyncIteratorCallbackHandler
import redis  # Using synchronous Redis
from dotenv import load_dotenv
from typing import AsyncIterable, List


class SentimentLogic:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = self.get_gemini_model()

    def get_gemini_model(self):
        model = ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            stream=True,
            model="gemini-pro",
            callbacks=[]  # Add any callbacks if needed
        )
        return model

    async def analyze_sentiment(self, feedback: str) -> str:
        prompt = f"Analyze the sentiment of the following text and respond with either 'positive', 'negative', or 'neutral'.\nText: {user_input}"
        human_message = HumanMessage(content=prompt)
        response = await asyncio.to_thread(self.model.invoke, [human_message])

        if hasattr(response, 'content'):
            sentiment_result = response.content.strip()
        else:
            sentiment_result = "No valid response received."

        return sentiment_result

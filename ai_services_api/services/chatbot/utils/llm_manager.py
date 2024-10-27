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

# Load environment variables from the .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load your embedding model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

class GeminiLLMManager:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        # Change this line to connect using the service name
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379")  # Use 'redis' as the hostname
        self.callback = AsyncIteratorCallbackHandler()

        # Initialize Redis
        self.redis_client = redis.StrictRedis.from_url(self.redis_url, decode_responses=True)


    def query_redis_data(self, query_vector, top_n=3, threshold=0.5) -> List[str]:
        """Fetch multiple relevant data points from Redis based on the user query vector."""
        try:
            keys = self.redis_client.keys("embedding:*")
            scores = []

            for key in keys:
                embedding_str = self.redis_client.hget(key, "embedding")
                if embedding_str is None:
                    logger.warning(f"No embedding found for key: {key.decode()}")
                    continue

                embedding = np.array(json.loads(embedding_str))

                # Calculate cosine similarity
                score = np.dot(embedding, query_vector) / (np.linalg.norm(embedding) * np.linalg.norm(query_vector))
                text = self.redis_client.hget(key, "text")
                scores.append((score, text))

            # Sort by score and select the top N above the threshold
            scores.sort(key=lambda x: x[0], reverse=True)
            return [text.decode() for score, text in scores if score >= threshold][:top_n]

        except redis.RedisError as e:
            logger.error(f"Error accessing Redis: {e}")
            return []

    def create_memory(self):
        """Create memory without session handling."""
        return ConversationBufferWindowMemory(max_token_limit=4000)

    def get_gemini_model(self):
        model = ChatGoogleGenerativeAI(
            google_api_key=self.api_key,
            stream=True,
            model="gemini-pro",
            convert_system_message_to_human=True,
            callbacks=[self.callback],
        )
        return model

    async def generate_async_response(self, message: str) -> AsyncIterable[str]:
        model = self.get_gemini_model()
        memory = self.create_memory()
        chat_memory = memory.load_memory_variables({})
        history = chat_memory.get("chat_history", [])

        # Convert the message into a vector
        query_vector = self.get_vector_from_message(message)

        # Query multiple scraped data from Redis
        scraped_responses = self.query_redis_data(query_vector)

        # Prepare message list
        message_list = [
            SystemMessage(content=os.getenv("SYSTEM_INSTRUCTION", 
                "I am a bot that gives responses based on APHRC only and don't answer questions generally but rather in the context of aphrc.org."))
        ]
        if history:
            message_list += history

        message_list.append(HumanMessage(content=message))

        # Append the scraped responses if available
        if scraped_responses:
            for response in scraped_responses:
                # Clean response by removing newlines and formatting links
                formatted_response = self.format_response(response)
                message_list.append(HumanMessage(content=formatted_response))

        response = ""
        max_response_length = 500  # Set your desired max length

        async for token in model.astream(input=message_list):
            response += f"{repr(token.content)}"
            if len(response) >= max_response_length:
                break  # Stop once you reach the max length
            yield f"{repr(token.content)}".encode("utf-8", errors="replace")

        await self.add_conversation_to_memory(message, response)

    def format_response(self, response: str) -> str:
        """Format the response to remove newlines and make links clickable, while cleaning up Markdown."""
        # Replace newlines with spaces
        cleaned_response = response.replace('\n', ' ').replace('\r', ' ')
        
        # Remove Markdown indicators like ** and *
        cleaned_response = cleaned_response.replace('**', '').replace('*', '').strip()

        # Convert plain text URLs to clickable HTML links
        formatted_response = self.make_links_clickable(cleaned_response)

        # Optionally, wrapping formatted response in paragraph tags
        return f"<p>{formatted_response}</p>"

    def make_links_clickable(self, text: str) -> str:
        """Convert plain text URLs to clickable HTML links."""
        import re
        url_pattern = r'(https?://[^\s]+)'
        return re.sub(url_pattern, r'<a href="\1">\1</a>', text)

    def get_vector_from_message(self, message: str):
        """Convert a message to a vector using a pre-trained model."""
        vector = embedding_model.encode(message).tolist()  # Convert to a list

        # Check if the length of the vector is correct
        if len(vector) != 384:
            logger.warning(f"Vector length is {len(vector)}, expected 384.")
            raise ValueError(f"Vector length is {len(vector)}, expected 384.")

        logger.debug(f"Generated vector: {vector} with length: {len(vector)}")
        return vector

# Example usage
if __name__ == "__main__":
    import asyncio

    async def main():
        message = "Where can I get publications?"
        manager = GeminiLLMManager()
        async for response in manager.generate_async_response(message):
            print(response.decode("utf-8", errors="replace"))

    asyncio.run(main())

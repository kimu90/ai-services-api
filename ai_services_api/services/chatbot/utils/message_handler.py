import logging
from typing import AsyncIterable, Optional, Dict
from .llm_manager import GeminiLLMManager

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, llm_manager: GeminiLLMManager):
        self.llm_manager = llm_manager
        
    async def send_message_async(
        self, 
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> AsyncIterable[str]:
        """
        Sends the user message to the LLM and streams the response asynchronously.
        
        Args:
            message: The user input message
            conversation_id: Optional ID to track conversation history
            context: Optional additional context
            
        Returns:
            Async generator that yields response tokens from the LLM
        """
        try:
            async for token in self.llm_manager.generate_async_response(message):
                yield token
                
        except Exception as e:
            logger.error(f"Error in send_message_async: {e}")
            error_message = "I apologize, but I encountered an error. Please try again."
            yield error_message.encode("utf-8", errors="replace")
    
    async def flush_conversation_cache(self, conversation_id: str):
        """
        Clears the conversation history stored in the memory.
        
        Args:
            conversation_id: The unique identifier for the conversation
        """
        try:
            memory = self.llm_manager.create_memory()
            memory.clear()
            logger.info(f"Successfully flushed conversation cache for ID: {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error while flushing conversation cache for ID {conversation_id}: {e}")
            raise RuntimeError("Failed to clear conversation history.") from e
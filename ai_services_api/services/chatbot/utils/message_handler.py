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
        user_id: str,
        session_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> AsyncIterable[str]:
        """
        Sends the user message to the LLM and streams the response asynchronously.
        
        Args:
            message: The user input message
            user_id: The unique identifier for the user
            session_id: Optional ID for the current session
            conversation_id: Optional ID to track conversation history
            context: Optional additional context
            
        Returns:
            Async generator that yields response tokens from the LLM
        """
        try:
            # Generate response using only the message parameter
            async for token in self.llm_manager.generate_async_response(message):
                # Ensure token is string, not bytes
                if isinstance(token, bytes):
                    token = token.decode('utf-8', errors='replace')
                yield token
                
        except Exception as e:
            logger.error(f"Error in send_message_async: {e}", exc_info=True)
            error_message = "I apologize, but I encountered an error. Please try again."
            yield error_message
    
    async def flush_conversation_cache(self, conversation_id: str):
        """
        Clears the conversation history stored in the memory.
        
        Args:
            conversation_id: The unique identifier for the conversation
        
        Raises:
            RuntimeError: If clearing the conversation history fails
        """
        try:
            memory = self.llm_manager.create_memory()
            memory.clear()
            logger.info(f"Successfully flushed conversation cache for ID: {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error while flushing conversation cache for ID {conversation_id}: {e}")
            raise RuntimeError(f"Failed to clear conversation history: {str(e)}")

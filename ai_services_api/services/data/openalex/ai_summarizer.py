import os
import logging
import google.generativeai as genai
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class TextSummarizer:
    def __init__(self):
        """Initialize the TextSummarizer with Gemini model."""
        self.model = self._setup_gemini()
        logger.info("TextSummarizer initialized successfully")

    def _setup_gemini(self):
        """Set up and configure the Gemini model."""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable is not set")
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini model setup completed")
            return model
            
        except Exception as e:
            logger.error(f"Error setting up Gemini model: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def summarize(self, title: str, abstract: str) -> Optional[str]:
        """
        Generate a summary of the title and abstract using Gemini.
        
        Args:
            title: Title of the publication
            abstract: Abstract of the publication
            
        Returns:
            str: Generated summary or fallback message if summarization fails
        """
        try:
            if not abstract or abstract.strip() == "N/A":
                logger.warning("No abstract available for summarization")
                return "No abstract available for summarization"

            # Prepare prompt
            prompt = self._create_prompt(title, abstract)
            
            # Generate summary
            response = self.model.generate_content(prompt)
            summary = response.text.strip()
            
            if not summary:
                logger.warning("Generated summary is empty")
                return "Failed to generate meaningful summary"
            
            # Clean and format summary
            cleaned_summary = self._clean_summary(summary)
            logger.info(f"Successfully generated summary for: {title[:100]}...")
            return cleaned_summary

        except Exception as e:
            logger.error(f"Error in summarization: {e}")
            return "Failed to generate summary due to technical issues"

    def _create_prompt(self, title: str, abstract: str) -> str:
        """
        Create a prompt for the summarization model.
        
        Args:
            title: Title of the publication
            abstract: Abstract of the publication
            
        Returns:
            str: Formatted prompt
        """
        return f"""
        Please create a concise summary combining the following title and abstract.
        
        Title: {title}
        
        Abstract: {abstract}
        
        Instructions:
        1. Provide a clear and concise summary in 2-3 sentences
        2. Focus on the main research findings and implications
        3. Use academic but accessible language
        4. Keep the summary under 200 words
        5. Retain technical terms and key concepts
        6. Begin directly with the summary, do not include phrases like "This paper" or "This research"
        """

    def _clean_summary(self, summary: str) -> str:
        """
        Clean and format the generated summary.
        
        Args:
            summary: Raw summary from the model
            
        Returns:
            str: Cleaned summary
        """
        try:
            # Basic cleaning
            cleaned = summary.strip()
            cleaned = ' '.join(cleaned.split())  # Normalize whitespace
            
            # Remove common prefixes if present
            prefixes = [
                'Summary:', 
                'Here is a summary:', 
                'The summary is:', 
                'Here is a concise summary:',
                'This paper',
                'This research',
                'This study'
            ]
            
            lower_cleaned = cleaned.lower()
            for prefix in prefixes:
                if lower_cleaned.startswith(prefix.lower()):
                    cleaned = cleaned[len(prefix):].strip()
                    break
            
            # Ensure the summary starts with a capital letter
            if cleaned:
                cleaned = cleaned[0].upper() + cleaned[1:]
            
            # Add a period at the end if missing
            if cleaned and cleaned[-1] not in ['.', '!', '?']:
                cleaned += '.'
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning summary: {e}")
            return summary

    def __del__(self):
        """Cleanup any resources."""
        try:
            # Add any cleanup code if needed
            pass
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
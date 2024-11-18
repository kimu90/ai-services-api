from gemini import GeminiClient
from ai_services_api.services.search.config import get_settings

settings = get_settings()

class AIPredictor:
    def __init__(self):
        self.client = GeminiClient(api_key=settings.GEMINI_API_KEY)  # Replace with appropriate Gemini API key retrieval
        self.last_embedding = None
        self.last_response = None
        
    def predict_completion(self, text: str) -> Tuple[str, float]:
        # Assuming Gemini's completion API usage is similar to OpenAI's
        response = self.client.completions.create(
            model="gemini-turbo",
            messages=[
                {"role": "system", "content": "Predict the likely completion of this user message."},
                {"role": "user", "content": text}
            ]
        )
        completion = response.choices[0].message.content
        
        # Get completion likelihood
        likelihood_response = self.client.completions.create(
            model="gemini-turbo",
            messages=[
                {"role": "system", "content": "Rate the likelihood (0-100) that this message needs completion."},
                {"role": "user", "content": text}
            ]
        )
        likelihood = float(likelihood_response.choices[0].message.content)
        
        return completion, likelihood

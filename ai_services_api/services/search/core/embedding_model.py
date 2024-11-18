import torch
from transformers import DistilBertTokenizer, DistilBertModel
from ai_services_api.services.search.config import get_settings

settings = get_settings()

class EmbeddingModel:
    def __init__(self):
        self.tokenizer = DistilBertTokenizer.from_pretrained(settings.MODEL_PATH)
        self.model = DistilBertModel.from_pretrained(settings.MODEL_PATH)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
    def get_embedding(self, text: str, pooling: str = 'mean') -> np.ndarray:
        input_ids = self.tokenizer.encode(text, return_tensors="pt", truncation=True)
        input_ids = input_ids.to(self.device)
        
        with torch.no_grad():
            output = self.model(input_ids)
            
        if pooling == 'mean':
            embedding = output.last_hidden_state.mean(dim=1)
        elif pooling == 'max':
            embedding = output.last_hidden_state.max(dim=1)[0]
        else:
            raise ValueError(f"Unsupported pooling method: {pooling}")
            
        return embedding.cpu().numpy()
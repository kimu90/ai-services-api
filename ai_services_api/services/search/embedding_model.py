from sentence_transformers import SentenceTransformer
import numpy as np

class EmbeddingModel:
    def __init__(self, model_path):
        """
        Initialize the embedding model with a given model path.

        Args:
            model_path (str): Path or name of the sentence transformer model
        """
        self.model = SentenceTransformer(model_path)

    def get_embedding(self, text):
        """
        Generate embedding for a given text.

        Args:
            text (str): Input text to generate embedding for

        Returns:
            numpy.ndarray: Embedding vector for the input text
        """
        return self.model.encode([text], convert_to_numpy=True)
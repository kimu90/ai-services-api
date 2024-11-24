import os
import pandas as pd
import numpy as np
import faiss
import pickle
from ai_services_api.services.search.config import get_settings
from ai_services_api.services.search.embedding_model import EmbeddingModel

def create_faiss_index(data_path=None, model_path=None):
    """
    Create FAISS index and chunk mapping from CSV data.

    Args:
        data_path (str, optional): Path to the CSV file. Defaults to config setting.
        model_path (str, optional): Path to embedding model. Defaults to config setting.
    """
    # Get settings
    settings = get_settings()

    # Use provided paths or default from settings
    data_path = data_path or settings.DATA_PATH
    model_path = model_path or settings.MODEL_PATH

    # Read the CSV
    df = pd.read_csv(data_path)

    # Initialize embedding model
    embedding_model = EmbeddingModel(model_path)

    # Create embeddings for your text columns
    text_columns = ['Title', 'Summary']

    # Combine text columns
    texts = df[text_columns].apply(lambda row: ' '.join(row.dropna().astype(str)), axis=1)

    # Generate embeddings
    embeddings = np.array([embedding_model.get_embedding(text)[0] for text in texts])

    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)

    # Ensure models directory exists
    os.makedirs(os.path.dirname(settings.INDEX_PATH), exist_ok=True)

    # Save FAISS index
    faiss.write_index(index, settings.INDEX_PATH)

    # Create chunk mapping
    chunk_mapping = {i: row.to_dict() for i, row in df.iterrows()}

    # Save chunk mapping
    with open(settings.CHUNK_MAPPING_PATH, 'wb') as f:
        pickle.dump(chunk_mapping, f)

    print("FAISS index and chunk mapping created successfully!")

# Standalone script to create index
if __name__ == "__main__":
    create_faiss_index()

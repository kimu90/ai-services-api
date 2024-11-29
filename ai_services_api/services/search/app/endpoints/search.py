import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from ai_services_api.services.search.search_engine import SearchEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize search engine with error handling
try:
    logger.info("Initializing SearchEngine...")
    search_engine = SearchEngine()
    logger.info("SearchEngine initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize SearchEngine: {e}")
    raise

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5

class SearchResponse(BaseModel):
    title: str
    abstract: str
    summary: str
    tags: str
    authors: str
    similarity_score: float

@router.get("/")
async def search(query: str, limit: Optional[int] = 5) -> List[SearchResponse]:
    """
    GET endpoint for semantic search
    """
    try:
        logger.info(f"Received search request - query: {query}, limit: {limit}")
        
        # Perform search
        logger.info("Calling search_engine.search()")
        results = search_engine.search(query, k=limit)
        logger.info(f"Search completed, found {len(results)} results")
        
        # Format results
        formatted_results = []
        for result in results:
            try:
                metadata = result['metadata']
                formatted_results.append({
                    'title': metadata.get('title', ''),
                    'abstract': metadata.get('abstract', ''),
                    'summary': metadata.get('summary', ''),
                    'tags': metadata.get('tags', ''),
                    'authors': metadata.get('authors', ''),
                    'similarity_score': result['similarity_score']
                })
            except Exception as e:
                logger.error(f"Error formatting result: {e}")
                logger.error(f"Problematic result: {result}")
                continue
        
        logger.info(f"Successfully formatted {len(formatted_results)} results")
        return JSONResponse(content=formatted_results)
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        logger.exception("Full traceback:")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")
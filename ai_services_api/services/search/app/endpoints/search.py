from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import logging
from ai_services_api.services.search.search_engine import SearchEngine
from ai_services_api.services.search.database_manager import DatabaseManager

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Initialize components
try:
    logger.info("Initializing SearchEngine and DatabaseManager...")
    search_engine = SearchEngine()
    db_manager = DatabaseManager()
    logger.info("SearchEngine and DatabaseManager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize components: {e}")
    raise

@router.get("/predict")
async def predict_queries(
    partial_query: str = Query(..., description="Partial query to get predictions for"),
    limit: int = Query(5, description="Number of predictions to return"),
    user_id: Optional[str] = None
):
    """Get query predictions based on partial input."""
    logger.info(f"Received prediction request for: {partial_query}")
    try:
        if len(partial_query) < 2:
            return []
            
        # Prepare context
        context = {
            'user_id': user_id
        }
        
        # Get user's recent queries if available
        if user_id:
            context['user_queries'] = db_manager.get_user_queries(
                user_id, 
                limit=100
            )
            
        # Get predictions
        predictions = search_engine.predict_queries(
            partial_query=partial_query,
            limit=limit,
            context=context
        )
        
        logger.info(f"Returning predictions: {predictions}")
        return predictions
        
    except Exception as e:
        logger.error(f"Prediction error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/")
async def search(
    query: str,
    limit: Optional[int] = 5
):
    """Perform a semantic search and store the query in history."""
    try:
        logger.info(f"Received search request - query: {query}, limit: {limit}")
        
        results = search_engine.search(
            query=query,
            k=limit
        )
        
        try:
            query_id = db_manager.add_query(
                query=query,
                result_count=len(results),
                search_type='semantic'
            )
            logger.info(f"Successfully stored query with ID: {query_id}")
        except Exception as db_error:
            logger.error(f"Failed to store query in database: {db_error}")
        
        formatted_results = [{
            'doi': r['metadata'].get('doi', ''),  # Add DOI to the response
            'title': r['metadata'].get('title', ''),
            'authors': r['metadata'].get('authors', ''),
            'summary': r['metadata'].get('summary', '')  # Keep summary in response
        } for r in results]
        
        return formatted_results
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/popular")
async def get_popular_searches(limit: Optional[int] = 10):
    """Get most popular searches from the database."""
    try:
        popular_searches = db_manager.get_popular_queries(limit=limit)
        return popular_searches
    except Exception as e:
        logger.error(f"Error getting popular searches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recent")
async def get_recent_searches(limit: Optional[int] = 10):
    """Get most recent searches from the database."""
    try:
        recent_searches = db_manager.get_recent_queries(limit=limit)
        return recent_searches
    except Exception as e:
        logger.error(f"Error getting recent searches: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List, Dict, Any
from pydantic import BaseModel
import logging
from ai_services_api.services.search.index_creator import ExpertSearchIndexManager
from ai_services_api.services.search.ml_predictor import MLPredictor

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize ML Predictor
ml_predictor = MLPredictor()

class ExpertSearchResult(BaseModel):
    id: str
    name: str
    designation: str
    theme: str
    unit: str
    contact: str
    is_active: bool
    score: float = None
    requested_by: str

class SearchResponse(BaseModel):
    total_results: int
    experts: List[ExpertSearchResult]
    user_id: str  

class PredictionResponse(BaseModel):
    predictions: List[str]
    confidence_scores: List[float]

@router.get("/experts/search/{query}")
async def search_experts(
    query: str, 
    user_id: str,
    limit: int = 10,
):
    try:
        search_manager = ExpertSearchIndexManager()
        results = search_manager.search_experts(query, k=limit)
        
        formatted_results = [
            ExpertSearchResult(
                id=str(result['id']),
                name=result['name'],
                designation=result['designation'],
                theme=result['theme'],
                unit=result['unit'],
                contact=result['contact'],
                is_active=result['is_active'],
                score=result.get('score'),
                requested_by=user_id  # Add this line
            )
            for result in results
        ]
        
        # Keep the ML predictor update
        ml_predictor.update(query)
        
        return SearchResponse(
            total_results=len(formatted_results),
            experts=formatted_results,
            user_id=user_id
        )
        
    except Exception as e:
        logger.error(f"Error searching experts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while searching experts"
        )

# Keep the ML predictor endpoints
@router.get("/experts/predict/{partial_query}")
async def predict_query(
    partial_query: str,
    user_id: str
):
    """Predict query completions based on partial input."""
    try:
        predictions = ml_predictor.predict(partial_query, limit=5)
        scores = [1.0 - (i * 0.1) for i in range(len(predictions))]
        
        return PredictionResponse(
            predictions=predictions,
            confidence_scores=scores
        )
        
    except Exception as e:
        logger.error(f"Error predicting queries: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while predicting queries"
        )

@router.post("/experts/train-predictor")
async def train_predictor(
    background_tasks: BackgroundTasks,
    queries: List[str],
    user_id: str
):
    """Train the ML predictor with historical queries."""
    try:
        background_tasks.add_task(ml_predictor.train, queries)
        return {"message": "Predictor training initiated"}
    except Exception as e:
        logger.error(f"Error training predictor: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error initiating predictor training"
        )

@router.get("/experts/similar/{expert_id}")
async def find_similar_experts(expert_id: str):
    """Find similar experts based on an expert's ID."""
    try:
        search_manager = ExpertSearchIndexManager()
        
        # Get expert's data
        expert_data = await search_manager.get_expert_text_by_id(expert_id)
        if not expert_data:
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ID {expert_id} not found"
            )
        
        # Search for similar experts
        results = search_manager.search_experts(expert_data, k=6)  # Get 6 to account for self-match
        
        # Format and filter results
        formatted_results = [
            ExpertSearchResult(
                id=str(result['id']),
                name=result['name'],
                designation=result['designation'],
                theme=result['theme'],
                unit=result['unit'],
                contact=result['contact'],
                is_active=result['is_active'],
                score=result.get('score')
            )
            for result in results
            if str(result['id']) != expert_id  # Filter out the original expert
        ][:5]  # Limit to 5 results
        
        return SearchResponse(
            total_results=len(formatted_results),
            experts=formatted_results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error finding similar experts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while finding similar experts"
        )

@router.get("/experts/{expert_id}")
async def get_expert_details(expert_id: str):
    """Get detailed information for an expert."""
    try:
        search_manager = ExpertSearchIndexManager()
        expert_data = await search_manager.get_expert_metadata(expert_id)
        
        if not expert_data:
            raise HTTPException(
                status_code=404,
                detail=f"Expert with ID {expert_id} not found"
            )
        
        return ExpertSearchResult(
            id=str(expert_data['id']),
            name=expert_data['name'],
            designation=expert_data['designation'],
            theme=expert_data['theme'],
            unit=expert_data['unit'],
            contact=expert_data['contact'],
            is_active=expert_data['is_active']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expert details: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting expert details"
        )

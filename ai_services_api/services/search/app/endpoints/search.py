from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List
from pydantic import BaseModel
import logging
from ai_services_api.services.search.index_creator import ExpertSearchIndexManager
from ai_services_api.services.search.ml_predictor import MLPredictor

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize ML Predictor
ml_predictor = MLPredictor()

class ExpertSpecialties(BaseModel):
    expertise: List[str]
    fields: List[str]
    subfields: List[str]
    domains: List[str]

class ExpertSearchResult(BaseModel):
    id: str
    name: str
    description: str
    specialties: ExpertSpecialties

class SearchResponse(BaseModel):
    total_results: int
    experts: List[ExpertSearchResult]

class PredictionResponse(BaseModel):
    predictions: List[str]
    confidence_scores: List[float]

@router.get("/experts/search/{query}")
async def search_experts(query: str):
    """Search for experts based on query text."""
    try:
        # Initialize search manager
        search_manager = ExpertSearchIndexManager()
        
        # Perform search with default limit of 5
        results = search_manager.search_experts(query, k=5)
        
        # Format results
        formatted_results = [
            ExpertSearchResult(
                id=str(result['id']),
                name=result['name'],
                description=result.get('bio', ''),
                specialties=ExpertSpecialties(
                    expertise=result.get('knowledge_expertise', []),
                    fields=result.get('fields', []),
                    subfields=result.get('subfields', []),
                    domains=result.get('domains', [])
                )
            )
            for result in results
        ]
        
        # Update ML predictor with successful query
        ml_predictor.update(query)
        
        return SearchResponse(
            total_results=len(formatted_results),
            experts=formatted_results
        )
        
    except Exception as e:
        logger.error(f"Error searching experts: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while searching experts"
        )

@router.get("/experts/predict/{partial_query}")
async def predict_query(partial_query: str):
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
async def train_predictor(background_tasks: BackgroundTasks, queries: List[str]):
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
                description=result.get('bio', ''),
                specialties=ExpertSpecialties(
                    expertise=result.get('knowledge_expertise', []),
                    fields=result.get('fields', []),
                    subfields=result.get('subfields', []),
                    domains=result.get('domains', [])
                )
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

@router.get("/experts/{expert_id}/expertise")
async def get_expert_expertise(expert_id: str):
    """Get detailed expertise information for an expert."""
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
            description=expert_data.get('bio', ''),
            specialties=ExpertSpecialties(
                expertise=expert_data.get('knowledge_expertise', []),
                fields=expert_data.get('fields', []),
                subfields=expert_data.get('subfields', []),
                domains=expert_data.get('domains', [])
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting expert expertise: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while getting expert expertise"
        )
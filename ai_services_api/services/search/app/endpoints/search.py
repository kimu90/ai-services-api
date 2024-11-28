from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from ai_services_api.services.search.search_engine import SearchEngine
from ai_services_api.services.search.experts_manager import ExpertsManager

router = APIRouter()  # Now APIRouter is defined properly

# Global search engine and experts manager
search_engine = SearchEngine()
experts_manager = ExpertsManager()

@router.on_event("startup")
async def startup_event():
    """
    Startup event to ensure index is ready
    """
    try:
        # Attempt to read the index (removed FAISS index creation)
        SearchEngine()
    except Exception:
        # No longer attempting to create FAISS index
        pass

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Render the main search page
    """
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "results": [], "title_results": []}
    )

@router.post("/search", response_class=HTMLResponse)
async def semantic_search(request: Request, query: str = Form(...)):
    """
    Perform semantic search and return results
    """
    # Perform search
    results = search_engine.search(query)

    # Render template with results
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": results,
            "query": query,
            "title_results": []
        }
    )

@router.post("/search-title", response_class=HTMLResponse)
async def title_search(request: Request, title: str = Form(...)):
    """
    Search for documents by title
    """
    # Perform title search
    title_results = search_engine.search_by_title(title)

    # Render template with results
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "results": [],
            "title_results": title_results,
            "title_query": title
        }
    )

@router.get("/get-summary")
async def get_summary(title: str):
    """
    API endpoint to get summary by title
    """
    # Get summary by title
    summary = search_engine.get_summary_by_title(title)

    if not summary:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "title": summary['Title'],
        "summary": summary['Summary'],
        "domain": summary['Domain'],
        "link": summary['Link']
    }

@router.get("/get-experts")
async def get_experts(domain: str):
    """
    API endpoint to get experts by domain
    """
    experts = experts_manager.find_experts_by_domain(domain)
    return experts

@router.get("/autocomplete")
async def autocomplete(query: str):
    """
    Provide autocomplete suggestions based on the query
    """
    # Perform semantic search with a higher k value to get more potential matches
    suggestions = search_engine.search(query, k=10)
    
    # Extract unique titles and summaries
    unique_suggestions = []
    seen_titles = set()
    
    for result in suggestions:
        title = result['metadata']['Title']
        if title not in seen_titles:
            unique_suggestions.append({
                'title': title,
                'summary': result['metadata']['Summary'][:100] + '...'
            })
            seen_titles.add(title)
    
    return JSONResponse(content=unique_suggestions)

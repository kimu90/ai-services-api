from ai_services_api.services.search.services.search_service import SearchService
from ai_services_api.services.search.config import get_settings

def get_search_service() -> SearchService:
    """
    Provides an instance of the SearchService, potentially with external dependencies like configuration.
    """
    settings = get_settings()  # Fetch the settings instance
    return SearchService(settings=settings)  # Initialize SearchService with the settings

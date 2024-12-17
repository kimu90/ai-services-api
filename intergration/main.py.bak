import asyncio
from core.config import get_config
from core.database import Database
from integrators.dspace import DSpaceIntegrator
from integrators.openalex import OpenAlexIntegrator
from integrators.orcid import OrcidIntegrator
from utils.deduplication import Deduplicator

async def main():
    config = get_config()
    db = Database(config.database)
    
    integrators = [
        DSpaceIntegrator(db, config.dspace_url, config.dspace_key),
        OpenAlexIntegrator(db, config.openalex_url),
        OrcidIntegrator(db, config.orcid_url, config.orcid_token)
    ]
    
    for integrator in integrators:
        publications = await integrator.fetch_publications()
        unique_pubs = Deduplicator.deduplicate_by_doi(publications)
        for pub in unique_pubs:
            await integrator.process_publication(pub)

if __name__ == "__main__":
    asyncio.run(main())
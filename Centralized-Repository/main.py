import asyncio
from services.integration_service import IntegrationService
import logging
from utils.logger import setup_logging

async def main():
    setup_logging()
    integration_service = IntegrationService()
    await integration_service.sync_all_data()

if __name__ == "__main__":
    asyncio.run(main())
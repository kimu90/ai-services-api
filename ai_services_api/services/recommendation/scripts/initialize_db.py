import asyncio
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from ai_services_api.services.recommendation.scripts.data_loader import DataLoader

async def main():
    loader = DataLoader()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "data", "try_test.csv")
    await loader.load_initial_experts(data_path)
    loader.verify_graph()

if __name__ == "__main__":
    asyncio.run(main())




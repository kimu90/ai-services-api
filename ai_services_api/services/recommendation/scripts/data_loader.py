import asyncio
from typing import List
import csv
from ai_services_api.services.recommendation.services.initial_expert_service import ExpertService
from ai_services_api.services.recommendation.core.database import GraphDatabase  # Changed from RedisGraph

class DataLoader:
    def __init__(self):
        self.expert_service = ExpertService()
        self.graph = GraphDatabase()

    async def load_initial_experts(self, orcid_file_path: str):
        """Load initial experts from a CSV file containing ORCIDs"""
        print("Starting initial data load...")
        
        # Read ORCIDs from CSV
        with open(orcid_file_path, 'r') as file:
            reader = csv.reader(file)
            next(reader)  # Skip header
            orcids = [row[0] for row in reader]

        # Process ORCIDs in batches
        batch_size = 100
        for i in range(0, len(orcids), batch_size):
            batch = orcids[i:i + batch_size]
            tasks = [self.expert_service.add_expert(orcid) for orcid in batch]
            await asyncio.gather(*tasks)
            print(f"Processed {i + len(batch)} experts...")

        print("Initial data load complete!")

    def verify_graph(self):
        """Verify that the graph has been populated"""
        stats = self.graph.get_graph_stats()
        print(f"Graph Statistics:")
        print(f"Number of Expert nodes: {stats['expert_count']}")
        print(f"Number of Topic nodes: {stats['topic_count']}")
        print(f"Number of relationships: {stats['relationship_count']}")




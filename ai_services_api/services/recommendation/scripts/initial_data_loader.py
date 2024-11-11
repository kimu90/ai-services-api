import asyncio
from typing import List, Union, Dict, Any
import csv
from pathlib import Path
import logging
import time
from ai_services_api.services.recommendation.services.expert_service import ExpertService
from ai_services_api.services.recommendation.core.database import GraphDatabase

logger = logging.getLogger(__name__)

class DataLoader:
    def __init__(self):
        self.expert_service = ExpertService()
        self.graph = GraphDatabase()
        self.batch_size = 100

    async def load_initial_experts(self, orcids: Union[str, Path, List[str]]):
        """
        Load initial experts from either a CSV file or a list of ORCIDs
        
        Args:
            orcids: Either a file path (str) or a list of ORCID IDs
        """
        logger.info("Starting initial data load...")
        
        try:
            # Handle input type
            if isinstance(orcids, (str, Path)):
                orcid_list = self._read_orcids_from_file(orcids)
            else:
                orcid_list = orcids

            # Validate ORCID list
            if not orcid_list:
                raise ValueError("No ORCIDs found to process")

            # Process ORCIDs in batches
            total_processed = 0
            for i in range(0, len(orcid_list), self.batch_size):
                batch = orcid_list[i:i + self.batch_size]
                try:
                    tasks = [self.expert_service.add_expert(orcid) for orcid in batch]
                    await asyncio.gather(*tasks)
                    total_processed += len(batch)
                    logger.info(f"Processed {total_processed} experts out of {len(orcid_list)}...")
                except Exception as e:
                    logger.error(f"Error processing batch starting at index {i}: {e}")
                    # Continue with next batch instead of failing completely
                    continue

            logger.info("Initial data load complete!")

        except Exception as e:
            logger.error(f"Error in load_initial_experts: {e}")
            raise

    def _read_orcids_from_file(self, file_path: Union[str, Path]) -> List[str]:
        """
        Read ORCIDs from a CSV file
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            List of ORCID IDs
        """
        try:
            with open(file_path, 'r') as file:
                reader = csv.reader(file)
                next(reader)  # Skip header
                orcids = [row[0] for row in reader if row]  # Only process non-empty rows
                
            logger.info(f"Successfully read {len(orcids)} ORCIDs from file")
            return orcids
            
        except Exception as e:
            logger.error(f"Error reading ORCIDs from file: {e}")
            raise

    def verify_graph(self) -> Dict[str, Any]:
        """
        Verify the graph's integrity and return statistics.
        
        Returns:
            Dict containing verification results and statistics
        """
        try:
            # Get basic statistics
            stats = self.get_graph_stats()
            
            # Verify node connections
            orphaned_experts = self.query_graph("""
                MATCH (e:Expert)
                WHERE NOT (e)-[:RELATED_TO]->()
                RETURN COUNT(e) as count
            """)[0][0]
            
            orphaned_domains = self.query_graph("""
                MATCH (d:Domain)
                WHERE NOT ()-[:RELATED_TO]->(d)
                RETURN COUNT(d) as count
            """)[0][0]
            
            verification_results = {
                **stats,
                'orphaned_experts': orphaned_experts,
                'orphaned_domains': orphaned_domains,
                'verification_timestamp': time.time(),
                'status': 'healthy' if orphaned_experts == 0 and orphaned_domains == 0 else 'warning'
            }
            
            logger.info(f"Graph verification complete: {verification_results}")
            return verification_results
            
        except Exception as e:
            logger.error(f"Error during graph verification: {str(e)}")
            verification_results = {
                'error': str(e),
                'verification_timestamp': time.time(),
                'status': 'error'
            }
            return verification_results
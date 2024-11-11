import asyncio
from typing import List, Union
import csv
from pathlib import Path
import logging
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

    def verify_graph(self):
        """
        Verify that the graph has been populated
        
        Returns:
            Dictionary containing graph statistics
        """
        try:
            stats = self.graph.get_graph_stats()
            
            # Log graph statistics
            logger.info("Graph Statistics:")
            logger.info(f"Number of Expert nodes: {stats['expert_count']}")
            logger.info(f"Number of Domain nodes: {stats['domain_count']}")
            logger.info(f"Number of Field nodes: {stats['field_count']}")
            logger.info(f"Number of Subfield nodes: {stats['subfield_count']}")
            logger.info(f"Number of relationships: {stats['relationship_count']}")
            
            return stats
            
        except Exception as e:
            logger.error(f"Error verifying graph: {e}")
            raise
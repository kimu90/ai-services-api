import pandas as pd
from typing import List, Dict
from ai_services_api.services.search.config import get_settings

class ExpertsManager:
    def __init__(self):
        """
        Initialize ExpertsManager with experts database
        """
        settings = get_settings()

        # Update the path from 'static' to 'models'
        try:
            self.experts_df = pd.read_csv(settings.EXPERTS_DB_PATH)
        except FileNotFoundError:
            print(f"Error: The file at {settings.EXPERTS_DB_PATH} was not found.")
            self.experts_df = pd.DataFrame()  # Empty DataFrame as fallback
        except pd.errors.ParserError:
            print(f"Error: There was an issue parsing the file at {settings.EXPERTS_DB_PATH}.")
            self.experts_df = pd.DataFrame()  # Empty DataFrame as fallback

    def find_experts_by_domain(self, domain: str) -> List[Dict]:
        """
        Find experts matching a specific domain

        Args:
            domain (str): Domain to search for experts

        Returns:
            List of expert dictionaries
        """
        if self.experts_df.empty:
            return []  # Return empty list if the DataFrame is empty

        matching_experts = self.experts_df[
            self.experts_df['Domain'].str.contains(domain, case=False, na=False)
        ]
        return matching_experts.to_dict('records')

    def get_expert_details(self, expert_id: str) -> Dict:
        """
        Get details of a specific expert

        Args:
            expert_id (str): Unique identifier for the expert

        Returns:
            Expert details dictionary or None if not found
        """
        if self.experts_df.empty:
            return None  # Return None if the DataFrame is empty

        expert = self.experts_df[self.experts_df['ID'] == expert_id]
        return expert.to_dict('records')[0] if not expert.empty else None

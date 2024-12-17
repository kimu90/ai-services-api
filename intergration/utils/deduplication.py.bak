class Deduplicator:
    @staticmethod
    def deduplicate_by_doi(publications):
        seen_dois = set()
        unique_pubs = []
        
        for pub in publications:
            doi = pub.get("doi")
            if doi and doi not in seen_dois:
                seen_dois.add(doi)
                unique_pubs.append(pub)
        
        return unique_pubs
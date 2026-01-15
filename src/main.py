"""Main script for scraping FEB competitions and storing in MongoDB."""

import logging
import time
from typing import List, Dict, Optional
from .scraper import FEBWebScraper, FEBApiClient, WebClient, TokenManager
from .database import MongoDBClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scouting_feb.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class FEBScoutingScraper:
    """Main scraper orchestrator for FEB competitions."""

    def __init__(self, mongodb_uri: str = "mongodb://localhost:27017/", 
                 database_name: str = "scouting_feb"):
        """
        Initialize the scouting scraper.

        Args:
            mongodb_uri: MongoDB connection string
            database_name: Database name
        """
        self.web_client = WebClient()
        self.token_manager = TokenManager()
        self.scraper = FEBWebScraper(self.web_client)
        self.api_client = FEBApiClient(self.token_manager, self.web_client)
        self.db_client = MongoDBClient(mongodb_uri, database_name)
        
        logger.info("FEBScoutingScraper initialized")

    def determine_gender_from_competition(self, comp_name: str, comp_url: str) -> str:
        """
        Determine if competition is masculine or feminine.

        Args:
            comp_name: Competition name
            comp_url: Competition URL

        Returns:
            'masc' or 'fem'
        """
        comp_lower = comp_name.lower()
        url_lower = comp_url.lower()
        
        # Keywords for feminine competitions
        fem_keywords = ['femenina', 'fem', 'women', 'women', 'lf', 'lf2', 'femenino']
        
        # Check both name and URL
        for keyword in fem_keywords:
            if keyword in comp_lower or keyword in url_lower:
                return 'fem'
        
        return 'masc'

    def get_collection_name(self, gender: str) -> str:
        """
        Get MongoDB collection name based on gender.

        Args:
            gender: 'masc' or 'fem'

        Returns:
            Collection name
        """
        return f"all_feb_games_{gender}"

    def scrape_competition(self, competition_url: str, competition_name: str, 
                          gender: Optional[str] = None, incremental: bool = True) -> Dict:
        """
        Scrape all games from a competition across all seasons and groups.

        Args:
            competition_url: URL of the competition calendar
            competition_name: Name of the competition
            gender: 'masc' or 'fem' (auto-detected if None)
            incremental: If True, only process new matches not in database (default: True)

        Returns:
            Dictionary with scraping statistics
        """
        if gender is None:
            gender = self.determine_gender_from_competition(competition_name, competition_url)
        
        collection_name = self.get_collection_name(gender)
        
        logger.info(f"Starting scrape for {competition_name} ({gender})")
        logger.info(f"URL: {competition_url}")
        logger.info(f"Collection: {collection_name}")
        
        stats = {
            "competition": competition_name,
            "gender": gender,
            "collection": collection_name,
            "total_seasons": 0,
            "total_groups": 0,
            "total_matches_found": 0,
            "total_matches_scraped": 0,
            "total_matches_skipped": 0,
            "total_matches_failed": 0
        }

        try:
            # Get the initial page
            response = self.web_client.get(competition_url)
            if not response:
                logger.error(f"Failed to fetch competition page: {competition_url}")
                return stats

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            session = self.web_client.get_session()

            # Get all available seasons
            seasons = self.scraper.get_seasons(soup)
            if not seasons:
                logger.warning(f"No seasons found for {competition_name}")
                return stats

            stats["total_seasons"] = len(seasons)
            logger.info(f"Found {len(seasons)} seasons")

            # Iterate through each season
            for season_text, season_value in seasons:
                logger.info(f"Processing season: {season_text}")
                
                # Select the season to get access to groups and series/phases
                hidden_fields = self.scraper.get_hidden_fields(soup)
                soup_season, hidden_fields = self.scraper.select_season(
                    session, competition_url, season_value, hidden_fields
                )
                
                # Get available groups for this season
                groups = self.scraper.get_groups(soup_season)
                if groups:
                    logger.info(f"Found {len(groups)} groups for season {season_text}")
                    stats["total_groups"] += len(groups)
                    for group_text, group_value in groups:
                        logger.info(f"  - {group_text} (value: {group_value})")
                else:
                    logger.info(f"No groups dropdown found, using default calendar")
                    groups = [("Default", "")]  # Fallback to single group
                
                # Collect all matches with their source (regular or series name)
                all_matches = []
                
                # 1. Get matches from regular calendar - ITERATE THROUGH EACH GROUP
                #    Each group needs a separate POST request to load its matches
                for group_text, group_value in groups:
                    # Select the specific group (this changes the page content via POST)
                    if group_value:  # Only if there's a real group value
                        try:
                            soup_group = self.scraper.select_group(
                                session, competition_url, season_value, group_value, hidden_fields
                            )
                            # Extract matches from this group's page
                            matches_group = self.scraper._extract_match_codes(soup_group)
                        except Exception as e:
                            logger.error(f"Failed to select group '{group_text}': {e}")
                            matches_group = []
                    else:
                        # No group dropdown, just get matches from current page
                        matches_group = self.scraper.get_matches(
                            season_value, "", season_text, session, competition_url
                        )
                    
                    if matches_group:
                        logger.info(f"Found {len(matches_group)} matches in group '{group_text}'")
                        
                        # Add group matches (will use API's 'round' field as group name)
                        for match_code in matches_group:
                            all_matches.append({
                                "code": match_code,
                                "source": group_text,
                                "source_type": "calendar"
                            })
                
                # 2. Get matches from series/phases (Play-offs, Copa, Supercopa, etc.)
                series_links = self.scraper.get_series_links(soup_season)
                
                if series_links:
                    logger.info(f"Found {len(series_links)} series/phases for season {season_text}")
                    for serie in series_links:
                        logger.info(f"  - {serie['name']} (ID: {serie['fase_id']})")
                
                # Add series matches (these will use the series name as group)
                for serie in series_links:
                    serie_matches = self.scraper.get_matches_from_series(serie["url"])
                    logger.info(f"Found {len(serie_matches)} matches in {serie['name']}")
                    
                    for match_code in serie_matches:
                        all_matches.append({
                            "code": match_code,
                            "source": serie["name"],
                            "source_type": "series"
                        })
                
                # Remove duplicates (a match might appear in both calendar and series)
                seen_codes = set()
                unique_matches = []
                for match_info in all_matches:
                    if match_info["code"] not in seen_codes:
                        seen_codes.add(match_info["code"])
                        unique_matches.append(match_info)
                
                logger.info(f"Total unique matches for season {season_text}: {len(unique_matches)}")
                stats["total_matches_found"] += len(unique_matches)

                # Incremental processing: filter out already processed matches
                matches_to_process = unique_matches
                if incremental:
                    # Check which matches are already in the database (by match code only)
                    processed_matches = set(self.db_client.get_all_processed_matches_by_season(
                        competition_name, season_text, collection_name
                    ))
                    
                    matches_to_process = [m for m in unique_matches if m["code"] not in processed_matches]
                    
                    if len(matches_to_process) < len(unique_matches):
                        skipped = len(unique_matches) - len(matches_to_process)
                        logger.info(f"Incremental mode: {skipped} matches already processed, "
                                  f"{len(matches_to_process)} new matches to process")
                        stats["total_matches_skipped"] += skipped
                
                if not matches_to_process:
                    logger.info(f"All matches already processed for season {season_text}")
                    continue

                # Scrape each match
                for i, match_info in enumerate(matches_to_process, 1):
                    match_code = match_info["code"]
                    match_source = match_info["source"]
                    match_source_type = match_info["source_type"]
                    
                    logger.info(f"Processing match {i}/{len(matches_to_process)}: {match_code} ({match_source})")
                    
                    # Double-check if match exists (in case of concurrent runs)
                    if self.db_client.game_exists(match_code, collection_name):
                        logger.info(f"Match {match_code} already exists, skipping")
                        stats["total_matches_skipped"] += 1
                        continue

                    # Fetch match data
                    match_data = self.api_client.fetch_boxscore(match_code, session)
                    
                    if match_data:
                        # Add metadata
                        if "HEADER" not in match_data:
                            match_data["HEADER"] = {}
                        
                        # Determine group/phase:
                        # - For series matches: use the series name (more specific)
                        # - For calendar matches: use API's 'round' field (contains group info like "GR. 1", "GR. 2", etc.)
                        if match_source_type == "series":
                            group_name = match_source
                        else:
                            # For calendar matches, use the 'round' field from API
                            # This field contains the actual group: "GR. 1", "GR. 2", "FASE FINAL", etc.
                            group_name = match_data["HEADER"].get("round", "Unknown").strip()
                            if not group_name or group_name == "Unknown":
                                group_name = "Único"
                        
                        match_data["HEADER"]["competition_name"] = competition_name
                        match_data["HEADER"]["season"] = season_text
                        match_data["HEADER"]["group"] = group_name
                        match_data["HEADER"]["gender"] = gender
                        
                        # Insert into MongoDB
                        result = self.db_client.insert_game(match_data, collection_name)
                        if result:
                            stats["total_matches_scraped"] += 1
                            logger.info(f"Successfully inserted match {match_code} (group: {group_name})")
                        else:
                            stats["total_matches_failed"] += 1
                            logger.error(f"Failed to insert match {match_code}")
                    else:
                        stats["total_matches_failed"] += 1
                        logger.error(f"Failed to fetch data for match {match_code}")
                    
                    # Small delay to avoid overwhelming the server
                    time.sleep(0.5)
                
                # Update scraping state after processing this season
                if matches_to_process:
                    from datetime import datetime
                    last_match = matches_to_process[-1]
                    timestamp = datetime.utcnow().isoformat()
                    # Store state by season only (not by group)
                    self.db_client.update_scraping_state(
                        competition_name, season_text, "All Groups", 
                        collection_name, last_match, len(unique_matches), timestamp
                    )

        except Exception as e:
            logger.error(f"Error scraping competition {competition_name}: {e}", exc_info=True)
        
        # Create indexes after scraping
        self.db_client.create_indexes(collection_name)
        
        logger.info(f"Scraping completed for {competition_name}")
        logger.info(f"Stats: {stats}")
        
        return stats

    def scrape_competition_by_name(self, competition_name: str, gender: Optional[str] = None, 
                                  incremental: bool = True) -> Dict:
        """
        Scrape a competition by name (searches for it first).

        Args:
            competition_name: Name of the competition to scrape
            gender: 'masc' or 'fem' (auto-detected if None)
            incremental: If True, only process new matches not in database (default: True)

        Returns:
            Dictionary with scraping statistics
        """
        logger.info(f"Searching for competition: {competition_name}")
        
        # Get all competitions
        competitions = self.scraper.get_feb_competitions()
        
        # Find the competition
        for comp in competitions:
            if competition_name.lower() in comp["name"].lower():
                logger.info(f"Found competition: {comp['name']}")
                return self.scrape_competition(comp["results_url"], comp["name"], gender, incremental)
        
        logger.error(f"Competition not found: {competition_name}")
        return {"error": "Competition not found"}

    def list_available_competitions(self) -> List[Dict[str, str]]:
        """
        List all available FEB competitions.

        Returns:
            List of competition dictionaries
        """
        logger.info("Fetching available competitions")
        competitions = self.scraper.get_feb_competitions()
        
        for comp in competitions:
            gender = self.determine_gender_from_competition(comp["name"], comp["results_url"])
            comp["detected_gender"] = gender
            print(f"- {comp['name']} ({gender}) - {comp['results_url']}")
        
        return competitions

    def close(self):
        """Close all connections."""
        self.db_client.close()
        logger.info("All connections closed")


def main():
    """Main entry point."""
    scraper = FEBScoutingScraper()
    
    try:
        # List available competitions
        print("\n=== Available FEB Competitions ===\n")
        competitions = scraper.list_available_competitions()
        
        print("\n=== Starting scraping process ===\n")
        
        # Example: Scrape a specific competition
        # You can modify this to scrape the competition you want
        # scraper.scrape_competition_by_name("LF2")
        
        # Or scrape by URL directly:
        # stats = scraper.scrape_competition(
        #     "https://baloncestoenvivo.feb.es/calendario/lf2/9/2024",
        #     "LF2 - Liga Femenina 2",
        #     "fem"
        # )
        
        print("\nTo scrape a competition, uncomment the relevant lines in main()")
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

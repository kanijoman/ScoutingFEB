"""MongoDB client for storing FEB game data."""

from pymongo import MongoClient, UpdateOne
from pymongo.errors import BulkWriteError, PyMongoError
from typing import Dict, List, Optional
import logging


class MongoDBClient:
    """Client for MongoDB operations."""

    def __init__(self, connection_string: str = "mongodb://localhost:27017/", 
                 database_name: str = "scouting_feb"):
        """
        Initialize MongoDB client.

        Args:
            connection_string: MongoDB connection string
            database_name: Name of the database to use
        """
        self.client = MongoClient(connection_string)
        self.db = self.client[database_name]
        self.logger = logging.getLogger(__name__)

    def get_collection(self, collection_name: str):
        """
        Get a MongoDB collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Collection object
        """
        return self.db[collection_name]

    def insert_game(self, game_data: Dict, collection_name: str) -> Optional[str]:
        """
        Insert a single game into the collection.

        Args:
            game_data: Game data dictionary
            collection_name: Name of the collection (e.g., 'all_feb_games_masc')

        Returns:
            Inserted document ID or None if failed
        """
        try:
            collection = self.get_collection(collection_name)
            
            # Use game_code as _id if available
            if "HEADER" in game_data and "game_code" in game_data["HEADER"]:
                game_data["_id"] = game_data["HEADER"]["game_code"]
            
            result = collection.insert_one(game_data)
            self.logger.info(f"Inserted game {result.inserted_id} into {collection_name}")
            return str(result.inserted_id)
        except PyMongoError as e:
            self.logger.error(f"Error inserting game: {e}")
            return None

    def insert_games_bulk(self, games_data: List[Dict], collection_name: str) -> Dict:
        """
        Insert multiple games into the collection using bulk operations.

        Args:
            games_data: List of game data dictionaries
            collection_name: Name of the collection

        Returns:
            Dictionary with 'inserted', 'updated', 'errors' counts
        """
        if not games_data:
            return {"inserted": 0, "updated": 0, "errors": 0}

        collection = self.get_collection(collection_name)
        operations = []
        
        for game_data in games_data:
            # Use game_code as _id if available
            if "HEADER" in game_data and "game_code" in game_data["HEADER"]:
                game_id = game_data["HEADER"]["game_code"]
                game_data["_id"] = game_id
                
                # Upsert: insert if not exists, update if exists
                operations.append(
                    UpdateOne(
                        {"_id": game_id},
                        {"$set": game_data},
                        upsert=True
                    )
                )
            else:
                self.logger.warning(f"Game data missing game_code, skipping")
                continue

        if not operations:
            return {"inserted": 0, "updated": 0, "errors": 0}

        try:
            result = collection.bulk_write(operations, ordered=False)
            return {
                "inserted": result.upserted_count,
                "updated": result.modified_count,
                "errors": 0
            }
        except BulkWriteError as bwe:
            # Even with errors, some operations may have succeeded
            inserted = bwe.details.get('nUpserted', 0)
            updated = bwe.details.get('nModified', 0)
            errors = len(bwe.details.get('writeErrors', []))
            
            self.logger.error(f"Bulk write errors: {errors} failed operations")
            return {
                "inserted": inserted,
                "updated": updated,
                "errors": errors
            }
        except PyMongoError as e:
            self.logger.error(f"Error during bulk insert: {e}")
            return {"inserted": 0, "updated": 0, "errors": len(operations)}

    def game_exists(self, game_code: str, collection_name: str) -> bool:
        """
        Check if a game already exists in the collection.

        Args:
            game_code: Game identifier
            collection_name: Name of the collection

        Returns:
            True if game exists, False otherwise
        """
        try:
            collection = self.get_collection(collection_name)
            return collection.count_documents({"_id": int(game_code)}, limit=1) > 0
        except PyMongoError as e:
            self.logger.error(f"Error checking game existence: {e}")
            return False

    def get_game(self, game_code: str, collection_name: str) -> Optional[Dict]:
        """
        Retrieve a game from the collection.

        Args:
            game_code: Game identifier
            collection_name: Name of the collection

        Returns:
            Game data dictionary or None if not found
        """
        try:
            collection = self.get_collection(collection_name)
            return collection.find_one({"_id": int(game_code)})
        except PyMongoError as e:
            self.logger.error(f"Error retrieving game: {e}")
            return None

    def get_all_games(self, collection_name: str, filter_query: Optional[Dict] = None) -> List[Dict]:
        """
        Retrieve all games from the collection.

        Args:
            collection_name: Name of the collection
            filter_query: Optional MongoDB query filter

        Returns:
            List of game data dictionaries
        """
        try:
            collection = self.get_collection(collection_name)
            query = filter_query or {}
            return list(collection.find(query))
        except PyMongoError as e:
            self.logger.error(f"Error retrieving games: {e}")
            return []

    def count_games(self, collection_name: str, filter_query: Optional[Dict] = None) -> int:
        """
        Count games in the collection.

        Args:
            collection_name: Name of the collection
            filter_query: Optional MongoDB query filter

        Returns:
            Number of games
        """
        try:
            collection = self.get_collection(collection_name)
            query = filter_query or {}
            return collection.count_documents(query)
        except PyMongoError as e:
            self.logger.error(f"Error counting games: {e}")
            return 0

    def create_indexes(self, collection_name: str):
        """
        Create useful indexes for the collection.

        Args:
            collection_name: Name of the collection
        """
        try:
            collection = self.get_collection(collection_name)
            
            # Index on competition
            collection.create_index([("HEADER.competition", 1)])
            
            # Index on start time
            collection.create_index([("HEADER.starttime", 1)])
            
            # Index on team IDs
            collection.create_index([("HEADER.TEAM.id", 1)])
            
            self.logger.info(f"Created indexes for {collection_name}")
        except PyMongoError as e:
            self.logger.error(f"Error creating indexes: {e}")

    def get_scraping_state(self, competition_name: str, season: str, group: str, 
                          collection_name: str) -> Optional[Dict]:
        """
        Get the scraping state for a specific competition/season/group.

        Args:
            competition_name: Name of the competition
            season: Season identifier
            group: Group identifier
            collection_name: Collection being scraped

        Returns:
            State dictionary or None if not found
        """
        try:
            state_collection = self.get_collection("scraping_state")
            state_id = f"{collection_name}_{competition_name}_{season}_{group}"
            return state_collection.find_one({"_id": state_id})
        except PyMongoError as e:
            self.logger.error(f"Error retrieving scraping state: {e}")
            return None

    def update_scraping_state(self, competition_name: str, season: str, group: str,
                             collection_name: str, last_match_code: str, 
                             total_matches: int, timestamp: str) -> bool:
        """
        Update the scraping state for a specific competition/season/group.

        Args:
            competition_name: Name of the competition
            season: Season identifier
            group: Group identifier
            collection_name: Collection being scraped
            last_match_code: Last match code processed
            total_matches: Total number of matches in this group
            timestamp: ISO timestamp of last update

        Returns:
            True if successful, False otherwise
        """
        try:
            state_collection = self.get_collection("scraping_state")
            state_id = f"{collection_name}_{competition_name}_{season}_{group}"
            
            state_collection.update_one(
                {"_id": state_id},
                {"$set": {
                    "competition_name": competition_name,
                    "season": season,
                    "group": group,
                    "collection_name": collection_name,
                    "last_match_code": last_match_code,
                    "total_matches": total_matches,
                    "last_update": timestamp
                }},
                upsert=True
            )
            self.logger.info(f"Updated scraping state for {competition_name}/{season}/{group}")
            return True
        except PyMongoError as e:
            self.logger.error(f"Error updating scraping state: {e}")
            return False

    def get_all_processed_matches(self, competition_name: str, season: str, 
                                 group: str, collection_name: str) -> List[str]:
        """
        Get all match codes already processed for a competition/season/group.

        Args:
            competition_name: Name of the competition
            season: Season identifier
            group: Group identifier
            collection_name: Collection name

        Returns:
            List of match codes already in the database
        """
        try:
            collection = self.get_collection(collection_name)
            # Query for matches with matching metadata
            query = {
                "HEADER.competition_name": competition_name,
                "HEADER.season": season,
                "HEADER.group": group
            }
            
            # Get only the game_code field
            cursor = collection.find(query, {"HEADER.game_code": 1})
            match_codes = [str(doc.get("HEADER", {}).get("game_code", "")) 
                          for doc in cursor if doc.get("HEADER", {}).get("game_code")]
            
            return match_codes
        except PyMongoError as e:
            self.logger.error(f"Error retrieving processed matches: {e}")
            return []

    def get_all_processed_matches_by_season(self, competition_name: str, season: str,
                                          collection_name: str) -> List[str]:
        """
        Get all match codes already processed for a competition/season (all groups).

        Args:
            competition_name: Name of the competition
            season: Season identifier
            collection_name: Collection name

        Returns:
            List of match codes already in the database
        """
        try:
            collection = self.get_collection(collection_name)
            # Query for matches with matching metadata (no group filter)
            query = {
                "HEADER.competition_name": competition_name,
                "HEADER.season": season
            }
            
            # Get only the game_code field
            cursor = collection.find(query, {"HEADER.game_code": 1})
            match_codes = [str(doc.get("HEADER", {}).get("game_code", "")) 
                          for doc in cursor if doc.get("HEADER", {}).get("game_code")]
            
            return match_codes
        except PyMongoError as e:
            self.logger.error(f"Error retrieving processed matches: {e}")
            return []

    def close(self):
        """Close the MongoDB connection."""
        self.client.close()
        self.logger.info("MongoDB connection closed")

"""Normalize data from different sources (API moderna, legacy HTML) to unified format."""

from typing import Dict, Optional, List


class DataNormalizer:
    """Normalizes match data from different sources to a unified format."""
    
    @staticmethod
    def normalize_match_data(data: Dict) -> Dict:
        """
        Normalize match data to unified format.
        
        Detects the source format and converts to standard structure:
        - HEADER: Match metadata and team info
        - BOXSCORE: Player statistics grouped by team
        
        Args:
            data: Match data from any source (API or legacy HTML)
            
        Returns:
            Normalized data dictionary
        """
        if not data:
            return data
        
        # Check if data is already in modern API format (has BOXSCORE.TEAM structure)
        if DataNormalizer._is_modern_api_format(data):
            return DataNormalizer._normalize_modern_api(data)
        
        # Otherwise, assume it's legacy format (has BOXSCORE.PLAYER flat list)
        if DataNormalizer._is_legacy_format(data):
            return DataNormalizer._normalize_legacy_format(data)
        
        # If neither format, return as-is
        return data
    
    @staticmethod
    def _is_modern_api_format(data: Dict) -> bool:
        """Check if data is in modern API format."""
        return (
            "BOXSCORE" in data and 
            isinstance(data["BOXSCORE"], dict) and
            "TEAM" in data["BOXSCORE"] and
            isinstance(data["BOXSCORE"]["TEAM"], list)
        )
    
    @staticmethod
    def _is_legacy_format(data: Dict) -> bool:
        """Check if data is in legacy HTML format."""
        return (
            "BOXSCORE" in data and 
            isinstance(data["BOXSCORE"], dict) and
            "PLAYER" in data["BOXSCORE"] and
            isinstance(data["BOXSCORE"]["PLAYER"], list) and
            len(data["BOXSCORE"]["PLAYER"]) > 0 and
            "player_id" in data["BOXSCORE"]["PLAYER"][0]  # Legacy uses player_id not playerid
        )
    
    @staticmethod
    def _normalize_modern_api(data: Dict) -> Dict:
        """
        Normalize modern API format.
        Already mostly standardized, just ensure consistent field names.
        """
        # Normalize team structure
        if "BOXSCORE" in data and "TEAM" in data["BOXSCORE"]:
            for team in data["BOXSCORE"]["TEAM"]:
                if "PLAYER" in team and isinstance(team["PLAYER"], list):
                    for player in team["PLAYER"]:
                        DataNormalizer._normalize_player_fields(player, is_legacy=False)
        
        return data
    
    @staticmethod
    def _normalize_legacy_format(data: Dict) -> Dict:
        """
        Normalize legacy HTML format to modern API structure.
        Converts flat PLAYER list to TEAM-grouped structure.
        """
        # Get teams from HEADER
        header = data.get("HEADER", {})
        teams = header.get("TEAM", [])
        
        if len(teams) < 2:
            # Can't group players without team info
            # Convert player fields but keep flat structure
            if "BOXSCORE" in data and "PLAYER" in data["BOXSCORE"]:
                for player in data["BOXSCORE"]["PLAYER"]:
                    DataNormalizer._normalize_player_fields(player, is_legacy=True)
            return data
        
        # Get team names for matching
        home_team_name = teams[0].get("name", "").upper()
        away_team_name = teams[1].get("name", "").upper() if len(teams) > 1 else ""
        
        # Group players by team name matching
        home_players = []
        away_players = []
        unassigned_players = []
        
        if "BOXSCORE" in data and "PLAYER" in data["BOXSCORE"]:
            for player in data["BOXSCORE"]["PLAYER"]:
                # Normalize player fields
                DataNormalizer._normalize_player_fields(player, is_legacy=True)
                
                # Determine team by matching team_name field
                player_team = player.get("team_name", "").upper().strip()
                
                # Try to match by team_name
                assigned = False
                if player_team:  # Only if team_name is not empty
                    # Check if player team matches home team
                    if home_team_name and (
                        home_team_name in player_team or 
                        player_team in home_team_name or
                        DataNormalizer._fuzzy_team_match(home_team_name, player_team)
                    ):
                        player["is_home"] = True
                        home_players.append(player)
                        assigned = True
                    # Check if player team matches away team
                    elif away_team_name and (
                        away_team_name in player_team or 
                        player_team in away_team_name or
                        DataNormalizer._fuzzy_team_match(away_team_name, player_team)
                    ):
                        player["is_home"] = False
                        away_players.append(player)
                        assigned = True
                
                if not assigned:
                    unassigned_players.append(player)
        
        # If we have unassigned players (no team_name), use smart detection
        # HTML typically lists all players from team 1, then all from team 2
        # Each team has exactly 5 starters, so we can detect the split point
        if unassigned_players:
            split_index = DataNormalizer._detect_team_split_point(unassigned_players)
            
            for i, player in enumerate(unassigned_players):
                if i < split_index:
                    player["is_home"] = True
                    home_players.append(player)
                else:
                    player["is_home"] = False
                    away_players.append(player)
        
        # Create modern TEAM structure
        modern_teams = []
        
        for i, team in enumerate(teams):
            team_data = {
                "teamid": team.get("team_id", ""),
                "code": team.get("code", ""),
                "name": team.get("name", ""),
                "score": team.get("score", "0"),
                "is_home": team.get("is_home", i == 0),
                "PLAYER": home_players if team.get("is_home", i == 0) else away_players
            }
            modern_teams.append(team_data)
        
        # Replace flat PLAYER list with TEAM structure
        data["BOXSCORE"]["TEAM"] = modern_teams
        del data["BOXSCORE"]["PLAYER"]
        
        return data
    
    @staticmethod
    def _detect_team_split_point(players: List[Dict]) -> int:
        """
        Detect where the first team ends and second team begins.
        
        Strategy:
        1. Each basketball team has exactly 5 starters (is_starter=True)
        2. HTML lists all players from team 1, then all from team 2
        3. Find the index after the 5th starter - that's where team 2 begins
        
        Args:
            players: List of player dictionaries
            
        Returns:
            Index where team 2 starts (0-based)
        """
        if len(players) < 10:
            # If fewer than 10 players, just split in half
            return len(players) // 2
        
        # Count starters until we find the 6th one
        starter_count = 0
        
        for i, player in enumerate(players):
            if player.get("is_starter", False):
                starter_count += 1
                
                # When we find the 6th starter, that's the beginning of team 2
                if starter_count == 6:
                    return i
        
        # Fallback: if we didn't find exactly 10 starters (5 per team),
        # use a heuristic based on typical roster sizes
        # Most teams have 8-12 players, so look for the midpoint
        # but adjusted for common patterns
        
        # Try to find a natural break point around the middle
        mid = len(players) // 2
        
        # Look for the first starter after the midpoint
        # This handles cases where teams have unequal roster sizes
        for i in range(mid - 2, min(mid + 3, len(players))):
            if i > 0 and players[i].get("is_starter", False):
                # If this is a starter and previous player wasn't,
                # this is likely the start of team 2
                if not players[i-1].get("is_starter", False):
                    return i
        
        # Last resort: split in half
        return mid
    
    @staticmethod
    def _fuzzy_team_match(team1: str, team2: str) -> bool:
        """
        Fuzzy match team names (handles abbreviations and variations).
        
        Examples:
        - "PERFUMERIAS AVENIDA" matches "PERFUMERIAS AVENIDA SALAMANCA"
        - "IDK EUSKOTREN" matches "IDK"
        """
        # Remove common words that might differ
        stop_words = ["C.B.", "C.D.", "S.A.D.", "BALONCESTO", "CLUB"]
        
        def clean_name(name):
            for word in stop_words:
                name = name.replace(word, "")
            # Remove extra spaces and get words
            return set(name.split())
        
        words1 = clean_name(team1)
        words2 = clean_name(team2)
        
        # Check if there's significant overlap
        if not words1 or not words2:
            return False
        
        intersection = words1 & words2
        # If at least 50% of words match, consider it a match
        return len(intersection) >= min(len(words1), len(words2)) * 0.5
    
    @staticmethod
    def _normalize_player_fields(player: Dict, is_legacy: bool):
        """
        Normalize player field names to unified format.
        
        Unified format uses:
        - playerid (not player_id)
        - playername (not name)
        - shirtnumber (not dorsal)
        - min (not minutes)
        """
        if is_legacy:
            # Legacy format: player_id, name, dorsal, minutes
            # Convert to: playerid, playername, shirtnumber, min
            
            if "player_id" in player and "playerid" not in player:
                player["playerid"] = player.pop("player_id")
            
            if "name" in player and "playername" not in player:
                player["playername"] = player.pop("name")
            
            if "dorsal" in player and "shirtnumber" not in player:
                player["shirtnumber"] = player.pop("dorsal")
            
            if "minutes" in player and "min" not in player:
                # Convert "MM:SS" format to "MM:SS" (keep as string)
                player["min"] = str(player.pop("minutes"))
        
        else:
            # Modern API format - ensure all fields exist
            # Already uses correct names, but ensure backwards compatibility
            
            if "playerid" not in player and "player_id" in player:
                player["playerid"] = player["player_id"]
            
            if "playername" not in player and "name" in player:
                player["playername"] = player["name"]
            
            if "shirtnumber" not in player and "dorsal" in player:
                player["shirtnumber"] = player["dorsal"]
        
        # Ensure games_played field exists (will be set by DataProcessor)
        if "games_played" not in player:
            player["games_played"] = 0
        
        # Ensure numeric fields ONLY for legacy format
        # Modern format uses FEB keys (pts, p1m, p2m, p3m, etc.) and should not have these fields
        if is_legacy:
            numeric_fields = [
                "points", "field_goals_made", "field_goals_attempted",
                "two_points_made", "two_points_attempted",
                "three_points_made", "three_points_attempted",
                "free_throws_made", "free_throws_attempted",
                "offensive_rebounds", "defensive_rebounds", "total_rebounds",
                "assists", "steals", "turnovers", "blocks", "blocks_received",
                "personal_fouls", "fouls_received", "efficiency"
            ]
            
            for field in numeric_fields:
                if field in player:
                    # Convert to int if it's a string number
                    try:
                        if isinstance(player[field], str):
                            player[field] = int(player[field]) if player[field].isdigit() else 0
                    except (ValueError, AttributeError):
                        player[field] = 0
                else:
                    player[field] = 0
        
        # Handle plus_minus separately (can be negative)
        if "plus_minus" in player:
            try:
                if isinstance(player["plus_minus"], str):
                    player["plus_minus"] = int(player["plus_minus"].replace("+", ""))
            except (ValueError, AttributeError):
                player["plus_minus"] = 0
        else:
            player["plus_minus"] = 0

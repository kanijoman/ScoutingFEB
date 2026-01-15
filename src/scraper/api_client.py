"""FEB API client for fetching match data."""

import requests
from typing import Optional, Dict, List

from .constants import BOXSCORE_API_URL, SHOTCHART_API_URL, KEYFACTS_API_URL, DEFAULT_HEADERS, MATCH_PAGE_URL
from .web_client import WebClient
from .token_manager import TokenManager
from .data_processor import DataProcessor
from .legacy_parser import LegacyHTMLParser
from .data_normalizer import DataNormalizer


class FEBApiClient:
    """Client for FEB API endpoints."""

    def __init__(self, token_manager: TokenManager, web_client: WebClient):
        """
        Initialize API client.

        Args:
            token_manager: TokenManager instance
            web_client: WebClient instance
        """
        self.token_manager = token_manager
        self.web_client = web_client
        self.data_processor = DataProcessor()
        self.legacy_parser = LegacyHTMLParser()

    def fetch_boxscore(self, match_code: str, session: requests.Session) -> Optional[Dict]:
        """
        Fetch and process complete boxscore data including shotchart and playbyplay.
        Falls back to HTML parsing for legacy matches (pre-2019-20) when API returns 404.

        Args:
            match_code: Match identifier
            session: Requests session

        Returns:
            Complete boxscore data or None if failed
        """
        token = self.token_manager.get_token(match_code, session)
        if not token:
            print(f"[FEBApiClient] No token available for match {match_code}")
            return None

        # Try API endpoint first
        url = BOXSCORE_API_URL.format(match_code=match_code)
        headers = {"Authorization": f"Bearer {token}"}

        response = self.web_client.get_with_retry(
            url,
            headers=headers,
            on_401=lambda: self._refresh_token(match_code, session),
            allow_404=True  # Allow 404 so we can fall back to HTML parsing
        )

        # If API returns 404 or no response, try HTML fallback
        if not response or response.status_code == 404:
            reason = "404" if response and response.status_code == 404 else "no response"
            print(f"[FEBApiClient] API returned {reason} for match {match_code}, trying HTML fallback...")
            return self._fetch_boxscore_from_html(match_code, session)

        try:
            data = response.json()
        except ValueError as e:
            print(f"[FEBApiClient] Failed to parse JSON response: {e}")
            # Try HTML fallback
            return self._fetch_boxscore_from_html(match_code, session)

        # Normalize data format (modern API)
        data = DataNormalizer.normalize_match_data(data)
        
        # Process boxscore data
        data = self.data_processor.process_boxscore(data, match_code)
        if not data:
            return None

        # Fetch additional data
        token = self.token_manager.get_token(match_code, session)  # Get fresh token
        if token:
            self._add_shotchart_data(data, match_code, session, token)
            self._add_playbyplay_data(data, match_code, session, token)

        return data
    
    def _fetch_boxscore_from_html(self, match_code: str, session: requests.Session) -> Optional[Dict]:
        """
        Fetch boxscore data by parsing HTML (for legacy matches).
        Converts legacy format to standard FEB API format.
        
        Args:
            match_code: Match identifier
            session: Requests session
            
        Returns:
            Boxscore data in standard FEB format or None if failed
        """
        try:
            from .constants import HTML_HEADERS
            match_url = MATCH_PAGE_URL.format(match_code=match_code)
            
            response = session.get(match_url, headers=HTML_HEADERS, timeout=15)
            response.raise_for_status()
            
            print(f"[FEBApiClient] Parsing HTML for legacy match {match_code}")
            legacy_data = self.legacy_parser.parse_boxscore(response.text, match_code)
            
            if not legacy_data:
                print(f"[FEBApiClient] Legacy parser returned no data")
                return None
            
            # Convert legacy format to standard FEB API format
            standard_data = self._convert_legacy_to_standard_format(legacy_data, match_code)
            
            if standard_data:
                # Normalize legacy data to unified format
                standard_data = DataNormalizer.normalize_match_data(standard_data)
                
                print(f"[FEBApiClient] Successfully parsed legacy match data")
                home_team = standard_data["HEADER"]["TEAM"][0]["name"] if standard_data["HEADER"].get("TEAM") else "Unknown"
                away_team = standard_data["HEADER"]["TEAM"][1]["name"] if len(standard_data["HEADER"].get("TEAM", [])) > 1 else "Unknown"
                
                # Count players (could be in TEAM structure or flat PLAYER list)
                if "TEAM" in standard_data.get("BOXSCORE", {}):
                    player_count = sum(len(team.get("PLAYER", [])) for team in standard_data["BOXSCORE"]["TEAM"])
                else:
                    player_count = len(standard_data.get("BOXSCORE", {}).get("PLAYER", []))
                
                print(f"  - Teams: {home_team} vs {away_team}")
                print(f"  - Players: {player_count}")
            
            return standard_data
            
        except Exception as e:
            print(f"[FEBApiClient] Failed to fetch HTML for match {match_code}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _convert_legacy_to_standard_format(self, legacy_data: Dict, match_code: str) -> Optional[Dict]:
        """
        Convert legacy HTML parser format to standard FEB API format.
        
        Args:
            legacy_data: Data from legacy HTML parser
            match_code: Match identifier
            
        Returns:
            Data in standard FEB API format with HEADER and BOXSCORE sections
        """
        try:
            # Create HEADER section
            header = {
                "game_code": match_code,
                "competition_name": legacy_data.get("competition_name", ""),
                "season": legacy_data.get("season", ""),
                "starttime": legacy_data.get("match_date", ""),
                "location": legacy_data.get("venue", ""),
                "city": legacy_data.get("city", ""),
                "round": "",  # Will be filled by main.py
                "TEAM": []
            }
            
            # Add team data
            if "home_team" in legacy_data:
                header["TEAM"].append({
                    "team_id": legacy_data.get("home_team_id", ""),
                    "code": legacy_data.get("home_team_code", ""),
                    "name": legacy_data.get("home_team", ""),
                    "score": str(legacy_data.get("home_score", 0)),
                    "is_home": True
                })
            
            if "away_team" in legacy_data:
                header["TEAM"].append({
                    "team_id": legacy_data.get("away_team_id", ""),
                    "code": legacy_data.get("away_team_code", ""),
                    "name": legacy_data.get("away_team", ""),
                    "score": str(legacy_data.get("away_score", 0)),
                    "is_home": False
                })
            
            # Create BOXSCORE section
            boxscore = {
                "PLAYER": []
            }
            
            # Get team names for matching
            home_team_name = legacy_data.get("home_team", "").upper()
            away_team_name = legacy_data.get("away_team", "").upper()
            
            # Convert player stats and assign is_home based on team name
            for player in legacy_data.get("players", []):
                player_team = player.get("team", "").upper()
                
                # Determine if player is home or away by matching team name
                is_home = True  # Default to home
                if player_team:
                    # Check similarity with team names
                    # Player team might be abbreviated or slightly different
                    if away_team_name and away_team_name in player_team:
                        is_home = False
                    elif away_team_name and player_team in away_team_name:
                        is_home = False
                    elif home_team_name and home_team_name in player_team:
                        is_home = True
                    elif home_team_name and player_team in home_team_name:
                        is_home = True
                
                player_stat = {
                    "player_id": player.get("player_id", ""),
                    "name": player.get("name", ""),
                    "dorsal": player.get("jersey", ""),
                    "is_starter": player.get("starter", False),
                    "is_home": is_home,
                    "team_name": player.get("team", ""),
                    
                    # Stats - map legacy field names to standard names
                    "minutes": player.get("minutes", "0"),
                    "points": player.get("points", 0),
                    "field_goals_made": player.get("field_goals_made", 0),
                    "field_goals_attempted": player.get("field_goals_att", 0),
                    "two_points_made": player.get("two_pt_made", 0),
                    "two_points_attempted": player.get("two_pt_att", 0),
                    "three_points_made": player.get("three_pt_made", 0),
                    "three_points_attempted": player.get("three_pt_att", 0),
                    "free_throws_made": player.get("free_throws_made", 0),
                    "free_throws_attempted": player.get("free_throws_att", 0),
                    "offensive_rebounds": player.get("rebounds_off", 0),
                    "defensive_rebounds": player.get("rebounds_def", 0),
                    "total_rebounds": player.get("rebounds_total", 0),
                    "assists": player.get("assists", 0),
                    "steals": player.get("steals", 0),
                    "turnovers": player.get("turnovers", 0),
                    "blocks": player.get("blocks_favor", 0),
                    "blocks_received": player.get("blocks_against", 0),
                    "personal_fouls": player.get("fouls_committed", 0),
                    "fouls_received": player.get("fouls_received", 0),
                    "plus_minus": player.get("plus_minus", "0"),
                    "efficiency": player.get("efficiency", 0)
                }
                boxscore["PLAYER"].append(player_stat)
            
            # Combine into standard format
            standard_data = {
                "HEADER": header,
                "BOXSCORE": boxscore,
                "data_source": "html_legacy"
            }
            
            return standard_data
            
        except Exception as e:
            print(f"[FEBApiClient] Failed to convert legacy data to standard format: {e}")
            import traceback
            traceback.print_exc()
            return None

    def fetch_shotchart(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """
        Fetch shotchart data for a match.

        Args:
            match_code: Match identifier
            session: Requests session
            token: Authentication token

        Returns:
            Shotchart data list or None if failed
        """
        return self._fetch_api_data(
            SHOTCHART_API_URL.format(match_code=match_code),
            match_code,
            session,
            token,
            "SHOTCHART"
        )

    def fetch_playbyplay(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """
        Fetch play-by-play data for a match.

        Args:
            match_code: Match identifier
            session: Requests session
            token: Authentication token

        Returns:
            Play-by-play data list or None if failed
        """
        return self._fetch_api_data(
            KEYFACTS_API_URL.format(match_code=match_code),
            match_code,
            session,
            token,
            "PLAYBYPLAY"
        )

    def _fetch_api_data(self, url: str, match_code: str, session: requests.Session,
                       token: str, key: str) -> Optional[List]:
        """
        Fetch data from API endpoint with retry on 401.

        Args:
            url: API endpoint URL
            match_code: Match identifier
            session: Requests session
            token: Authentication token
            key: JSON key to extract from response

        Returns:
            Data list or None if failed
        """
        headers = {"Authorization": f"Bearer {token}"}

        response = self.web_client.get_with_retry(
            url,
            headers=headers,
            on_401=lambda: self._refresh_token(match_code, session)
        )

        if not response:
            return None

        try:
            json_data = response.json()
            return json_data.get(key, [])
        except ValueError as e:
            return None

    def _refresh_token(self, match_code: str, session: requests.Session) -> Optional[str]:
        """
        Refresh token after 401 error.

        Args:
            match_code: Match identifier
            session: Requests session

        Returns:
            New token or None if failed
        """
        self.token_manager.invalidate_token(match_code)
        return self.token_manager.get_token(match_code, session)

    def _add_shotchart_data(self, data: Dict, match_code: str, session: requests.Session, token: str):
        """Add shotchart data to boxscore dictionary."""
        shotchart_data = self.fetch_shotchart(match_code, session, token)
        if shotchart_data is not None:
            data["SHOTCHART"] = shotchart_data

    def _add_playbyplay_data(self, data: Dict, match_code: str, session: requests.Session, token: str):
        """Add play-by-play data to boxscore dictionary."""
        playbyplay_data = self.fetch_playbyplay(match_code, session, token)
        if playbyplay_data is not None:
            data["PLAYBYPLAY"] = playbyplay_data

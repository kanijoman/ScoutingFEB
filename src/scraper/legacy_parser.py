"""HTML parser for legacy match data (pre-2019-20)."""

from bs4 import BeautifulSoup
from typing import Optional, Dict, List
import re


class LegacyHTMLParser:
    """Parser for extracting match data from HTML when API is not available."""
    
    def parse_boxscore(self, html_content: str, match_code: str) -> Optional[Dict]:
        """
        Parse boxscore data from HTML content.
        
        Args:
            html_content: HTML content from match page
            match_code: Match identifier
            
        Returns:
            Boxscore data dictionary or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Quick check: Does this page have any player stats tables?
            # If not, this is likely a future match or one without data
            tables = soup.find_all('table', cellpadding="0", cellspacing="0")
            has_player_data = False
            for table in tables:
                # Check if table has player stats rows (not just headers)
                rows = table.find_all('tr')
                for row in rows:
                    if not row.find('th') and 'row-total' not in row.get('class', []):
                        cells = row.find_all('td')
                        if len(cells) >= 20:  # Player stats have 20+ columns
                            has_player_data = True
                            break
                if has_player_data:
                    break
            
            if not has_player_data:
                print(f"[LegacyHTMLParser] No player data found for match {match_code} (likely future/unplayed)")
                return None
            
            # Extract basic match info
            boxscore = {
                'match_code': match_code,
                'competition_name': self._extract_competition(soup),
                'season': self._extract_season(soup),
                'match_date': self._extract_date(soup),
                'match_time': self._extract_time(soup),
                'venue': self._extract_venue(soup),
                'city': self._extract_city(soup),
                'referees': self._extract_referees(soup),
            }
            
            # Extract team info and scores
            team_data = self._extract_team_data(soup)
            boxscore.update(team_data)
            
            # Extract player stats
            boxscore['players'] = self._extract_player_stats(soup)
            
            # Mark as legacy data
            boxscore['data_source'] = 'html_legacy'
            
            return boxscore if boxscore.get('players') else None
            
        except Exception as e:
            print(f"[LegacyHTMLParser] Failed to parse HTML for match {match_code}: {e}")
            return None
    
    def _extract_competition(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract competition name from page title or header."""
        title_elem = soup.find('h1', class_='titulo-modulo')
        if not title_elem:
            # Try page title
            page_content = soup.find('div', id='page-content')
            if page_content:
                h1 = page_content.find('h1')
                if h1:
                    return h1.get_text(strip=True)
        
        # Try from breadcrumbs or meta
        for elem in soup.find_all('span'):
            text = elem.get_text(strip=True)
            if 'L.F' in text or 'LF' in text or 'LIGA' in text.upper():
                return text
        
        return None
    
    def _extract_season(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract season from page."""
        # Look for season pattern like "2019/2020"
        text = soup.get_text()
        season_match = re.search(r'(\d{4}/\d{4})', text)
        if season_match:
            return season_match.group(1)
        return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract match date."""
        # Look for date in various formats
        text = soup.get_text()
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', text)
        if date_match:
            return date_match.group(1)
        return None
    
    def _extract_time(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract match time."""
        text = soup.get_text()
        time_match = re.search(r'(\d{2}:\d{2})', text)
        if time_match:
            return time_match.group(1)
        return None
    
    def _extract_venue(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract venue/pavilion name."""
        # Try specific span ID
        venue_span = soup.find('span', id='_ctl0_MainContentPlaceHolderMaster_pabellon')
        if venue_span:
            venue_text = venue_span.get_text(strip=True)
            if venue_text and venue_text != ' ':
                return venue_text
        return None
    
    def _extract_city(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract city."""
        # Try specific span ID
        city_span = soup.find('span', id='_ctl0_MainContentPlaceHolderMaster_localidad')
        if city_span:
            city_text = city_span.get_text(strip=True)
            if city_text and city_text != ' ':
                return city_text
        return None
    
    def _extract_referees(self, soup: BeautifulSoup) -> List[str]:
        """Extract referee names."""
        referees = []
        # Try specific referee span IDs first
        for i in range(1, 4):
            ref_span = soup.find('span', id=f'_ctl0_MainContentPlaceHolderMaster_arbitro{i}Nombre')
            if ref_span:
                ref_name = ref_span.get_text(strip=True)
                if ref_name and ref_name != ' ':
                    referees.append(ref_name)
        
        # Fallback: search in text for referee patterns
        if not referees:
            text = soup.get_text()
            ref_matches = re.findall(r'[A-Z]{3,}\s+[A-Z]{3,},\s+[A-Z]{3,}', text)
            referees = ref_matches[:3]
        
        return referees
    
    def _extract_team_data(self, soup: BeautifulSoup) -> Dict:
        """Extract team names, logos, and scores."""
        data = {}
        
        # Find score box
        score_box = soup.find('div', class_='box-marcador')
        if not score_box:
            return data
        
        # Home team (local) - try both class patterns
        home_div = score_box.find('div', class_='columna equipo local')
        if not home_div:
            home_div = score_box.find('div', class_='equipo local')
        
        if home_div:
            name_span = home_div.find('span', class_='nombre')
            if name_span:
                link = name_span.find('a')
                if link:
                    data['home_team'] = link.get_text(strip=True)
                    team_url = link.get('href', '')
                    team_id_match = re.search(r'i=(\d+)', team_url)
                    if team_id_match:
                        data['home_team_id'] = team_id_match.group(1)
            
            score_span = home_div.find('span', class_='resultado')
            if score_span:
                data['home_score'] = int(score_span.get_text(strip=True))
            
            logo_img = home_div.find('img')
            if logo_img:
                data['home_logo'] = logo_img.get('src', '')
        
        # Away team (visitante) - try both class patterns
        away_div = score_box.find('div', class_='columna equipo visitante')
        if not away_div:
            away_div = score_box.find('div', class_='equipo visitante')
        
        if away_div:
            name_span = away_div.find('span', class_='nombre')
            if name_span:
                link = name_span.find('a')
                if link:
                    data['away_team'] = link.get_text(strip=True)
                    team_url = link.get('href', '')
                    team_id_match = re.search(r'i=(\d+)', team_url)
                    if team_id_match:
                        data['away_team_id'] = team_id_match.group(1)
            
            score_span = away_div.find('span', class_='resultado')
            if score_span:
                data['away_score'] = int(score_span.get_text(strip=True))
            
            logo_img = away_div.find('img')
            if logo_img:
                data['away_logo'] = logo_img.get('src', '')
        
        # Quarter scores (parciales)
        parciales_div = score_box.find('div', class_='fila parciales')
        if parciales_div:
            home_quarters = parciales_div.find('div', class_='columna equipo local')
            away_quarters = parciales_div.find('div', class_='columna equipo visitante')
            
            if home_quarters and away_quarters:
                home_q_spans = home_quarters.find_all('span')
                away_q_spans = away_quarters.find_all('span')
                
                data['home_quarters'] = [int(s.get_text(strip=True)) for s in home_q_spans if s.get_text(strip=True).isdigit()]
                data['away_quarters'] = [int(s.get_text(strip=True)) for s in away_q_spans if s.get_text(strip=True).isdigit()]
        
        return data
    
    def _extract_player_stats(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract player statistics from all tables."""
        players = []
        
        # Find all stat tables
        tables = soup.find_all('table', cellpadding="0", cellspacing="0")
        
        current_team = None
        for table in tables:
            # Get team name from preceding h1
            prev_h1 = table.find_previous('h1', class_='titulo-modulo')
            if prev_h1:
                current_team = prev_h1.get_text(strip=True)
            
            # Find all player rows (skip header and total rows)
            rows = table.find_all('tr')
            for row in rows:
                # Skip if it's a header or total row
                if row.find('th') or 'row-total' in row.get('class', []):
                    continue
                
                player_data = self._parse_player_row(row, current_team)
                if player_data:
                    players.append(player_data)
        
        return players
    
    def _parse_player_row(self, row, team_name: Optional[str]) -> Optional[Dict]:
        """Parse a single player stats row."""
        try:
            cells = row.find_all('td')
            if len(cells) < 20:  # Need at least 20 columns
                return None
            
            # Extract player name and link
            name_cell = cells[2]  # Column 3 is player name
            name_link = name_cell.find('a')
            if not name_link:
                return None
            
            player_url = name_link.get('href', '')
            player_id_match = re.search(r'c=(\d+)', player_url)
            player_id = player_id_match.group(1) if player_id_match else None
            
            # Parse shooting stats
            def parse_shots(text):
                """Parse shots like '7/12 58,3%' into (made, attempted, pct)."""
                match = re.match(r'(\d+)/(\d+)\s*<span[^>]*>([^<]+)</span>', str(text))
                if match:
                    return int(match.group(1)), int(match.group(2)), match.group(3)
                match = re.match(r'(\d+)/(\d+)', text.strip())
                if match:
                    made, attempted = int(match.group(1)), int(match.group(2))
                    pct = f"{(made/attempted*100):.1f}%" if attempted > 0 else "0%"
                    return made, attempted, pct
                return 0, 0, "0%"
            
            # Get cell text safely
            def get_text(idx):
                return cells[idx].get_text(strip=True) if idx < len(cells) else ''
            
            def get_int(idx, default=0):
                text = get_text(idx)
                try:
                    return int(text) if text.lstrip('-').isdigit() else default
                except:
                    return default
            
            # Parse all stats
            t2_made, t2_att, t2_pct = parse_shots(cells[5].decode_contents())
            t3_made, t3_att, t3_pct = parse_shots(cells[6].decode_contents())
            fg_made, fg_att, fg_pct = parse_shots(cells[7].decode_contents())
            ft_made, ft_att, ft_pct = parse_shots(cells[8].decode_contents())
            
            player = {
                'team': team_name,
                'player_id': player_id,
                'name': name_link.get_text(strip=True),
                'starter': '*' in get_text(0),  # Column 1 is starter indicator
                'jersey': get_text(1),  # Column 2 is jersey number
                'minutes': get_text(3),  # Column 4 is minutes
                'points': get_int(4),  # Column 5 is points
                'two_pt_made': t2_made,
                'two_pt_att': t2_att,
                'two_pt_pct': t2_pct,
                'three_pt_made': t3_made,
                'three_pt_att': t3_att,
                'three_pt_pct': t3_pct,
                'field_goals_made': fg_made,
                'field_goals_att': fg_att,
                'field_goals_pct': fg_pct,
                'free_throws_made': ft_made,
                'free_throws_att': ft_att,
                'free_throws_pct': ft_pct,
                'rebounds_off': get_int(9),
                'rebounds_def': get_int(10),
                'rebounds_total': get_int(11),
                'assists': get_int(12),
                'steals': get_int(13),
                'turnovers': get_int(14),
                'blocks_favor': get_int(15),
                'blocks_against': get_int(16),
                'dunks': get_int(17),
                'fouls_committed': get_int(18),
                'fouls_received': get_int(19),
                'efficiency': get_int(20),
                'plus_minus': get_text(21) if len(cells) > 21 else None,
            }
            
            return player
            
        except Exception as e:
            print(f"[LegacyHTMLParser] Error parsing player row: {e}")
            return None

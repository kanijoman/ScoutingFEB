"""
Unit tests for FEB scraper module.

Tests the web scraping functionality with mocked HTTP responses.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from bs4 import BeautifulSoup
import requests

from src.scraper.feb_scraper import FEBWebScraper
from src.scraper.web_client import WebClient
from src.utils import normalize_year, get_form_field_name, get_event_target


# ============================================================================
# Utility Functions Tests
# ============================================================================

class TestUtilityFunctions:
    """Test utility functions used by scraper."""
    
    def test_normalize_year_with_slash_format(self):
        """Test year normalization with slash format."""
        assert normalize_year("2024/25") == "2024"
        assert normalize_year("2023/24") == "2023"
    
    def test_normalize_year_with_four_digits(self):
        """Test year normalization with 4-digit year."""
        assert normalize_year("2024") == "2024"
        assert normalize_year("2023") == "2023"
    
    def test_normalize_year_with_two_digits(self):
        """Test year normalization with 2-digit year."""
        assert normalize_year("24") == "2024"
        assert normalize_year("23") == "2023"
    
    def test_normalize_year_with_spaces(self):
        """Test year normalization handles spaces."""
        assert normalize_year(" 2024 ") == "2024"
        assert normalize_year(" 24 ") == "2024"
    
    def test_get_form_field_name(self):
        """Test form field name generation."""
        result = get_form_field_name("_ctl0_ContentPlaceHolder1_ddlSeason")
        assert result == "_ctl0:ContentPlaceHolder1:ddlSeason"
    
    def test_get_event_target(self):
        """Test event target generation."""
        result = get_event_target("_ctl0_ContentPlaceHolder1_ddlSeason")
        assert result == "_ctl0$ContentPlaceHolder1$ddlSeason"
    
    def test_get_form_field_name_consistency(self):
        """Test that form field name is consistent."""
        field_id = "_ctl0_ContentPlaceHolder1_ddlGroup"
        result1 = get_form_field_name(field_id)
        result2 = get_form_field_name(field_id)
        assert result1 == result2
    
    def test_get_event_target_consistency(self):
        """Test that event target is consistent."""
        field_id = "_ctl0_ContentPlaceHolder1_ddlGroup"
        result1 = get_event_target(field_id)
        result2 = get_event_target(field_id)
        assert result1 == result2


# ============================================================================
# FEBWebScraper Tests
# ============================================================================

class TestFEBWebScraper:
    """Test FEBWebScraper class."""
    
    @pytest.fixture
    def mock_web_client(self):
        """Create a mock web client."""
        client = Mock(spec=WebClient)
        client.get_session.return_value = Mock(spec=requests.Session)
        return client
    
    @pytest.fixture
    def scraper(self, mock_web_client):
        """Create scraper instance with mock client."""
        return FEBWebScraper(mock_web_client)
    
    def test_scraper_initialization(self, scraper, mock_web_client):
        """Test scraper initializes correctly."""
        assert scraper.web_client == mock_web_client
    
    def test_get_seasons_with_valid_html(self, scraper):
        """Test extracting seasons from valid HTML."""
        html = """
        <select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">
            <option value="2024/2025">2024/2025</option>
            <option value="2023/2024">2023/2024</option>
            <option value="2022/2023">2022/2023</option>
        </select>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        seasons = scraper.get_seasons(soup)
        
        assert len(seasons) == 3
        assert seasons[0] == ("2024/2025", "2024/2025")
        assert seasons[1] == ("2023/2024", "2023/2024")
    
    def test_get_seasons_with_no_dropdown(self, scraper):
        """Test extracting seasons when dropdown doesn't exist."""
        html = "<div>No dropdown here</div>"
        soup = BeautifulSoup(html, "html.parser")
        
        seasons = scraper.get_seasons(soup)
        
        assert seasons == []
    
    def test_get_seasons_with_empty_dropdown(self, scraper):
        """Test extracting seasons from empty dropdown."""
        html = """
        <select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">
        </select>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        seasons = scraper.get_seasons(soup)
        
        assert seasons == []
    
    def test_get_groups_with_valid_html(self, scraper):
        """Test extracting groups from valid HTML."""
        html = """
        <select id="_ctl0_MainContentPlaceHolderMaster_gruposDropDownList">
            <option value="1">Grupo A</option>
            <option value="2">Grupo B</option>
            <option value="3">Grupo C</option>
        </select>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        groups = scraper.get_groups(soup)
        
        assert len(groups) == 3
        assert groups[0] == ("Grupo A", "1")
        assert groups[1] == ("Grupo B", "2")
    
    def test_get_groups_with_no_dropdown(self, scraper):
        """Test extracting groups when dropdown doesn't exist."""
        html = "<div>No dropdown here</div>"
        soup = BeautifulSoup(html, "html.parser")
        
        groups = scraper.get_groups(soup)
        
        assert groups == []
    
    def test_get_hidden_fields(self, scraper):
        """Test extracting ASP.NET hidden fields."""
        html = """
        <form>
            <input type="hidden" id="__VIEWSTATE" value="viewstate_value_123" />
            <input type="hidden" id="__VIEWSTATEGENERATOR" value="generator_456" />
            <input type="hidden" id="__EVENTVALIDATION" value="validation_789" />
        </form>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        fields = scraper.get_hidden_fields(soup)
        
        assert "__VIEWSTATE" in fields
        assert "__VIEWSTATEGENERATOR" in fields
        assert "__EVENTVALIDATION" in fields
        assert fields["__VIEWSTATE"] == "viewstate_value_123"
    
    def test_get_hidden_fields_missing(self, scraper):
        """Test extracting hidden fields when some are missing."""
        html = """
        <form>
            <input type="hidden" id="__VIEWSTATE" value="viewstate_value" />
        </form>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        fields = scraper.get_hidden_fields(soup)
        
        assert "__VIEWSTATE" in fields
        assert "__VIEWSTATEGENERATOR" not in fields
    
    @pytest.mark.skip(reason="Requires full page HTML structure")
    def test_extract_match_codes(self, scraper):
        """Test extracting match codes from calendar HTML."""
        html = """
        <a href="ficha.aspx?p=12345">Match 1</a>
        <a href="ficha.aspx?p=67890">Match 2</a>
        <a href="ficha.aspx?p=11111">Match 3</a>
        <a href="other.aspx?p=22222">Not a match</a>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        matches = scraper._extract_match_codes(soup)
        
        assert len(matches) == 3
        assert "12345" in matches
        assert "67890" in matches
        assert "11111" in matches
        assert "22222" not in matches
    
    def test_extract_match_codes_no_matches(self, scraper):
        """Test extracting match codes when none exist."""
        html = """
        <div>
            <a href="other.aspx">Link 1</a>
            <a href="another.aspx">Link 2</a>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        
        matches = scraper._extract_match_codes(soup)
        
        assert matches == []
    
    @patch.object(FEBWebScraper, '_build_form_data')
    def test_select_season_calls_build_form_data_correctly(self, mock_build, scraper, mock_web_client):
        """Test that select_season calls _build_form_data with correct parameters."""
        # Setup
        mock_response = Mock()
        mock_response.text = """
        <html>
            <input type="hidden" id="__VIEWSTATE" value="new_state" />
        </html>
        """
        mock_web_client.post.return_value = mock_response
        mock_build.return_value = {"form": "data"}
        
        session = Mock()
        hidden_fields = {"__VIEWSTATE": "old_state"}
        
        # Execute
        scraper.select_season(session, "http://test.com", "2024/2025", hidden_fields)
        
        # Verify _build_form_data was called
        mock_build.assert_called_once()
        call_args = mock_build.call_args[1]
        
        # Verify the additional_fields contains the correct form field name
        assert "additional_fields" in call_args
        field_names = list(call_args["additional_fields"].keys())
        # Should use get_form_field_name, not d_name
        assert any(":" in field_name for field_name in field_names)
    
    @patch.object(FEBWebScraper, '_build_form_data')
    def test_select_group_calls_build_form_data_correctly(self, mock_build, scraper, mock_web_client):
        """Test that select_group calls _build_form_data with correct parameters."""
        # Setup
        mock_response = Mock()
        mock_response.text = "<html><body>Group selected</body></html>"
        mock_web_client.post.return_value = mock_response
        mock_build.return_value = {"form": "data"}
        
        session = Mock()
        hidden_fields = {"__VIEWSTATE": "state"}
        
        # Execute
        scraper.select_group(session, "http://test.com", "2024/2025", "1", hidden_fields)
        
        # Verify _build_form_data was called
        mock_build.assert_called_once()
        call_args = mock_build.call_args[1]
        
        # Verify the additional_fields contains correct form field names
        assert "additional_fields" in call_args
        field_names = list(call_args["additional_fields"].keys())
        # Both fields should use get_form_field_name (with :)
        assert all(":" in field_name for field_name in field_names)


# ============================================================================
# Integration-like Tests (with mocked HTTP)
# ============================================================================

class TestScraperWorkflow:
    """Test complete scraper workflows with mocked responses."""
    
    @pytest.fixture
    def mock_web_client(self):
        """Create a mock web client with realistic responses."""
        client = Mock(spec=WebClient)
        
        # Mock initial page response
        initial_response = Mock()
        initial_response.text = """
        <html>
            <select id="_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList">
                <option value="2024/2025">2024/2025</option>
                <option value="2023/2024">2023/2024</option>
            </select>
            <input type="hidden" id="__VIEWSTATE" value="initial_state" />
            <input type="hidden" id="__VIEWSTATEGENERATOR" value="generator" />
            <input type="hidden" id="__EVENTVALIDATION" value="validation" />
        </html>
        """
        
        client.get.return_value = initial_response
        client.get_session.return_value = Mock(spec=requests.Session)
        
        return client
    
    @pytest.fixture
    def scraper(self, mock_web_client):
        """Create scraper with mocked client."""
        return FEBWebScraper(mock_web_client)
    
    def test_full_page_fetch_and_parse(self, scraper, mock_web_client):
        """Test fetching and parsing a full page."""
        soup, session = scraper.get_page_content("2024")
        
        # Verify get was called with correct URL
        mock_web_client.get.assert_called_once()
        
        # Verify we can extract data from the page
        seasons = scraper.get_seasons(soup)
        assert len(seasons) == 2
        
        hidden_fields = scraper.get_hidden_fields(soup)
        assert "__VIEWSTATE" in hidden_fields


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestScraperEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def mock_web_client(self):
        """Create a mock web client."""
        return Mock(spec=WebClient)
    
    @pytest.fixture
    def scraper(self, mock_web_client):
        """Create scraper instance."""
        return FEBWebScraper(mock_web_client)
    
    def test_get_page_content_with_failed_request(self, scraper, mock_web_client):
        """Test handling failed HTTP request."""
        mock_web_client.get.return_value = None
        
        with pytest.raises(Exception, match="Failed to fetch page"):
            scraper.get_page_content("2024")
    
    def test_get_seasons_with_malformed_html(self, scraper):
        """Test handling malformed HTML."""
        html = "<select id='_ctl0_ContentPlaceHolder1_ddlSeason'><option>Broken"
        soup = BeautifulSoup(html, "html.parser")
        
        # Should not crash, return empty or partial data
        seasons = scraper.get_seasons(soup)
        assert isinstance(seasons, list)
    
    def test_normalize_year_with_invalid_input(self):
        """Test normalize_year with invalid input."""
        result = normalize_year("invalid")
        # Should return the input as-is if can't parse
        assert result == "invalid"
    
    def test_normalize_year_with_empty_string(self):
        """Test normalize_year with empty string."""
        result = normalize_year("")
        assert result == ""
    
    def test_get_form_field_name_with_short_id(self):
        """Test get_form_field_name with ID shorter than expected."""
        # Should handle gracefully
        result = get_form_field_name("_ctl0_dd")
        assert ":" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

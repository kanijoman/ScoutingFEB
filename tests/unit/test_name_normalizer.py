"""
Unit tests for name normalization and matching functionality.

Tests cover corner cases, edge cases, and various name format scenarios
for the NameNormalizer class.
"""

import pytest
from src.ml.name_normalizer import NameNormalizer


@pytest.mark.unit
class TestNameNormalization:
    """Test name normalization function."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_normalize_basic_name(self):
        """Test basic name normalization."""
        result = self.normalizer.normalize_name("Juan Pérez")
        assert result == "JUAN PEREZ"
    
    def test_normalize_removes_accents(self):
        """Test that accents are properly removed."""
        test_cases = [
            ("José María", "JOSE MARIA"),
            ("Ángel García", "ANGEL GARCIA"),
            ("Iñaki López", "INAKI LOPEZ"),
            ("Müller", "MULLER"),
            ("François", "FRANCOIS"),
        ]
        
        for input_name, expected in test_cases:
            result = self.normalizer.normalize_name(input_name)
            assert result == expected, f"Failed for {input_name}"
    
    def test_normalize_removes_special_characters(self):
        """Test that special characters are removed."""
        test_cases = [
            ("O'Connor", "OCONNOR"),
            ("Jean-Pierre", "JEAN-PIERRE"),  # Hyphens are preserved
            ("María José (MJ)", "MARIA JOSE MJ"),
            ("Player #10", "PLAYER 10"),
        ]
        
        for input_name, expected in test_cases:
            result = self.normalizer.normalize_name(input_name)
            assert result == expected, f"Failed for {input_name}"
    
    def test_normalize_handles_multiple_spaces(self):
        """Test that multiple spaces are normalized to single space."""
        result = self.normalizer.normalize_name("Juan    Manuel   García")
        assert result == "JUAN MANUEL GARCIA"
        assert "  " not in result  # No double spaces
    
    def test_normalize_preserves_periods_and_commas(self):
        """Test that periods and commas are preserved."""
        test_cases = [
            ("J. Pérez", "J. PEREZ"),
            ("Pérez, Juan", "PEREZ, JUAN"),
            ("J.M. García", "J.M. GARCIA"),
        ]
        
        for input_name, expected in test_cases:
            result = self.normalizer.normalize_name(input_name)
            assert result == expected
    
    def test_normalize_empty_string(self):
        """Test normalization of empty string."""
        assert self.normalizer.normalize_name("") == ""
        assert self.normalizer.normalize_name("   ") == ""
    
    def test_normalize_none(self):
        """Test normalization of None value."""
        result = self.normalizer.normalize_name(None)
        assert result == ""
    
    def test_normalize_already_normalized(self):
        """Test that already normalized names remain unchanged."""
        normalized = "JUAN PEREZ"
        result = self.normalizer.normalize_name(normalized)
        assert result == normalized


@pytest.mark.unit
class TestParseNameComponents:
    """Test name component parsing."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_parse_simple_name_surname(self):
        """Test parsing simple 'Name Surname' format."""
        initial, first_name, surnames = self.normalizer.parse_name_components("Juan Pérez")
        
        assert initial == "J"
        assert first_name == "JUAN"
        assert surnames == "PEREZ"
    
    def test_parse_multiple_surnames(self):
        """Test parsing with multiple surnames."""
        initial, first_name, surnames = self.normalizer.parse_name_components("María García López")
        
        assert initial == "M"
        assert first_name == "MARIA"
        assert surnames == "GARCIA LOPEZ"
    
    def test_parse_comma_separated_format(self):
        """Test parsing 'Surnames, FirstName' format."""
        initial, first_name, surnames = self.normalizer.parse_name_components("García López, Juan")
        
        assert initial == "J"
        assert first_name == "JUAN"
        assert surnames == "GARCIA LOPEZ"
    
    def test_parse_comma_format_multiple_given_names(self):
        """Test comma format with multiple given names."""
        initial, first_name, surnames = self.normalizer.parse_name_components("Pérez, Juan Manuel")
        
        assert initial == "J"
        assert first_name == "JUAN"
        assert surnames == "PEREZ"
    
    def test_parse_initial_with_period(self):
        """Test parsing name with initial (J. Surname)."""
        initial, first_name, surnames = self.normalizer.parse_name_components("J. Pérez")
        
        assert initial == "J"
        assert first_name == ""
        assert surnames == "PEREZ"
    
    def test_parse_multiple_initials(self):
        """Test parsing with multiple initials (J.M. Surname)."""
        initial, first_name, surnames = self.normalizer.parse_name_components("J.M. García López")
        
        assert initial == "J"
        assert first_name == ""
        assert surnames == "GARCIA LOPEZ"
    
    def test_parse_single_component(self):
        """Test parsing single word (assumed to be surname)."""
        initial, first_name, surnames = self.normalizer.parse_name_components("Pérez")
        
        assert initial == ""
        assert first_name == ""
        assert surnames == "PEREZ"
    
    def test_parse_with_particles(self):
        """Test parsing names with particles (de, del, van, etc)."""
        initial, first_name, surnames = self.normalizer.parse_name_components("María de la Torre")
        
        assert initial == "M"
        assert first_name == "MARIA"
        assert surnames == "DE LA TORRE"
    
    def test_parse_empty_name(self):
        """Test parsing empty name."""
        initial, first_name, surnames = self.normalizer.parse_name_components("")
        
        assert initial == ""
        assert first_name == ""
        assert surnames == ""
    
    def test_parse_comma_only_surnames(self):
        """Test comma format with only surnames."""
        initial, first_name, surnames = self.normalizer.parse_name_components("García López,")
        
        assert surnames == "GARCIA LOPEZ"


@pytest.mark.unit
class TestGetSurnameTokens:
    """Test surname token extraction."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_get_tokens_simple_surname(self):
        """Test token extraction from simple surname."""
        tokens = self.normalizer.get_surname_tokens("GARCIA")
        assert tokens == ["GARCIA"]
    
    def test_get_tokens_compound_surname(self):
        """Test token extraction from compound surname."""
        tokens = self.normalizer.get_surname_tokens("GARCIA LOPEZ")
        assert set(tokens) == {"GARCIA", "LOPEZ"}
    
    def test_get_tokens_filters_particles(self):
        """Test that common particles are filtered out."""
        test_cases = [
            ("DE LA TORRE", ["TORRE"]),
            ("VAN DER BERG", ["DER", "BERG"]),  # DER not in particle list
            ("DEL BOSQUE", ["BOSQUE"]),
            ("DE LOS SANTOS", ["SANTOS"]),
        ]
        
        for input_surname, expected_tokens in test_cases:
            tokens = self.normalizer.get_surname_tokens(input_surname)
            assert tokens == expected_tokens, f"Failed for {input_surname}"
    
    def test_get_tokens_mixed_particles_and_names(self):
        """Test extraction with mix of particles and significant names."""
        tokens = self.normalizer.get_surname_tokens("FERNANDEZ DE LA CRUZ")
        assert set(tokens) == {"FERNANDEZ", "CRUZ"}
        assert "DE" not in tokens
        assert "LA" not in tokens
    
    def test_get_tokens_empty_string(self):
        """Test token extraction from empty string."""
        tokens = self.normalizer.get_surname_tokens("")
        assert tokens == []
    
    def test_get_tokens_only_particles(self):
        """Test extraction when surname contains only particles."""
        tokens = self.normalizer.get_surname_tokens("DE LA")
        assert tokens == []
    
    def test_get_tokens_returns_uppercase(self):
        """Test that tokens are returned in uppercase."""
        tokens = self.normalizer.get_surname_tokens("garcia lopez")
        assert all(token.isupper() for token in tokens)


@pytest.mark.unit
class TestCalculateNameSimilarity:
    """Test name similarity calculation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_similarity_identical_names(self):
        """Test similarity of identical names."""
        score = self.normalizer.calculate_name_similarity("Juan Pérez", "Juan Pérez")
        assert score == 1.0
    
    def test_similarity_same_surnames_different_format(self):
        """Test names with same surname, different format."""
        score = self.normalizer.calculate_name_similarity("J. Pérez", "Juan Pérez")
        # Should be high: same surname (0.6) + same initial (0.2) + partial name (0.1) = 0.9
        assert score >= 0.8
    
    def test_similarity_comma_format_vs_normal(self):
        """Test comma format vs normal format."""
        score = self.normalizer.calculate_name_similarity("Pérez, Juan", "Juan Pérez")
        # Same surname + same first name + same initial = 1.0
        assert score == 1.0
    
    def test_similarity_different_players(self):
        """Test similarity of completely different players."""
        score = self.normalizer.calculate_name_similarity("Juan García", "Pedro López")
        assert score < 0.3
    
    def test_similarity_same_surname_different_names(self):
        """Test same surname but different first names."""
        score = self.normalizer.calculate_name_similarity("Juan García", "Pedro García")
        # Same surname (0.6) but different names/initials
        assert 0.5 < score < 0.7
    
    def test_similarity_compound_surnames_partial_match(self):
        """Test compound surnames with partial matches."""
        score = self.normalizer.calculate_name_similarity(
            "María García López",
            "María García Pérez"
        )
        # Same first name + same first surname token = high similarity
        assert score > 0.5
    
    def test_similarity_with_particles(self):
        """Test similarity handles particles correctly."""
        score = self.normalizer.calculate_name_similarity(
            "María de la Torre",
            "María Torre"
        )
        # Particles should be filtered, so surnames should match
        assert score >= 0.8
    
    def test_similarity_only_initials(self):
        """Test similarity when only initials are available."""
        score = self.normalizer.calculate_name_similarity("J. García", "J. García")
        # Same surname (0.6) + same initial (0.2) + bonus (0.1) = 0.9
        assert score >= 0.8
    
    def test_similarity_different_initials_same_surname(self):
        """Test different initials but same surname."""
        score = self.normalizer.calculate_name_similarity("J. García", "M. García")
        # Only surname matches (0.6)
        assert 0.55 < score < 0.65
    
    def test_similarity_empty_names(self):
        """Test similarity with empty names."""
        score = self.normalizer.calculate_name_similarity("", "Juan García")
        assert score == 0.0
        
        score = self.normalizer.calculate_name_similarity("", "")
        assert score == 0.0
    
    def test_similarity_substring_first_names(self):
        """Test when one first name is substring of another."""
        score = self.normalizer.calculate_name_similarity(
            "José García",
            "José María García"
        )
        # Same surname (0.6) + substring bonus (0.1) = 0.7
        assert score >= 0.7


@pytest.mark.unit
class TestLevenshteinDistance:
    """Test Levenshtein distance calculation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_distance_identical_strings(self):
        """Test distance between identical strings."""
        distance = self.normalizer.calculate_levenshtein_distance("GARCIA", "GARCIA")
        assert distance == 0
    
    def test_distance_single_substitution(self):
        """Test distance with single character substitution."""
        distance = self.normalizer.calculate_levenshtein_distance("GARCIA", "GARSIA")
        assert distance == 1
    
    def test_distance_single_insertion(self):
        """Test distance with single character insertion."""
        distance = self.normalizer.calculate_levenshtein_distance("GARCIA", "GARCIAA")
        assert distance == 1
    
    def test_distance_single_deletion(self):
        """Test distance with single character deletion."""
        distance = self.normalizer.calculate_levenshtein_distance("GARCIA", "GARCI")
        assert distance == 1
    
    def test_distance_multiple_edits(self):
        """Test distance with multiple edits."""
        distance = self.normalizer.calculate_levenshtein_distance("KITTEN", "SITTING")
        # k->s, e->i, insert g = 3 edits
        assert distance == 3
    
    def test_distance_empty_strings(self):
        """Test distance with empty strings."""
        distance = self.normalizer.calculate_levenshtein_distance("", "")
        assert distance == 0
        
        distance = self.normalizer.calculate_levenshtein_distance("ABC", "")
        assert distance == 3
        
        distance = self.normalizer.calculate_levenshtein_distance("", "XYZ")
        assert distance == 3
    
    def test_distance_completely_different(self):
        """Test distance between completely different strings."""
        distance = self.normalizer.calculate_levenshtein_distance("ABC", "XYZ")
        assert distance == 3
    
    def test_distance_case_sensitive(self):
        """Test that distance calculation is case-sensitive."""
        # Should be treated as different since it's raw distance
        distance = self.normalizer.calculate_levenshtein_distance("Garcia", "GARCIA")
        assert distance > 0
    
    def test_distance_symmetric(self):
        """Test that distance is symmetric (d(a,b) = d(b,a))."""
        d1 = self.normalizer.calculate_levenshtein_distance("GARCIA", "PEREZ")
        d2 = self.normalizer.calculate_levenshtein_distance("PEREZ", "GARCIA")
        assert d1 == d2


@pytest.mark.unit
class TestFuzzyMatchScore:
    """Test fuzzy matching score."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_fuzzy_identical_names(self):
        """Test fuzzy score for identical names."""
        score = self.normalizer.fuzzy_match_score("Juan García", "Juan García")
        assert score == 1.0
    
    def test_fuzzy_normalized_comparison(self):
        """Test that fuzzy score normalizes before comparing."""
        # With accents vs without
        score = self.normalizer.fuzzy_match_score("José García", "Jose Garcia")
        assert score == 1.0
    
    def test_fuzzy_small_typo(self):
        """Test fuzzy score with small typo."""
        score = self.normalizer.fuzzy_match_score("GARCIA", "GARSIA")
        # 1 char diff in 6 chars = ~0.83
        assert 0.8 < score < 0.9
    
    def test_fuzzy_completely_different(self):
        """Test fuzzy score for completely different names."""
        score = self.normalizer.fuzzy_match_score("GARCIA", "PEREZ")
        assert score < 0.5
    
    def test_fuzzy_substring(self):
        """Test fuzzy score when one is substring."""
        score = self.normalizer.fuzzy_match_score("GARCIA", "GARCIA LOPEZ")
        # GARCIA is 6 chars, GARCIA LOPEZ is 12 chars
        # 6 chars match perfectly out of 12 = 0.5
        assert 0.4 < score < 0.6
    
    def test_fuzzy_empty_strings(self):
        """Test fuzzy score with empty strings."""
        score = self.normalizer.fuzzy_match_score("", "")
        assert score == 0.0
        
        score = self.normalizer.fuzzy_match_score("GARCIA", "")
        assert score == 0.0
    
    def test_fuzzy_case_insensitive(self):
        """Test that fuzzy matching is case-insensitive."""
        score = self.normalizer.fuzzy_match_score("garcia", "GARCIA")
        assert score == 1.0
    
    def test_fuzzy_with_special_characters(self):
        """Test fuzzy matching with special characters removed."""
        score = self.normalizer.fuzzy_match_score("O'Connor", "OConnor")
        assert score == 1.0  # Special chars removed during normalization


@pytest.mark.unit
class TestEdgeCasesAndCornerCases:
    """Test various edge cases and corner cases."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_very_long_name(self):
        """Test handling of very long names."""
        long_name = "Juan Manuel Fernando Alejandro García López Fernández de la Torre"
        initial, first_name, surnames = self.normalizer.parse_name_components(long_name)
        
        assert initial == "J"
        assert first_name == "JUAN"
        assert len(surnames) > 0
    
    def test_single_letter_name(self):
        """Test handling of single letter names."""
        initial, first_name, surnames = self.normalizer.parse_name_components("J P")
        
        assert initial == "J"
        assert first_name == "J"
        assert surnames == "P"
    
    def test_numbers_in_name(self):
        """Test handling of numbers in names."""
        normalized = self.normalizer.normalize_name("Player 10")
        assert "10" in normalized
        assert normalized == "PLAYER 10"
    
    def test_all_caps_input(self):
        """Test that all-caps input is handled correctly."""
        normalized = self.normalizer.normalize_name("JUAN GARCÍA")
        assert normalized == "JUAN GARCIA"
    
    def test_mixed_case_input(self):
        """Test mixed case input."""
        normalized = self.normalizer.normalize_name("JuAn GaRcÍa")
        assert normalized == "JUAN GARCIA"
    
    def test_leading_trailing_spaces(self):
        """Test that leading/trailing spaces are removed."""
        normalized = self.normalizer.normalize_name("  Juan García  ")
        assert normalized == "JUAN GARCIA"
        assert normalized[0] != " "
        assert normalized[-1] != " "
    
    def test_multiple_commas(self):
        """Test handling of multiple commas."""
        initial, first_name, surnames = self.normalizer.parse_name_components("García, López, Juan")
        # Should split on first comma only
        assert surnames == "GARCIA"
    
    def test_name_with_only_periods(self):
        """Test name that is only periods."""
        initial, first_name, surnames = self.normalizer.parse_name_components("J.M.")
        assert initial == "J"
        assert surnames == ""
    
    def test_unicode_characters(self):
        """Test handling of various Unicode characters."""
        test_names = [
            "Müller",
            "Żółć",
            "Çağlar",
            "Ñoño",
        ]
        
        for name in test_names:
            normalized = self.normalizer.normalize_name(name)
            # Should normalize to ASCII
            assert normalized.isascii() or normalized == ""
    
    def test_similarity_with_accents_mismatch(self):
        """Test similarity when one has accents and other doesn't."""
        score = self.normalizer.calculate_name_similarity("José García", "Jose Garcia")
        # Should be identical after normalization
        assert score == 1.0
    
    def test_three_word_surname(self):
        """Test surname with three words."""
        tokens = self.normalizer.get_surname_tokens("GARCIA DE LA CRUZ")
        assert "GARCIA" in tokens
        assert "CRUZ" in tokens
        assert len([t for t in tokens if t in self.normalizer.PARTICLES]) == 0


@pytest.mark.unit
class TestRealWorldScenarios:
    """Test real-world naming scenarios from basketball data."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.normalizer = NameNormalizer()
    
    def test_spanish_compound_surnames(self):
        """Test typical Spanish compound surnames."""
        test_cases = [
            ("María García López", ("M", "MARIA", "GARCIA LOPEZ")),
            ("Ana Martín Ruiz", ("A", "ANA", "MARTIN RUIZ")),
            ("Laura Pérez Sánchez", ("L", "LAURA", "PEREZ SANCHEZ")),
        ]
        
        for name, expected in test_cases:
            result = self.normalizer.parse_name_components(name)
            assert result == expected
    
    def test_eastern_european_names(self):
        """Test Eastern European naming patterns."""
        score = self.normalizer.calculate_name_similarity(
            "Ivana Djordjevic",
            "Ivana Djordjevic"
        )
        assert score == 1.0
    
    def test_hyphenated_surnames(self):
        """Test hyphenated surnames (common in some leagues)."""
        normalized = self.normalizer.normalize_name("Smith-Johnson")
        # Hyphens are preserved
        assert normalized == "SMITH-JOHNSON"
    
    def test_nickname_vs_full_name(self):
        """Test nickname vs full name matching."""
        # This should have moderate similarity
        score = self.normalizer.calculate_name_similarity(
            "J. García",  # Could be José, Juan, Javier, etc.
            "José García"
        )
        # Same surname + same initial
        assert score >= 0.8
    
    def test_maiden_vs_married_name(self):
        """Test detecting when surnames are completely different."""
        score = self.normalizer.calculate_name_similarity(
            "María García",
            "María López"
        )
        # Same first name but different surname
        assert 0.3 < score < 0.5
    
    def test_double_barrel_name_variations(self):
        """Test variations of double-barrel names."""
        test_cases = [
            ("María José García", "María José García", 1.0),
            ("María José García", "M.J. García", 0.6),  # Only surname match
            ("María José García", "María García", 0.7),  # Surname + partial name (actual score)
        ]
        
        for name1, name2, min_score in test_cases:
            score = self.normalizer.calculate_name_similarity(name1, name2)
            assert score >= min_score, f"Failed for {name1} vs {name2}: {score} < {min_score}"

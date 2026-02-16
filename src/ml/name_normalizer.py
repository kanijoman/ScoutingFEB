"""
Module for player name normalization and matching.

Handles inconsistencies in player names across different formats:
- "J. PÉREZ" (initial + surnames)
- "JUAN PÉREZ" (given name + surnames) 
- "PÉREZ, JUAN" (surnames, given name)
"""

import re
from typing import Tuple, List, Optional
import unicodedata


class NameNormalizer:
    """Normalizes and compares player names."""
    
    # Common particles to ignore in compound surnames
    PARTICLES = {'de', 'del', 'la', 'los', 'las', 'da', 'dos', 'das', 'van', 'von', 'el'}
    
    def __init__(self):
        """Initialize the name normalizer."""
        pass
    
    def normalize_name(self, name: str) -> str:
        """
        Normalizes a name for comparison.
        
        Process:
        1. Converts to uppercase
        2. Removes accents
        3. Removes special characters
        4. Normalizes spaces
        
        Args:
            name: Original name
            
        Returns:
            Normalized name
        """
        if not name:
            return ""
        
        # Convert to uppercase
        name = name.upper().strip()
        
        # Remove accents
        name = self._remove_accents(name)
        
        # Remove special characters except spaces, periods and commas
        name = re.sub(r'[^A-Z0-9\s\.,\-]', '', name)
        
        # Normalize multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def _remove_accents(self, text: str) -> str:
        """
        Removes accents and diacritics.
        
        Args:
            text: Text with accents
            
        Returns:
            Text without accents
        """
        # Decompose Unicode characters
        nfd = unicodedata.normalize('NFD', text)
        # Filter diacritic marks
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    
    def parse_name_components(self, name: str) -> Tuple[str, str, str]:
        """
        Extracts name components: initials, first name, surnames.
        
        Detects and processes formats:
        - "J. PÉREZ" -> ("J", "", "PEREZ")
        - "JUAN PÉREZ" -> ("J", "JUAN", "PEREZ")
        - "PÉREZ, JUAN" -> ("J", "JUAN", "PEREZ")
        - "JUAN MANUEL PÉREZ GARCÍA" -> ("J", "JUAN", "PEREZ GARCIA")
        
        Args:
            name: Full name
            
        Returns:
            Tuple (first_name_initial, full_first_name, surnames)
        """
        name = self.normalize_name(name)
        
        if not name:
            return ("", "", "")
        
        # Format: "SURNAMES, NAME"
        if ',' in name:
            parts = name.split(',', 1)
            surnames = parts[0].strip()
            given_names = parts[1].strip() if len(parts) > 1 else ""
            
            # Extract first name
            first_name = given_names.split()[0] if given_names else ""
            initial = first_name[0] if first_name else ""
            
            return (initial, first_name, surnames)
        
        # Format with period: "J. PÉREZ" or "J.M. PÉREZ"
        if '.' in name:
            parts = name.split()
            
            # Find where initials end
            initials_end = 0
            for i, part in enumerate(parts):
                if '.' in part:
                    initials_end = i + 1
                else:
                    break
            
            # First initial
            initial = parts[0][0] if parts else ""
            
            # Surnames are the rest
            surnames = ' '.join(parts[initials_end:]) if initials_end < len(parts) else ""
            
            return (initial, "", surnames)
        
        # Format: "NAME SURNAMES"
        parts = name.split()
        
        if len(parts) == 1:
            # Only one component - assume it's a surname
            return ("", "", parts[0])
        
        # Assume first token is the given name
        first_name = parts[0]
        initial = first_name[0] if first_name else ""
        
        # Rest are surnames (can be multiple)
        surnames = ' '.join(parts[1:])
        
        return (initial, first_name, surnames)
    
    def get_surname_tokens(self, surnames: str) -> List[str]:
        """
        Extracts significant surname tokens.
        
        Ignores common particles like "de", "del", "la", etc.
        
        Args:
            surnames: Full surnames
            
        Returns:
            List of significant tokens
        """
        if not surnames:
            return []
        
        tokens = surnames.lower().split()
        
        # Filter particles
        significant = [t for t in tokens if t not in self.PARTICLES]
        
        return [t.upper() for t in significant]
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calculates similarity between two names (0.0 - 1.0).
        
        Strategy:
        1. If surnames match exactly -> high similarity
        2. If surnames have tokens in common -> medium similarity
        3. If initials match -> bonus
        4. If full name matches -> additional bonus
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical)
        """
        # Parse components
        init1, fname1, sname1 = self.parse_name_components(name1)
        init2, fname2, sname2 = self.parse_name_components(name2)
        
        similarity_score = 0.0
        
        # 1. Compare surnames (60% weight)
        if sname1 and sname2:
            # Exact surname match
            if sname1 == sname2:
                similarity_score += 0.60
            else:
                # Compare surname tokens
                tokens1 = set(self.get_surname_tokens(sname1))
                tokens2 = set(self.get_surname_tokens(sname2))
                
                if tokens1 and tokens2:
                    # Jaccard similarity of tokens
                    intersection = tokens1.intersection(tokens2)
                    union = tokens1.union(tokens2)
                    
                    if union:
                        jaccard = len(intersection) / len(union)
                        similarity_score += 0.60 * jaccard
        
        # 2. Compare initials (20% weight)
        if init1 and init2:
            if init1 == init2:
                similarity_score += 0.20
        
        # 3. Compare full names if available (20% weight)
        if fname1 and fname2:
            if fname1 == fname2:
                similarity_score += 0.20
            # Partial match (one is substring of the other)
            elif fname1 in fname2 or fname2 in fname1:
                similarity_score += 0.10
        elif init1 and init2 and init1 == init2:
            # Only have initials and they match
            similarity_score += 0.10
        
        return min(1.0, similarity_score)
    
    def calculate_levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculates Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            return self.calculate_levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Cost of insertion, deletion, substitution
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def fuzzy_match_score(self, name1: str, name2: str) -> float:
        """
        Fuzzy matching score using Levenshtein distance.
        
        Args:
            name1: First name
            name2: Second name
            
        Returns:
            Normalized score (0.0 - 1.0)
        """
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        distance = self.calculate_levenshtein_distance(norm1, norm2)
        max_len = max(len(norm1), len(norm2))
        
        if max_len == 0:
            return 0.0
        
        # Normalize: 1.0 = identical, 0.0 = completely different
        return 1.0 - (distance / max_len)


def test_name_normalizer():
    """Test function for the name normalizer."""
    normalizer = NameNormalizer()
    
    test_cases = [
        ("J. PÉREZ", "JUAN PÉREZ"),
        ("PÉREZ, JUAN", "JUAN PÉREZ"),
        ("J.M. GARCÍA", "JOSÉ MARÍA GARCÍA"),
        ("FERNÁNDEZ LÓPEZ", "FERNANDEZ, JUAN"),
        ("DE LA TORRE, MARÍA", "MARÍA DE LA TORRE"),
    ]
    
    print("=" * 80)
    print("TEST: Name Normalizer")
    print("=" * 80)
    
    for name1, name2 in test_cases:
        score = normalizer.calculate_name_similarity(name1, name2)
        fuzzy = normalizer.fuzzy_match_score(name1, name2)
        
        comp1 = normalizer.parse_name_components(name1)
        comp2 = normalizer.parse_name_components(name2)
        
        print(f"\n'{name1}' vs '{name2}'")
        print(f"  Components 1: {comp1}")
        print(f"  Components 2: {comp2}")
        print(f"  Similarity:   {score:.2f}")
        print(f"  Fuzzy match:  {fuzzy:.2f}")


if __name__ == "__main__":
    test_name_normalizer()

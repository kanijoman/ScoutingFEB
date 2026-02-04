"""
Módulo para normalización y matching de nombres de jugadores.

Gestiona las inconsistencias en nombres de jugadores entre diferentes formatos:
- "J. PÉREZ" (inicial + apellidos)
- "JUAN PÉREZ" (nombre + apellidos) 
- "PÉREZ, JUAN" (apellidos, nombre)
"""

import re
from typing import Tuple, List, Optional
import unicodedata


class NameNormalizer:
    """Normaliza y compara nombres de jugadores."""
    
    # Palabras comunes a ignorar en apellidos compuestos
    PARTICLES = {'de', 'del', 'la', 'los', 'las', 'da', 'dos', 'das', 'van', 'von', 'el'}
    
    def __init__(self):
        """Inicializar el normalizador."""
        pass
    
    def normalize_name(self, name: str) -> str:
        """
        Normaliza un nombre para comparación.
        
        Proceso:
        1. Convierte a mayúsculas
        2. Elimina acentos
        3. Elimina caracteres especiales
        4. Normaliza espacios
        
        Args:
            name: Nombre original
            
        Returns:
            Nombre normalizado
        """
        if not name:
            return ""
        
        # Convertir a mayúsculas
        name = name.upper().strip()
        
        # Eliminar acentos
        name = self._remove_accents(name)
        
        # Eliminar caracteres especiales excepto espacios, puntos y comas
        name = re.sub(r'[^A-Z0-9\s\.,\-]', '', name)
        
        # Normalizar espacios múltiples
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def _remove_accents(self, text: str) -> str:
        """
        Elimina acentos y diacríticos.
        
        Args:
            text: Texto con acentos
            
        Returns:
            Texto sin acentos
        """
        # Descomponer caracteres Unicode
        nfd = unicodedata.normalize('NFD', text)
        # Filtrar marcas diacríticas
        return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    
    def parse_name_components(self, name: str) -> Tuple[str, str, str]:
        """
        Extrae componentes del nombre: iniciales, primer nombre, apellidos.
        
        Detecta y procesa formatos:
        - "J. PÉREZ" -> ("J", "", "PEREZ")
        - "JUAN PÉREZ" -> ("J", "JUAN", "PEREZ")
        - "PÉREZ, JUAN" -> ("J", "JUAN", "PEREZ")
        - "JUAN MANUEL PÉREZ GARCÍA" -> ("J", "JUAN", "PEREZ GARCIA")
        
        Args:
            name: Nombre completo
            
        Returns:
            Tupla (inicial_primer_nombre, primer_nombre_completo, apellidos)
        """
        name = self.normalize_name(name)
        
        if not name:
            return ("", "", "")
        
        # Formato: "APELLIDOS, NOMBRE"
        if ',' in name:
            parts = name.split(',', 1)
            surnames = parts[0].strip()
            given_names = parts[1].strip() if len(parts) > 1 else ""
            
            # Extraer primer nombre
            first_name = given_names.split()[0] if given_names else ""
            initial = first_name[0] if first_name else ""
            
            return (initial, first_name, surnames)
        
        # Formato con punto: "J. PÉREZ" o "J.M. PÉREZ"
        if '.' in name:
            parts = name.split()
            
            # Buscar dónde terminan las iniciales
            initials_end = 0
            for i, part in enumerate(parts):
                if '.' in part:
                    initials_end = i + 1
                else:
                    break
            
            # Primera inicial
            initial = parts[0][0] if parts else ""
            
            # Apellidos son el resto
            surnames = ' '.join(parts[initials_end:]) if initials_end < len(parts) else ""
            
            return (initial, "", surnames)
        
        # Formato: "NOMBRE APELLIDOS"
        parts = name.split()
        
        if len(parts) == 1:
            # Solo un componente - asumimos que es apellido
            return ("", "", parts[0])
        
        # Asumimos que el primer token es el nombre
        first_name = parts[0]
        initial = first_name[0] if first_name else ""
        
        # El resto son apellidos (pueden ser múltiples)
        surnames = ' '.join(parts[1:])
        
        return (initial, first_name, surnames)
    
    def get_surname_tokens(self, surnames: str) -> List[str]:
        """
        Extrae tokens significativos de apellidos.
        
        Ignora partículas comunes como "de", "del", "la", etc.
        
        Args:
            surnames: Apellidos completos
            
        Returns:
            Lista de tokens significativos
        """
        if not surnames:
            return []
        
        tokens = surnames.lower().split()
        
        # Filtrar partículas
        significant = [t for t in tokens if t not in self.PARTICLES]
        
        return [t.upper() for t in significant]
    
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """
        Calcula similitud entre dos nombres (0.0 - 1.0).
        
        Estrategia:
        1. Si los apellidos coinciden exactamente -> alta similitud
        2. Si los apellidos tienen tokens en común -> similitud media
        3. Si las iniciales coinciden -> bonus
        4. Si el nombre completo coincide -> bonus adicional
        
        Args:
            name1: Primer nombre
            name2: Segundo nombre
            
        Returns:
            Score de similitud (0.0 = totalmente diferentes, 1.0 = idénticos)
        """
        # Parsear componentes
        init1, fname1, sname1 = self.parse_name_components(name1)
        init2, fname2, sname2 = self.parse_name_components(name2)
        
        similarity_score = 0.0
        
        # 1. Comparar apellidos (peso 60%)
        if sname1 and sname2:
            # Coincidencia exacta de apellidos
            if sname1 == sname2:
                similarity_score += 0.60
            else:
                # Comparar tokens de apellidos
                tokens1 = set(self.get_surname_tokens(sname1))
                tokens2 = set(self.get_surname_tokens(sname2))
                
                if tokens1 and tokens2:
                    # Jaccard similarity de tokens
                    intersection = tokens1.intersection(tokens2)
                    union = tokens1.union(tokens2)
                    
                    if union:
                        jaccard = len(intersection) / len(union)
                        similarity_score += 0.60 * jaccard
        
        # 2. Comparar iniciales (peso 20%)
        if init1 and init2:
            if init1 == init2:
                similarity_score += 0.20
        
        # 3. Comparar nombres completos si están disponibles (peso 20%)
        if fname1 and fname2:
            if fname1 == fname2:
                similarity_score += 0.20
            # Coincidencia parcial (uno es substring del otro)
            elif fname1 in fname2 or fname2 in fname1:
                similarity_score += 0.10
        elif init1 and init2 and init1 == init2:
            # Solo tenemos iniciales y coinciden
            similarity_score += 0.10
        
        return min(1.0, similarity_score)
    
    def calculate_levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calcula distancia de Levenshtein entre dos strings.
        
        Args:
            s1: Primer string
            s2: Segundo string
            
        Returns:
            Distancia de edición
        """
        if len(s1) < len(s2):
            return self.calculate_levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                # Coste de inserción, eliminación, sustitución
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    def fuzzy_match_score(self, name1: str, name2: str) -> float:
        """
        Score de matching difuso usando Levenshtein.
        
        Args:
            name1: Primer nombre
            name2: Segundo nombre
            
        Returns:
            Score normalizado (0.0 - 1.0)
        """
        norm1 = self.normalize_name(name1)
        norm2 = self.normalize_name(name2)
        
        if not norm1 or not norm2:
            return 0.0
        
        distance = self.calculate_levenshtein_distance(norm1, norm2)
        max_len = max(len(norm1), len(norm2))
        
        if max_len == 0:
            return 0.0
        
        # Normalizar: 1.0 = idénticos, 0.0 = completamente diferentes
        return 1.0 - (distance / max_len)


def test_name_normalizer():
    """Función de prueba para el normalizador."""
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

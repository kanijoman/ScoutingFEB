"""
Módulo para matching y scoring de identidades de jugadores.

Implementa el sistema de candidate_score para identificar perfiles
que probablemente corresponden al mismo jugador real.
"""

import sqlite3
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

from ml.name_normalizer import NameNormalizer


class PlayerIdentityMatcher:
    """Gestor de matching de identidades de jugadores."""
    
    # Pesos para candidate_score
    WEIGHT_NAME_MATCH = 0.40
    WEIGHT_AGE_MATCH = 0.30
    WEIGHT_TEAM_OVERLAP = 0.20
    WEIGHT_TIMELINE_FIT = 0.10
    
    # Thresholds para clasificación de confianza
    THRESHOLD_VERY_HIGH = 0.85
    THRESHOLD_HIGH = 0.70
    THRESHOLD_MEDIUM = 0.50
    THRESHOLD_LOW = 0.30
    
    def __init__(self, db_path: str):
        """
        Inicializar el matcher.
        
        Args:
            db_path: Ruta a la base de datos SQLite
        """
        self.db_path = db_path
        self.name_normalizer = NameNormalizer()
        self.logger = logging.getLogger(__name__)
    
    def calculate_candidate_score(
        self,
        profile1: Dict,
        profile2: Dict
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calcular candidate_score entre dos perfiles.
        
        Formula:
        candidate_score = 0.40 * name_match +
                         0.30 * age_match +
                         0.20 * team_overlap +
                         0.10 * timeline_fit
        
        Args:
            profile1: Primer perfil
            profile2: Segundo perfil
            
        Returns:
            Tupla (candidate_score, componentes_dict)
        """
        # 1. Name match (40%)
        name_match = self.name_normalizer.calculate_name_similarity(
            profile1['name_raw'],
            profile2['name_raw']
        )
        
        # 2. Age match (30%)
        age_match = self._calculate_age_match(profile1, profile2)
        
        # 3. Team overlap (20%)
        team_overlap = self._calculate_team_overlap(profile1, profile2)
        
        # 4. Timeline fit (10%)
        timeline_fit = self._calculate_timeline_fit(profile1, profile2)
        
        # Calcular score total
        candidate_score = (
            self.WEIGHT_NAME_MATCH * name_match +
            self.WEIGHT_AGE_MATCH * age_match +
            self.WEIGHT_TEAM_OVERLAP * team_overlap +
            self.WEIGHT_TIMELINE_FIT * timeline_fit
        )
        
        components = {
            'name_match_score': name_match,
            'age_match_score': age_match,
            'team_overlap_score': team_overlap,
            'timeline_fit_score': timeline_fit
        }
        
        return candidate_score, components
    
    def _calculate_age_match(self, profile1: Dict, profile2: Dict) -> float:
        """
        Calcular score de similitud de edad.
        
        Args:
            profile1: Primer perfil
            profile2: Segundo perfil
            
        Returns:
            Score de 0.0 a 1.0
        """
        birth_year1 = profile1.get('birth_year')
        birth_year2 = profile2.get('birth_year')
        
        # Si no tenemos información de edad, score neutral
        if not birth_year1 or not birth_year2:
            return 0.5
        
        # Diferencia de años
        age_diff = abs(birth_year1 - birth_year2)
        
        if age_diff == 0:
            return 1.0
        elif age_diff == 1:
            return 0.7  # Puede ser error en datos
        elif age_diff == 2:
            return 0.3
        else:
            return 0.0
    
    def _calculate_team_overlap(self, profile1: Dict, profile2: Dict) -> float:
        """
        Calcular score de solapamiento de equipos.
        
        Si ambos perfiles han jugado en el mismo equipo, es más probable
        que sean el mismo jugador.
        
        Args:
            profile1: Primer perfil
            profile2: Segundo perfil
            
        Returns:
            Score de 0.0 a 1.0
        """
        team1 = profile1.get('team_id')
        team2 = profile2.get('team_id')
        
        if not team1 or not team2:
            return 0.3  # Score neutral si falta información
        
        # Mismo equipo = alta probabilidad
        if team1 == team2:
            return 1.0
        
        # Equipos diferentes - verificar si son equipos vinculados
        # (requeriría lógica adicional con información de equipos vinculados)
        # Por ahora, asumimos que son diferentes
        return 0.2
    
    def _calculate_timeline_fit(self, profile1: Dict, profile2: Dict) -> float:
        """
        Calcular score de continuidad temporal.
        
        Verifica si los perfiles aparecen en temporadas consecutivas o cercanas.
        
        Args:
            profile1: Primer perfil
            profile2: Segundo perfil
            
        Returns:
            Score de 0.0 a 1.0
        """
        season1 = profile1.get('season')
        season2 = profile2.get('season')
        
        if not season1 or not season2:
            return 0.3
        
        # Extraer años de las temporadas (formato: "2023/24")
        try:
            year1 = int(season1.split('/')[0])
            year2 = int(season2.split('/')[0])
            
            year_diff = abs(year1 - year2)
            
            if year_diff == 0:
                # Misma temporada, probablemente fichaje
                return 0.8
            elif year_diff == 1:
                # Temporadas consecutivas
                return 1.0
            elif year_diff == 2:
                # Gap de un año (lesión, sin jugar)
                return 0.6
            elif year_diff <= 4:
                # Gap más largo
                return 0.3
            else:
                # Gap muy largo, probablemente jugadores diferentes
                return 0.1
        except:
            return 0.3
    
    def get_confidence_level(self, candidate_score: float) -> str:
        """
        Clasificar nivel de confianza basado en candidate_score.
        
        Args:
            candidate_score: Score del candidato
            
        Returns:
            Nivel de confianza ('very_high', 'high', 'medium', 'low')
        """
        if candidate_score >= self.THRESHOLD_VERY_HIGH:
            return 'very_high'
        elif candidate_score >= self.THRESHOLD_HIGH:
            return 'high'
        elif candidate_score >= self.THRESHOLD_MEDIUM:
            return 'medium'
        else:
            return 'low'
    
    def find_candidate_matches(
        self,
        profile_id: int,
        min_score: float = 0.30
    ) -> List[Dict]:
        """
        Buscar perfiles candidatos para un perfil dado.
        
        Args:
            profile_id: ID del perfil a buscar
            min_score: Score mínimo para considerar candidato
            
        Returns:
            Lista de candidatos ordenados por score
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener perfil base
        cursor.execute("""
            SELECT * FROM player_profiles
            WHERE profile_id = ?
        """, (profile_id,))
        
        profile = dict(cursor.fetchone())
        
        # Obtener otros perfiles (excluyendo el mismo)
        cursor.execute("""
            SELECT * FROM player_profiles
            WHERE profile_id != ?
                AND is_consolidated = 0
        """, (profile_id,))
        
        other_profiles = [dict(row) for row in cursor.fetchall()]
        
        candidates = []
        
        for other in other_profiles:
            score, components = self.calculate_candidate_score(profile, other)
            
            if score >= min_score:
                candidate = {
                    'profile_id': other['profile_id'],
                    'name_raw': other['name_raw'],
                    'team_id': other['team_id'],
                    'season': other['season'],
                    'birth_year': other['birth_year'],
                    'candidate_score': score,
                    'confidence_level': self.get_confidence_level(score),
                    **components
                }
                candidates.append(candidate)
        
        conn.close()
        
        # Ordenar por score descendente
        candidates.sort(key=lambda x: x['candidate_score'], reverse=True)
        
        return candidates
    
    def generate_all_candidates(
        self,
        min_score: float = 0.50,
        batch_size: int = 100
    ) -> int:
        """
        Generar candidatos de matching para todos los perfiles.
        
        Args:
            min_score: Score mínimo para guardar candidato
            batch_size: Tamaño de lote para procesamiento
            
        Returns:
            Número de candidatos generados
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Obtener todos los perfiles no consolidados
        cursor.execute("""
            SELECT * FROM player_profiles
            WHERE is_consolidated = 0
            ORDER BY profile_id
        """)
        
        profiles = [dict(row) for row in cursor.fetchall()]
        
        self.logger.info(f"Procesando {len(profiles)} perfiles para matching...")
        
        candidates_count = 0
        
        # Comparar cada par de perfiles (solo una vez)
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                profile1 = profiles[i]
                profile2 = profiles[j]
                
                score, components = self.calculate_candidate_score(profile1, profile2)
                
                if score >= min_score:
                    # Insertar candidato
                    try:
                        cursor.execute("""
                            INSERT OR IGNORE INTO player_identity_candidates (
                                profile_id_1, profile_id_2,
                                name_match_score, age_match_score,
                                team_overlap_score, timeline_fit_score,
                                candidate_score, confidence_level
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            profile1['profile_id'],
                            profile2['profile_id'],
                            components['name_match_score'],
                            components['age_match_score'],
                            components['team_overlap_score'],
                            components['timeline_fit_score'],
                            score,
                            self.get_confidence_level(score)
                        ))
                        
                        candidates_count += 1
                    except sqlite3.IntegrityError:
                        pass  # Ya existe
            
            # Commit cada batch
            if (i + 1) % batch_size == 0:
                conn.commit()
                self.logger.info(f"Procesados {i + 1}/{len(profiles)} perfiles...")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"✓ Generados {candidates_count} candidatos de matching")
        
        return candidates_count
    
    def get_high_confidence_candidates(
        self,
        min_score: float = 0.70
    ) -> List[Dict]:
        """
        Obtener candidatos de alta confianza para revisión.
        
        Args:
            min_score: Score mínimo
            
        Returns:
            Lista de candidatos con alta confianza
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                c.*,
                p1.name_raw as name_1,
                p1.team_id as team_1,
                p1.season as season_1,
                p1.birth_year as birth_year_1,
                p2.name_raw as name_2,
                p2.team_id as team_2,
                p2.season as season_2,
                p2.birth_year as birth_year_2
            FROM player_identity_candidates c
            JOIN player_profiles p1 ON c.profile_id_1 = p1.profile_id
            JOIN player_profiles p2 ON c.profile_id_2 = p2.profile_id
            WHERE c.candidate_score >= ?
                AND c.validation_status = 'pending'
            ORDER BY c.candidate_score DESC
        """, (min_score,))
        
        candidates = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return candidates
    
    def validate_candidate(
        self,
        candidate_id: int,
        status: str,
        validated_by: str = "system",
        notes: Optional[str] = None
    ) -> bool:
        """
        Validar un candidato de matching.
        
        Args:
            candidate_id: ID del candidato
            status: 'confirmed', 'rejected', 'unsure'
            validated_by: Usuario que valida
            notes: Notas opcionales
            
        Returns:
            True si se validó exitosamente
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE player_identity_candidates
                SET validation_status = ?,
                    validated_by = ?,
                    validated_at = ?,
                    validation_notes = ?
                WHERE candidate_id = ?
            """, (
                status,
                validated_by,
                datetime.now().isoformat(),
                notes,
                candidate_id
            ))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception as e:
            self.logger.error(f"Error validando candidato: {e}")
            conn.close()
            return False


def test_identity_matcher():
    """Función de prueba para el matcher."""
    # Esta función requiere una base de datos con datos de prueba
    print("=" * 80)
    print("TEST: Player Identity Matcher")
    print("=" * 80)
    print("Nota: Requiere base de datos con datos de prueba")


if __name__ == "__main__":
    test_identity_matcher()

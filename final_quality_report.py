"""Informe completo de calidad de datos después del scraping."""
from src.database.mongodb_client import MongoDBClient
from collections import defaultdict

client = MongoDBClient()
collection = client.db.all_feb_games_fem

print("=" * 80)
print("INFORME FINAL DE CALIDAD DE DATOS - SCRAPING COMPLETO")
print("=" * 80)
print()

# 1. Total y por competición
total = collection.count_documents({})
print(f"📊 TOTAL DE PARTIDOS: {total:,}\n")

print("🏀 DISTRIBUCIÓN POR COMPETICIÓN:")
print("-" * 80)
comp_stats = defaultdict(int)
for doc in collection.find({}, {"HEADER.competition_name": 1}):
    comp = doc.get("HEADER", {}).get("competition_name", "Unknown")
    comp_stats[comp] += 1

for comp, count in sorted(comp_stats.items(), key=lambda x: -x[1]):
    pct = (count / total * 100) if total > 0 else 0
    print(f"  {comp:30} {count:6,} partidos ({pct:5.1f}%)")

# 2. Distribución por temporada
print("\n📅 DISTRIBUCIÓN POR TEMPORADA:")
print("-" * 80)
season_stats = defaultdict(int)
for doc in collection.find({}, {"HEADER.season": 1}):
    season = doc.get("HEADER", {}).get("season", "Unknown")
    season_stats[season] += 1

print(f"  Total temporadas: {len(season_stats)}")
print(f"  Rango: {min(season_stats.keys())} - {max(season_stats.keys())}\n")

# Top 10 temporadas
print("  Top 10 temporadas con más partidos:")
for season, count in sorted(season_stats.items(), key=lambda x: -x[1])[:10]:
    print(f"    {season:15} {count:,} partidos")

# 3. Estructura de datos
print("\n📋 ESTRUCTURA DE DATOS:")
print("-" * 80)
with_team = collection.count_documents({"BOXSCORE.TEAM": {"$exists": True}})
with_team_player = collection.count_documents({"BOXSCORE.TEAM.PLAYER": {"$exists": True}})
with_legacy = collection.count_documents({
    "PLAYER": {"$exists": True},
    "BOXSCORE.TEAM": {"$exists": False}
})

print(f"  Formato MODERNO (BOXSCORE.TEAM):        {with_team:6,} ({with_team/total*100:.1f}%)")
print(f"  Con datos de jugadores (TEAM.PLAYER):   {with_team_player:6,} ({with_team_player/total*100:.1f}%)")
print(f"  Formato LEGACY:                         {with_legacy:6,} ({with_legacy/total*100:.1f}%)")

if with_team == total:
    print("\n  ✅ DATASET 100% HOMOGÉNEO - Todo en formato moderno")
elif with_team_player / total >= 0.95:
    print("\n  ✅ DATASET DE ALTA CALIDAD - >95% con datos completos")
else:
    print("\n  ⚠️  DATASET MIXTO - Revisar calidad")

# 4. Análisis de jugadoras
print("\n👥 ANÁLISIS DE JUGADORAS:")
print("-" * 80)
print("Contando jugadoras únicas...")

unique_players = set()
total_player_records = 0
matches_with_players = 0

for doc in collection.find({"BOXSCORE.TEAM.PLAYER": {"$exists": True}}, {"BOXSCORE.TEAM": 1}):
    teams = doc.get("BOXSCORE", {}).get("TEAM", [])
    has_players = False
    for team in teams:
        players = team.get("PLAYER", [])
        if players:
            has_players = True
        for player in players:
            player_id = player.get("id")
            player_name = player.get("name", player.get("playername"))
            if player_id:
                unique_players.add(player_id)
            elif player_name:
                unique_players.add(player_name)
            total_player_records += 1
    if has_players:
        matches_with_players += 1

print(f"  Jugadoras únicas identificadas:     {len(unique_players):,}")
print(f"  Total registros de jugadoras:       {total_player_records:,}")
print(f"  Partidos con datos de jugadoras:    {matches_with_players:,} ({matches_with_players/total*100:.1f}%)")
if total_player_records > 0 and len(unique_players) > 0:
    avg_games = total_player_records / len(unique_players)
    print(f"  Promedio partidos por jugadora:     {avg_games:.1f}")

# 5. Top jugadoras
print("\n  Top 10 jugadoras (más partidos):")
player_counts = defaultdict(int)
for doc in collection.find({"BOXSCORE.TEAM.PLAYER": {"$exists": True}}, {"BOXSCORE.TEAM": 1}):
    teams = doc.get("BOXSCORE", {}).get("TEAM", [])
    for team in teams:
        players = team.get("PLAYER", [])
        for player in players:
            player_name = player.get("name", player.get("playername", "Unknown"))
            player_counts[player_name] += 1

for i, (player, count) in enumerate(sorted(player_counts.items(), key=lambda x: -x[1])[:10], 1):
    print(f"    {i:2}. {player:40} {count:,} partidos")

# 6. Evaluación para ML
print("\n" + "=" * 80)
print("🎯 EVALUACIÓN PARA ANÁLISIS DE SCOUTING Y ML")
print("=" * 80)

quality_score = (with_team_player / total * 100) if total > 0 else 0
player_coverage = len(unique_players)
season_coverage = len(season_stats)
comp_coverage = len(comp_stats)

print(f"\n  ✅ Partidos totales:              {total:,}")
print(f"  ✅ Calidad de datos:              {quality_score:.1f}%")
print(f"  ✅ Jugadoras únicas:              {player_coverage:,}")
print(f"  ✅ Temporadas cubiertas:          {season_coverage}")
print(f"  ✅ Competiciones:                 {comp_coverage}")

# Criterios de evaluación
print("\n  Criterios de evaluación:")
print(f"    • Partidos mínimos (1,000):     {'✅ PASS' if total >= 1000 else '❌ FAIL'} ({total:,})")
print(f"    • Jugadoras mínimas (200):      {'✅ PASS' if player_coverage >= 200 else '❌ FAIL'} ({player_coverage:,})")
print(f"    • Calidad datos (95%):          {'✅ PASS' if quality_score >= 95 else '❌ FAIL'} ({quality_score:.1f}%)")
print(f"    • Temporadas mínimas (3):       {'✅ PASS' if season_coverage >= 3 else '❌ FAIL'} ({season_coverage})")

# Conclusión final
print("\n" + "=" * 80)
if quality_score >= 95 and player_coverage >= 200 and total >= 1000:
    print("🎉 DATASET DE EXCELENTE CALIDAD")
    print("=" * 80)
    print("\n✅ El dataset cumple todos los criterios para análisis ML")
    print("✅ Listo para ETL y entrenamiento de modelos")
    print("✅ Alta diversidad de jugadoras y temporadas")
elif quality_score >= 80 and player_coverage >= 100:
    print("✅ DATASET DE BUENA CALIDAD")
    print("=" * 80)
    print("\n✅ El dataset es apto para análisis")
    print("⚠️  Algunas mejoras posibles en cobertura")
else:
    print("⚠️  DATASET REQUIERE ATENCIÓN")
    print("=" * 80)
    print("\n⚠️  Revisar calidad y cobertura antes de ML")

# 7. Muestra de partido
print("\n" + "=" * 80)
print("📋 MUESTRA DE PARTIDO (verificación de estructura)")
print("=" * 80)

sample = collection.find_one({"BOXSCORE.TEAM.PLAYER": {"$exists": True}})
if sample:
    header = sample.get("HEADER", {})
    print(f"\nCompetición: {header.get('competition_name', 'N/A')}")
    print(f"Temporada:   {header.get('season', 'N/A')}")
    print(f"Grupo:       {header.get('group', 'N/A')}")
    print(f"Fecha:       {header.get('starttime', 'N/A')}")
    
    teams = sample.get("BOXSCORE", {}).get("TEAM", [])
    if len(teams) >= 2:
        team1, team2 = teams[0], teams[1]
        score1 = team1.get("TOTAL", {}).get("pts", "?")
        score2 = team2.get("TOTAL", {}).get("pts", "?")
        
        print(f"\nPartido: {team1.get('name', 'N/A')} {score1} - {score2} {team2.get('name', 'N/A')}")
        
        players1 = team1.get("PLAYER", [])
        print(f"\nJugadoras equipo local: {len(players1)}")
        
        if players1:
            p = players1[0]
            print(f"\nEjemplo estadísticas:")
            print(f"  Nombre:       {p.get('name', 'N/A')}")
            print(f"  Minutos:      {p.get('minFormatted', p.get('min', 'N/A'))}")
            print(f"  Puntos:       {p.get('pts', 'N/A')}")
            print(f"  Rebotes:      {p.get('rt', p.get('reb', 'N/A'))}")
            print(f"  Asistencias:  {p.get('assist', 'N/A')}")
            print(f"  Valoración:   {p.get('val', 'N/A')}")

print("\n" + "=" * 80)

client.close()

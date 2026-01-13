"""Configuration file for ScoutingFEB."""

# MongoDB Configuration
MONGODB_CONFIG = {
    "uri": "mongodb://localhost:27017/",
    "database": "scouting_feb",
    "collections": {
        "masculine": "all_feb_games_masc",
        "feminine": "all_feb_games_fem"
    }
}

# Scraping Configuration
SCRAPING_CONFIG = {
    "delay_between_matches": 0.5,  # seconds
    "timeout": 15,  # seconds
    "retry_attempts": 3,
    "skip_existing": True,  # Skip matches already in database
    "incremental_mode": True,  # Only process new matches (uses scraping_state collection)
    "force_full_rescrape": False  # If True, ignore incremental mode and rescrape all
}

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "file": "scouting_feb.log",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
}

# Competition specific URLs (examples)
COMPETITION_URLS = {
    "LF2": "https://baloncestoenvivo.feb.es/calendario/lf2/9/2024",
    "LF": "https://baloncestoenvivo.feb.es/calendario/lf/1/2024",
    # Add more competitions as needed
}

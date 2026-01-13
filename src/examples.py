"""Example script demonstrating different use cases."""

from main import FEBScoutingScraper
import logging

# Configure simple logging for the example
logging.basicConfig(level=logging.INFO)


def example_1_list_competitions():
    """Example 1: List all available competitions."""
    print("\n" + "="*60)
    print("EXAMPLE 1: List available competitions")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    competitions = scraper.list_available_competitions()
    print(f"\nTotal competitions found: {len(competitions)}")
    scraper.close()


def example_2_scrape_by_name():
    """Example 2: Scrape a specific competition by name."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Scrape competition by name")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Scrape LF2 (Liga Femenina 2)
    stats = scraper.scrape_competition_by_name("LF2")
    
    print("\n" + "-"*60)
    print("SCRAPING RESULTS:")
    print("-"*60)
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    scraper.close()


def example_3_scrape_by_url():
    """Example 3: Scrape a competition by direct URL."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Scrape competition by URL")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Direct URL scraping
    stats = scraper.scrape_competition(
        competition_url="https://baloncestoenvivo.feb.es/calendario/lf2/9/2024",
        competition_name="LF2 - Liga Femenina 2",
        gender="fem"
    )
    
    print("\n" + "-"*60)
    print("SCRAPING RESULTS:")
    print("-"*60)
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    scraper.close()


def example_4_custom_database():
    """Example 4: Use custom MongoDB configuration."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Custom database configuration")
    print("="*60 + "\n")
    
    # Custom MongoDB configuration
    scraper = FEBScoutingScraper(
        mongodb_uri="mongodb://localhost:27017/",
        database_name="mi_base_datos_scouting"
    )
    
    competitions = scraper.list_available_competitions()
    print(f"Connected to custom database: mi_base_datos_scouting")
    print(f"Found {len(competitions)} competitions")
    
    scraper.close()


def example_5_query_database():
    """Example 5: Query games from database."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Query existing games from database")
    print("="*60 + "\n")
    
    scraper = FEBScoutingScraper()
    
    # Count games in each collection
    masc_count = scraper.db_client.count_games("all_feb_games_masc")
    fem_count = scraper.db_client.count_games("all_feb_games_fem")
    
    print(f"Masculine games in database: {masc_count}")
    print(f"Feminine games in database: {fem_count}")
    print(f"Total games: {masc_count + fem_count}")
    
    # Get a sample game (if any exists)
    if fem_count > 0:
        print("\n" + "-"*60)
        print("SAMPLE GAME (first feminine game):")
        print("-"*60)
        
        games = scraper.db_client.get_all_games("all_feb_games_fem")
        if games:
            sample_game = games[0]
            header = sample_game.get("HEADER", {})
            print(f"Competition: {header.get('competition_name', 'N/A')}")
            print(f"Season: {header.get('season', 'N/A')}")
            print(f"Group: {header.get('group', 'N/A')}")
            print(f"Date: {header.get('starttime', 'N/A')}")
            
            teams = header.get("TEAM", [])
            if len(teams) == 2:
                print(f"\nMatch: {teams[0].get('name', 'N/A')} {teams[0].get('pts', '?')} - "
                      f"{teams[1].get('pts', '?')} {teams[1].get('name', 'N/A')}")
    
    scraper.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("ScoutingFEB - Usage Examples")
    print("="*60)
    
    # Choose which example to run
    print("\nAvailable examples:")
    print("1. List all available competitions")
    print("2. Scrape competition by name (LF2)")
    print("3. Scrape competition by URL")
    print("4. Use custom database configuration")
    print("5. Query existing games from database")
    print("0. Exit")
    
    choice = input("\nSelect an example (0-5): ").strip()
    
    examples = {
        "1": example_1_list_competitions,
        "2": example_2_scrape_by_name,
        "3": example_3_scrape_by_url,
        "4": example_4_custom_database,
        "5": example_5_query_database
    }
    
    if choice in examples:
        examples[choice]()
    elif choice == "0":
        print("Goodbye!")
    else:
        print("Invalid choice")

"""Test script to verify ScoutingFEB installation and setup."""

import sys
import logging

# Disable logging for cleaner output
logging.disable(logging.CRITICAL)


def test_python_version():
    """Test Python version."""
    print("1. Checking Python version...", end=" ")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)")
        return False


def test_dependencies():
    """Test if required dependencies are installed."""
    print("2. Checking dependencies...", end=" ")
    missing = []
    
    try:
        import requests
    except ImportError:
        missing.append("requests")
    
    try:
        import bs4
    except ImportError:
        missing.append("beautifulsoup4")
    
    try:
        import pymongo
    except ImportError:
        missing.append("pymongo")
    
    if not missing:
        print("✓ All dependencies installed")
        return True
    else:
        print(f"✗ Missing: {', '.join(missing)}")
        print("   Run: pip install -r requirements.txt")
        return False


def test_mongodb_connection():
    """Test MongoDB connection."""
    print("3. Checking MongoDB connection...", end=" ")
    try:
        from pymongo import MongoClient
        from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
        
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        client.close()
        print("✓ MongoDB is running")
        return True
    except (ConnectionFailure, ServerSelectionTimeoutError):
        print("✗ Cannot connect to MongoDB")
        print("   Make sure MongoDB is running: net start MongoDB")
        return False
    except ImportError:
        print("✗ pymongo not installed")
        return False


def test_imports():
    """Test if project modules can be imported."""
    print("4. Checking project modules...", end=" ")
    try:
        from scraper import FEBWebScraper, FEBApiClient, WebClient, TokenManager
        from database import MongoDBClient
        print("✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_web_connectivity():
    """Test internet connectivity to FEB website."""
    print("5. Checking internet connectivity...", end=" ")
    try:
        import requests
        response = requests.get("https://competiciones.feb.es/estadisticas/", timeout=5)
        if response.status_code == 200:
            print("✓ Can reach FEB website")
            return True
        else:
            print(f"✗ FEB website returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Cannot reach FEB website: {e}")
        return False


def test_database_operations():
    """Test basic database operations."""
    print("6. Testing database operations...", end=" ")
    try:
        from database import MongoDBClient
        
        db = MongoDBClient("mongodb://localhost:27017/", "scouting_feb_test")
        
        # Test collection access
        collection = db.get_collection("test_collection")
        
        # Test count (should work even if empty)
        count = db.count_games("test_collection")
        
        # Clean up test database
        db.client.drop_database("scouting_feb_test")
        db.close()
        
        print("✓ Database operations working")
        return True
    except Exception as e:
        print(f"✗ Database operation failed: {e}")
        return False


def test_scraper_initialization():
    """Test if scraper can be initialized."""
    print("7. Testing scraper initialization...", end=" ")
    try:
        from main import FEBScoutingScraper
        
        scraper = FEBScoutingScraper()
        scraper.close()
        
        print("✓ Scraper initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Scraper initialization failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("ScoutingFEB - System Test")
    print("="*60 + "\n")
    
    tests = [
        test_python_version,
        test_dependencies,
        test_mongodb_connection,
        test_imports,
        test_web_connectivity,
        test_database_operations,
        test_scraper_initialization
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            results.append(False)
    
    print("\n" + "="*60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"✓ ALL TESTS PASSED ({passed}/{total})")
        print("="*60)
        print("\nYour system is ready to use ScoutingFEB!")
        print("\nNext steps:")
        print("1. Run: python main.py         (to list competitions)")
        print("2. Run: python examples.py     (to see usage examples)")
        print("3. Edit main.py to scrape specific competitions")
    else:
        print(f"✗ SOME TESTS FAILED ({passed}/{total} passed)")
        print("="*60)
        print("\nPlease fix the issues above before using ScoutingFEB.")
        print("\nCommon fixes:")
        print("- Install dependencies: pip install -r requirements.txt")
        print("- Start MongoDB: net start MongoDB")
        print("- Check internet connection")
    
    print("\n")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

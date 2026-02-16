#!/usr/bin/env python3
"""
Full Regression Test Suite

Runs all regression tests to validate functionality after refactoring.
This should be run before committing major changes.

Usage:
    python scripts/run_regression_suite.py
    
    # With coverage report
    python scripts/run_regression_suite.py --coverage
    
Exit codes:
    0 - All tests passed
    1 - Tests failed
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_regression_suite(with_coverage=False):
    """
    Run full regression test suite.
    
    Args:
        with_coverage: Whether to generate coverage report
        
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    print("=" * 70)
    print("RUNNING FULL REGRESSION TEST SUITE")
    print("=" * 70)
    print()
    
    # Base pytest command
    cmd = ["pytest", "-v", "-m", "regression"]
    
    if with_coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term"
        ])
        print("📊 Coverage reporting enabled")
        print()
    
    # Run tests
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
    
    print("\n" + "=" * 70)
    if result.returncode == 0:
        print("✅ ALL REGRESSION TESTS PASSED")
        if with_coverage:
            print("\n📊 Coverage report generated in htmlcov/index.html")
    else:
        print("❌ REGRESSION TESTS FAILED")
    print("=" * 70)
    
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run full regression test suite"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Generate coverage report"
    )
    
    args = parser.parse_args()
    sys.exit(run_regression_suite(with_coverage=args.coverage))

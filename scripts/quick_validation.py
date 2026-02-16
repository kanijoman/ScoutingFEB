#!/usr/bin/env python3
"""
Quick Validation Script

Runs a subset of critical tests for fast feedback during development.
This is useful for rapid validation without running the full test suite.

Usage:
    python scripts/quick_validation.py
    
Exit codes:
    0 - All tests passed
    1 - Tests failed
"""

import subprocess
import sys
from pathlib import Path


def run_quick_tests():
    """
    Run quick validation tests.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    print("=" * 70)
    print("RUNNING QUICK VALIDATION TESTS")
    print("=" * 70)
    print()
    
    # Define quick test markers
    quick_tests = [
        # Run all smoke tests (should be very fast)
        ("Smoke Tests", ["-m", "smoke", "-v"]),
        
        # Run a subset of integration tests
        ("Critical Integration Tests", [
            "tests/integration/test_etl_sanity.py::TestETLMetricsSanity::test_no_nan_or_inf_in_metrics",
            "-v"
        ]),
    ]
    
    all_passed = True
    
    for test_name, test_args in quick_tests:
        print(f"\n{'─' * 70}")
        print(f"Running: {test_name}")
        print(f"{'─' * 70}\n")
        
        cmd = ["pytest"] + test_args
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        
        if result.returncode != 0:
            all_passed = False
            print(f"\n❌ {test_name} FAILED")
        else:
            print(f"\n✅ {test_name} PASSED")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ QUICK VALIDATION PASSED")
        print("=" * 70)
        return 0
    else:
        print("❌ QUICK VALIDATION FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(run_quick_tests())

"""
Test runner for HunterZ Trading Bot

This script runs all tests for the TP/SL management functionality.

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py -v                 # Run with verbose output
    python run_tests.py test_tp_sl_*       # Run specific test file(s)
"""
import sys
import unittest
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_tests(verbosity=2, pattern='test_*.py'):
    """
    Run tests with specified verbosity and pattern.
    
    Args:
        verbosity: Test output verbosity (1=quiet, 2=normal, 3=verbose)
        pattern: Pattern to match test files
    
    Returns:
        unittest.TestResult object
    """
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    suite = loader.discover(start_dir, pattern=pattern)
    
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    # Parse command line arguments
    verbosity = 2
    pattern = 'test_*.py'
    
    if '-v' in sys.argv or '--verbose' in sys.argv:
        verbosity = 3
    elif '-q' in sys.argv or '--quiet' in sys.argv:
        verbosity = 1
    
    # Check for pattern argument
    for arg in sys.argv[1:]:
        if arg.startswith('test_') and arg.endswith('.py'):
            pattern = arg
        elif arg.startswith('test_') and not arg.endswith('.py'):
            pattern = f"{arg}.py"
    
    print(f"Running tests with pattern: {pattern}")
    print(f"Verbosity: {verbosity}")
    print("-" * 70)
    
    result = run_tests(verbosity=verbosity, pattern=pattern)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)

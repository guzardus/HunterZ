"""
Test balance history persistence and limits.
"""

import sys
import os
import json
import tempfile
import shutil

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import state

def test_balance_history_persistence():
    """Test that balance history is saved and loaded correctly."""
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_file = state.BALANCE_HISTORY_FILE
    
    try:
        # Override the file path to use temp directory
        state.BALANCE_HISTORY_FILE = os.path.join(temp_dir, 'balance_history.json')
        
        # Initialize state
        state.bot_state.balance_history = []
        state.bot_state.total_pnl = 100.0
        
        # Add some balance history entries
        state.update_full_balance(1000.0, 800.0, 200.0)
        state.update_full_balance(1050.0, 850.0, 200.0)
        state.update_full_balance(1100.0, 900.0, 200.0)
        
        # Verify entries were added
        assert len(state.bot_state.balance_history) == 3, \
            f"Expected 3 entries, got {len(state.bot_state.balance_history)}"
        
        # Verify file was created
        assert os.path.exists(state.BALANCE_HISTORY_FILE), \
            "Balance history file was not created"
        
        # Load the file and verify contents
        with open(state.BALANCE_HISTORY_FILE, 'r') as f:
            saved_data = json.load(f)
        
        assert len(saved_data) == 3, \
            f"Expected 3 entries in file, got {len(saved_data)}"
        
        assert saved_data[0]['total_balance'] == 1000.0, \
            f"Expected first entry total_balance=1000.0, got {saved_data[0]['total_balance']}"
        
        # Reset state and reload from disk
        state.bot_state.balance_history = []
        state.load_balance_history_on_startup()
        
        # Verify data was loaded
        assert len(state.bot_state.balance_history) == 3, \
            f"Expected 3 entries after reload, got {len(state.bot_state.balance_history)}"
        
        assert state.bot_state.balance_history[0]['total_balance'] == 1000.0, \
            f"Expected first entry total_balance=1000.0 after reload"
        
        print("✓ Balance history persistence test passed")
        
    finally:
        # Cleanup
        state.BALANCE_HISTORY_FILE = original_file
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_balance_history_trimming():
    """Test that balance history is trimmed to MAX_BALANCE_HISTORY_POINTS."""
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_file = state.BALANCE_HISTORY_FILE
    original_max = state.MAX_BALANCE_HISTORY_POINTS
    
    try:
        # Test configuration
        TEST_MAX_ENTRIES = 10
        ENTRIES_TO_ADD = 15
        
        # Override the file path and max points for testing
        state.BALANCE_HISTORY_FILE = os.path.join(temp_dir, 'balance_history.json')
        state.MAX_BALANCE_HISTORY_POINTS = TEST_MAX_ENTRIES
        
        # Initialize state
        state.bot_state.balance_history = []
        state.bot_state.total_pnl = 0.0
        
        # Add more entries than the limit
        for i in range(ENTRIES_TO_ADD):
            state.update_full_balance(1000.0 + i, 800.0, 200.0)
        
        # Verify entries were trimmed to the limit
        assert len(state.bot_state.balance_history) == TEST_MAX_ENTRIES, \
            f"Expected {TEST_MAX_ENTRIES} entries (trimmed), got {len(state.bot_state.balance_history)}"
        
        # Verify the oldest entries were removed (should start at 1005.0)
        expected_first = 1000.0 + (ENTRIES_TO_ADD - TEST_MAX_ENTRIES)
        assert state.bot_state.balance_history[0]['total_balance'] == expected_first, \
            f"Expected first entry total_balance={expected_first}, got {state.bot_state.balance_history[0]['total_balance']}"
        
        # Verify the newest entries were kept (should end at 1014.0)
        expected_last = 1000.0 + (ENTRIES_TO_ADD - 1)
        assert state.bot_state.balance_history[-1]['total_balance'] == expected_last, \
            f"Expected last entry total_balance={expected_last}, got {state.bot_state.balance_history[-1]['total_balance']}"
        
        print("✓ Balance history trimming test passed")
        
    finally:
        # Cleanup
        state.BALANCE_HISTORY_FILE = original_file
        state.MAX_BALANCE_HISTORY_POINTS = original_max
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_balance_history_structure():
    """Test that balance history entries have the correct structure."""
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    original_file = state.BALANCE_HISTORY_FILE
    
    try:
        # Override the file path
        state.BALANCE_HISTORY_FILE = os.path.join(temp_dir, 'balance_history.json')
        
        # Initialize state
        state.bot_state.balance_history = []
        state.bot_state.total_pnl = 150.5
        
        # Add a balance history entry
        state.update_full_balance(2000.0, 1500.0, 500.0)
        
        # Verify structure
        entry = state.bot_state.balance_history[0]
        
        assert 'timestamp' in entry, "Entry missing 'timestamp' field"
        assert 'total_balance' in entry, "Entry missing 'total_balance' field"
        assert 'free_balance' in entry, "Entry missing 'free_balance' field"
        assert 'used_balance' in entry, "Entry missing 'used_balance' field"
        assert 'total_pnl' in entry, "Entry missing 'total_pnl' field"
        
        assert entry['total_balance'] == 2000.0, \
            f"Expected total_balance=2000.0, got {entry['total_balance']}"
        assert entry['free_balance'] == 1500.0, \
            f"Expected free_balance=1500.0, got {entry['free_balance']}"
        assert entry['used_balance'] == 500.0, \
            f"Expected used_balance=500.0, got {entry['used_balance']}"
        assert entry['total_pnl'] == 150.5, \
            f"Expected total_pnl=150.5, got {entry['total_pnl']}"
        
        print("✓ Balance history structure test passed")
        
    finally:
        # Cleanup
        state.BALANCE_HISTORY_FILE = original_file
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    print("\n=== Testing Balance History ===\n")
    
    try:
        test_balance_history_persistence()
        test_balance_history_trimming()
        test_balance_history_structure()
        
        print("\n✓ All balance history tests passed!\n")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

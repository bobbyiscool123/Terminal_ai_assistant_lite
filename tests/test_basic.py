#!/usr/bin/env python3

import os
import sys
import unittest

# Add the parent directory to the path so we can import the main script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import main script for testing
try:
    import terminal_ai_lite
except ImportError:
    print("Could not import terminal_ai_lite. Please check your installation.")
    sys.exit(1)

class TestBasicFunctionality(unittest.TestCase):
    """Basic tests for Terminal AI Assistant Lite"""

    def test_import(self):
        """Test that the module can be imported"""
        self.assertTrue(hasattr(terminal_ai_lite, 'API_KEY'))
    
    def test_colors(self):
        """Test that color constants are defined"""
        self.assertTrue(hasattr(terminal_ai_lite, 'MS_BLUE'))
        self.assertTrue(hasattr(terminal_ai_lite, 'MS_RED'))
        self.assertTrue(hasattr(terminal_ai_lite, 'MS_GREEN'))
    
    def test_functions(self):
        """Test that key functions are defined"""
        self.assertTrue(callable(getattr(terminal_ai_lite, 'format_output', None)))
        self.assertTrue(callable(getattr(terminal_ai_lite, 'is_json', None)))

if __name__ == '__main__':
    unittest.main() 
#!/usr/bin/env python3
"""
Test script for the enhanced hadith progression logic.
This script tests the find_next_valid_hadith_position function.
"""

import os
import sys
from dotenv import load_dotenv

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from db import find_valid_hadith_position, check_hadith_exists


def test_hadith_progression():
    """Test the hadith progression logic"""
    load_dotenv()

    print("Testing Enhanced Hadith Progression Logic")
    print("=" * 50)

    # Test Case 1: valid hadith
    print("\n1. Testing normal progression within a chapter:")
    hadith_no, book_no, chapter_no = find_valid_hadith_position(1, 1, 1)
    print(f"   Input: hadith=1, book=1, chapter=1")
    print(f"   Result: hadith={hadith_no}, book={book_no}, chapter={chapter_no}")

    # Test Case 2: Test with a non-existent hadith (should progress)
    print("\n2. Testing progression when hadith doesn't exist:")
    hadith_no, book_no, chapter_no = find_valid_hadith_position(9999, 1, 1)
    print(f"   Input: hadith=9999, book=1, chapter=1")
    print(f"   Result: hadith={hadith_no}, book={book_no}, chapter={chapter_no}")

    # Test Case 3: Test with a non-existent chapter (should move to next chapter)
    print("\n3. Testing progression when chapter doesn't exist:")
    hadith_no, book_no, chapter_no = find_valid_hadith_position(1, 1, 9999)
    print(f"   Input: hadith=1, book=1, chapter=9999")
    print(f"   Result: hadith={hadith_no}, book={book_no}, chapter={chapter_no}")

    # Test Case 4: Test with a non-existent book (should wrap)
    print("\n3. Testing progression when chapter doesn't exist:")
    hadith_no, book_no, chapter_no = find_valid_hadith_position(1, 9999, 1)
    print(f"   Input: hadith=1, book=9999, chapter=1")
    print(f"   Result: hadith={hadith_no}, book={book_no}, chapter={chapter_no}")

    print("\n" + "=" * 50)
    print("Test completed!")


if __name__ == "__main__":
    try:
        test_hadith_progression()
    except Exception as e:
        print(f"Error running test: {e}")
        print(
            "Make sure your .env file is configured with SUPABASE_URL and SUPABASE_KEY"
        )

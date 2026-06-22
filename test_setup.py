#!/usr/bin/env python3
"""
Test script to verify HadithBot setup and configuration.
Run this script to check if all dependencies and configurations are working correctly.
"""

import sys
import os
from pathlib import Path

def test_python_version():
    """Test if Python version is 3.11+"""
    print("Testing Python version...")
    if sys.version_info < (3, 11):
        print(f"❌ Python 3.11+ required, found {sys.version}")
        return False
    print(f"✅ Python version: {sys.version}")
    return True

def test_dependencies():
    """Test if all required dependencies are installed"""
    print("\nTesting dependencies...")
    required_packages = [
        'discord',
        'dotenv',
        'flask',
        'aiofiles',
        'supabase'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - not installed")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install them with: pip install -r requirements.txt")
        return False
    
    return True

def test_environment_variables():
    """Test if required environment variables are set"""
    print("\nTesting environment variables...")
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = ['DISCORD_TOKEN', 'SUPABASE_URL', 'SUPABASE_KEY']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith('your_'):
            print(f"❌ {var} - not set or using placeholder value")
            missing_vars.append(var)
        else:
            print(f"✅ {var} - configured")
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Create a .env file with your actual values (see .env.example)")
        return False
    
    return True

def test_data_files():
    """Test if required data files exist"""
    print("\nTesting data files...")
    required_files = ['data/99names.json']
    missing_files = []
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - not found")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n❌ Missing data files: {', '.join(missing_files)}")
        return False
    
    return True

def test_database_connection():
    """Test Supabase database connection"""
    print("\nTesting database connection...")
    try:
        from db import get_channels
        result = get_channels()
        print("✅ Database connection successful")
        print(f"✅ Found {len(result.data)} configured channels")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Check your Supabase URL and key, and ensure tables are created")
        return False

def test_data_loading():
    """Test loading of local data files"""
    print("\nTesting data loading...")
    try:
        import json

        # Test 99 names loading
        with open('data/99names.json', 'r') as f:
            names_data = json.load(f)
        
        print(f"✅ Loaded {len(names_data)} names from 99names.json")
        
        # Test Name dataclass (constructs without error)
        from utils import Name
        Name(**names_data[0])
        print("✅ Name dataclass working correctly")
        
        return True
    except Exception as e:
        print(f"❌ Data loading failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🤖 HadithBot Setup Test\n" + "="*50)
    
    tests = [
        test_python_version,
        test_dependencies,
        test_environment_variables,
        test_data_files,
        test_data_loading,
        test_database_connection
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Add spacing between tests
    
    print("="*50)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Your HadithBot setup is ready.")
        print("\nYou can now run the bot with:")
        print("  python bot.py")
        print("Or with the web server:")
        print("  python server.py")
    else:
        print("❌ Some tests failed. Please fix the issues above before running the bot.")
        sys.exit(1)

if __name__ == "__main__":
    main()

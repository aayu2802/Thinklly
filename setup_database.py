#!/usr/bin/env python
"""
Database Setup Script
Run this script to initialize or verify database integrity manually
Usage: python setup_database.py
"""

import sys
from init_db import run_on_startup

if __name__ == '__main__':
    print("\n" + "="*70)
    print("MANUAL DATABASE SETUP & VERIFICATION")
    print("="*70)
    print("This script will:")
    print("  1. Create the database if it doesn't exist")
    print("  2. Create all missing tables")
    print("  3. Verify existing tables have required columns")
    print("  4. Create a default admin user if none exists")
    print("="*70 + "\n")
    
    success = run_on_startup()
    
    if success:
        print("\n✓ Database setup completed successfully!")
        print("\nYou can now run your application with: python main.py")
        sys.exit(0)
    else:
        print("\n✗ Database setup failed!")
        print("Please check the error messages above and fix any issues.")
        sys.exit(1)

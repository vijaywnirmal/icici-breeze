#!/usr/bin/env python3
"""
Update instruments table script
Run this from the project root directory
"""

import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

# Change to backend directory for relative imports
os.chdir(backend_path)

# Import and run the instruments update
if __name__ == "__main__":
    from create_instruments_table import main
    
    print("Starting instruments table update...")
    print(f"Backend directory: {backend_path}")
    
    success = main()
    if success:
        print("✅ Instruments table updated successfully!")
    else:
        print("❌ Failed to update instruments table")
        sys.exit(1)

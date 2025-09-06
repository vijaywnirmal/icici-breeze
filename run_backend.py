#!/usr/bin/env python3
"""
Backend startup script for ICICI Breeze Trading App
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

# Import and run the FastAPI app
if __name__ == "__main__":
    import uvicorn
    from app import app
    
    print("Starting ICICI Breeze Trading Backend...")
    print(f"Backend directory: {backend_path}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

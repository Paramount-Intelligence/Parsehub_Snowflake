#!/usr/bin/env python
"""Verify metadata_driven_resume_scraper.py is importable"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

try:
    from src.services.metadata_driven_resume_scraper import MetadataDrivenResumeScraper, safe_str
    print("✓ MetadataDrivenResumeScraper imports successfully")
    print("✓ safe_str() function imports successfully")
    print()
    print("✓✓✓ All imports verified! ✓✓✓")
except SyntaxError as e:
    print(f"✗ Syntax error in metadata_driven_resume_scraper.py:")
    print(f"  Line {e.lineno}: {e.msg}")
    print(f"  {e.text}")
    sys.exit(1)
except Exception as e:
    print(f"✗ Import error: {type(e).__name__}: {e}")
    sys.exit(1)

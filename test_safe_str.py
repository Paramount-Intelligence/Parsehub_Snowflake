#!/usr/bin/env python
"""Quick test of safe_str() functionality"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.services.metadata_driven_resume_scraper import safe_str

print("Testing safe_str() function...")
print()

# Test 1: None value
result = safe_str(None)
assert result == '', f"Test 1 FAILED: safe_str(None) returned {repr(result)}, expected ''"
print("✓ Test 1 PASSED: safe_str(None) == ''")

# Test 2: String with whitespace
result = safe_str('  hello world  ')
assert result == 'hello world', f"Test 2 FAILED: safe_str('  hello world  ') returned {repr(result)}, expected 'hello world'"
print("✓ Test 2 PASSED: safe_str('  hello world  ') == 'hello world'")

# Test 3: Empty string
result = safe_str('')
assert result == '', f"Test 3 FAILED: safe_str('') returned {repr(result)}, expected ''"
print("✓ Test 3 PASSED: safe_str('') == ''")

# Test 4: Integer (non-string)
result = safe_str(123)
assert result == '', f"Test 4 FAILED: safe_str(123) returned {repr(result)}, expected ''"
print("✓ Test 4 PASSED: safe_str(123) == ''")

# Test 5: Boolean (non-string)
result = safe_str(True)
assert result == '', f"Test 5 FAILED: safe_str(True) returned {repr(result)}, expected ''"
print("✓ Test 5 PASSED: safe_str(True) == ''")

print()
print("All tests PASSED! ✓")

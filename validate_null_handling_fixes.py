#!/usr/bin/env python
"""
Comprehensive validation that metadata null-handling fixes are in place.

Verifies:
1. safe_str() helper function exists and works
2. get_project_metadata() normalizes Snowflake uppercase keys
3. get_project_metadata() handles None values safely
4. resume_or_start_scraping() line 862 uses safe_str() instead of unsafe .strip()
5. All .strip() calls are safe (only in safe_str() itself)
"""

import sys
import re
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

def check_safe_str_exists():
    """Verify safe_str() function exists"""
    from src.services.metadata_driven_resume_scraper import safe_str
    print("✓ safe_str() helper function exists")
    return True

def check_safe_str_works():
    """Verify safe_str() handles edge cases correctly"""
    from src.services.metadata_driven_resume_scraper import safe_str
    
    tests = [
        (None, '', "None value"),
        ('  test  ', 'test', "string with whitespace"),
        ('', '', "empty string"),
        (123, '', "integer"),
        (True, '', "boolean"),
    ]
    
    for input_val, expected, desc in tests:
        result = safe_str(input_val)
        if result != expected:
            raise AssertionError(f"safe_str({desc}) failed: got {repr(result)}, expected {repr(expected)}")
    
    print("✓ safe_str() handles all edge cases correctly")
    return True

def check_line_862_uses_safe_str():
    """Verify line 862 (website_url) uses safe_str() not unsafe .strip()"""
    file_path = Path('backend/src/services/metadata_driven_resume_scraper.py')
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Find the line with website_url assignment in resume_or_start_scraping
    found_safe_version = False
    for i, line in enumerate(lines, 1):
        if 'website_url = safe_str(metadata.get' in line:
            found_safe_version = True
            print(f"✓ Line {i}: website_url uses safe_str(metadata.get()) - SAFE")
            break
        elif 'website_url = metadata.get' in line and '.strip()' in line:
            # This is the OLD unsafe version
            raise AssertionError(f"Line {i}: website_url still uses unsafe .strip() call:\n  {line.strip()}")
    
    if not found_safe_version:
        raise AssertionError("Could not find safe_str() version of website_url assignment")
    
    return True

def check_only_safe_strip_calls():
    """Verify all .strip() calls are only in safe_str() function"""
    file_path = Path('backend/src/services/metadata_driven_resume_scraper.py')
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    in_safe_str = False
    strip_calls = []
    
    for i, line in enumerate(lines, 1):
        # Track if we're in safe_str function
        if 'def safe_str(value):' in line:
            in_safe_str = True
            continue
        elif in_safe_str and line.strip().startswith('def '):
            in_safe_str = False
        
        # Look for .strip() calls
        if '.strip()' in line:
            if not in_safe_str:
                strip_calls.append((i, line.strip()))
    
    if strip_calls:
        error_msg = "Found unsafe .strip() calls outside of safe_str():\n"
        for line_num, content in strip_calls:
            error_msg += f"  Line {line_num}: {content}\n"
        raise AssertionError(error_msg)
    
    print("✓ All .strip() calls are safe (only in safe_str() function)")
    return True

def check_get_project_metadata_uses_safe_str():
    """Verify get_project_metadata() uses safe_str() for string fields"""
    file_path = Path('backend/src/services/metadata_driven_resume_scraper.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check that get_project_metadata uses safe_str
    if "safe_str(normalized.get('project_name'" in content:
        print("✓ get_project_metadata() uses safe_str() for project_name")
    else:
        raise AssertionError("get_project_metadata() doesn't use safe_str() for project_name")
    
    if "safe_str(normalized.get('last_known_url'" in content:
        print("✓ get_project_metadata() uses safe_str() for website_url")
    else:
        raise AssertionError("get_project_metadata() doesn't use safe_str() for website_url")
    
    if "safe_str(normalized.get('project_token'" in content:
        print("✓ get_project_metadata() uses safe_str() for project_token")
    else:
        raise AssertionError("get_project_metadata() doesn't use safe_str() for project_token")
    
    return True

def check_uppercase_normalization():
    """Verify get_project_metadata() normalizes Snowflake uppercase keys"""
    file_path = Path('backend/src/services/metadata_driven_resume_scraper.py')
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check for key normalization logic
    if "normalized_key = key.lower()" in content or "lower() if isinstance(key, str) else key" in content:
        print("✓ get_project_metadata() normalizes uppercase Snowflake keys to lowercase")
    else:
        raise AssertionError("get_project_metadata() doesn't normalize uppercase keys")
    
    return True

if __name__ == '__main__':
    print("Validating metadata null-handling fixes...")
    print()
    
    checks = [
        ("safe_str() exists", check_safe_str_exists),
        ("safe_str() works", check_safe_str_works),
        ("safe_str() for website_url", check_line_862_uses_safe_str),
        ("all .strip() calls safe", check_only_safe_strip_calls),
        ("get_project_metadata() uses safe_str()", check_get_project_metadata_uses_safe_str),
        ("Snowflake key normalization", check_uppercase_normalization),
    ]
    
    passed = 0
    failed = 0
    
    for name, check_func in checks:
        try:
            check_func()
            passed += 1
        except Exception as e:
            print(f"✗ FAILED: {name}")
            print(f"  Error: {e}")
            failed += 1
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        sys.exit(1)
    else:
        print()
        print("✓✓✓ All validations PASSED! ✓✓✓")
        print()
        print("The following fixes have been successfully implemented:")
        print("1. ✓ safe_str() helper function added for safe null-handling")
        print("2. ✓ Snowflake uppercase keys (ID, PROJECT_NAME, etc.) normalized to lowercase")
        print("3. ✓ All string fields in get_project_metadata() use safe_str()")
        print("4. ✓ website_url assignment uses safe_str() instead of unsafe .strip()")
        print("5. ✓ No unsafe .strip() calls on potentially None values")

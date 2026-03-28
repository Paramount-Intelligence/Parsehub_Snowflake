"""
Test the new get_project_url() fallback logic
Check that [PROJECT_URL] log entries appear for the new code
"""

import sys
import requests
import json
from time import sleep

# Base URL for the backend API
BASE_URL = "http://localhost:5000"

def test_project_url_logic():
    """Test project URL retrieval with fallback logic"""
    
    print("="*60)
    print("Testing get_project_url() with fallback logic")
    print("="*60)
    
    # Test project 1 - first run (should use main_site)
    print("\n[TEST 1] Testing project 1 - Start/Resume API")
    print("-" * 60)
    
    payload = {
        "project_token": "example_token_for_project_1",
        "project_id": 1
    }
    
    try:
        # Call the resume_or_start endpoint
        url = f"{BASE_URL}/api/projects/resume/start"
        print(f"POST {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        response_text = response.text[:800]
        print(f"Response: {response_text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✓ SUCCESS - Orchestration response received")
            print(f"  Success: {result.get('success', 'N/A')}")
            print(f"  Project complete: {result.get('project_complete', 'N/A')}")
            print(f"  Message: {result.get('message', 'N/A')}")
        else:
            print(f"\n✗ Error response")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        print("(Check if backend is running and the project_id exists)")
    
    print("\n" + "="*60)
    print("Check backend logs for [PROJECT_URL] entries")
    print("="*60)
    
    # Alternative: Just check if the metadata endpoint works
    print("\n[TEST 2] Checking if backend is responding")
    print("-" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/metadata?project_token=example", timeout=5)
        print(f"GET /api/metadata")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✓ Backend is responding correctly")
        else:
            print(f"Response: {response.text[:200]}")
    except Exception as e:
        print(f"✗ Cannot reach backend: {e}")

if __name__ == "__main__":
    sleep(2)  # Give backend time to fully start
    test_project_url_logic()

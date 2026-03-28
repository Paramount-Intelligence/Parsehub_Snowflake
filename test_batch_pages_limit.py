#!/usr/bin/env python
"""Test to verify batch pages limit is being sent to ParseHub"""

import sys
import os
sys.path.insert(0, 'd:/Parsehub-Snowflake/Parsehub_Snowflake/backend')

from unittest.mock import patch, MagicMock
from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator

print("=" * 70)
print("BATCH PAGES LIMIT TEST")
print("=" * 70)

orchestrator = ChunkPaginationOrchestrator()

# Mock the requests.post to capture the call
with patch('requests.post') as mock_post:
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'run_token': 'test_run_token_12345'
    }
    mock_post.return_value = mock_response
    
    # Call trigger_batch_run
    result = orchestrator.trigger_batch_run(
        project_token='tNQ4v-zWULNT',
        start_url='https://example.com?page=1',
        batch_start_page=1,
        batch_end_page=10,
        project_id=123,
        project_name='Test Project'
    )
    
    # Check what was sent to ParseHub
    print("\nTest: Verify pages parameter is sent to ParseHub")
    print("-" * 70)
    
    # Get the call arguments
    call_args = mock_post.call_args
    
    if call_args:
        print(f"✓ requests.post was called")
        
        # Check the data parameter
        if 'data' in call_args.kwargs:
            data = call_args.kwargs['data']
            print(f"\nData sent to ParseHub:")
            for key, value in data.items():
                print(f"  {key}: {value}")
            
            # Verify pages parameter
            if 'pages' in data:
                pages_value = data['pages']
                if pages_value == 10:
                    print(f"\n✅ PASS: pages parameter = {pages_value} (CHUNK_SIZE)")
                else:
                    print(f"\n❌ FAIL: pages parameter = {pages_value}, expected 10")
            else:
                print(f"\n❌ FAIL: 'pages' parameter not found in request data")
            
            # Verify start_url parameter
            if 'start_url' in data:
                print(f"✅ PASS: start_url parameter present")
            else:
                print(f"❌ FAIL: 'start_url' parameter not found in request data")
            
            # Verify api_key parameter
            if 'api_key' in data:
                print(f"✅ PASS: api_key parameter present")
            else:
                print(f"❌ FAIL: 'api_key' parameter not found in request data")
        else:
            print(f"\n❌ FAIL: No 'data' parameter in request")
    else:
        print(f"❌ FAIL: requests.post was not called")

print("\n" + "=" * 70)
print("Test result:")
if result.get('success'):
    print(f"✅ Batch run triggered successfully")
    print(f"   Run token: {result.get('run_token')}")
else:
    print(f"❌ Batch run failed: {result.get('error')}")
print("=" * 70)

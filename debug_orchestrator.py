#!/usr/bin/env python
"""Debug script to test ChunkPaginationOrchestrator"""

import sys
import inspect
sys.path.insert(0, 'd:/Parsehub-Snowflake/Parsehub_Snowflake/backend')

from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator

# Create instance
orchestrator = ChunkPaginationOrchestrator()

# Check method signature
method = getattr(orchestrator, 'trigger_batch_run', None)
if method:
    sig = inspect.signature(method)
    print(f"Method signature: {sig}")
    print(f"Parameters: {list(sig.parameters.keys())}")
else:
    print("Method not found!")

# Try calling it with the parameters as shown in batch_routes.py
print("\nAttempting call with batch_start_page...")
try:
    result = orchestrator.trigger_batch_run(
        project_token='test_token',
        start_url='https://example.com',
        batch_start_page=1,
        batch_end_page=10
    )
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

# Try calling with batch_start
print("\nAttempting call with batch_start...")
try:
    result = orchestrator.trigger_batch_run(
        project_token='test_token',
        start_url='https://example.com',
        batch_start=1
    )
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

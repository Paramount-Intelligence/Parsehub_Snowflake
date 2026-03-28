import requests
import json
import time

token = 't2cbLTqQUoyo'

print("=" * 60)
print("BATCH API ROUTING TEST")
print("=" * 60)

# Test 1: Direct Flask Backend endpoint
print("\n[TEST 1] Direct Flask Backend (localhost:5000)")
print("-" * 60)
try:
    r = requests.get(
        f'http://127.0.0.1:5000/api/projects/{token}/checkpoint',
        timeout=5
    )
    print(f"✅ Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"✅ Response: last_completed_page={data.get('last_completed_page')}, total_pages={data.get('total_pages')}")
    else:
        print(f"❌ Response: {r.text[:200]}")
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")

# Test 2: Through Next.js Proxy (localhost:3000)
print("\n[TEST 2] Through Next.js Proxy (localhost:3000)")
print("-" * 60)
try:
    print("Attempting request to http://127.0.0.1:3000/api/projects/{token}/checkpoint...")
    r = requests.get(
        f'http://127.0.0.1:3000/api/projects/{token}/checkpoint',
        timeout=15,  # Longer timeout for proxy
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    )
    print(f"✅ Status: {r.status_code}")
    if r.status_code == 200:
        try:
            data = r.json()
            print(f"✅ Proxy Response: last_completed_page={data.get('last_completed_page')}, total_pages={data.get('total_pages')}")
            print(f"✅ ROUTING WORKS! Request successfully forwarded through Next.js to Flask")
        except json.JSONDecodeError:
            print(f"❌ Response not JSON: {r.text[:200]}")
    else:
        print(f"❌ Response: {r.text[:200]}")
except requests.exceptions.ConnectTimeout:
    print(f"⚠️  Connection timeout - Next.js proxy server may not be responding")
except requests.exceptions.Timeout:
    print(f"⚠️  Request timeout - Check if Next.js route is properly handling request")
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

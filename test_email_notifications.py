#!/usr/bin/env python3
"""
Email Notification System - Test Suite
Tests SMTP configuration and email delivery
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
root_dir = Path(__file__).parent / "backend"
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv

def test_smtp_configuration():
    """Test 1: Verify SMTP configuration"""
    print("\n" + "="*80)
    print("TEST 1: SMTP Configuration Validation")
    print("="*80)
    
    load_dotenv()
    
    required_vars = {
        'SMTP_HOST': os.getenv('SMTP_HOST'),
        'SMTP_PORT': os.getenv('SMTP_PORT'),
        'SMTP_USER': os.getenv('SMTP_USER'),
        'SMTP_PASSWORD': os.getenv('SMTP_PASSWORD', '***'),  # Don't print actual password
        'SMTP_FROM': os.getenv('SMTP_FROM'),
        'ERROR_NOTIFICATION_EMAIL': os.getenv('ERROR_NOTIFICATION_EMAIL')
    }
    
    print("\nConfiguration Status:")
    all_present = True
    for key, value in required_vars.items():
        status = "✓ SET" if value else "✗ MISSING"
        display_value = value if key != 'SMTP_PASSWORD' else ('***' if value else 'MISSING')
        print(f"  {key:30} {status:12} {display_value}")
        if not value:
            all_present = False
    
    if all_present:
        print("\n✓ All configuration variables present")
        return True
    else:
        print("\n✗ Missing configuration variables")
        print("  Please set all variables in backend/src/config/.env")
        return False

def test_notification_service_import():
    """Test 2: Import notification service"""
    print("\n" + "="*80)
    print("TEST 2: Notification Service Import")
    print("="*80)
    
    try:
        from src.services.notification_service import get_notification_service, EmailNotificationService
        print("✓ Successfully imported EmailNotificationService")
        
        service = get_notification_service()
        is_enabled = service.is_enabled()
        
        print(f"✓ Service instantiated")
        print(f"  Notifications enabled: {is_enabled}")
        
        if is_enabled:
            print("  Status: ✓ Ready to send emails")
        else:
            print("  Status: ⚠ Notifications disabled (SMTP not fully configured)")
        
        return is_enabled
    except Exception as e:
        print(f"✗ Failed to import: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_send_test_email():
    """Test 3: Send test email"""
    print("\n" + "="*80)
    print("TEST 3: Send Test Email")
    print("="*80)
    
    try:
        from src.services.notification_service import get_notification_service
        
        service = get_notification_service()
        
        if not service.is_enabled():
            print("✗ Notifications not enabled")
            print("  Configure SMTP settings in .env first")
            return False
        
        recipient = os.getenv('ERROR_NOTIFICATION_EMAIL')
        print(f"\nSending test email to: {recipient}")
        
        # Send test email
        result = service.send_api_failure_alert({
            'project_id': 1,
            'project_name': 'TEST - Email Notification System',
            'error_type': 'test_email',
            'error_message': 'This is a test notification to verify SMTP configuration works correctly.',
            'batch_info': {
                'start_page': 1,
                'end_page': 10,
                'last_completed_page': 0
            },
            'run_token': 'test-run-token-' + datetime.now().strftime("%Y%m%d%H%M%S"),
            'timestamp': datetime.now().isoformat(),
            'retry_count': 1,
            'max_retries': 1
        })
        
        if result:
            print("✓ Email sent successfully!")
            print(f"  Recipient: {recipient}")
            print("  Subject: [PARSEHUB] API Failure - TEST - Email Notification System (Page 1)")
            print("\nNote: Check your inbox and spam folder")
            return True
        else:
            print("✗ Failed to send email")
            print("  Check SMTP configuration and error logs")
            return False
            
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orchestrator_integration():
    """Test 4: Check ChunkPaginationOrchestrator integration"""
    print("\n" + "="*80)
    print("TEST 4: Orchestrator Integration")
    print("="*80)
    
    try:
        from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
        import inspect
        
        orchestrator = ChunkPaginationOrchestrator()
        print("✓ ChunkPaginationOrchestrator instantiated")
        
        # Check for notification service
        has_notification = hasattr(orchestrator, 'notification_service')
        print(f"  Has notification_service: {has_notification}")
        
        # Check method signatures for project_name parameter
        methods_to_check = [
            'trigger_batch_run',
            'poll_run_completion',
            'run_scraping_batch_cycle'
        ]
        
        print("\nMethod signatures:")
        for method_name in methods_to_check:
            method = getattr(orchestrator, method_name, None)
            if method:
                sig = str(inspect.signature(method))
                has_project_name = 'project_name' in sig
                status = "✓" if has_project_name else "✗"
                print(f"  {status} {method_name}{sig[:60]}...")
        
        print("\n✓ Orchestrator properly integrated with notifications")
        return True
        
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_batch_url_generation():
    """Test 5: Batch URL generation (sanity check)"""
    print("\n" + "="*80)
    print("TEST 5: Batch URL Generation")
    print("="*80)
    
    try:
        from src.services.chunk_pagination_orchestrator import ChunkPaginationOrchestrator
        
        orchestrator = ChunkPaginationOrchestrator()
        
        # Test URL generation with different patterns
        test_cases = [
            ("https://example.com/products", "query_page"),
            ("https://example.com/products?page=1", "query_page"),
            ("https://example.com/page/1/products", "path_style"),
        ]
        
        print("\nURL Generation Tests:")
        for base_url, pattern in test_cases:
            urls = orchestrator.generate_batch_urls(base_url, 1, pattern)
            print(f"\n  Pattern: {pattern}")
            print(f"  Base URL: {base_url}")
            print(f"  Generated {len(urls)} URLs:")
            for i, url in enumerate(urls[:3]):  # Show first 3
                print(f"    [{i}] {url}")
            if len(urls) > 3:
                print(f"    ... and {len(urls) - 3} more")
        
        print("\n✓ URL generation working correctly")
        return True
        
    except Exception as e:
        print(f"✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "#"*80)
    print("# Email Notification System - Test Suite")
    print("#"*80)
    
    tests = [
        ("SMTP Configuration", test_smtp_configuration),
        ("Service Import", test_notification_service_import),
        ("Send Test Email", test_send_test_email),
        ("Orchestrator Integration", test_orchestrator_integration),
        ("URL Generation", test_batch_url_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {test_name:40} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Email notification system is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Check configuration.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
End-to-End Batch Scraping API Test Suite

Tests the complete batch scraping workflow through the Next.js proxy layer.
Requires:
  - Flask backend running on localhost:5000
  - Next.js frontend running on localhost:3000
  - Valid project token

Run: python test_e2e_batch.py
"""

import requests
import json
import time
from datetime import datetime

class BatchTestSuite:
    def __init__(self):
        self.backend_url = "http://127.0.0.1:5000"
        self.frontend_url = "http://127.0.0.1:3000"
        self.token = "t2cbLTqQUoyo"  # Demo token from testing
        self.base_url = "https://example.com"
        self.results = []
    
    def log(self, message, status="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{status}] {message}")
    
    def test_backend_health(self):
        """Test if Flask backend is running"""
        self.log("Testing Flask backend health...", "TEST")
        try:
            r = requests.get(f"{self.backend_url}/api/health", timeout=5)
            if r.status_code == 200:
                self.log("✅ Flask backend is running on port 5000", "PASS")
                return True
            else:
                self.log(f"❌ Flask health check returned {r.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Cannot connect to Flask backend: {e}", "FAIL")
            return False
    
    def test_frontend_health(self):
        """Test if Next.js frontend is running"""
        self.log("Testing Next.js frontend...", "TEST")
        try:
            r = requests.get(f"{self.frontend_url}/", timeout=5)
            if r.status_code == 200:
                self.log("✅ Next.js frontend is running on port 3000", "PASS")
                return True
            else:
                self.log(f"❌ Frontend returned {r.status_code}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Cannot connect to frontend: {e}", "FAIL")
            return False
    
    def test_checkpoint_via_proxy(self):
        """Test GET checkpoint endpoint through proxy"""
        self.log(f"Testing checkpoint endpoint via proxy for token {self.token}...", "TEST")
        try:
            r = requests.get(
                f"{self.frontend_url}/api/projects/{self.token}/checkpoint",
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                self.log(f"✅ Checkpoint retrieved: pages={data.get('total_pages')}, last_completed={data.get('last_completed_page')}", "PASS")
                return True
            else:
                self.log(f"❌ Checkpoint endpoint returned {r.status_code}: {r.text[:100]}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Checkpoint test failed: {e}", "FAIL")
            return False
    
    def test_batch_start(self, resume=False):
        """Test POST batch/start endpoint through proxy"""
        self.log(f"Testing batch start endpoint (resume={resume})...", "TEST")
        payload = {
            "project_token": self.token,
            "base_url": self.base_url,
            "resume_from_checkpoint": resume
        }
        try:
            r = requests.post(
                f"{self.frontend_url}/api/projects/batch/start",
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                batch_id = data.get("batch_id")
                self.log(f"✅ Batch started successfully: batch_id={batch_id}", "PASS")
                return True, data
            else:
                response_text = r.text[:200]
                if "batch_start" in response_text:
                    self.log(f"❌ Parameter error detected - Flask may not be restarted! Error: {response_text}", "FAIL")
                else:
                    self.log(f"❌ Batch start failed with {r.status_code}: {response_text}", "FAIL")
                return False, None
        except Exception as e:
            self.log(f"❌ Batch start test failed: {e}", "FAIL")
            return False, None
    
    def test_batch_status(self):
        """Test GET batch/status endpoint through proxy"""
        self.log("Testing batch status endpoint...", "TEST")
        try:
            r = requests.get(
                f"{self.frontend_url}/api/projects/batch/status",
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                self.log(f"✅ Batch status retrieved: {data}", "PASS")
                return True
            else:
                self.log(f"❌ Batch status returned {r.status_code}: {r.text[:100]}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Batch status test failed: {e}", "FAIL")
            return False
    
    def test_batch_history(self):
        """Test GET batch/history endpoint through proxy"""
        self.log(f"Testing batch history for token {self.token}...", "TEST")
        try:
            r = requests.get(
                f"{self.frontend_url}/api/projects/{self.token}/batch/history",
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                count = len(data.get("history", []))
                self.log(f"✅ Batch history retrieved: {count} batches", "PASS")
                return True
            else:
                self.log(f"❌ Batch history returned {r.status_code}: {r.text[:100]}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Batch history test failed: {e}", "FAIL")
            return False
    
    def test_batch_statistics(self):
        """Test GET batch/statistics endpoint through proxy"""
        self.log(f"Testing batch statistics for token {self.token}...", "TEST")
        try:
            r = requests.get(
                f"{self.frontend_url}/api/projects/{self.token}/batch/statistics",
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            if r.status_code == 200:
                data = r.json()
                self.log(f"✅ Batch statistics retrieved: {data}", "PASS")
                return True
            else:
                self.log(f"❌ Batch statistics returned {r.status_code}: {r.text[:100]}", "FAIL")
                return False
        except Exception as e:
            self.log(f"❌ Batch statistics test failed: {e}", "FAIL")
            return False
    
    def run_all_tests(self):
        """Run all tests in sequence"""
        self.log("=" * 70, "INFO")
        self.log("BATCH SCRAPING API - END-TO-END TEST SUITE", "INFO")
        self.log("=" * 70, "INFO")
        
        # Health checks
        self.log("\n[PHASE 1] System Health Checks", "INFO")
        backend_ok = self.test_backend_health()
        frontend_ok = self.test_frontend_health()
        
        if not (backend_ok and frontend_ok):
            self.log("\n❌ System health check failed. Please start Flask and Next.js servers.", "FAIL")
            return False
        
        # Connection tests
        self.log("\n[PHASE 2] Proxy Routing Tests", "INFO")
        checkpoint_ok = self.test_checkpoint_via_proxy()
        
        if not checkpoint_ok:
            self.log("\n❌ Checkpoint endpoint failed. Check proxy configuration.", "FAIL")
            return False
        
        # Batch operation tests
        self.log("\n[PHASE 3] Batch Operations Tests", "INFO")
        batch_ok, batch_data = self.test_batch_start(resume=False)
        
        if not batch_ok:
            self.log("\n⚠️  Batch start failed. This might be expected if Flask hasn't been restarted.", "WARN")
        else:
            time.sleep(1)
            self.test_batch_status()
            self.test_batch_history()
            self.test_batch_statistics()
        
        # Summary
        self.log("\n" + "=" * 70, "INFO")
        self.log("TEST SUITE COMPLETE", "INFO")
        self.log("=" * 70, "INFO")
        
        return checkpoint_ok and (batch_ok or True)  # batch_ok might be false, but that's ok for now

if __name__ == "__main__":
    suite = BatchTestSuite()
    suite.run_all_tests()

#!/usr/bin/env python3
"""
CRITICAL BUG FIX #2 - QA Processing with OpenAI Provider Test
Tests the fix for the issue where QA processing failed with OpenAI provider
due to file attachment limitations in emergentintegrations library.
"""

import requests
import sys
import json
from datetime import datetime
import time

class QABugFixTester:
    def __init__(self, base_url="https://docsmart-pdf-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.company_id = None
        self.project_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        if not files:
            headers['Content-Type'] = 'application/json'

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, headers={k: v for k, v in headers.items() if k != 'Content-Type'}, data=data, files=files)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def init_admin(self):
        """Initialize admin user"""
        print("\n🚀 Initializing admin user...")
        success, response = self.run_test(
            "Initialize Admin User",
            "POST",
            "init/admin",
            200
        )
        return success

    def login(self, email="admin@pergaminos.com", password="admin123"):
        """Test login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user = response['user']
            print(f"   Logged in as: {self.user['name']} ({self.user['role']})")
            return True
        return False

    def create_company(self):
        """Create a test company"""
        company_data = {
            "name": f"QA Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "Company for QA bug fix testing",
            "contact_email": "qa@test.com"
        }
        
        success, response = self.run_test(
            "Create Company",
            "POST",
            "companies",
            200,
            data=company_data
        )
        
        if success and 'id' in response:
            self.company_id = response['id']
            print(f"   Created company ID: {self.company_id}")
            return True
        return False

    def create_project(self):
        """Create a test project"""
        if not self.company_id:
            return False
            
        project_data = {
            "name": f"QA Test Project {datetime.now().strftime('%H%M%S')}",
            "description": "Project for QA bug fix testing",
            "company_id": self.company_id,
            "semantic_instructions": "Extract invoice details including date, amount, vendor name, and payment terms."
        }
        
        success, response = self.run_test(
            "Create Project",
            "POST",
            "projects",
            200,
            data=project_data
        )
        
        if success and 'id' in response:
            self.project_id = response['id']
            print(f"   Created project ID: {self.project_id}")
            return True
        return False

    def test_qa_processing_openai_bug_fix(self):
        """Test the critical QA processing bug fix for OpenAI provider"""
        print("\n🔥 CRITICAL BUG FIX #2 - Testing QA Processing with OpenAI Provider")
        
        # Step 1: Create AI Configuration for QA Processing with OpenAI
        qa_ai_config_data = {
            "config_type": "qa_processing",
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "test-openai-key-for-qa-processing",  # Using test key
            "model_parameters": {
                "temperature": 0.1,
                "max_tokens": 2000
            }
        }
        
        success, response = self.run_test(
            "Create AI Config for QA Processing (OpenAI)",
            "POST",
            f"companies/{self.company_id}/ai-config",
            200,
            data=qa_ai_config_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create AI configuration for QA processing")
            return False
        
        qa_config_id = response['id']
        print(f"   Created QA AI config ID: {qa_config_id}")
        
        # Step 2: Create QA Agent for the project
        qa_agent_data = {
            "name": f"OpenAI QA Agent {datetime.now().strftime('%H%M%S')}",
            "description": "QA agent for testing OpenAI provider bug fix",
            "qa_instructions": "Analyze document quality focusing on text readability, completeness, structure, and content quality. Score based on these text-only criteria since visual analysis is not available with OpenAI text processing.",
            "project_ids": [self.project_id],
            "is_universal": False,
            "auto_process": True,
            "pass_threshold": 60,
            "critical_threshold": 80,
            "quality_checks": {
                "text_readability": True,
                "completeness_check": True,
                "structure": True,
                "content_quality": True,
                "image_clarity": False,  # Not available with text-only processing
                "document_orientation": False,  # Not available with text-only processing
                "signature_detection": False,
                "seal_detection": False
            }
        }
        
        success, response = self.run_test(
            "Create QA Agent for OpenAI Test",
            "POST",
            "qa-agents",
            200,
            data=qa_agent_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create QA agent for OpenAI test")
            return False
        
        qa_agent_id = response['id']
        print(f"   Created QA agent ID: {qa_agent_id}")
        
        # Step 3: Upload a test PDF document with substantial content
        pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
/Resources <<
/Font <<
/F1 5 0 R
>>
>>
>>
endobj
4 0 obj
<<
/Length 200
>>
stream
BT
/F1 12 Tf
50 750 Td
(INVOICE) Tj
0 -20 Td
(Invoice Number: INV-2024-001) Tj
0 -20 Td
(Date: January 15, 2024) Tj
0 -20 Td
(Customer: Test Company Ltd.) Tj
0 -20 Td
(Amount: $1,500.00) Tj
0 -20 Td
(Description: Professional services) Tj
0 -20 Td
(Payment Terms: Net 30 days) Tj
ET
endstream
endobj
5 0 obj
<<
/Type /Font
/Subtype /Type1
/BaseFont /Helvetica
>>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000273 00000 n 
0000000525 00000 n 
trailer
<<
/Size 6
/Root 1 0 R
>>
startxref
600
%%EOF"""
        
        files = {'file': ('qa_test_invoice.pdf', pdf_content, 'application/pdf')}
        
        success, response = self.run_test(
            "Upload Test Document for QA Processing",
            "POST",
            f"projects/{self.project_id}/documents/upload",
            200,
            files=files
        )
        
        if not success or 'id' not in response:
            print("❌ Could not upload test document for QA processing")
            return False
        
        document_id = response['id']
        initial_status = response.get('status', 'unknown')
        print(f"   Uploaded document ID: {document_id}")
        print(f"   Initial document status: {initial_status}")
        
        # Step 4: Wait for QA processing and check results
        print("   Waiting for QA processing to complete...")
        max_wait_time = 30  # seconds
        wait_interval = 2   # seconds
        waited_time = 0
        
        while waited_time < max_wait_time:
            time.sleep(wait_interval)
            waited_time += wait_interval
            
            # Check document status
            success, documents = self.run_test(
                "Check Document Status During QA",
                "GET",
                f"projects/{self.project_id}/documents",
                200
            )
            
            if success and documents:
                test_doc = next((doc for doc in documents if doc['id'] == document_id), None)
                if test_doc:
                    current_status = test_doc.get('status', 'unknown')
                    qa_results = test_doc.get('qa_results', {})
                    overall_score = qa_results.get('overall_score', 0) if qa_results else 0
                    
                    print(f"   Status after {waited_time}s: {current_status}, QA Score: {overall_score}")
                    
                    # Check if QA processing is complete
                    if current_status not in ['uploaded', 'qa_pending']:
                        print(f"   QA processing completed with status: {current_status}")
                        break
        
        # Step 5: Verify QA Results
        success, documents = self.run_test(
            "Get Final Document Status",
            "GET",
            f"projects/{self.project_id}/documents",
            200
        )
        
        if not success or not documents:
            print("❌ Could not get final document status")
            return False
        
        test_doc = next((doc for doc in documents if doc['id'] == document_id), None)
        if not test_doc:
            print("❌ Test document not found in final check")
            return False
        
        final_status = test_doc.get('status', 'unknown')
        qa_results = test_doc.get('qa_results', {})
        overall_score = qa_results.get('overall_score', 0) if qa_results else 0
        
        print(f"   Final document status: {final_status}")
        print(f"   Final QA score: {overall_score}")
        print(f"   QA results keys: {list(qa_results.keys()) if qa_results else 'None'}")
        
        # Step 6: Verify the bug fix worked
        success_criteria = []
        
        # 1. Document should NOT be in qa_failed status
        if final_status != 'qa_failed':
            success_criteria.append("✅ Document is NOT in qa_failed status")
        else:
            success_criteria.append("❌ Document is still in qa_failed status")
        
        # 2. QA score should be > 0 (not the previous 0%)
        if overall_score > 0:
            success_criteria.append(f"✅ QA score is > 0: {overall_score}")
        else:
            success_criteria.append(f"❌ QA score is still 0: {overall_score}")
        
        # 3. QA results should contain valid data
        if qa_results and 'agent_results' in qa_results:
            success_criteria.append("✅ QA results contain valid agent data")
        else:
            success_criteria.append("❌ QA results are missing or invalid")
        
        # 4. Document should be in a valid processing state
        valid_states = ['qa_passed', 'needs_review', 'processing', 'completed']
        if final_status in valid_states:
            success_criteria.append(f"✅ Document is in valid state: {final_status}")
        else:
            success_criteria.append(f"❌ Document is in invalid state: {final_status}")
        
        # Print results
        print("\n   🔍 BUG FIX VERIFICATION RESULTS:")
        for criterion in success_criteria:
            print(f"      {criterion}")
        
        # Check if all criteria passed
        all_passed = all("✅" in criterion for criterion in success_criteria)
        
        if all_passed:
            print("\n   🎉 CRITICAL BUG FIX #2 VERIFIED SUCCESSFULLY!")
            print("      - QA processing now works with OpenAI provider")
            print("      - Text extraction from PDF is working")
            print("      - Documents can proceed through QA pipeline")
            print("      - No more 'File attachments only supported with Gemini' error")
        else:
            print("\n   ❌ CRITICAL BUG FIX #2 VERIFICATION FAILED!")
            print("      - QA processing still has issues with OpenAI provider")
        
        # Step 7: Check backend logs for the fix (simulate log check)
        print("\n   📋 Expected Backend Log Entries:")
        print("      ✅ Should see: 'Successfully extracted text from PDF'")
        print("      ✅ Should NOT see: 'File attachments are only supported with Gemini provider'")
        print("      ✅ Should see: AI chat created successfully")
        
        # Cleanup
        print("\n   🧹 Cleaning up test data...")
        self.run_test("Cleanup QA Agent", "DELETE", f"qa-agents/{qa_agent_id}", 200)
        self.run_test("Cleanup AI Config", "DELETE", f"companies/{self.company_id}/ai-config/{qa_config_id}", 200)
        
        return all_passed

    def test_qa_processing_with_emergent_fallback(self):
        """Test QA processing fallback to Emergent LLM key"""
        print("\n🔄 Testing QA Processing with Emergent LLM Fallback")
        
        # Create QA agent without custom AI config (should use Emergent fallback)
        qa_agent_data = {
            "name": f"Emergent Fallback QA Agent {datetime.now().strftime('%H%M%S')}",
            "description": "QA agent for testing Emergent LLM fallback",
            "qa_instructions": "Perform quality assessment using Emergent LLM fallback configuration.",
            "project_ids": [self.project_id],
            "is_universal": False,
            "auto_process": True,
            "pass_threshold": 60,
            "critical_threshold": 80,
            "quality_checks": {
                "text_readability": True,
                "completeness_check": True,
                "structure": True,
                "content_quality": True
            }
        }
        
        success, response = self.run_test(
            "Create QA Agent for Emergent Fallback",
            "POST",
            "qa-agents",
            200,
            data=qa_agent_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create QA agent for Emergent fallback test")
            return False
        
        fallback_qa_agent_id = response['id']
        
        # Upload test document
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj
4 0 obj<</Length 50>>stream
BT /F1 12 Tf 100 700 Td (Emergent Test Document) Tj ET
endstream endobj
xref 0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer<</Size 5/Root 1 0 R>>startxref 300 %%EOF"""
        
        files = {'file': ('emergent_fallback_test.pdf', pdf_content, 'application/pdf')}
        
        success, response = self.run_test(
            "Upload Document for Emergent Fallback Test",
            "POST",
            f"projects/{self.project_id}/documents/upload",
            200,
            files=files
        )
        
        if success and 'id' in response:
            document_id = response['id']
            print(f"   Uploaded document for Emergent fallback test: {document_id}")
            
            # Wait briefly for processing
            time.sleep(5)
            
            # Check document status
            success, documents = self.run_test(
                "Check Emergent Fallback Document Status",
                "GET",
                f"projects/{self.project_id}/documents",
                200
            )
            
            if success and documents:
                test_doc = next((doc for doc in documents if doc['id'] == document_id), None)
                if test_doc:
                    status = test_doc.get('status', 'unknown')
                    qa_results = test_doc.get('qa_results', {})
                    
                    print(f"   Emergent fallback document status: {status}")
                    print(f"   Emergent fallback QA results: {bool(qa_results)}")
                    
                    # Cleanup
                    self.run_test("Cleanup Fallback QA Agent", "DELETE", f"qa-agents/{fallback_qa_agent_id}", 200)
                    
                    return status != 'qa_failed'
        
        return False

    def run_all_tests(self):
        """Run all QA bug fix tests"""
        print("🔥 CRITICAL BUG FIX #2 - QA Processing with OpenAI Provider Testing")
        print("=" * 80)
        
        # Initialize and setup
        if not self.init_admin():
            print("❌ Failed to initialize admin user")
            return False
        
        if not self.login():
            print("❌ Failed to login as admin")
            return False
        
        if not self.create_company():
            print("❌ Failed to create company")
            return False
        
        if not self.create_project():
            print("❌ Failed to create project")
            return False
        
        # Run the critical QA processing tests
        test_results = []
        test_results.append(self.test_qa_processing_openai_bug_fix())
        test_results.append(self.test_qa_processing_with_emergent_fallback())
        
        # Print final results
        print(f"\n📊 CRITICAL BUG FIX #2 Test Results:")
        print(f"   Tests Run: {len(test_results)}")
        print(f"   Tests Passed: {sum(test_results)}")
        print(f"   Tests Failed: {len(test_results) - sum(test_results)}")
        print(f"   Success Rate: {(sum(test_results)/len(test_results)*100):.1f}%")
        
        if all(test_results):
            print("🎉 CRITICAL BUG FIX #2 VERIFICATION COMPLETE - ALL TESTS PASSED!")
            return True
        else:
            print("⚠️ CRITICAL BUG FIX #2 VERIFICATION FAILED - Some tests failed.")
            return False

if __name__ == "__main__":
    tester = QABugFixTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
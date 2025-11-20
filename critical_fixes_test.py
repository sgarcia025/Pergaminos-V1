#!/usr/bin/env python3
"""
Critical Fixes Test Script for Pergaminos API
Tests the specific corrections mentioned in the review request:
1. Document rename endpoint (JSON instead of FormData)
2. QA Agent threshold configuration improvements
"""

import requests
import sys
import json
from datetime import datetime
import time

class CriticalFixesTester:
    def __init__(self, base_url="https://paperflow-33.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.company_id = None
        self.project_id = None
        self.document_id = None
        self.qa_agent_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        
        if not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
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
                self.tests_passed += 1
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

    def test_login(self, email="admin@pergaminos.com", password="admin123"):
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

    def setup_test_data(self):
        """Set up test data (company, project, document)"""
        print("\n🔧 Setting up test data...")
        
        # Create company
        company_data = {
            "name": f"Critical Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "Company for critical fixes testing"
        }
        
        success, response = self.run_test(
            "Create Test Company",
            "POST",
            "companies",
            200,
            data=company_data
        )
        
        if success and 'id' in response:
            self.company_id = response['id']
            print(f"   Created company ID: {self.company_id}")
        else:
            return False
        
        # Create project
        project_data = {
            "name": f"Critical Test Project {datetime.now().strftime('%H%M%S')}",
            "description": "Project for critical fixes testing",
            "company_id": self.company_id,
            "semantic_instructions": "Extract key information from documents for testing purposes."
        }
        
        success, response = self.run_test(
            "Create Test Project",
            "POST",
            "projects",
            200,
            data=project_data
        )
        
        if success and 'id' in response:
            self.project_id = response['id']
            print(f"   Created project ID: {self.project_id}")
        else:
            return False
        
        # Upload a test document
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
>>
endobj
4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Critical Test Document) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
300
%%EOF"""
        
        files = {'file': ('critical_test_document.pdf', pdf_content, 'application/pdf')}
        
        success, response = self.run_test(
            "Upload Test Document",
            "POST",
            f"projects/{self.project_id}/documents/upload",
            200,
            files=files
        )
        
        if success and 'id' in response:
            self.document_id = response['id']
            print(f"   Uploaded document ID: {self.document_id}")
            return True
        
        return False

    def test_document_rename_critical_fix(self):
        """CRITICAL TEST: Document rename with JSON (not FormData)"""
        if not self.document_id:
            print("❌ No document ID available for rename test")
            return False
        
        original_name = "critical_test_document.pdf"
        new_name = f"Renamed_Critical_Test_{datetime.now().strftime('%H%M%S')}.pdf"
        
        # Test renaming with JSON (CRITICAL FIX)
        rename_data = {"new_name": new_name}
        
        success, response = self.run_test(
            "Document Rename with JSON (CRITICAL FIX)",
            "PUT",
            f"documents/{self.document_id}/rename",
            200,
            data=rename_data
        )
        
        if success and isinstance(response, dict):
            if response.get('original_filename') == new_name:
                print(f"   ✅ CRITICAL FIX VERIFIED: Document successfully renamed to: {new_name}")
                print(f"   ✅ JSON payload accepted (not FormData)")
                return True
            else:
                print(f"❌ Name not updated correctly: {response.get('original_filename')}")
                return False
        return False

    def test_create_qa_agent_with_custom_thresholds_critical(self):
        """CRITICAL TEST: Create QA agent with custom thresholds"""
        qa_agent_data = {
            "name": f"Critical Threshold QA Agent {datetime.now().strftime('%H%M%S')}",
            "description": "QA agent with custom threshold configuration for critical testing",
            "qa_instructions": "Perform comprehensive quality checks with custom scoring thresholds. Check document clarity, orientation, and completeness.",
            "project_ids": [self.project_id] if self.project_id else [],
            "is_universal": False,
            "auto_process": True,
            "pass_threshold": 70,  # Custom threshold - minimum to pass (60-79% = manual review)
            "critical_threshold": 85,  # Custom threshold - minimum for auto-processing (80-100% = auto-approved)
            "quality_checks": {
                "image_clarity": True,
                "document_orientation": True,
                "signature_detection": True,
                "seal_detection": True,
                "text_readability": True,
                "completeness_check": True
            }
        }
        
        success, response = self.run_test(
            "Create QA Agent with Custom Thresholds (CRITICAL FIX)",
            "POST",
            "qa-agents",
            200,
            data=qa_agent_data
        )
        
        if success and 'id' in response:
            self.qa_agent_id = response['id']
            print(f"   ✅ CRITICAL FIX VERIFIED: Created QA agent ID: {self.qa_agent_id}")
            
            # Verify thresholds were saved correctly
            if (response.get('pass_threshold') == 70 and
                response.get('critical_threshold') == 85):
                print(f"   ✅ Custom thresholds saved correctly:")
                print(f"      - pass_threshold: {response.get('pass_threshold')}% (minimum to pass)")
                print(f"      - critical_threshold: {response.get('critical_threshold')}% (minimum for auto-processing)")
                print(f"   ✅ Threshold ranges configured:")
                print(f"      - 0-69%: Rejected (qa_failed)")
                print(f"      - 70-84%: Manual review (needs_review)")
                print(f"      - 85-100%: Auto-approved (qa_passed → processing)")
                return True
            else:
                print(f"❌ Thresholds not saved correctly: pass={response.get('pass_threshold')}, critical={response.get('critical_threshold')}")
                return False
        return False

    def test_edit_qa_agent_thresholds_critical(self):
        """CRITICAL TEST: Edit QA agent thresholds"""
        if not self.qa_agent_id:
            print("❌ No QA agent ID available for threshold edit test")
            return False
        
        # Update thresholds to different values
        update_data = {
            "name": f"Updated Critical QA Agent {datetime.now().strftime('%H%M%S')}",
            "description": "QA agent with updated threshold configuration for critical testing",
            "qa_instructions": "Updated quality checks with modified scoring thresholds for comprehensive document analysis.",
            "project_ids": [self.project_id] if self.project_id else [],
            "is_universal": True,  # Change to universal
            "auto_process": True,
            "pass_threshold": 65,  # Changed from 70 to 65
            "critical_threshold": 80,  # Changed from 85 to 80
            "quality_checks": {
                "image_clarity": True,
                "document_orientation": True,
                "signature_detection": False,  # Disabled
                "seal_detection": False,  # Disabled
                "text_readability": True,
                "completeness_check": True
            }
        }
        
        success, response = self.run_test(
            "Edit QA Agent Thresholds (CRITICAL FIX)",
            "PUT",
            f"qa-agents/{self.qa_agent_id}",
            200,
            data=update_data
        )
        
        if success and isinstance(response, dict):
            # Verify updated thresholds
            if (response.get('pass_threshold') == 65 and
                response.get('critical_threshold') == 80 and
                response.get('is_universal') == True):
                print(f"   ✅ CRITICAL FIX VERIFIED: Thresholds updated successfully:")
                print(f"      - pass_threshold: {response.get('pass_threshold')}% (was 70%)")
                print(f"      - critical_threshold: {response.get('critical_threshold')}% (was 85%)")
                print(f"   ✅ Agent scope changed to universal: {response.get('is_universal')}")
                print(f"   ✅ Quality checks updated:")
                print(f"      - signature_detection: {response.get('quality_checks', {}).get('signature_detection')} (disabled)")
                print(f"      - seal_detection: {response.get('quality_checks', {}).get('seal_detection')} (disabled)")
                print(f"   ✅ New threshold ranges:")
                print(f"      - 0-64%: Rejected (qa_failed)")
                print(f"      - 65-79%: Manual review (needs_review)")
                print(f"      - 80-100%: Auto-approved (qa_passed → processing)")
                return True
            else:
                print(f"❌ Thresholds not updated correctly")
                return False
        return False

    def test_extreme_threshold_values(self):
        """Test extreme threshold values for validation"""
        extreme_qa_data = {
            "name": f"Extreme Threshold QA Agent {datetime.now().strftime('%H%M%S')}",
            "description": "QA agent with extreme threshold values for validation testing",
            "qa_instructions": "Test extreme threshold configurations with very high standards.",
            "project_ids": [],
            "is_universal": True,
            "auto_process": True,
            "pass_threshold": 90,  # Very high pass threshold
            "critical_threshold": 95,  # Very high critical threshold
            "quality_checks": {
                "image_clarity": True,
                "document_orientation": True,
                "signature_detection": True,
                "seal_detection": True,
                "text_readability": True,
                "completeness_check": True
            }
        }
        
        success, response = self.run_test(
            "Create QA Agent with Extreme Thresholds",
            "POST",
            "qa-agents",
            200,
            data=extreme_qa_data
        )
        
        if success and 'id' in response:
            extreme_qa_agent_id = response['id']
            print(f"   ✅ Created extreme threshold QA agent ID: {extreme_qa_agent_id}")
            
            # Verify extreme thresholds were accepted
            if (response.get('pass_threshold') == 90 and
                response.get('critical_threshold') == 95):
                print(f"   ✅ Extreme thresholds accepted and configured:")
                print(f"      - pass_threshold: 90% (very high standard)")
                print(f"      - critical_threshold: 95% (extremely high standard)")
                print(f"   ✅ Extreme threshold behavior:")
                print(f"      - 0-89%: Rejected (qa_failed)")
                print(f"      - 90-94%: Manual review (needs_review)")
                print(f"      - 95-100%: Auto-approved (qa_passed → processing)")
                
                # Clean up extreme agent
                cleanup_success, cleanup_response = self.run_test(
                    "Cleanup Extreme QA Agent",
                    "DELETE",
                    f"qa-agents/{extreme_qa_agent_id}",
                    200
                )
                return True
            else:
                print(f"❌ Extreme thresholds not saved correctly")
                return False
        return False

    def test_document_rename_with_special_characters(self):
        """Test document rename with special characters, spaces, and accents"""
        if not self.document_id:
            print("❌ No document ID available for special character rename test")
            return False
        
        # Test with special characters, spaces, and accents
        special_names = [
            "Documento con Espacios y Acentos.pdf",
            "Document_with-special@characters#2024.pdf",
            "Contrato Número 123 - Empresa López & Asociados.pdf"
        ]
        
        for i, special_name in enumerate(special_names):
            rename_data = {"new_name": special_name}
            
            success, response = self.run_test(
                f"Rename with Special Characters {i+1}",
                "PUT",
                f"documents/{self.document_id}/rename",
                200,
                data=rename_data
            )
            
            if success and isinstance(response, dict):
                if response.get('original_filename') == special_name:
                    print(f"   ✅ Special character rename successful: {special_name}")
                else:
                    print(f"❌ Special character rename failed: {special_name}")
                    return False
            else:
                return False
        
        print(f"   ✅ All special character renames successful")
        return True

    def cleanup_test_data(self):
        """Clean up test data"""
        print("\n🧹 Cleaning up test data...")
        
        # Delete QA agent
        if self.qa_agent_id:
            success, response = self.run_test(
                "Cleanup QA Agent",
                "DELETE",
                f"qa-agents/{self.qa_agent_id}",
                200
            )
        
        # Delete project (will also delete documents)
        if self.project_id:
            success, response = self.run_test(
                "Cleanup Project",
                "DELETE",
                f"projects/{self.project_id}",
                200
            )
        
        # Delete company
        if self.company_id:
            success, response = self.run_test(
                "Cleanup Company",
                "DELETE",
                f"companies/{self.company_id}",
                200
            )

def main():
    print("🧪 CRITICAL FIXES TESTING - Pergaminos API")
    print("Testing specific corrections from review request:")
    print("1. Document rename endpoint (JSON instead of FormData)")
    print("2. QA Agent threshold configuration improvements")
    print("=" * 80)
    
    tester = CriticalFixesTester()
    
    # Test sequence
    test_results = []
    
    # Login
    test_results.append(("Admin Login", tester.test_login()))
    if not tester.token:
        print("❌ Login failed, stopping tests")
        return 1
    
    # Setup test data
    test_results.append(("Setup Test Data", tester.setup_test_data()))
    
    # Wait for document processing
    print("\n⏳ Waiting for document processing...")
    time.sleep(5)
    
    # CRITICAL TESTS
    print("\n🔥 RUNNING CRITICAL FIXES TESTS...")
    test_results.append(("Document Rename with JSON (CRITICAL)", tester.test_document_rename_critical_fix()))
    test_results.append(("Create QA Agent Custom Thresholds (CRITICAL)", tester.test_create_qa_agent_with_custom_thresholds_critical()))
    test_results.append(("Edit QA Agent Thresholds (CRITICAL)", tester.test_edit_qa_agent_thresholds_critical()))
    test_results.append(("Extreme Threshold Values", tester.test_extreme_threshold_values()))
    test_results.append(("Document Rename Special Characters", tester.test_document_rename_with_special_characters()))
    
    # Cleanup
    tester.cleanup_test_data()
    
    # Print results
    print("\n" + "=" * 80)
    print("📊 CRITICAL FIXES TEST RESULTS")
    print("=" * 80)
    
    passed_tests = []
    failed_tests = []
    
    for test_name, result in test_results:
        if result:
            passed_tests.append(test_name)
            print(f"✅ {test_name}")
        else:
            failed_tests.append(test_name)
            print(f"❌ {test_name}")
    
    print(f"\n📈 SUMMARY: {len(passed_tests)}/{len(test_results)} tests passed")
    
    if failed_tests:
        print(f"\n❌ FAILED CRITICAL TESTS:")
        for test in failed_tests:
            print(f"   - {test}")
        print(f"\n⚠️  CRITICAL FIXES NEED ATTENTION!")
    else:
        print(f"\n🎉 ALL CRITICAL FIXES WORKING CORRECTLY!")
        print(f"✅ Document rename endpoint accepts JSON")
        print(f"✅ QA Agent threshold configuration is functional")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
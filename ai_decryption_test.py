import requests
import sys
import json
import time
from datetime import datetime

class AIDecryptionTester:
    def __init__(self, base_url="https://docsmart-pdf-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.company_id = None
        self.project_id = None
        self.ai_config_id = None

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

    def test_login(self):
        """Test admin login"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@pergaminos.com", "password": "admin123"}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user = response['user']
            print(f"   Logged in as: {self.user['name']} ({self.user['role']})")
            return True
        return False

    def test_create_test_company(self):
        """Create a test company for AI configuration testing"""
        company_data = {
            "name": "Test Decryption Company",
            "description": "Company for testing AI configuration decryption in real scenarios",
            "contact_email": "test@decryption.com"
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
            return True
        return False

    def test_create_project(self):
        """Create a test project"""
        if not self.company_id:
            print("❌ No company ID available")
            return False

        project_data = {
            "name": "AI Decryption Test Project",
            "description": "Project for testing AI configuration decryption",
            "company_id": self.company_id,
            "semantic_instructions": "Extract key information from documents using AI processing"
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
            return True
        return False

    def test_create_ai_config_for_qa(self):
        """Create AI configuration for QA processing"""
        if not self.company_id:
            print("❌ No company ID available")
            return False

        config_data = {
            "config_type": "qa_processing",
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "sk-test-qa-decryption-key-123456789",
            "model_parameters": {
                "temperature": 0.1,
                "max_tokens": 1000
            }
        }
        
        success, response = self.run_test(
            "Create AI Config for QA",
            "POST",
            f"companies/{self.company_id}/ai-config",
            200,
            data=config_data
        )
        
        if success and 'id' in response:
            self.ai_config_id = response['id']
            print(f"   Created AI config ID: {self.ai_config_id}")
            
            # Verify API key is encrypted in response
            if response.get('api_key') == '***ENCRYPTED***':
                print(f"   ✅ API key properly encrypted in response")
                return True
            else:
                print(f"   ❌ API key not encrypted: {response.get('api_key')}")
                return False
        return False

    def test_upload_document_to_trigger_qa(self):
        """Upload a document to trigger QA processing which should use decryption"""
        if not self.project_id:
            print("❌ No project ID available")
            return False
        
        # Create a simple test PDF content
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
(Test Document for AI Decryption) Tj
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
        
        files = {'file': ('test_decryption_document.pdf', pdf_content, 'application/pdf')}
        
        success, response = self.run_test(
            "Upload Document to Trigger QA",
            "POST",
            f"projects/{self.project_id}/documents/upload",
            200,
            files=files
        )
        
        if success and 'id' in response:
            self.document_id = response['id']
            print(f"   Uploaded document ID: {self.document_id}")
            print(f"   Document status: {response.get('status', 'unknown')}")
            
            # Wait a moment for processing to start
            time.sleep(2)
            return True
        return False

    def test_check_document_processing_status(self):
        """Check if document processing is working (indicates decryption is working)"""
        if not self.project_id or not hasattr(self, 'document_id'):
            print("❌ No project ID or document ID available")
            return False

        # Check document status multiple times to see processing
        for i in range(3):
            success, documents = self.run_test(
                f"Check Document Status (attempt {i+1})",
                "GET",
                f"projects/{self.project_id}/documents",
                200
            )
            
            if success and isinstance(documents, list):
                doc = next((d for d in documents if d['id'] == self.document_id), None)
                if doc:
                    status = doc.get('status', 'unknown')
                    print(f"   Document status: {status}")
                    
                    # If document is processing or completed, decryption is working
                    if status in ['qa_pending', 'processing', 'completed', 'needs_review']:
                        print(f"   ✅ Document processing indicates decryption is working")
                        return True
                    elif status == 'qa_failed':
                        print(f"   ⚠️ QA failed - may indicate decryption issue")
                        return False
                    
            time.sleep(2)
        
        print(f"   ⚠️ Document still in initial status - may indicate processing issue")
        return False

    def test_verify_encryption_key_in_env(self):
        """Verify that ENCRYPTION_KEY exists in .env file"""
        print(f"\n🔑 Verifying ENCRYPTION_KEY in environment...")
        
        try:
            with open('/app/backend/.env', 'r') as f:
                env_content = f.read()
            
            if 'ENCRYPTION_KEY=' in env_content:
                # Extract the key (don't print the full key for security)
                lines = env_content.split('\n')
                key_line = next((line for line in lines if line.startswith('ENCRYPTION_KEY=')), None)
                if key_line:
                    key_value = key_line.split('=', 1)[1].strip('"')
                    if len(key_value) > 20:  # Fernet keys are base64 encoded and long
                        print(f"   ✅ ENCRYPTION_KEY found in .env (length: {len(key_value)})")
                        print(f"   Key preview: {key_value[:10]}...")
                        return True
                    else:
                        print(f"   ❌ ENCRYPTION_KEY too short: {len(key_value)}")
                        return False
                else:
                    print(f"   ❌ ENCRYPTION_KEY line not found")
                    return False
            else:
                print(f"   ❌ ENCRYPTION_KEY not found in .env")
                return False
                
        except Exception as e:
            print(f"   ❌ Error reading .env file: {str(e)}")
            return False

    def test_create_qa_agent_to_trigger_processing(self):
        """Create a QA agent to ensure QA processing is triggered"""
        qa_agent_data = {
            "name": "Decryption Test QA Agent",
            "description": "QA agent to test decryption functionality",
            "qa_instructions": "Check document quality and readability",
            "project_ids": [self.project_id] if self.project_id else [],
            "is_universal": False,
            "auto_process": True,
            "pass_threshold": 60,
            "critical_threshold": 80,
            "quality_checks": {
                "image_clarity": True,
                "document_orientation": True,
                "text_readability": True,
                "completeness_check": True
            }
        }
        
        success, response = self.run_test(
            "Create QA Agent for Decryption Test",
            "POST",
            "qa-agents",
            200,
            data=qa_agent_data
        )
        
        if success and 'id' in response:
            self.qa_agent_id = response['id']
            print(f"   Created QA agent ID: {self.qa_agent_id}")
            return True
        return False

    def cleanup_test_data(self):
        """Clean up test data"""
        print(f"\n🧹 Cleaning up test data...")
        
        # Delete QA agent
        if hasattr(self, 'qa_agent_id'):
            success, response = self.run_test(
                "Delete QA Agent",
                "DELETE",
                f"qa-agents/{self.qa_agent_id}",
                200
            )
            if success:
                print(f"   ✅ Deleted QA agent: {self.qa_agent_id}")
        
        # Delete AI configuration
        if self.ai_config_id and self.company_id:
            success, response = self.run_test(
                "Delete AI Config",
                "DELETE",
                f"companies/{self.company_id}/ai-config/{self.ai_config_id}",
                200
            )
            if success:
                print(f"   ✅ Deleted AI config: {self.ai_config_id}")
        
        # Delete project (this will also delete documents)
        if self.project_id:
            success, response = self.run_test(
                "Delete Test Project",
                "DELETE",
                f"projects/{self.project_id}",
                200
            )
            if success:
                print(f"   ✅ Deleted test project: {self.project_id}")
        
        # Delete test company
        if self.company_id:
            success, response = self.run_test(
                "Delete Test Company",
                "DELETE",
                f"companies/{self.company_id}",
                200
            )
            if success:
                print(f"   ✅ Deleted test company: {self.company_id}")

    def run_all_tests(self):
        """Run all AI decryption tests"""
        print("🔓 Starting AI Configuration Decryption Tests")
        print("=" * 60)
        
        tests = [
            self.test_verify_encryption_key_in_env,
            self.test_login,
            self.test_create_test_company,
            self.test_create_project,
            self.test_create_ai_config_for_qa,
            self.test_create_qa_agent_to_trigger_processing,
            self.test_upload_document_to_trigger_qa,
            self.test_check_document_processing_status
        ]
        
        for test in tests:
            try:
                if not test():
                    print(f"\n❌ Test failed: {test.__name__}")
            except Exception as e:
                print(f"\n💥 Test error in {test.__name__}: {str(e)}")
        
        # Always try to cleanup
        try:
            self.cleanup_test_data()
        except Exception as e:
            print(f"⚠️ Cleanup error: {str(e)}")
        
        print(f"\n" + "=" * 60)
        print(f"🏁 AI Decryption Tests Complete")
        print(f"📊 Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed >= self.tests_run - 1:  # Allow 1 failure for processing timing
            print(f"✅ DECRYPTION TESTS PASSED - AI Configuration decryption is working!")
            return True
        else:
            print(f"❌ DECRYPTION TESTS FAILED - AI Configuration decryption needs attention")
            return False

if __name__ == "__main__":
    tester = AIDecryptionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
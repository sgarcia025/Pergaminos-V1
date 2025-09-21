import requests
import sys
import json
from datetime import datetime
import time

class PergaminosAPITester:
    def __init__(self, base_url="https://aipaperflow-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.company_id = None
        self.project_id = None
        self.reorder_task_id = None

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

    def test_init_admin(self):
        """Initialize admin user"""
        print("\n🚀 Initializing admin user...")
        success, response = self.run_test(
            "Initialize Admin User",
            "POST",
            "init/admin",
            200
        )
        return success

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

    def test_auth_me(self):
        """Test getting current user info"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_create_company(self):
        """Test creating a company"""
        company_data = {
            "name": f"Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "A test company for API testing",
            "contact_email": "test@company.com",
            "contact_phone": "+1234567890",
            "address": "123 Test Street, Test City"
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

    def test_get_companies(self):
        """Test getting companies list"""
        success, response = self.run_test(
            "Get Companies",
            "GET",
            "companies",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} companies")
            return True
        return False

    def test_get_company_detail(self):
        """Test getting specific company details"""
        if not self.company_id:
            print("❌ No company ID available for detail test")
            return False
            
        success, response = self.run_test(
            "Get Company Detail",
            "GET",
            f"companies/{self.company_id}",
            200
        )
        return success

    def test_create_project(self):
        """Test creating a project"""
        if not self.company_id:
            print("❌ No company ID available for project creation")
            return False
            
        project_data = {
            "name": f"Test Project {datetime.now().strftime('%H%M%S')}",
            "description": "A test project for document processing",
            "company_id": self.company_id,
            "semantic_instructions": "Extract all invoice details including date, amount, vendor name, and line items. Focus on financial data and payment terms."
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

    def test_get_projects(self):
        """Test getting projects list"""
        success, response = self.run_test(
            "Get Projects",
            "GET",
            "projects",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} projects")
            return True
        return False

    def test_get_project_detail(self):
        """Test getting specific project details"""
        if not self.project_id:
            print("❌ No project ID available for detail test")
            return False
            
        success, response = self.run_test(
            "Get Project Detail",
            "GET",
            f"projects/{self.project_id}",
            200
        )
        return success

    def test_get_project_documents(self):
        """Test getting project documents"""
        if not self.project_id:
            print("❌ No project ID available for documents test")
            return False
            
        success, response = self.run_test(
            "Get Project Documents",
            "GET",
            f"projects/{self.project_id}/documents",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} documents")
            return True
        return False

    def test_document_upload(self):
        """Test document upload (simulated PDF)"""
        if not self.project_id:
            print("❌ No project ID available for document upload")
            return False
        
        # Create a simple test PDF content (minimal PDF structure)
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
(Test Document) Tj
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
        
        files = {'file': ('test_document.pdf', pdf_content, 'application/pdf')}
        
        success, response = self.run_test(
            "Upload Document",
            "POST",
            f"projects/{self.project_id}/documents/upload",
            200,
            files=files
        )
        
        if success and 'id' in response:
            print(f"   Uploaded document ID: {response['id']}")
            print(f"   Document status: {response.get('status', 'unknown')}")
            return True
        return False

    def test_dashboard_stats(self):
        """Test dashboard statistics"""
        success, response = self.run_test(
            "Get Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        if success and isinstance(response, dict):
            print(f"   Stats: {json.dumps(response, indent=2)}")
            return True
        return False

    def test_document_rename(self):
        """Test document renaming functionality"""
        if not self.project_id:
            print("❌ No project ID available for document rename test")
            return False
        
        # First get documents to find one to rename
        success, documents = self.run_test(
            "Get Documents for Rename",
            "GET",
            f"projects/{self.project_id}/documents",
            200
        )
        
        if not success or not documents:
            print("❌ No documents found for rename test")
            return False
        
        document_id = documents[0]['id']
        original_name = documents[0]['original_filename']
        new_name = f"Renamed_{datetime.now().strftime('%H%M%S')}.pdf"
        
        # Test renaming with form data
        import requests
        url = f"{self.api_url}/documents/{document_id}/rename"
        headers = {'Authorization': f'Bearer {self.token}'}
        data = {'new_name': new_name}
        
        print(f"\n🔍 Testing Document Rename...")
        print(f"   URL: {url}")
        print(f"   Original name: {original_name}")
        print(f"   New name: {new_name}")
        
        try:
            response = requests.put(url, headers=headers, data=data)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                result = response.json()
                if result.get('original_filename') == new_name:
                    print(f"   Document successfully renamed to: {new_name}")
                    return True
                else:
                    print(f"❌ Name not updated correctly: {result.get('original_filename')}")
                    return False
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False
        finally:
            self.tests_run += 1

    def test_document_reorder_start(self):
        """Test starting AI document reordering"""
        if not self.project_id:
            print("❌ No project ID available for reorder test")
            return False
        
        # Check if we have completed documents
        success, documents = self.run_test(
            "Get Documents for Reorder",
            "GET",
            f"projects/{self.project_id}/documents",
            200
        )
        
        if not success or not documents:
            print("❌ No documents found for reorder test")
            return False
        
        completed_docs = [doc for doc in documents if doc.get('status') == 'completed']
        if len(completed_docs) < 1:
            print("❌ No completed documents found for reorder test")
            return False
        
        # Test reordering with form data
        import requests
        url = f"{self.api_url}/projects/{self.project_id}/documents/reorder"
        headers = {'Authorization': f'Bearer {self.token}'}
        data = {'semantic_instructions': 'Order documents chronologically with descriptive names based on content'}
        
        print(f"\n🔍 Testing Document Reorder Start...")
        print(f"   URL: {url}")
        print(f"   Documents to reorder: {len(completed_docs)}")
        
        try:
            response = requests.post(url, headers=headers, data=data)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                result = response.json()
                if 'task_id' in result:
                    print(f"   Reorder task started with ID: {result['task_id']}")
                    self.reorder_task_id = result['task_id']
                    return True
                else:
                    print(f"❌ No task_id in response: {result}")
                    return False
            else:
                print(f"❌ Failed - Expected 200, got {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False
        finally:
            self.tests_run += 1

    def test_document_reorder_status(self):
        """Test checking AI document reordering status"""
        if not self.project_id or not hasattr(self, 'reorder_task_id'):
            print("❌ No project ID or task ID available for reorder status test")
            return False
        
        success, response = self.run_test(
            "Get Reorder Status",
            "GET",
            f"projects/{self.project_id}/reorder-status/{self.reorder_task_id}",
            200
        )
        
        if success and isinstance(response, dict):
            status = response.get('status', 'unknown')
            progress = response.get('progress', 0)
            print(f"   Reorder status: {status} ({progress}%)")
            
            # If processing, wait a bit and check again
            if status == 'processing':
                print("   Waiting for AI processing to complete...")
                time.sleep(5)
                
                success2, response2 = self.run_test(
                    "Get Reorder Status (2nd check)",
                    "GET",
                    f"projects/{self.project_id}/reorder-status/{self.reorder_task_id}",
                    200
                )
                
                if success2:
                    status2 = response2.get('status', 'unknown')
                    progress2 = response2.get('progress', 0)
                    print(f"   Updated status: {status2} ({progress2}%)")
            
            return True
        return False

    def test_invalid_login(self):
        """Test login with invalid credentials"""
        success, response = self.run_test(
            "Invalid Login Test",
            "POST",
            "auth/login",
            401,
            data={"email": "invalid@test.com", "password": "wrongpassword"}
        )
        return success

    def test_unauthorized_access(self):
        """Test accessing protected endpoint without token"""
        # Temporarily remove token
        temp_token = self.token
        self.token = None
        
        success, response = self.run_test(
            "Unauthorized Access Test",
            "GET",
            "companies",
            401
        )
        
        # Restore token
        self.token = temp_token
        return success

def main():
    print("🧪 Starting Pergaminos API Testing Suite")
    print("=" * 50)
    
    tester = PergaminosAPITester()
    
    # Test sequence
    test_results = []
    
    # Initialize admin user
    test_results.append(("Initialize Admin", tester.test_init_admin()))
    
    # Authentication tests
    test_results.append(("Admin Login", tester.test_login()))
    if not tester.token:
        print("❌ Login failed, stopping tests")
        return 1
    
    test_results.append(("Get Current User", tester.test_auth_me()))
    test_results.append(("Invalid Login", tester.test_invalid_login()))
    test_results.append(("Unauthorized Access", tester.test_unauthorized_access()))
    
    # Company management tests
    test_results.append(("Create Company", tester.test_create_company()))
    test_results.append(("Get Companies", tester.test_get_companies()))
    test_results.append(("Get Company Detail", tester.test_get_company_detail()))
    
    # Project management tests
    test_results.append(("Create Project", tester.test_create_project()))
    test_results.append(("Get Projects", tester.test_get_projects()))
    test_results.append(("Get Project Detail", tester.test_get_project_detail()))
    test_results.append(("Get Project Documents", tester.test_get_project_documents()))
    
    # Document upload test
    test_results.append(("Upload Document", tester.test_document_upload()))
    
    # Dashboard stats test
    test_results.append(("Dashboard Stats", tester.test_dashboard_stats()))
    
    # Print final results
    print("\n" + "=" * 50)
    print("📊 FINAL TEST RESULTS")
    print("=" * 50)
    
    passed_tests = []
    failed_tests = []
    
    for test_name, result in test_results:
        if result:
            passed_tests.append(test_name)
            print(f"✅ {test_name}")
        else:
            failed_tests.append(test_name)
            print(f"❌ {test_name}")
    
    print(f"\n📈 Summary: {len(passed_tests)}/{len(test_results)} tests passed")
    
    if failed_tests:
        print(f"\n❌ Failed tests:")
        for test in failed_tests:
            print(f"   - {test}")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
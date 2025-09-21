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
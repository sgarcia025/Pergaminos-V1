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

    # NEW FEATURE TESTS - QA Agents
    def test_create_qa_agent(self):
        """Test creating a QA agent"""
        qa_agent_data = {
            "name": f"Test QA Agent {datetime.now().strftime('%H%M%S')}",
            "description": "A test QA agent for document quality checks",
            "qa_instructions": "Check document clarity, orientation, and completeness. Verify all text is readable and signatures are present.",
            "project_ids": [self.project_id] if self.project_id else [],
            "is_universal": False,
            "quality_checks": {
                "image_clarity": True,
                "document_orientation": True,
                "signature_detection": True,
                "seal_detection": False,
                "text_readability": True,
                "completeness_check": True
            }
        }
        
        success, response = self.run_test(
            "Create QA Agent",
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

    def test_get_qa_agents(self):
        """Test getting QA agents list"""
        success, response = self.run_test(
            "Get QA Agents",
            "GET",
            "qa-agents",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} QA agents")
            return True
        return False

    def test_run_qa_agent(self):
        """Test running a QA agent"""
        if not hasattr(self, 'qa_agent_id'):
            print("❌ No QA agent ID available for run test")
            return False
        
        success, response = self.run_test(
            "Run QA Agent",
            "POST",
            f"qa-agents/{self.qa_agent_id}/run",
            200
        )
        
        if success and 'task_id' in response:
            print(f"   QA check started with task ID: {response['task_id']}")
            return True
        return False

    # NEW FEATURE TESTS - User Management
    def test_create_client_user(self):
        """Test creating a client user"""
        if not self.company_id:
            print("❌ No company ID available for client user creation")
            return False
            
        client_user_data = {
            "email": f"testclient{datetime.now().strftime('%H%M%S')}@test.com",
            "name": "Test Client User",
            "password": "testpass123",
            "role": "client",
            "company_id": self.company_id
        }
        
        success, response = self.run_test(
            "Create Client User",
            "POST",
            "auth/register",
            200,
            data=client_user_data
        )
        
        if success and 'id' in response:
            self.client_user_id = response['id']
            self.client_email = client_user_data['email']
            self.client_password = client_user_data['password']
            print(f"   Created client user ID: {self.client_user_id}")
            return True
        return False

    def test_get_users(self):
        """Test getting users list (staff only)"""
        success, response = self.run_test(
            "Get Users List",
            "GET",
            "users",
            200
        )
        if success and isinstance(response, list):
            print(f"   Found {len(response)} users")
            return True
        return False

    def test_toggle_user_status(self):
        """Test toggling user status"""
        if not hasattr(self, 'client_user_id'):
            print("❌ No client user ID available for status toggle test")
            return False
        
        # First disable user
        success, response = self.run_test(
            "Toggle User Status (Disable)",
            "PUT",
            f"users/{self.client_user_id}/toggle-status",
            200,
            data={"is_active": False}
        )
        
        if success:
            print(f"   User disabled successfully")
            
            # Then re-enable user for other tests
            success2, response2 = self.run_test(
                "Toggle User Status (Enable)",
                "PUT",
                f"users/{self.client_user_id}/toggle-status",
                200,
                data={"is_active": True}
            )
            
            if success2:
                print(f"   User re-enabled successfully")
                return True
        return False

    # NEW FEATURE TESTS - Document Processing (Enhanced)
    def test_process_documents_rename_reorder(self):
        """Test NEW enhanced document processing with individual rename/reorder"""
        if not self.project_id:
            print("❌ No project ID available for document processing test")
            return False
        
        # First get documents to create changes for
        success, documents = self.run_test(
            "Get Documents for Enhanced Processing",
            "GET",
            f"projects/{self.project_id}/documents",
            200
        )
        
        if not success or not documents:
            print("❌ No documents found for enhanced processing test")
            return False
        
        completed_docs = [doc for doc in documents if doc.get('status') == 'completed']
        if len(completed_docs) < 1:
            print("❌ No completed documents found for enhanced processing test")
            return False
        
        # Create document changes JSON
        document_changes = {}
        for i, doc in enumerate(completed_docs[:3]):  # Test with first 3 docs
            document_changes[doc['id']] = {
                "newName": f"Procesado_{i+1}_{doc['original_filename']}",
                "newOrder": i + 1,
                "currentName": doc['original_filename'],
                "currentOrder": doc.get('display_order', i + 1)
            }
        
        # Test NEW enhanced processing endpoint
        import requests
        url = f"{self.api_url}/projects/{self.project_id}/documents/process-rename-reorder"
        headers = {'Authorization': f'Bearer {self.token}'}
        data = {'document_changes': json.dumps(document_changes)}
        
        print(f"\n🔍 Testing NEW Enhanced Document Processing...")
        print(f"   URL: {url}")
        print(f"   Documents to process: {len(document_changes)}")
        
        try:
            response = requests.post(url, headers=headers, data=data)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                result = response.json()
                if 'task_id' in result:
                    print(f"   Enhanced processing task started with ID: {result['task_id']}")
                    self.enhanced_process_task_id = result['task_id']
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

    def test_process_documents_reorder(self):
        """Test document processing with reorder (legacy)"""
        if not self.project_id:
            print("❌ No project ID available for document processing test")
            return False
        
        # Test processing with form data
        import requests
        url = f"{self.api_url}/projects/{self.project_id}/documents/process-reorder"
        headers = {'Authorization': f'Bearer {self.token}'}
        data = {'semantic_instructions': 'Organize documents by importance and create a comprehensive summary'}
        
        print(f"\n🔍 Testing Document Processing...")
        print(f"   URL: {url}")
        
        try:
            response = requests.post(url, headers=headers, data=data)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                result = response.json()
                if 'task_id' in result:
                    print(f"   Processing task started with ID: {result['task_id']}")
                    self.process_task_id = result['task_id']
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

    def test_get_process_status(self):
        """Test getting document processing status"""
        if not self.project_id or not hasattr(self, 'process_task_id'):
            print("❌ No project ID or process task ID available")
            return False
        
        success, response = self.run_test(
            "Get Process Status",
            "GET",
            f"projects/{self.project_id}/process-status/{self.process_task_id}",
            200
        )
        
        if success and isinstance(response, dict):
            status = response.get('status', 'unknown')
            progress = response.get('progress', 0)
            print(f"   Process status: {status} ({progress}%)")
            return True
        return False

    # NEW FEATURE TESTS - Client AI Questions
    def test_client_login(self):
        """Test client user login"""
        if not hasattr(self, 'client_email'):
            print("❌ No client credentials available for login test")
            return False
        
        # Save admin token
        admin_token = self.token
        
        success, response = self.run_test(
            "Client Login",
            "POST",
            "auth/login",
            200,
            data={"email": self.client_email, "password": self.client_password}
        )
        
        if success and 'access_token' in response:
            self.client_token = response['access_token']
            print(f"   Client logged in successfully")
            
            # Restore admin token for other tests
            self.token = admin_token
            return True
        return False

    def test_ask_ai_about_documents(self):
        """Test AI questions about documents (client feature)"""
        # Use existing client credentials to test AI questions
        success, response = self.run_test(
            "Existing Client Login for AI Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success or 'access_token' not in response:
            print("❌ Could not login existing client for AI test")
            return False
        
        # Save admin token and use client token
        admin_token = self.token
        self.token = response['access_token']
        client_user = response['user']
        
        # Get client's projects to find one with documents
        success_projects, projects = self.run_test(
            "Get Client Projects",
            "GET",
            "projects",
            200
        )
        
        if not success_projects or not projects:
            print("❌ No projects found for client")
            self.token = admin_token
            return False
        
        # Find a project with documents
        test_project_id = None
        for project in projects:
            success_docs, documents = self.run_test(
                "Get Project Documents for AI Test",
                "GET",
                f"projects/{project['id']}/documents",
                200
            )
            if success_docs and documents:
                # Check if any documents have extracted data
                completed_docs = [doc for doc in documents if doc.get('status') == 'completed' and doc.get('extracted_data')]
                if completed_docs:
                    test_project_id = project['id']
                    break
        
        if not test_project_id:
            print("❌ No project with processed documents found for AI test")
            self.token = admin_token
            return False
        
        ai_question_data = {
            "question": "What are the main topics covered in the uploaded documents?",
            "include_context": True
        }
        
        success, response = self.run_test(
            "Ask AI About Documents",
            "POST",
            f"projects/{test_project_id}/ask-ai",
            200,
            data=ai_question_data
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success and isinstance(response, dict):
            if 'answer' in response:
                print(f"   AI answered: {response['answer'][:100]}...")
                print(f"   Sources consulted: {response.get('sources', [])}")
                return True
        return False

    # EXISTING CREDENTIAL TESTS
    def test_existing_admin_login(self):
        """Test login with existing admin credentials"""
        success, response = self.run_test(
            "Existing Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": "admin@pergaminos.com", "password": "admin123"}
        )
        if success and 'access_token' in response:
            print(f"   Existing admin login successful")
            return True
        return False

    def test_existing_client_login(self):
        """Test login with existing client credentials"""
        success, response = self.run_test(
            "Existing Client Login",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        if success and 'access_token' in response:
            print(f"   Existing client login successful")
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
    print("🧪 Starting Comprehensive Pergaminos API Testing Suite")
    print("🔍 Testing ALL NEW FEATURES: QA Agents, User Management, Document Processing, Client Portal")
    print("=" * 80)
    
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
    
    # Test existing credentials
    test_results.append(("Existing Admin Login", tester.test_existing_admin_login()))
    test_results.append(("Existing Client Login", tester.test_existing_client_login()))
    
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
    
    # Wait a bit for document processing
    print("\n⏳ Waiting for document processing...")
    time.sleep(10)
    
    # Document management tests
    test_results.append(("Document Rename", tester.test_document_rename()))
    test_results.append(("Document Reorder Start", tester.test_document_reorder_start()))
    test_results.append(("Document Reorder Status", tester.test_document_reorder_status()))
    
    # NEW FEATURE TESTS - QA Agents Module
    print("\n🔍 Testing QA Agents Module...")
    test_results.append(("Create QA Agent", tester.test_create_qa_agent()))
    test_results.append(("Get QA Agents", tester.test_get_qa_agents()))
    test_results.append(("Run QA Agent", tester.test_run_qa_agent()))
    
    # NEW FEATURE TESTS - User Management Module
    print("\n🔍 Testing User Management Module...")
    test_results.append(("Create Client User", tester.test_create_client_user()))
    test_results.append(("Get Users List", tester.test_get_users()))
    test_results.append(("Toggle User Status", tester.test_toggle_user_status()))
    test_results.append(("Client Login", tester.test_client_login()))
    
    # NEW FEATURE TESTS - Document Processing Module
    print("\n🔍 Testing Document Processing Module...")
    test_results.append(("Process Documents Reorder", tester.test_process_documents_reorder()))
    test_results.append(("Get Process Status", tester.test_get_process_status()))
    
    # NEW FEATURE TESTS - Client Portal AI Questions
    print("\n🔍 Testing Client Portal AI Questions...")
    test_results.append(("Ask AI About Documents", tester.test_ask_ai_about_documents()))
    
    # Dashboard stats test
    test_results.append(("Dashboard Stats", tester.test_dashboard_stats()))
    
    # Print final results
    print("\n" + "=" * 80)
    print("📊 COMPREHENSIVE TEST RESULTS - ALL NEW PERGAMINOS FEATURES")
    print("=" * 80)
    
    passed_tests = []
    failed_tests = []
    
    # Group results by category
    categories = {
        "Authentication & Security": ["Initialize Admin", "Admin Login", "Get Current User", "Invalid Login", "Unauthorized Access", "Existing Admin Login", "Existing Client Login"],
        "Company Management": ["Create Company", "Get Companies", "Get Company Detail"],
        "Project Management": ["Create Project", "Get Projects", "Get Project Detail", "Get Project Documents"],
        "Document Management": ["Upload Document", "Document Rename", "Document Reorder Start", "Document Reorder Status"],
        "QA Agents Module (NEW)": ["Create QA Agent", "Get QA Agents", "Run QA Agent"],
        "User Management Module (NEW)": ["Create Client User", "Get Users List", "Toggle User Status", "Client Login"],
        "Document Processing Module (NEW)": ["Process Documents Reorder", "Get Process Status"],
        "Client Portal AI (NEW)": ["Ask AI About Documents"],
        "Dashboard": ["Dashboard Stats"]
    }
    
    for category, tests in categories.items():
        print(f"\n📋 {category}:")
        category_passed = 0
        category_total = 0
        
        for test_name, result in test_results:
            if test_name in tests:
                category_total += 1
                if result:
                    passed_tests.append(test_name)
                    print(f"   ✅ {test_name}")
                    category_passed += 1
                else:
                    failed_tests.append(test_name)
                    print(f"   ❌ {test_name}")
        
        if category_total > 0:
            print(f"   📊 {category_passed}/{category_total} passed")
    
    print(f"\n📈 OVERALL SUMMARY: {len(passed_tests)}/{len(test_results)} tests passed")
    
    if failed_tests:
        print(f"\n❌ FAILED TESTS REQUIRING ATTENTION:")
        for test in failed_tests:
            print(f"   - {test}")
    else:
        print(f"\n🎉 ALL TESTS PASSED! All new Pergaminos features are working correctly.")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
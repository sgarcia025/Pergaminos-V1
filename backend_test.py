import requests
import sys
import json
from datetime import datetime
import time

class PergaminosAPITester:
    def __init__(self, base_url="https://digitaldocs.preview.emergentagent.com"):
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

    def test_get_enhanced_process_status(self):
        """Test getting enhanced document processing status"""
        if not self.project_id or not hasattr(self, 'enhanced_process_task_id'):
            print("❌ No project ID or enhanced process task ID available")
            return False
        
        success, response = self.run_test(
            "Get Enhanced Process Status",
            "GET",
            f"projects/{self.project_id}/process-status/{self.enhanced_process_task_id}",
            200
        )
        
        if success and isinstance(response, dict):
            status = response.get('status', 'unknown')
            progress = response.get('progress', 0)
            download_url = response.get('download_url', None)
            print(f"   Enhanced process status: {status} ({progress}%)")
            if download_url:
                print(f"   Download URL available: {download_url}")
                self.enhanced_download_url = download_url
            return True
        return False

    def test_download_processed_pdf(self):
        """Test downloading processed PDF"""
        if not self.project_id or not hasattr(self, 'enhanced_process_task_id'):
            print("❌ No project ID or enhanced process task ID available for download test")
            return False
        
        # Test the download endpoint
        success, response = self.run_test(
            "Download Processed PDF",
            "GET",
            f"projects/{self.project_id}/download-processed/{self.enhanced_process_task_id}",
            200
        )
        
        if success:
            print(f"   PDF download successful")
            return True
        return False

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

    # NEW FEATURE TESTS - DELETE ENDPOINTS (Staff Only)
    def test_delete_company_without_projects(self):
        """Test deleting a company without projects (should work)"""
        # Create a new company specifically for deletion test
        company_data = {
            "name": f"Delete Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "A company created specifically for deletion testing",
            "contact_email": "delete@test.com"
        }
        
        success, response = self.run_test(
            "Create Company for Deletion",
            "POST",
            "companies",
            200,
            data=company_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create company for deletion test")
            return False
        
        delete_company_id = response['id']
        print(f"   Created company for deletion: {delete_company_id}")
        
        # Now delete the company (should work since no projects/users)
        success, response = self.run_test(
            "Delete Company Without Projects",
            "DELETE",
            f"companies/{delete_company_id}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('message') and 'deleted successfully' in response.get('message', ''):
                print(f"   Company deleted successfully: {delete_company_id}")
                return True
        return False

    def test_delete_company_with_projects_should_fail(self):
        """Test deleting a company with projects (should fail)"""
        if not self.company_id:
            print("❌ No company ID available for deletion test")
            return False
        
        # Try to delete company that has projects (should fail)
        success, response = self.run_test(
            "Delete Company With Projects (Should Fail)",
            "DELETE",
            f"companies/{self.company_id}",
            400  # Should return 400 Bad Request
        )
        
        if success:
            print(f"   Correctly prevented deletion of company with projects")
            return True
        return False

    def test_delete_project_with_documents(self):
        """Test deleting a project with documents (should work and clean up)"""
        if not self.project_id:
            print("❌ No project ID available for deletion test")
            return False
        
        # First check how many documents exist
        success_docs, documents = self.run_test(
            "Get Documents Before Project Deletion",
            "GET",
            f"projects/{self.project_id}/documents",
            200
        )
        
        doc_count = len(documents) if success_docs and documents else 0
        print(f"   Project has {doc_count} documents before deletion")
        
        # Delete the project (should work and clean up documents)
        success, response = self.run_test(
            "Delete Project With Documents",
            "DELETE",
            f"projects/{self.project_id}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('message') and 'deleted successfully' in response.get('message', ''):
                deleted_docs = response.get('deleted_documents', 0)
                print(f"   Project deleted successfully with {deleted_docs} documents cleaned up")
                # Clear project_id since it's been deleted
                self.project_id = None
                return True
        return False

    def test_client_cannot_delete_company(self):
        """Test that client users cannot delete companies"""
        # Create a test company first
        company_data = {
            "name": f"Client Delete Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "Company for testing client deletion permissions"
        }
        
        success, response = self.run_test(
            "Create Company for Client Delete Test",
            "POST",
            "companies",
            200,
            data=company_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create company for client delete test")
            return False
        
        test_company_id = response['id']
        
        # Login as client user
        admin_token = self.token
        success_login, login_response = self.run_test(
            "Client Login for Delete Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for delete test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        # Try to delete company as client (should fail with 403)
        success, response = self.run_test(
            "Client Delete Company (Should Fail)",
            "DELETE",
            f"companies/{test_company_id}",
            403  # Should return 403 Forbidden
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from deleting company")
            
            # Clean up: delete the test company as admin
            cleanup_success, cleanup_response = self.run_test(
                "Cleanup Test Company",
                "DELETE",
                f"companies/{test_company_id}",
                200
            )
            return True
        return False

    def test_client_cannot_delete_project(self):
        """Test that client users cannot delete projects"""
        # Create a test project first
        if not self.company_id:
            print("❌ No company ID available for client project delete test")
            return False
        
        project_data = {
            "name": f"Client Delete Test Project {datetime.now().strftime('%H%M%S')}",
            "description": "Project for testing client deletion permissions",
            "company_id": self.company_id
        }
        
        success, response = self.run_test(
            "Create Project for Client Delete Test",
            "POST",
            "projects",
            200,
            data=project_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create project for client delete test")
            return False
        
        test_project_id = response['id']
        
        # Login as client user
        admin_token = self.token
        success_login, login_response = self.run_test(
            "Client Login for Project Delete Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for project delete test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        # Try to delete project as client (should fail with 403)
        success, response = self.run_test(
            "Client Delete Project (Should Fail)",
            "DELETE",
            f"projects/{test_project_id}",
            403  # Should return 403 Forbidden
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from deleting project")
            
            # Clean up: delete the test project as admin
            cleanup_success, cleanup_response = self.run_test(
                "Cleanup Test Project",
                "DELETE",
                f"projects/{test_project_id}",
                200
            )
            return True
        return False

    def test_delete_nonexistent_company(self):
        """Test deleting a non-existent company (should return 404)"""
        fake_company_id = "nonexistent-company-id-12345"
        
        success, response = self.run_test(
            "Delete Non-existent Company",
            "DELETE",
            f"companies/{fake_company_id}",
            404  # Should return 404 Not Found
        )
        
        if success:
            print(f"   Correctly returned 404 for non-existent company")
            return True
        return False

    def test_delete_nonexistent_project(self):
        """Test deleting a non-existent project (should return 404)"""
        fake_project_id = "nonexistent-project-id-12345"
        
        success, response = self.run_test(
            "Delete Non-existent Project",
            "DELETE",
            f"projects/{fake_project_id}",
            404  # Should return 404 Not Found
        )
        
        if success:
            print(f"   Correctly returned 404 for non-existent project")
            return True
        return False

    # PHASE 1 NEW FEATURE TESTS - User Deletion
    def test_create_asesor_user(self):
        """Test creating an asesor user for testing"""
        asesor_user_data = {
            "email": f"asesor{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "Test Asesor Comercial",
            "password": "asesor123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create Asesor User",
            "POST",
            "auth/register",
            200,
            data=asesor_user_data
        )
        
        if success and 'id' in response:
            self.asesor_user_id = response['id']
            self.asesor_email = asesor_user_data['email']
            self.asesor_password = asesor_user_data['password']
            print(f"   Created asesor user ID: {self.asesor_user_id}")
            return True
        return False

    def test_delete_user_self_prevention(self):
        """Test that users cannot delete themselves"""
        success, response = self.run_test(
            "Delete Self (Should Fail)",
            "DELETE",
            f"users/{self.user['id']}",
            400  # Should return 400 Bad Request
        )
        
        if success:
            print(f"   Correctly prevented self-deletion")
            return True
        return False

    def test_delete_user_with_company_assignment(self):
        """Test deleting asesor assigned to companies (should fail)"""
        if not hasattr(self, 'asesor_user_id'):
            print("❌ No asesor user ID available for assignment test")
            return False
        
        # First create a company with this asesor assigned
        company_data = {
            "name": f"Asesor Test Company {datetime.now().strftime('%H%M%S')}",
            "razon_social": "Razón Social Test",
            "nit": "123456789-0",
            "contacto": "Juan Pérez",
            "telefono": "+57 300 123 4567",
            "direccion": "Calle 123 #45-67, Bogotá",
            "asesor_comercial_id": self.asesor_user_id,
            "segmento": "Tecnología",
            "estado": "Activo",
            "corporacion": "Grupo Empresarial Test"
        }
        
        success, response = self.run_test(
            "Create Company with Asesor Assignment",
            "POST",
            "companies",
            200,
            data=company_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create company with asesor assignment")
            return False
        
        self.asesor_company_id = response['id']
        print(f"   Created company with asesor assignment: {self.asesor_company_id}")
        
        # Now try to delete the asesor (should fail)
        success, response = self.run_test(
            "Delete Asesor with Company Assignment (Should Fail)",
            "DELETE",
            f"users/{self.asesor_user_id}",
            400  # Should return 400 Bad Request
        )
        
        if success:
            print(f"   Correctly prevented deletion of asesor with company assignments")
            return True
        return False

    def test_delete_user_after_reassignment(self):
        """Test deleting asesor after reassigning companies (should work)"""
        if not hasattr(self, 'asesor_company_id') or not hasattr(self, 'asesor_user_id'):
            print("❌ No asesor company or user ID available for reassignment test")
            return False
        
        # First reassign the company to remove asesor assignment
        # We'll update the company to remove the asesor_comercial_id
        # Since there's no PUT endpoint for companies, we'll create another asesor and assign
        
        # Create another asesor for reassignment
        new_asesor_data = {
            "email": f"newasesor{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "New Asesor for Reassignment",
            "password": "newasesor123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create New Asesor for Reassignment",
            "POST",
            "auth/register",
            200,
            data=new_asesor_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create new asesor for reassignment")
            return False
        
        new_asesor_id = response['id']
        
        # For this test, we'll simulate reassignment by deleting the company
        # since there's no company update endpoint
        success, response = self.run_test(
            "Delete Company to Remove Asesor Assignment",
            "DELETE",
            f"companies/{self.asesor_company_id}",
            200
        )
        
        if not success:
            print("❌ Could not delete company to remove asesor assignment")
            return False
        
        print(f"   Removed asesor assignment by deleting company")
        
        # Now try to delete the original asesor (should work)
        success, response = self.run_test(
            "Delete Asesor After Reassignment",
            "DELETE",
            f"users/{self.asesor_user_id}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('message') and 'deleted successfully' in response.get('message', ''):
                print(f"   Asesor deleted successfully after reassignment")
                # Clean up the new asesor too
                cleanup_success, cleanup_response = self.run_test(
                    "Cleanup New Asesor",
                    "DELETE",
                    f"users/{new_asesor_id}",
                    200
                )
                return True
        return False

    def test_client_cannot_delete_users(self):
        """Test that client users cannot delete users"""
        # Create a test user first
        test_user_data = {
            "email": f"deletetest{datetime.now().strftime('%H%M%S')}@test.com",
            "name": "Delete Test User",
            "password": "deletetest123",
            "role": "client"
        }
        
        success, response = self.run_test(
            "Create User for Client Delete Test",
            "POST",
            "auth/register",
            200,
            data=test_user_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create user for client delete test")
            return False
        
        test_user_id = response['id']
        
        # Login as client user
        admin_token = self.token
        success_login, login_response = self.run_test(
            "Client Login for User Delete Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for user delete test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        # Try to delete user as client (should fail with 403)
        success, response = self.run_test(
            "Client Delete User (Should Fail)",
            "DELETE",
            f"users/{test_user_id}",
            403  # Should return 403 Forbidden
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from deleting users")
            
            # Clean up: delete the test user as admin
            cleanup_success, cleanup_response = self.run_test(
                "Cleanup Test User",
                "DELETE",
                f"users/{test_user_id}",
                200
            )
            return True
        return False

    # PHASE 1 NEW FEATURE TESTS - Expanded Company Model
    def test_create_company_with_new_fields(self):
        """Test creating company with all new fields"""
        # First create a segmento to use
        segmento_data = {
            "nombre": "Tecnología Avanzada",
            "descripcion": "Empresas del sector tecnológico"
        }
        
        success, response = self.run_test(
            "Create Segmento for Company Test",
            "POST",
            "segmentos",
            200,
            data=segmento_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create segmento for company test")
            return False
        
        segmento_id = response['id']
        
        # Create another asesor for assignment
        asesor_data = {
            "email": f"asesorcompany{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "Asesor for Company Test",
            "password": "asesorcompany123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create Asesor for Company Test",
            "POST",
            "auth/register",
            200,
            data=asesor_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create asesor for company test")
            return False
        
        asesor_id = response['id']
        
        # Now create company with all new fields
        company_data = {
            "name": f"Empresa Completa {datetime.now().strftime('%H%M%S')}",
            "razon_social": "Empresa Completa S.A.S.",
            "nit": "900123456-7",
            "description": "Empresa de prueba con todos los campos nuevos",
            "contacto": "María González",
            "contact_email": "maria@empresacompleta.com",
            "telefono": "+57 301 234 5678",
            "direccion": "Carrera 15 #93-47, Oficina 501, Bogotá D.C.",
            "asesor_comercial_id": asesor_id,
            "segmento": segmento_id,
            "estado": "Prospecto",
            "corporacion": "Holding Empresarial Colombia"
        }
        
        success, response = self.run_test(
            "Create Company with All New Fields",
            "POST",
            "companies",
            200,
            data=company_data
        )
        
        if success and 'id' in response:
            self.expanded_company_id = response['id']
            self.test_asesor_id = asesor_id
            self.test_segmento_id = segmento_id
            print(f"   Created expanded company ID: {self.expanded_company_id}")
            
            # Verify all fields were saved correctly
            if (response.get('razon_social') == company_data['razon_social'] and
                response.get('nit') == company_data['nit'] and
                response.get('contacto') == company_data['contacto'] and
                response.get('telefono') == company_data['telefono'] and
                response.get('direccion') == company_data['direccion'] and
                response.get('asesor_comercial_id') == company_data['asesor_comercial_id'] and
                response.get('segmento') == company_data['segmento'] and
                response.get('estado') == company_data['estado'] and
                response.get('corporacion') == company_data['corporacion']):
                print(f"   All new fields saved correctly")
                return True
            else:
                print(f"   Some fields not saved correctly")
                return False
        return False

    # PHASE 1 NEW FEATURE TESTS - Asesor Role Functionality
    def test_asesor_login_and_permissions(self):
        """Test asesor login and company access permissions"""
        if not hasattr(self, 'test_asesor_id'):
            print("❌ No test asesor ID available for login test")
            return False
        
        # Get asesor credentials (we need to find the asesor we created)
        # For this test, we'll create a new asesor with known credentials
        asesor_login_data = {
            "email": f"asesorlogin{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "Asesor Login Test",
            "password": "asesorlogin123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create Asesor for Login Test",
            "POST",
            "auth/register",
            200,
            data=asesor_login_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create asesor for login test")
            return False
        
        login_asesor_id = response['id']
        
        # Create a company assigned to this asesor
        company_for_asesor = {
            "name": f"Asesor Company {datetime.now().strftime('%H%M%S')}",
            "razon_social": "Asesor Company S.A.S.",
            "asesor_comercial_id": login_asesor_id,
            "segmento": "Servicios"
        }
        
        success, response = self.run_test(
            "Create Company for Asesor Test",
            "POST",
            "companies",
            200,
            data=company_for_asesor
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create company for asesor test")
            return False
        
        asesor_company_id = response['id']
        
        # Save admin token and login as asesor
        admin_token = self.token
        success, response = self.run_test(
            "Asesor Login",
            "POST",
            "auth/login",
            200,
            data={"email": asesor_login_data['email'], "password": asesor_login_data['password']}
        )
        
        if not success or 'access_token' not in response:
            print("❌ Asesor login failed")
            self.token = admin_token
            return False
        
        # Use asesor token
        self.token = response['access_token']
        asesor_user = response['user']
        print(f"   Asesor logged in: {asesor_user['name']} ({asesor_user['role']})")
        
        # Test that asesor can only see assigned companies
        success, response = self.run_test(
            "Asesor Get Companies (Only Assigned)",
            "GET",
            "companies",
            200
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success and isinstance(response, list):
            # Asesor should only see companies assigned to them
            assigned_companies = [comp for comp in response if comp.get('asesor_comercial_id') == login_asesor_id]
            if len(response) == len(assigned_companies) and len(response) >= 1:
                print(f"   Asesor correctly sees only assigned companies: {len(response)}")
                
                # Clean up
                cleanup_success, cleanup_response = self.run_test(
                    "Cleanup Asesor Company",
                    "DELETE",
                    f"companies/{asesor_company_id}",
                    200
                )
                cleanup_success, cleanup_response = self.run_test(
                    "Cleanup Login Asesor",
                    "DELETE",
                    f"users/{login_asesor_id}",
                    200
                )
                return True
            else:
                print(f"   Asesor permission issue: saw {len(response)} companies, expected only assigned ones")
                return False
        return False

    def test_asesor_company_detail_access(self):
        """Test asesor access to specific company details"""
        if not hasattr(self, 'expanded_company_id') or not hasattr(self, 'test_asesor_id'):
            print("❌ No expanded company or test asesor ID available")
            return False
        
        # Create asesor credentials for this test
        asesor_detail_data = {
            "email": f"asesordetail{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "Asesor Detail Test",
            "password": "asesordetail123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create Asesor for Detail Test",
            "POST",
            "auth/register",
            200,
            data=asesor_detail_data
        )
        
        if not success or 'id' not in response:
            print("❌ Could not create asesor for detail test")
            return False
        
        detail_asesor_id = response['id']
        
        # Save admin token and login as asesor
        admin_token = self.token
        success, response = self.run_test(
            "Asesor Detail Login",
            "POST",
            "auth/login",
            200,
            data={"email": asesor_detail_data['email'], "password": asesor_detail_data['password']}
        )
        
        if not success or 'access_token' not in response:
            print("❌ Asesor detail login failed")
            self.token = admin_token
            return False
        
        # Use asesor token
        self.token = response['access_token']
        
        # Try to access company not assigned to this asesor (should fail with 403)
        success, response = self.run_test(
            "Asesor Access Non-Assigned Company (Should Fail)",
            "GET",
            f"companies/{self.expanded_company_id}",
            403  # Should return 403 Forbidden
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented asesor from accessing non-assigned company")
            
            # Clean up
            cleanup_success, cleanup_response = self.run_test(
                "Cleanup Detail Asesor",
                "DELETE",
                f"users/{detail_asesor_id}",
                200
            )
            return True
        return False

    # PHASE 1 NEW FEATURE TESTS - Segment Management
    def test_create_segmento(self):
        """Test creating a segmento"""
        segmento_data = {
            "nombre": f"Segmento Test {datetime.now().strftime('%H%M%S')}",
            "descripcion": "Segmento creado para pruebas automatizadas"
        }
        
        success, response = self.run_test(
            "Create Segmento",
            "POST",
            "segmentos",
            200,
            data=segmento_data
        )
        
        if success and 'id' in response:
            self.test_segmento_new_id = response['id']
            print(f"   Created segmento ID: {self.test_segmento_new_id}")
            
            # Verify fields were saved correctly
            if (response.get('nombre') == segmento_data['nombre'] and
                response.get('descripcion') == segmento_data['descripcion'] and
                response.get('is_active') == True):
                print(f"   Segmento fields saved correctly")
                return True
            else:
                print(f"   Segmento fields not saved correctly")
                return False
        return False

    def test_get_segmentos(self):
        """Test getting active segmentos list"""
        success, response = self.run_test(
            "Get Segmentos",
            "GET",
            "segmentos",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} active segmentos")
            # Verify all returned segmentos are active
            active_segmentos = [seg for seg in response if seg.get('is_active') == True]
            if len(response) == len(active_segmentos):
                print(f"   All returned segmentos are active")
                return True
            else:
                print(f"   Some inactive segmentos returned")
                return False
        return False

    def test_delete_segmento_in_use(self):
        """Test deleting segmento that's in use by companies (should fail)"""
        if not hasattr(self, 'test_segmento_id'):
            print("❌ No test segmento ID available for deletion test")
            return False
        
        # The expanded company we created earlier uses this segmento
        success, response = self.run_test(
            "Delete Segmento In Use (Should Fail)",
            "DELETE",
            f"segmentos/{self.test_segmento_id}",
            400  # Should return 400 Bad Request
        )
        
        if success:
            print(f"   Correctly prevented deletion of segmento in use")
            return True
        return False

    def test_delete_unused_segmento(self):
        """Test deleting segmento not in use (should work)"""
        if not hasattr(self, 'test_segmento_new_id'):
            print("❌ No unused segmento ID available for deletion test")
            return False
        
        success, response = self.run_test(
            "Delete Unused Segmento",
            "DELETE",
            f"segmentos/{self.test_segmento_new_id}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('message') and 'deleted successfully' in response.get('message', ''):
                print(f"   Unused segmento deleted successfully")
                return True
        return False

    def test_client_cannot_create_segmentos(self):
        """Test that client users cannot create segmentos"""
        # Login as client user
        admin_token = self.token
        success_login, login_response = self.run_test(
            "Client Login for Segmento Create Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for segmento create test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        segmento_data = {
            "nombre": "Segmento Client Test",
            "descripcion": "Should not be created by client"
        }
        
        # Try to create segmento as client (should fail with 403)
        success, response = self.run_test(
            "Client Create Segmento (Should Fail)",
            "POST",
            "segmentos",
            403  # Should return 403 Forbidden
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from creating segmentos")
            return True
        return False

    # PHASE 1 NEW FEATURE TESTS - Get Asesores List
    def test_get_asesores_list(self):
        """Test getting list of asesor users (staff only)"""
        success, response = self.run_test(
            "Get Asesores List",
            "GET",
            "users/asesores",
            200
        )
        
        if success and isinstance(response, list):
            # Verify all returned users have asesor role and are active
            asesor_users = [user for user in response if user.get('role') == 'asesor' and user.get('is_active') == True]
            if len(response) == len(asesor_users):
                print(f"   Found {len(response)} active asesor users")
                return True
            else:
                print(f"   Some non-asesor or inactive users returned")
                return False
        return False

    # NEW BATCH PROCESSING TESTS
    def test_batch_upload_documents(self):
        """Test batch upload of multiple PDFs (up to 10)"""
        if not self.project_id:
            print("❌ No project ID available for batch upload test")
            return False
        
        # Create multiple test PDF files (3 files for testing)
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
(Batch Test Document) Tj
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
        
        # Create 3 files for batch upload
        files = [
            ('files', ('batch_test_1.pdf', pdf_content, 'application/pdf')),
            ('files', ('batch_test_2.pdf', pdf_content, 'application/pdf')),
            ('files', ('batch_test_3.pdf', pdf_content, 'application/pdf'))
        ]
        
        import requests
        url = f"{self.api_url}/projects/{self.project_id}/documents/batch-upload"
        headers = {'Authorization': f'Bearer {self.token}'}
        
        print(f"\n🔍 Testing Batch Upload Documents...")
        print(f"   URL: {url}")
        print(f"   Files to upload: {len(files)}")
        
        try:
            response = requests.post(url, headers=headers, files=files)
            success = response.status_code == 200
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                result = response.json()
                if 'batch_task_id' in result and 'document_ids' in result:
                    self.batch_task_id = result['batch_task_id']
                    self.batch_document_ids = result['document_ids']
                    print(f"   Batch task ID: {self.batch_task_id}")
                    print(f"   Documents uploaded: {result.get('files_uploaded', 0)}")
                    print(f"   Document IDs: {len(self.batch_document_ids)}")
                    return True
                else:
                    print(f"❌ Missing batch_task_id or document_ids in response")
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

    def test_batch_upload_limit_exceeded(self):
        """Test batch upload with more than 10 files (should fail)"""
        if not self.project_id:
            print("❌ No project ID available for batch limit test")
            return False
        
        # Create 11 files to exceed the limit
        pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
trailer<</Size 4/Root 1 0 R>>
startxref
200
%%EOF"""
        
        files = []
        for i in range(11):  # 11 files to exceed limit
            files.append(('files', (f'limit_test_{i+1}.pdf', pdf_content, 'application/pdf')))
        
        import requests
        url = f"{self.api_url}/projects/{self.project_id}/documents/batch-upload"
        headers = {'Authorization': f'Bearer {self.token}'}
        
        print(f"\n🔍 Testing Batch Upload Limit (11 files - should fail)...")
        print(f"   URL: {url}")
        print(f"   Files to upload: {len(files)}")
        
        try:
            response = requests.post(url, headers=headers, files=files)
            success = response.status_code == 400  # Should return 400 Bad Request
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                print(f"   Correctly rejected upload of {len(files)} files (limit is 10)")
                return True
            else:
                print(f"❌ Failed - Expected 400, got {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False
        finally:
            self.tests_run += 1

    def test_batch_status_check(self):
        """Test checking batch processing status"""
        if not self.project_id or not hasattr(self, 'batch_task_id'):
            print("❌ No project ID or batch task ID available for status test")
            return False
        
        success, response = self.run_test(
            "Get Batch Processing Status",
            "GET",
            f"projects/{self.project_id}/batch-status/{self.batch_task_id}",
            200
        )
        
        if success and isinstance(response, dict):
            status = response.get('status', 'unknown')
            progress = response.get('progress', 0)
            total_docs = response.get('total_documents', 0)
            completed_docs = response.get('completed_documents', 0)
            failed_docs = response.get('failed_documents', 0)
            document_statuses = response.get('document_statuses', [])
            
            print(f"   Batch status: {status} ({progress}%)")
            print(f"   Documents: {completed_docs}/{total_docs} completed, {failed_docs} failed")
            print(f"   Individual document statuses: {len(document_statuses)}")
            
            # Verify response structure
            if ('batch_task_id' in response and 
                'status' in response and 
                'document_statuses' in response and
                isinstance(document_statuses, list)):
                print(f"   Batch status response structure is correct")
                return True
            else:
                print(f"   Batch status response structure is incorrect")
                return False
        return False

    def test_batch_processing_wait_completion(self):
        """Test waiting for batch processing to complete"""
        if not self.project_id or not hasattr(self, 'batch_task_id'):
            print("❌ No project ID or batch task ID available for completion test")
            return False
        
        print(f"\n🔍 Waiting for batch processing to complete...")
        max_wait_time = 60  # Maximum 60 seconds
        wait_interval = 3   # Check every 3 seconds
        waited_time = 0
        
        while waited_time < max_wait_time:
            success, response = self.run_test(
                f"Check Batch Status (wait {waited_time}s)",
                "GET",
                f"projects/{self.project_id}/batch-status/{self.batch_task_id}",
                200
            )
            
            if success and isinstance(response, dict):
                status = response.get('status', 'unknown')
                progress = response.get('progress', 0)
                
                print(f"   Status: {status} ({progress}%) - waited {waited_time}s")
                
                if status in ['completed', 'failed']:
                    if status == 'completed':
                        print(f"✅ Batch processing completed successfully")
                        return True
                    else:
                        print(f"❌ Batch processing failed")
                        return False
                
                # Wait before next check
                time.sleep(wait_interval)
                waited_time += wait_interval
            else:
                print(f"❌ Failed to get batch status")
                return False
        
        print(f"❌ Batch processing did not complete within {max_wait_time} seconds")
        return False

    # COMPANY EDITING TESTS
    def test_update_company_all_fields(self):
        """Test updating company with all new fields"""
        if not self.company_id:
            print("❌ No company ID available for update test")
            return False
        
        # Get current company data first
        success, current_company = self.run_test(
            "Get Company Before Update",
            "GET",
            f"companies/{self.company_id}",
            200
        )
        
        if not success:
            print("❌ Could not get current company data")
            return False
        
        # Create update data with all new fields
        update_data = {
            "name": f"Updated Company {datetime.now().strftime('%H%M%S')}",
            "razon_social": "Updated Company S.A.S.",
            "nit": "900987654-3",
            "description": "Updated company description with all new fields",
            "contacto": "Carlos Rodríguez",
            "contact_email": "carlos@updatedcompany.com",
            "telefono": "+57 302 987 6543",
            "direccion": "Avenida 68 #45-23, Piso 8, Bogotá D.C.",
            "segmento": "Servicios Financieros",
            "estado": "Cliente Activo",
            "corporacion": "Grupo Financiero Internacional"
        }
        
        success, response = self.run_test(
            "Update Company with All Fields",
            "PUT",
            f"companies/{self.company_id}",
            200,
            data=update_data
        )
        
        if success and isinstance(response, dict):
            # Verify all fields were updated correctly
            fields_correct = True
            for field, expected_value in update_data.items():
                actual_value = response.get(field)
                if actual_value != expected_value:
                    print(f"   Field {field}: expected '{expected_value}', got '{actual_value}'")
                    fields_correct = False
            
            if fields_correct:
                print(f"   All company fields updated correctly")
                print(f"   Updated company: {response.get('name')}")
                print(f"   Razón social: {response.get('razon_social')}")
                print(f"   NIT: {response.get('nit')}")
                print(f"   Contacto: {response.get('contacto')}")
                return True
            else:
                print(f"   Some company fields were not updated correctly")
                return False
        return False

    def test_update_company_partial_fields(self):
        """Test updating company with only some fields"""
        if not self.company_id:
            print("❌ No company ID available for partial update test")
            return False
        
        # Update only a few fields
        partial_update = {
            "telefono": "+57 305 111 2222",
            "estado": "Prospecto Calificado",
            "description": "Partially updated company description"
        }
        
        success, response = self.run_test(
            "Update Company Partial Fields",
            "PUT",
            f"companies/{self.company_id}",
            200,
            data=partial_update
        )
        
        if success and isinstance(response, dict):
            # Verify updated fields
            for field, expected_value in partial_update.items():
                actual_value = response.get(field)
                if actual_value != expected_value:
                    print(f"   Partial update failed for {field}: expected '{expected_value}', got '{actual_value}'")
                    return False
            
            print(f"   Partial company update successful")
            print(f"   Updated telefono: {response.get('telefono')}")
            print(f"   Updated estado: {response.get('estado')}")
            return True
        return False

    def test_update_nonexistent_company(self):
        """Test updating a non-existent company (should return 404)"""
        fake_company_id = "nonexistent-company-update-test"
        
        update_data = {
            "name": "Should Not Work",
            "description": "This update should fail"
        }
        
        success, response = self.run_test(
            "Update Non-existent Company",
            "PUT",
            f"companies/{fake_company_id}",
            404,  # Should return 404 Not Found
            data=update_data
        )
        
        if success:
            print(f"   Correctly returned 404 for non-existent company update")
            return True
        return False

    def test_client_cannot_update_company(self):
        """Test that client users cannot update companies"""
        if not self.company_id:
            print("❌ No company ID available for client update test")
            return False
        
        # Login as client user
        admin_token = self.token
        success_login, login_response = self.run_test(
            "Client Login for Company Update Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for company update test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        update_data = {
            "name": "Client Should Not Update This",
            "description": "This should fail"
        }
        
        # Try to update company as client (should fail with 403)
        success, response = self.run_test(
            "Client Update Company (Should Fail)",
            "PUT",
            f"companies/{self.company_id}",
            403,  # Should return 403 Forbidden
            data=update_data
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from updating company")
            return True
        return False

    def test_client_cannot_get_asesores(self):
        """Test that client users cannot get asesores list"""
        # Login as client user
        admin_token = self.token
        success_login, login_response = self.run_test(
            "Client Login for Asesores List Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for asesores list test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        # Try to get asesores list as client (should fail with 403)
        success, response = self.run_test(
            "Client Get Asesores (Should Fail)",
            "GET",
            "users/asesores",
            403  # Should return 403 Forbidden
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from accessing asesores list")
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
    
    # NEW FEATURE TESTS - Document Processing Module (Enhanced)
    print("\n🔍 Testing NEW Enhanced Document Processing Module...")
    test_results.append(("Process Documents Rename-Reorder (NEW)", tester.test_process_documents_rename_reorder()))
    test_results.append(("Get Enhanced Process Status (NEW)", tester.test_get_enhanced_process_status()))
    test_results.append(("Download Processed PDF (NEW)", tester.test_download_processed_pdf()))
    test_results.append(("Process Documents Reorder (Legacy)", tester.test_process_documents_reorder()))
    test_results.append(("Get Process Status (Legacy)", tester.test_get_process_status()))
    
    # PHASE 1 NEW FEATURE TESTS - User Deletion
    print("\n🔍 Testing PHASE 1 - User Deletion Features...")
    test_results.append(("Create Asesor User", tester.test_create_asesor_user()))
    test_results.append(("Delete Self Prevention", tester.test_delete_user_self_prevention()))
    test_results.append(("Delete User with Company Assignment (Should Fail)", tester.test_delete_user_with_company_assignment()))
    test_results.append(("Delete User After Reassignment", tester.test_delete_user_after_reassignment()))
    test_results.append(("Client Cannot Delete Users", tester.test_client_cannot_delete_users()))
    
    # PHASE 1 NEW FEATURE TESTS - Expanded Company Model
    print("\n🔍 Testing PHASE 1 - Expanded Company Model...")
    test_results.append(("Create Company with New Fields", tester.test_create_company_with_new_fields()))
    
    # PHASE 1 NEW FEATURE TESTS - Asesor Role Functionality
    print("\n🔍 Testing PHASE 1 - Asesor Role Functionality...")
    test_results.append(("Asesor Login and Permissions", tester.test_asesor_login_and_permissions()))
    test_results.append(("Asesor Company Detail Access", tester.test_asesor_company_detail_access()))
    
    # PHASE 1 NEW FEATURE TESTS - Segment Management
    print("\n🔍 Testing PHASE 1 - Segment Management...")
    test_results.append(("Create Segmento", tester.test_create_segmento()))
    test_results.append(("Get Segmentos", tester.test_get_segmentos()))
    test_results.append(("Delete Segmento In Use (Should Fail)", tester.test_delete_segmento_in_use()))
    test_results.append(("Delete Unused Segmento", tester.test_delete_unused_segmento()))
    test_results.append(("Client Cannot Create Segmentos", tester.test_client_cannot_create_segmentos()))
    
    # PHASE 1 NEW FEATURE TESTS - Get Asesores List
    print("\n🔍 Testing PHASE 1 - Asesores List...")
    test_results.append(("Get Asesores List", tester.test_get_asesores_list()))
    test_results.append(("Client Cannot Get Asesores", tester.test_client_cannot_get_asesores()))

    # NEW BATCH PROCESSING TESTS
    print("\n🔍 Testing NEW BATCH PROCESSING Features...")
    test_results.append(("Batch Upload Documents", tester.test_batch_upload_documents()))
    test_results.append(("Batch Upload Limit Exceeded", tester.test_batch_upload_limit_exceeded()))
    test_results.append(("Batch Status Check", tester.test_batch_status_check()))
    test_results.append(("Batch Processing Wait Completion", tester.test_batch_processing_wait_completion()))

    # NEW COMPANY EDITING TESTS
    print("\n🔍 Testing NEW COMPANY EDITING Features...")
    test_results.append(("Update Company All Fields", tester.test_update_company_all_fields()))
    test_results.append(("Update Company Partial Fields", tester.test_update_company_partial_fields()))
    test_results.append(("Update Non-existent Company", tester.test_update_nonexistent_company()))
    test_results.append(("Client Cannot Update Company", tester.test_client_cannot_update_company()))

    # NEW FEATURE TESTS - DELETE ENDPOINTS (Staff Only)
    print("\n🔍 Testing DELETE Endpoints (Staff Only)...")
    test_results.append(("Delete Company Without Projects", tester.test_delete_company_without_projects()))
    test_results.append(("Delete Company With Projects (Should Fail)", tester.test_delete_company_with_projects_should_fail()))
    test_results.append(("Delete Project With Documents", tester.test_delete_project_with_documents()))
    test_results.append(("Client Cannot Delete Company", tester.test_client_cannot_delete_company()))
    test_results.append(("Client Cannot Delete Project", tester.test_client_cannot_delete_project()))
    test_results.append(("Delete Non-existent Company", tester.test_delete_nonexistent_company()))
    test_results.append(("Delete Non-existent Project", tester.test_delete_nonexistent_project()))
    
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
        "PHASE 1 - User Deletion": ["Create Asesor User", "Delete Self Prevention", "Delete User with Company Assignment (Should Fail)", "Delete User After Reassignment", "Client Cannot Delete Users"],
        "PHASE 1 - Expanded Company Model": ["Create Company with New Fields"],
        "PHASE 1 - Asesor Role": ["Asesor Login and Permissions", "Asesor Company Detail Access"],
        "PHASE 1 - Segment Management": ["Create Segmento", "Get Segmentos", "Delete Segmento In Use (Should Fail)", "Delete Unused Segmento", "Client Cannot Create Segmentos"],
        "PHASE 1 - Asesores List": ["Get Asesores List", "Client Cannot Get Asesores"],
        "QA Agents Module (NEW)": ["Create QA Agent", "Get QA Agents", "Run QA Agent"],
        "User Management Module (NEW)": ["Create Client User", "Get Users List", "Toggle User Status", "Client Login"],
        "Document Processing Module (NEW)": ["Process Documents Rename-Reorder (NEW)", "Get Enhanced Process Status (NEW)", "Download Processed PDF (NEW)", "Process Documents Reorder (Legacy)", "Get Process Status (Legacy)"],
        "Delete Endpoints (NEW)": ["Delete Company Without Projects", "Delete Company With Projects (Should Fail)", "Delete Project With Documents", "Client Cannot Delete Company", "Client Cannot Delete Project", "Delete Non-existent Company", "Delete Non-existent Project"],
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
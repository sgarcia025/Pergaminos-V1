#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime
import time

class AIConfigTester:
    def __init__(self, base_url="https://digitaldocs.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.company_id = None
        self.ai_config_id = None
        self.qa_ai_config_id = None

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
        if data:
            print(f"   Data: {data}")
        print(f"   Headers: {headers}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, headers={k: v for k, v in headers.items() if k != 'Content-Type'}, data=data, files=files)
                else:
                    print(f"   Sending POST with json={data}")
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

    def test_create_company(self):
        """Test creating a company for AI config tests"""
        company_data = {
            "name": f"AI Config Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "A test company for AI configuration testing",
            "contact_email": "aitest@company.com"
        }
        
        success, response = self.run_test(
            "Create Company for AI Config",
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

    def test_get_ai_model_recommendations(self):
        """Test getting AI model recommendations"""
        success, response = self.run_test(
            "Get AI Model Recommendations",
            "GET",
            "ai-models/recommendations",
            200
        )
        
        if success and isinstance(response, dict):
            # Verify structure for each task type
            expected_types = ["data_extraction", "qa_processing", "document_processing"]
            for task_type in expected_types:
                if task_type in response:
                    recommendations = response[task_type].get("recommended", [])
                    if recommendations and len(recommendations) > 0:
                        # Check first recommendation structure
                        first_rec = recommendations[0]
                        if all(key in first_rec for key in ["model", "description", "use_case", "cost_level"]):
                            print(f"   {task_type}: {len(recommendations)} models recommended")
                        else:
                            print(f"❌ Missing fields in {task_type} recommendations")
                            return False
                    else:
                        print(f"❌ No recommendations found for {task_type}")
                        return False
                else:
                    print(f"❌ Missing task type: {task_type}")
                    return False
            
            print(f"   All AI model recommendations structured correctly")
            return True
        return False

    def test_create_ai_configuration(self):
        """Test creating AI configuration for a company"""
        if not self.company_id:
            print("❌ No company ID available for AI configuration test")
            return False
        
        ai_config_data = {
            "config_type": "data_extraction",
            "provider": "openai",
            "api_key": "sk-test-api-key-for-testing-12345",
            "model_name": "gpt-4o",
            "model_parameters": {
                "temperature": 0.1,
                "max_tokens": 2000
            }
        }
        
        success, response = self.run_test(
            "Create AI Configuration",
            "POST",
            f"companies/{self.company_id}/ai-config",
            200,
            data=ai_config_data
        )
        
        if success and 'id' in response:
            self.ai_config_id = response['id']
            print(f"   Created AI configuration ID: {self.ai_config_id}")
            
            # Verify API key is encrypted in response
            if response.get('api_key') == "***ENCRYPTED***":
                print(f"   API key correctly encrypted in response")
                
                # Verify other fields
                if (response.get('config_type') == ai_config_data['config_type'] and
                    response.get('provider') == ai_config_data['provider'] and
                    response.get('model_name') == ai_config_data['model_name']):
                    print(f"   All configuration fields saved correctly")
                    return True
                else:
                    print(f"❌ Configuration fields not saved correctly")
                    return False
            else:
                print(f"❌ API key not encrypted properly: {response.get('api_key')}")
                return False
        return False

    def test_create_different_type_ai_configuration(self):
        """Test creating AI configuration with different type"""
        if not self.company_id:
            print("❌ No company ID available for different type AI configuration test")
            return False
        
        qa_config_data = {
            "config_type": "qa_processing",
            "provider": "openai",
            "api_key": "sk-qa-test-api-key-67890",
            "model_name": "gpt-4o-mini",
            "model_parameters": {
                "temperature": 0.0,
                "max_tokens": 1000
            }
        }
        
        success, response = self.run_test(
            "Create QA Processing AI Configuration",
            "POST",
            f"companies/{self.company_id}/ai-config",
            200,
            data=qa_config_data
        )
        
        if success and 'id' in response:
            self.qa_ai_config_id = response['id']
            print(f"   Created QA AI configuration ID: {self.qa_ai_config_id}")
            
            # Verify different type is allowed
            if response.get('config_type') == "qa_processing":
                print(f"   Different configuration type created successfully")
                return True
        return False

    def test_get_ai_configurations(self):
        """Test getting AI configurations for a company"""
        if not self.company_id:
            print("❌ No company ID available for get AI configurations test")
            return False
        
        success, response = self.run_test(
            "Get AI Configurations",
            "GET",
            f"companies/{self.company_id}/ai-config",
            200
        )
        
        if success and isinstance(response, dict):
            # Verify response structure
            if ('company_id' in response and 
                'company_name' in response and 
                'configurations' in response and
                'available_types' in response):
                
                configurations = response['configurations']
                print(f"   Found {len(configurations)} AI configurations")
                
                # Verify API keys are masked
                all_encrypted = True
                for config in configurations:
                    if config.get('api_key') != "***ENCRYPTED***":
                        all_encrypted = False
                        break
                
                if all_encrypted:
                    print(f"   All API keys properly encrypted in response")
                    
                    # Verify available types
                    expected_types = ["data_extraction", "qa_processing", "document_processing"]
                    if response['available_types'] == expected_types:
                        print(f"   Available types correctly listed")
                        return True
                    else:
                        print(f"❌ Available types incorrect: {response['available_types']}")
                        return False
                else:
                    print(f"❌ Some API keys not encrypted in response")
                    return False
            else:
                print(f"❌ Response structure incorrect")
                return False
        return False

    def test_update_ai_configuration(self):
        """Test updating AI configuration"""
        if not self.company_id or not self.ai_config_id:
            print("❌ No company ID or AI config ID available for update test")
            return False
        
        update_data = {
            "model_name": "gpt-4o-mini",  # Changed from gpt-4o
            "api_key": "sk-updated-test-api-key-99999",  # New API key
            "model_parameters": {
                "temperature": 0.2,  # Changed from 0.1
                "max_tokens": 1500   # Changed from 2000
            }
        }
        
        success, response = self.run_test(
            "Update AI Configuration",
            "PUT",
            f"companies/{self.company_id}/ai-config/{self.ai_config_id}",
            200,
            data=update_data
        )
        
        if success and isinstance(response, dict):
            if response.get('message') and 'updated successfully' in response.get('message', ''):
                print(f"   AI configuration updated successfully")
                return True
        return False

    def test_delete_ai_configuration(self):
        """Test deleting (deactivating) AI configuration"""
        if not self.company_id or not self.qa_ai_config_id:
            print("❌ No company ID or QA AI config ID available for delete test")
            return False
        
        success, response = self.run_test(
            "Delete AI Configuration",
            "DELETE",
            f"companies/{self.company_id}/ai-config/{self.qa_ai_config_id}",
            200
        )
        
        if success and isinstance(response, dict):
            if response.get('message') and 'deactivated successfully' in response.get('message', ''):
                print(f"   AI configuration deactivated successfully")
                return True
        return False

    def test_client_cannot_manage_ai_configurations(self):
        """Test that client users cannot manage AI configurations"""
        if not self.company_id:
            print("❌ No company ID available for client AI config test")
            return False
        
        # First create a separate company for the client user
        admin_token = self.token
        client_company_data = {
            "name": f"Client Test Company {datetime.now().strftime('%H%M%S')}",
            "description": "A separate company for client user testing"
        }
        
        success_company, company_response = self.run_test(
            "Create Client Company for AI Config Test",
            "POST",
            "companies",
            200,
            data=client_company_data
        )
        
        if not success_company:
            print("❌ Could not create client company for AI config test")
            return False
        
        client_company_id = company_response['id']
        
        # Create a client user assigned to the separate company
        client_user_data = {
            "email": f"testclient{datetime.now().strftime('%H%M%S')}@test.com",
            "name": "Test Client User",
            "password": "testpass123",
            "role": "client",
            "company_id": client_company_id
        }
        
        success_create, create_response = self.run_test(
            "Create Client User for AI Config Test",
            "POST",
            "auth/register",
            200,
            data=client_user_data
        )
        
        if not success_create:
            print("❌ Could not create client user for AI config test")
            return False
        
        # Login as client user
        success_login, login_response = self.run_test(
            "Client Login for AI Config Test",
            "POST",
            "auth/login",
            200,
            data={"email": client_user_data["email"], "password": client_user_data["password"]}
        )
        
        if not success_login or 'access_token' not in login_response:
            print("❌ Could not login as client for AI config test")
            self.token = admin_token
            return False
        
        # Use client token
        self.token = login_response['access_token']
        
        # Try to create AI configuration as client (should fail with 403)
        client_config_data = {
            "config_type": "document_processing",
            "provider": "openai",
            "api_key": "sk-client-test-key",
            "model_name": "gpt-4o"
        }
        
        print(f"   Attempting to create AI config for company: {client_company_id}")
        print(f"   Config data: {client_config_data}")
        
        success, response = self.run_test(
            "Client Create AI Configuration (Should Fail)",
            "POST",
            f"companies/{client_company_id}/ai-config",
            403,  # Should return 403 Forbidden
            data=client_config_data
        )
        
        # Restore admin token
        self.token = admin_token
        
        if success:
            print(f"   Correctly prevented client from creating AI configuration")
            return True
        return False

def main():
    print("🧪 Starting AI Configuration Module Testing")
    print("🔍 Testing AI Configuration Management Features")
    print("=" * 60)
    
    tester = AIConfigTester()
    
    # Test sequence
    test_results = []
    
    # Authentication
    test_results.append(("Admin Login", tester.test_login()))
    if not tester.token:
        print("❌ Login failed, stopping tests")
        return 1
    
    # Setup
    test_results.append(("Create Company for AI Config", tester.test_create_company()))
    
    # AI Configuration tests
    test_results.append(("Get AI Model Recommendations", tester.test_get_ai_model_recommendations()))
    test_results.append(("Create AI Configuration", tester.test_create_ai_configuration()))
    test_results.append(("Create Different Type AI Configuration", tester.test_create_different_type_ai_configuration()))
    test_results.append(("Get AI Configurations", tester.test_get_ai_configurations()))
    test_results.append(("Update AI Configuration", tester.test_update_ai_configuration()))
    test_results.append(("Delete AI Configuration", tester.test_delete_ai_configuration()))
    test_results.append(("Client Cannot Manage AI Configurations", tester.test_client_cannot_manage_ai_configurations()))
    
    # Print results
    print("\n" + "=" * 60)
    print("📊 AI CONFIGURATION MODULE TEST RESULTS")
    print("=" * 60)
    
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
        print(f"\n❌ FAILED TESTS:")
        for test in failed_tests:
            print(f"   - {test}")
    else:
        print(f"\n🎉 ALL AI CONFIGURATION TESTS PASSED!")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
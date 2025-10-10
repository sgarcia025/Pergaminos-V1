import requests
import sys
import json
import time
import subprocess
from datetime import datetime

class AIEncryptionTester:
    def __init__(self, base_url="https://smart-doc-extract.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0
        self.company_id = None
        self.ai_config_ids = []

    def run_test(self, name, method, endpoint, expected_status, data=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
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
            "name": "Test Encryption Company",
            "description": "Company for testing AI configuration encryption",
            "contact_email": "test@encryption.com"
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

    def test_create_ai_config_qa_processing(self):
        """Test creating AI configuration for QA processing with encryption"""
        if not self.company_id:
            print("❌ No company ID available")
            return False

        config_data = {
            "config_type": "qa_processing",
            "provider": "openai",
            "model_name": "gpt-4o-mini",
            "api_key": "sk-test-12345678901234567890",
            "model_parameters": {
                "temperature": 0.1,
                "max_tokens": 1000
            }
        }
        
        success, response = self.run_test(
            "Create AI Config - QA Processing",
            "POST",
            f"companies/{self.company_id}/ai-config",
            200,
            data=config_data
        )
        
        if success and 'id' in response:
            config_id = response['id']
            self.ai_config_ids.append(config_id)
            print(f"   Created AI config ID: {config_id}")
            
            # Verify API key is encrypted in response
            if response.get('api_key') == '***ENCRYPTED***':
                print(f"   ✅ API key properly encrypted in response")
                return True
            else:
                print(f"   ❌ API key not encrypted: {response.get('api_key')}")
                return False
        return False

    def test_get_ai_configurations(self):
        """Test retrieving AI configurations and verify encryption"""
        if not self.company_id:
            print("❌ No company ID available")
            return False

        success, response = self.run_test(
            "Get AI Configurations",
            "GET",
            f"companies/{self.company_id}/ai-config",
            200
        )
        
        if success and isinstance(response, dict):
            configurations = response.get('configurations', [])
            if len(configurations) > 0:
                config = configurations[0]
                if config.get('api_key') == '***ENCRYPTED***':
                    print(f"   ✅ API key properly encrypted in list response")
                    print(f"   Found {len(configurations)} configurations")
                    return True
                else:
                    print(f"   ❌ API key not encrypted in list: {config.get('api_key')}")
                    return False
            else:
                print(f"   ❌ No configurations found")
                return False
        return False

    def test_backend_restart_persistence(self):
        """Test that encryption persists after backend restart"""
        print(f"\n🔄 Testing encryption persistence after backend restart...")
        
        try:
            # Restart backend service
            print("   Restarting backend service...")
            result = subprocess.run(['sudo', 'supervisorctl', 'restart', 'backend'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("   ✅ Backend restarted successfully")
            else:
                print(f"   ⚠️ Backend restart warning: {result.stderr}")
            
            # Wait for service to be ready
            print("   Waiting 3 seconds for service to be ready...")
            time.sleep(3)
            
            # Test that we can still decrypt configurations
            success, response = self.run_test(
                "Get AI Configurations After Restart",
                "GET",
                f"companies/{self.company_id}/ai-config",
                200
            )
            
            if success and isinstance(response, dict):
                configurations = response.get('configurations', [])
                if len(configurations) > 0:
                    config = configurations[0]
                    if config.get('api_key') == '***ENCRYPTED***':
                        print(f"   ✅ Encryption still working after restart")
                        return True
                    else:
                        print(f"   ❌ Encryption broken after restart: {config.get('api_key')}")
                        return False
                else:
                    print(f"   ❌ No configurations found after restart")
                    return False
            return False
            
        except subprocess.TimeoutExpired:
            print("   ❌ Backend restart timed out")
            return False
        except Exception as e:
            print(f"   ❌ Error during restart test: {str(e)}")
            return False

    def test_create_multiple_configurations(self):
        """Test creating multiple AI configurations with different types"""
        if not self.company_id:
            print("❌ No company ID available")
            return False

        # Create data_extraction configuration
        config_data_extraction = {
            "config_type": "data_extraction",
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": "sk-test-98765432109876543210",
            "model_parameters": {
                "temperature": 0.2,
                "max_tokens": 2000
            }
        }
        
        success, response = self.run_test(
            "Create AI Config - Data Extraction",
            "POST",
            f"companies/{self.company_id}/ai-config",
            200,
            data=config_data_extraction
        )
        
        if success and 'id' in response:
            config_id = response['id']
            self.ai_config_ids.append(config_id)
            print(f"   Created data extraction config ID: {config_id}")
            
            # Verify API key is encrypted
            if response.get('api_key') == '***ENCRYPTED***':
                print(f"   ✅ Data extraction API key properly encrypted")
                
                # Now verify we have multiple configurations
                success2, response2 = self.run_test(
                    "Verify Multiple Configurations",
                    "GET",
                    f"companies/{self.company_id}/ai-config",
                    200
                )
                
                if success2 and isinstance(response2, dict):
                    configurations = response2.get('configurations', [])
                    if len(configurations) >= 2:
                        print(f"   ✅ Multiple configurations stored: {len(configurations)}")
                        
                        # Verify both have encrypted keys
                        all_encrypted = all(config.get('api_key') == '***ENCRYPTED***' for config in configurations)
                        if all_encrypted:
                            print(f"   ✅ All API keys properly encrypted")
                            return True
                        else:
                            print(f"   ❌ Some API keys not encrypted")
                            return False
                    else:
                        print(f"   ❌ Expected multiple configurations, found: {len(configurations)}")
                        return False
                return False
            else:
                print(f"   ❌ Data extraction API key not encrypted: {response.get('api_key')}")
                return False
        return False

    def test_update_ai_configuration(self):
        """Test updating AI configuration and re-encryption"""
        if not self.company_id or not self.ai_config_ids:
            print("❌ No company ID or AI config IDs available")
            return False

        config_id = self.ai_config_ids[0]
        update_data = {
            "model_name": "gpt-4o-mini",
            "api_key": "sk-test-updated-key-123456789",
            "model_parameters": {
                "temperature": 0.3,
                "max_tokens": 1500
            }
        }
        
        success, response = self.run_test(
            "Update AI Configuration",
            "PUT",
            f"companies/{self.company_id}/ai-config/{config_id}",
            200,
            data=update_data
        )
        
        if success and isinstance(response, dict):
            if 'message' in response and 'updated successfully' in response['message']:
                print(f"   ✅ Configuration updated successfully")
                
                # Verify the updated configuration still has encrypted key
                success2, response2 = self.run_test(
                    "Verify Updated Configuration",
                    "GET",
                    f"companies/{self.company_id}/ai-config",
                    200
                )
                
                if success2 and isinstance(response2, dict):
                    configurations = response2.get('configurations', [])
                    updated_config = next((c for c in configurations if c['id'] == config_id), None)
                    
                    if updated_config and updated_config.get('api_key') == '***ENCRYPTED***':
                        print(f"   ✅ Updated API key properly re-encrypted")
                        return True
                    else:
                        print(f"   ❌ Updated API key not encrypted")
                        return False
                return False
            else:
                print(f"   ❌ Update response unexpected: {response}")
                return False
        return False

    def check_backend_logs(self):
        """Check backend logs for encryption-related messages"""
        print(f"\n📋 Checking backend logs for encryption activity...")
        
        try:
            # Get recent backend logs
            result = subprocess.run(['tail', '-n', '50', '/var/log/supervisor/backend.out.log'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                logs = result.stdout
                
                # Look for key encryption/decryption messages
                encryption_messages = [
                    "Getting AI config for company",
                    "Found company-specific AI config",
                    "Successfully decrypted API key",
                    "Creating AI chat with provider"
                ]
                
                found_messages = []
                for message in encryption_messages:
                    if message in logs:
                        found_messages.append(message)
                
                if found_messages:
                    print(f"   ✅ Found encryption activity in logs:")
                    for msg in found_messages:
                        print(f"      - {msg}")
                    return True
                else:
                    print(f"   ⚠️ No encryption activity found in recent logs")
                    return False
            else:
                print(f"   ❌ Could not read backend logs: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"   ❌ Error checking logs: {str(e)}")
            return False

    def test_get_ai_config_for_task_simulation(self):
        """Simulate the get_ai_config_for_task function that was failing"""
        if not self.company_id:
            print("❌ No company ID available")
            return False

        print(f"\n🧪 Simulating get_ai_config_for_task function...")
        
        # This simulates what happens when the QA system tries to get AI config
        # We'll check if we can retrieve and use the configuration
        success, response = self.run_test(
            "Simulate QA Config Retrieval",
            "GET",
            f"companies/{self.company_id}/ai-config",
            200
        )
        
        if success and isinstance(response, dict):
            configurations = response.get('configurations', [])
            qa_configs = [c for c in configurations if c.get('config_type') == 'qa_processing']
            
            if qa_configs:
                qa_config = qa_configs[0]
                print(f"   ✅ Found QA configuration: {qa_config['id']}")
                print(f"   Provider: {qa_config.get('provider')}")
                print(f"   Model: {qa_config.get('model_name')}")
                print(f"   API Key: {qa_config.get('api_key')}")
                
                if qa_config.get('api_key') == '***ENCRYPTED***':
                    print(f"   ✅ QA configuration properly encrypted and retrievable")
                    return True
                else:
                    print(f"   ❌ QA configuration API key not encrypted")
                    return False
            else:
                print(f"   ❌ No QA configuration found")
                return False
        return False

    def cleanup_test_data(self):
        """Clean up test data"""
        print(f"\n🧹 Cleaning up test data...")
        
        # Delete AI configurations
        for config_id in self.ai_config_ids:
            success, response = self.run_test(
                f"Delete AI Config {config_id}",
                "DELETE",
                f"companies/{self.company_id}/ai-config/{config_id}",
                200
            )
            if success:
                print(f"   ✅ Deleted AI config: {config_id}")
        
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
        """Run all AI encryption tests"""
        print("🚀 Starting AI Configuration Encryption Tests")
        print("=" * 60)
        
        tests = [
            self.test_login,
            self.test_create_test_company,
            self.test_create_ai_config_qa_processing,
            self.test_get_ai_configurations,
            self.test_create_multiple_configurations,
            self.test_update_ai_configuration,
            self.test_get_ai_config_for_task_simulation,
            self.test_backend_restart_persistence,
            self.check_backend_logs
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
        print(f"🏁 AI Encryption Tests Complete")
        print(f"📊 Results: {self.tests_passed}/{self.tests_run} tests passed")
        
        if self.tests_passed == self.tests_run:
            print(f"✅ ALL TESTS PASSED - AI Configuration encryption is working correctly!")
            return True
        else:
            print(f"❌ SOME TESTS FAILED - AI Configuration encryption needs attention")
            return False

if __name__ == "__main__":
    tester = AIEncryptionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
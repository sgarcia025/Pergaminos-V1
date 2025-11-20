#!/usr/bin/env python3
"""
Phase 1 Focused Testing Script for Pergaminos API
Tests the specific Phase 1 functionality requested in the review.
"""

import requests
import sys
import json
from datetime import datetime
import time

class Phase1Tester:
    def __init__(self, base_url="https://paperflow-33.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.token = None
        self.user = None
        self.tests_run = 0
        self.tests_passed = 0

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

    def login_admin(self):
        """Login as admin"""
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

    def test_phase1_user_deletion(self):
        """Test Phase 1 User Deletion Features"""
        print("\n" + "="*60)
        print("🧪 PHASE 1 - USER DELETION TESTING")
        print("="*60)
        
        results = []
        
        # 1. Create asesor user
        asesor_data = {
            "email": f"asesor_test_{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "Test Asesor Comercial",
            "password": "asesor123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create Asesor User",
            "POST",
            "auth/register",
            200,
            data=asesor_data
        )
        
        if success and 'id' in response:
            asesor_id = response['id']
            results.append(("Create Asesor User", True))
            
            # 2. Test self-deletion prevention
            success, response = self.run_test(
                "Prevent Self-Deletion",
                "DELETE",
                f"users/{self.user['id']}",
                400
            )
            results.append(("Prevent Self-Deletion", success))
            
            # 3. Create company with asesor assignment
            company_data = {
                "name": f"Test Company {datetime.now().strftime('%H%M%S')}",
                "razon_social": "Test Company S.A.S.",
                "nit": "123456789-0",
                "contacto": "Juan Pérez",
                "telefono": "+57 300 123 4567",
                "direccion": "Calle 123 #45-67, Bogotá",
                "asesor_comercial_id": asesor_id,
                "segmento": "Tecnología",
                "estado": "Activo"
            }
            
            success, response = self.run_test(
                "Create Company with Asesor Assignment",
                "POST",
                "companies",
                200,
                data=company_data
            )
            
            if success and 'id' in response:
                company_id = response['id']
                results.append(("Create Company with Asesor", True))
                
                # 4. Try to delete asesor with assignment (should fail)
                success, response = self.run_test(
                    "Delete Asesor with Assignment (Should Fail)",
                    "DELETE",
                    f"users/{asesor_id}",
                    400
                )
                results.append(("Prevent Asesor Deletion with Assignment", success))
                
                # 5. Remove assignment by deleting company
                success, response = self.run_test(
                    "Remove Assignment (Delete Company)",
                    "DELETE",
                    f"companies/{company_id}",
                    200
                )
                results.append(("Remove Assignment", success))
                
                # 6. Now delete asesor (should work)
                success, response = self.run_test(
                    "Delete Asesor After Reassignment",
                    "DELETE",
                    f"users/{asesor_id}",
                    200
                )
                results.append(("Delete Asesor After Reassignment", success))
            else:
                results.append(("Create Company with Asesor", False))
        else:
            results.append(("Create Asesor User", False))
        
        return results

    def test_phase1_expanded_company_model(self):
        """Test Phase 1 Expanded Company Model"""
        print("\n" + "="*60)
        print("🧪 PHASE 1 - EXPANDED COMPANY MODEL TESTING")
        print("="*60)
        
        results = []
        
        # 1. Create segmento first
        segmento_data = {
            "nombre": f"Segmento Test {datetime.now().strftime('%H%M%S')}",
            "descripcion": "Segmento para pruebas"
        }
        
        success, response = self.run_test(
            "Create Segmento",
            "POST",
            "segmentos",
            200,
            data=segmento_data
        )
        
        if success and 'id' in response:
            segmento_id = response['id']
            results.append(("Create Segmento", True))
            
            # 2. Create asesor for assignment
            asesor_data = {
                "email": f"asesor_company_{datetime.now().strftime('%H%M%S')}@pergaminos.com",
                "name": "Asesor for Company Test",
                "password": "asesor123",
                "role": "asesor"
            }
            
            success, response = self.run_test(
                "Create Asesor for Company",
                "POST",
                "auth/register",
                200,
                data=asesor_data
            )
            
            if success and 'id' in response:
                asesor_id = response['id']
                results.append(("Create Asesor for Company", True))
                
                # 3. Create company with all new fields
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
                    # Verify all fields were saved
                    all_fields_correct = (
                        response.get('razon_social') == company_data['razon_social'] and
                        response.get('nit') == company_data['nit'] and
                        response.get('contacto') == company_data['contacto'] and
                        response.get('telefono') == company_data['telefono'] and
                        response.get('direccion') == company_data['direccion'] and
                        response.get('asesor_comercial_id') == company_data['asesor_comercial_id'] and
                        response.get('segmento') == company_data['segmento'] and
                        response.get('estado') == company_data['estado'] and
                        response.get('corporacion') == company_data['corporacion']
                    )
                    
                    if all_fields_correct:
                        print("   ✅ All new fields saved correctly")
                        results.append(("Create Company with All New Fields", True))
                    else:
                        print("   ❌ Some fields not saved correctly")
                        results.append(("Create Company with All New Fields", False))
                        
                    # Clean up
                    self.run_test("Cleanup Company", "DELETE", f"companies/{response['id']}", 200)
                    self.run_test("Cleanup Asesor", "DELETE", f"users/{asesor_id}", 200)
                else:
                    results.append(("Create Company with All New Fields", False))
            else:
                results.append(("Create Asesor for Company", False))
                
            # Clean up segmento
            self.run_test("Cleanup Segmento", "DELETE", f"segmentos/{segmento_id}", 200)
        else:
            results.append(("Create Segmento", False))
        
        return results

    def test_phase1_asesor_role(self):
        """Test Phase 1 Asesor Role Functionality"""
        print("\n" + "="*60)
        print("🧪 PHASE 1 - ASESOR ROLE FUNCTIONALITY TESTING")
        print("="*60)
        
        results = []
        
        # 1. Create asesor user
        asesor_data = {
            "email": f"asesor_role_{datetime.now().strftime('%H%M%S')}@pergaminos.com",
            "name": "Asesor Role Test",
            "password": "asesor123",
            "role": "asesor"
        }
        
        success, response = self.run_test(
            "Create Asesor for Role Test",
            "POST",
            "auth/register",
            200,
            data=asesor_data
        )
        
        if success and 'id' in response:
            asesor_id = response['id']
            results.append(("Create Asesor for Role Test", True))
            
            # 2. Create company assigned to this asesor
            company_data = {
                "name": f"Asesor Company {datetime.now().strftime('%H%M%S')}",
                "razon_social": "Asesor Company S.A.S.",
                "asesor_comercial_id": asesor_id,
                "segmento": "Servicios"
            }
            
            success, response = self.run_test(
                "Create Company for Asesor",
                "POST",
                "companies",
                200,
                data=company_data
            )
            
            if success and 'id' in response:
                company_id = response['id']
                results.append(("Create Company for Asesor", True))
                
                # 3. Login as asesor
                admin_token = self.token
                success, response = self.run_test(
                    "Asesor Login",
                    "POST",
                    "auth/login",
                    200,
                    data={"email": asesor_data['email'], "password": asesor_data['password']}
                )
                
                if success and 'access_token' in response:
                    self.token = response['access_token']
                    results.append(("Asesor Login", True))
                    
                    # 4. Test that asesor only sees assigned companies
                    success, response = self.run_test(
                        "Asesor Get Companies (Only Assigned)",
                        "GET",
                        "companies",
                        200
                    )
                    
                    if success and isinstance(response, list):
                        # Should only see companies assigned to this asesor
                        assigned_companies = [comp for comp in response if comp.get('asesor_comercial_id') == asesor_id]
                        if len(response) == len(assigned_companies) and len(response) >= 1:
                            print(f"   ✅ Asesor correctly sees only assigned companies: {len(response)}")
                            results.append(("Asesor Sees Only Assigned Companies", True))
                        else:
                            print(f"   ❌ Asesor permission issue: saw {len(response)} companies")
                            results.append(("Asesor Sees Only Assigned Companies", False))
                    else:
                        results.append(("Asesor Sees Only Assigned Companies", False))
                    
                    # 5. Test access to specific company detail
                    success, response = self.run_test(
                        "Asesor Access Assigned Company Detail",
                        "GET",
                        f"companies/{company_id}",
                        200
                    )
                    results.append(("Asesor Access Assigned Company Detail", success))
                    
                    # Restore admin token
                    self.token = admin_token
                else:
                    results.append(("Asesor Login", False))
                    self.token = admin_token
                
                # Clean up
                self.run_test("Cleanup Asesor Company", "DELETE", f"companies/{company_id}", 200)
            else:
                results.append(("Create Company for Asesor", False))
                
            self.run_test("Cleanup Asesor User", "DELETE", f"users/{asesor_id}", 200)
        else:
            results.append(("Create Asesor for Role Test", False))
        
        return results

    def test_phase1_segment_management(self):
        """Test Phase 1 Segment Management"""
        print("\n" + "="*60)
        print("🧪 PHASE 1 - SEGMENT MANAGEMENT TESTING")
        print("="*60)
        
        results = []
        
        # 1. Create segmento
        segmento_data = {
            "nombre": f"Segmento Management Test {datetime.now().strftime('%H%M%S')}",
            "descripcion": "Segmento para pruebas de gestión"
        }
        
        success, response = self.run_test(
            "Create Segmento",
            "POST",
            "segmentos",
            200,
            data=segmento_data
        )
        
        if success and 'id' in response:
            segmento_id = response['id']
            results.append(("Create Segmento", True))
            
            # 2. Get segmentos list
            success, response = self.run_test(
                "Get Segmentos List",
                "GET",
                "segmentos",
                200
            )
            
            if success and isinstance(response, list):
                # Verify all are active
                active_segmentos = [seg for seg in response if seg.get('is_active') == True]
                if len(response) == len(active_segmentos):
                    print(f"   ✅ All {len(response)} segmentos are active")
                    results.append(("Get Active Segmentos", True))
                else:
                    results.append(("Get Active Segmentos", False))
            else:
                results.append(("Get Active Segmentos", False))
            
            # 3. Create company using this segmento
            company_data = {
                "name": f"Company with Segmento {datetime.now().strftime('%H%M%S')}",
                "segmento": segmento_id
            }
            
            success, response = self.run_test(
                "Create Company Using Segmento",
                "POST",
                "companies",
                200,
                data=company_data
            )
            
            if success and 'id' in response:
                company_id = response['id']
                results.append(("Create Company Using Segmento", True))
                
                # 4. Try to delete segmento in use (should fail)
                success, response = self.run_test(
                    "Delete Segmento In Use (Should Fail)",
                    "DELETE",
                    f"segmentos/{segmento_id}",
                    400
                )
                results.append(("Prevent Deletion of Segmento In Use", success))
                
                # 5. Delete company to free up segmento
                success, response = self.run_test(
                    "Delete Company to Free Segmento",
                    "DELETE",
                    f"companies/{company_id}",
                    200
                )
                results.append(("Delete Company to Free Segmento", success))
            else:
                results.append(("Create Company Using Segmento", False))
            
            # 6. Now delete unused segmento (should work)
            success, response = self.run_test(
                "Delete Unused Segmento",
                "DELETE",
                f"segmentos/{segmento_id}",
                200
            )
            results.append(("Delete Unused Segmento", success))
        else:
            results.append(("Create Segmento", False))
        
        return results

    def test_phase1_asesores_list(self):
        """Test Phase 1 Asesores List Functionality"""
        print("\n" + "="*60)
        print("🧪 PHASE 1 - ASESORES LIST TESTING")
        print("="*60)
        
        results = []
        
        # 1. Get asesores list (staff only)
        success, response = self.run_test(
            "Get Asesores List (Staff)",
            "GET",
            "users/asesores",
            200
        )
        
        if success and isinstance(response, list):
            # Verify all are asesor role and active
            asesor_users = [user for user in response if user.get('role') == 'asesor' and user.get('is_active') == True]
            if len(response) == len(asesor_users):
                print(f"   ✅ Found {len(response)} active asesor users")
                results.append(("Get Asesores List (Staff)", True))
            else:
                print(f"   ❌ Some non-asesor or inactive users returned")
                results.append(("Get Asesores List (Staff)", False))
        else:
            results.append(("Get Asesores List (Staff)", False))
        
        # 2. Test client cannot access asesores list
        admin_token = self.token
        success, response = self.run_test(
            "Client Login for Asesores Test",
            "POST",
            "auth/login",
            200,
            data={"email": "cliente@empresademo.com", "password": "cliente123"}
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            results.append(("Client Login for Asesores Test", True))
            
            # Try to get asesores as client (should fail)
            success, response = self.run_test(
                "Client Get Asesores (Should Fail)",
                "GET",
                "users/asesores",
                403
            )
            results.append(("Prevent Client Access to Asesores", success))
            
            # Restore admin token
            self.token = admin_token
        else:
            results.append(("Client Login for Asesores Test", False))
            results.append(("Prevent Client Access to Asesores", False))
        
        return results

def main():
    print("🧪 PHASE 1 FOCUSED TESTING - PERGAMINOS API")
    print("Testing specific Phase 1 functionality as requested")
    print("=" * 80)
    
    tester = Phase1Tester()
    
    # Login as admin
    if not tester.login_admin():
        print("❌ Admin login failed, stopping tests")
        return 1
    
    # Run Phase 1 tests
    all_results = []
    
    # Test 1: User Deletion
    user_deletion_results = tester.test_phase1_user_deletion()
    all_results.extend(user_deletion_results)
    
    # Test 2: Expanded Company Model
    company_model_results = tester.test_phase1_expanded_company_model()
    all_results.extend(company_model_results)
    
    # Test 3: Asesor Role Functionality
    asesor_role_results = tester.test_phase1_asesor_role()
    all_results.extend(asesor_role_results)
    
    # Test 4: Segment Management
    segment_mgmt_results = tester.test_phase1_segment_management()
    all_results.extend(segment_mgmt_results)
    
    # Test 5: Asesores List
    asesores_list_results = tester.test_phase1_asesores_list()
    all_results.extend(asesores_list_results)
    
    # Print final results
    print("\n" + "=" * 80)
    print("📊 PHASE 1 TEST RESULTS SUMMARY")
    print("=" * 80)
    
    categories = {
        "User Deletion": ["Create Asesor User", "Prevent Self-Deletion", "Create Company with Asesor", 
                         "Prevent Asesor Deletion with Assignment", "Remove Assignment", "Delete Asesor After Reassignment"],
        "Expanded Company Model": ["Create Segmento", "Create Asesor for Company", "Create Company with All New Fields"],
        "Asesor Role Functionality": ["Create Asesor for Role Test", "Create Company for Asesor", "Asesor Login", 
                                    "Asesor Sees Only Assigned Companies", "Asesor Access Assigned Company Detail"],
        "Segment Management": ["Create Segmento", "Get Active Segmentos", "Create Company Using Segmento", 
                             "Prevent Deletion of Segmento In Use", "Delete Company to Free Segmento", "Delete Unused Segmento"],
        "Asesores List": ["Get Asesores List (Staff)", "Client Login for Asesores Test", "Prevent Client Access to Asesores"]
    }
    
    total_passed = 0
    total_tests = 0
    
    for category, test_names in categories.items():
        print(f"\n📋 {category}:")
        category_passed = 0
        category_total = 0
        
        for test_name, result in all_results:
            if test_name in test_names:
                category_total += 1
                total_tests += 1
                if result:
                    category_passed += 1
                    total_passed += 1
                    print(f"   ✅ {test_name}")
                else:
                    print(f"   ❌ {test_name}")
        
        if category_total > 0:
            print(f"   📊 {category_passed}/{category_total} passed")
    
    print(f"\n📈 OVERALL PHASE 1 SUMMARY: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print(f"\n🎉 ALL PHASE 1 TESTS PASSED! Phase 1 functionality is working correctly.")
        return 0
    else:
        failed_count = total_tests - total_passed
        print(f"\n⚠️  {failed_count} tests failed. Phase 1 functionality needs attention.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
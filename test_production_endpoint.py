#!/usr/bin/env python3
"""
Script de diagnóstico para probar endpoints de producción
Ejecutar: python3 test_production_endpoint.py
"""

import requests
import json

# CONFIGURAR TU URL DE PRODUCCIÓN
BACKEND_URL = "https://digitaldocs-replaced-1763169316.emergent.host/api"
# O la URL que uses en producción

# Credenciales de admin
EMAIL = "admin@pergaminos.com"
PASSWORD = "admin123"

print("=" * 60)
print("DIAGNÓSTICO DE PRODUCCIÓN")
print("=" * 60)

# 1. Test de login
print("\n1. Probando login...")
try:
    response = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        token = response.json().get("access_token")
        print(f"   ✅ Login exitoso")
        print(f"   Token (primeros 20 chars): {token[:20]}...")
    else:
        print(f"   ❌ Login falló: {response.text}")
        exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 2. Test GET /api/users
print("\n2. Probando GET /api/users...")
try:
    response = requests.get(
        f"{BACKEND_URL}/users",
        headers=headers,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        users = response.json()
        print(f"   ✅ Usuarios cargados: {len(users)}")
        if users:
            print(f"   Primer usuario: {users[0].get('email')}")
    else:
        print(f"   ❌ Error {response.status_code}")
        print(f"   Response: {response.text[:500]}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

# 3. Test GET /api/companies
print("\n3. Probando GET /api/companies...")
try:
    response = requests.get(
        f"{BACKEND_URL}/companies",
        headers=headers,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        companies = response.json()
        print(f"   ✅ Empresas cargadas: {len(companies)}")
    else:
        print(f"   ❌ Error {response.status_code}")
        print(f"   Response: {response.text[:500]}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

# 4. Test de user info
print("\n4. Probando GET /api/auth/me...")
try:
    response = requests.get(
        f"{BACKEND_URL}/auth/me",
        headers=headers,
        timeout=10
    )
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        user = response.json()
        print(f"   ✅ User info obtenida")
        print(f"   Email: {user.get('email')}")
        print(f"   Role: {user.get('role')}")
        print(f"   company_ids: {user.get('company_ids')}")
        print(f"   assigned_corporation: {user.get('assigned_corporation')}")
    else:
        print(f"   ❌ Error {response.status_code}")
        print(f"   Response: {response.text[:500]}")
except Exception as e:
    print(f"   ❌ Exception: {e}")

print("\n" + "=" * 60)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 60)

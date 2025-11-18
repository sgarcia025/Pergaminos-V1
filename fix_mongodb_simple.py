#!/usr/bin/env python3
"""
Script SIMPLE para arreglar MongoDB - versión sincrónica
NO requiere motor, solo pymongo
"""

from pymongo import MongoClient
import os

# Tu MONGO_URL de producción
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/pergaminos')

print("=" * 60)
print("ARREGLANDO USUARIOS EN MONGODB")
print("=" * 60)

# Conectar
client = MongoClient(MONGO_URL)
db = client.get_database()

print(f"\n✓ Conectado a MongoDB")

# Contar usuarios sin campos
users_without = db.users.count_documents({
    "$or": [
        {"company_ids": {"$exists": False}},
        {"assigned_corporation": {"$exists": False}}
    ]
})

print(f"✓ Usuarios que necesitan actualización: {users_without}")

if users_without == 0:
    print("\n✅ Todos los usuarios ya tienen los campos!")
    exit(0)

# Actualizar
r1 = db.users.update_many(
    {"company_ids": {"$exists": False}},
    {"$set": {"company_ids": []}}
)
print(f"✓ Agregado company_ids=[] a {r1.modified_count} usuarios")

r2 = db.users.update_many(
    {"assigned_corporation": {"$exists": False}},
    {"$set": {"assigned_corporation": None}}
)
print(f"✓ Agregado assigned_corporation=None a {r2.modified_count} usuarios")

# Verificar
total = db.users.count_documents({})
fixed = db.users.count_documents({
    "company_ids": {"$exists": True},
    "assigned_corporation": {"$exists": True}
})

print(f"\n✅ COMPLETADO:")
print(f"   Total: {total} usuarios")
print(f"   Arreglados: {fixed} usuarios")

if fixed == total:
    print("\n🎉 ¡LISTO! Ahora recarga tu app")

client.close()

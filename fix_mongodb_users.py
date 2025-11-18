#!/usr/bin/env python3
"""
Script para arreglar usuarios en MongoDB agregando campos faltantes
Ejecutar en el servidor de producción donde está MongoDB
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

# CONFIGURAR TU MONGO_URL DE PRODUCCIÓN
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/pergaminos')

async def fix_users():
    """Agrega campos faltantes a todos los usuarios"""
    print("=" * 60)
    print("ARREGLANDO USUARIOS EN MONGODB")
    print("=" * 60)
    
    # Conectar a MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client.get_database()
    
    print(f"\n✓ Conectado a MongoDB")
    
    # Contar usuarios sin los campos nuevos
    users_without_fields = await db.users.count_documents({
        "$or": [
            {"company_ids": {"$exists": False}},
            {"assigned_corporation": {"$exists": False}}
        ]
    })
    
    print(f"✓ Usuarios que necesitan actualización: {users_without_fields}")
    
    if users_without_fields == 0:
        print("\n✅ Todos los usuarios ya tienen los campos necesarios!")
        return
    
    # Actualizar todos los usuarios que no tienen company_ids
    result1 = await db.users.update_many(
        {"company_ids": {"$exists": False}},
        {"$set": {"company_ids": []}}
    )
    print(f"✓ Agregado company_ids=[] a {result1.modified_count} usuarios")
    
    # Actualizar todos los usuarios que no tienen assigned_corporation
    result2 = await db.users.update_many(
        {"assigned_corporation": {"$exists": False}},
        {"$set": {"assigned_corporation": None}}
    )
    print(f"✓ Agregado assigned_corporation=None a {result2.modified_count} usuarios")
    
    # Verificar
    all_users = await db.users.count_documents({})
    fixed_users = await db.users.count_documents({
        "company_ids": {"$exists": True},
        "assigned_corporation": {"$exists": True}
    })
    
    print(f"\n✅ COMPLETADO:")
    print(f"   Total usuarios: {all_users}")
    print(f"   Usuarios arreglados: {fixed_users}")
    
    if fixed_users == all_users:
        print("\n🎉 ¡TODOS LOS USUARIOS ESTÁN ARREGLADOS!")
        print("   Ahora puedes recargar la aplicación")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_users())

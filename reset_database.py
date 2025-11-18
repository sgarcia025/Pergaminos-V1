#!/usr/bin/env python3
"""
Script para LIMPIAR la base de datos y empezar de cero
Mantiene solo el usuario admin@pergaminos.com
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

async def reset_database():
    print("=" * 60)
    print("⚠️  LIMPIANDO BASE DE DATOS")
    print("=" * 60)
    
    # Conectar a MongoDB
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    db = client.pergaminos  # Nombre de tu BD
    
    print(f"\n✓ Conectado a MongoDB")
    
    # 1. Contar antes de borrar
    users_count = await db.users.count_documents({})
    companies_count = await db.companies.count_documents({})
    projects_count = await db.projects.count_documents({})
    documents_count = await db.documents.count_documents({})
    
    print(f"\n📊 Estado actual:")
    print(f"   Usuarios: {users_count}")
    print(f"   Empresas: {companies_count}")
    print(f"   Proyectos: {projects_count}")
    print(f"   Documentos: {documents_count}")
    
    # 2. Borrar usuarios (excepto admin@pergaminos.com)
    result = await db.users.delete_many({
        "email": {"$ne": "admin@pergaminos.com"}
    })
    print(f"\n✓ Borrados {result.deleted_count} usuarios (manteniendo admin@pergaminos.com)")
    
    # 3. Borrar todas las empresas
    result = await db.companies.delete_many({})
    print(f"✓ Borradas {result.deleted_count} empresas")
    
    # 4. Borrar todos los proyectos
    result = await db.projects.delete_many({})
    print(f"✓ Borrados {result.deleted_count} proyectos")
    
    # 5. Borrar todos los documentos
    result = await db.documents.delete_many({})
    print(f"✓ Borrados {result.deleted_count} documentos")
    
    # 6. Borrar historial de PDFs
    result = await db.pdf_history.delete_many({})
    print(f"✓ Borrado historial de PDFs: {result.deleted_count} entradas")
    
    # 7. Borrar QA agents
    result = await db.qa_agents.delete_many({})
    print(f"✓ Borrados {result.deleted_count} agentes QA")
    
    # 8. Borrar segmentos
    result = await db.segmentos.delete_many({})
    print(f"✓ Borrados {result.deleted_count} segmentos")
    
    # 9. Actualizar el usuario admin para asegurar que tenga los campos nuevos
    await db.users.update_one(
        {"email": "admin@pergaminos.com"},
        {
            "$set": {
                "company_ids": [],
                "assigned_corporation": None
            }
        }
    )
    print(f"✓ Usuario admin actualizado con campos nuevos")
    
    # 10. Verificar estado final
    users_final = await db.users.count_documents({})
    companies_final = await db.companies.count_documents({})
    
    print(f"\n✅ LIMPIEZA COMPLETADA:")
    print(f"   Usuarios restantes: {users_final} (solo admin)")
    print(f"   Empresas restantes: {companies_final}")
    
    admin_user = await db.users.find_one({"email": "admin@pergaminos.com"})
    if admin_user:
        print(f"\n👤 Usuario admin preservado:")
        print(f"   Email: {admin_user.get('email')}")
        print(f"   Nombre: {admin_user.get('name')}")
        print(f"   Role: {admin_user.get('role')}")
        print(f"   company_ids: {admin_user.get('company_ids', 'N/A')}")
        print(f"   assigned_corporation: {admin_user.get('assigned_corporation', 'N/A')}")
    
    print(f"\n🎉 BASE DE DATOS LIMPIA!")
    print(f"   Ahora puedes crear nuevas empresas y usuarios sin problemas")
    
    client.close()

if __name__ == "__main__":
    print("\n⚠️  ADVERTENCIA: Este script borrará TODOS los datos")
    print("   excepto el usuario admin@pergaminos.com")
    print("\n¿Estás seguro? (escribe 'SI' para continuar)")
    
    confirm = input("\n> ")
    
    if confirm.strip().upper() == "SI":
        asyncio.run(reset_database())
    else:
        print("\n❌ Operación cancelada")

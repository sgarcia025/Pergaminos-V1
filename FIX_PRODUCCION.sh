#!/bin/bash
# Script para arreglar MongoDB en producción (Emergent)
# Ejecutar en el terminal de la plataforma Emergent

echo "============================================================"
echo "ARREGLANDO BASE DE DATOS - MongoDB"
echo "============================================================"

# Ejecutar comando MongoDB directamente
mongo $MONGO_URL --eval '
db = db.getSiblingDB("pergaminos");

print("\n✓ Conectado a MongoDB");

// Contar usuarios sin campos
var usersWithout = db.users.count({
    $or: [
        {"company_ids": {$exists: false}},
        {"assigned_corporation": {$exists: false}}
    ]
});

print("✓ Usuarios que necesitan actualización: " + usersWithout);

if (usersWithout === 0) {
    print("\n✅ Todos los usuarios ya tienen los campos!");
    quit(0);
}

// Actualizar usuarios sin company_ids
var r1 = db.users.updateMany(
    {"company_ids": {$exists: false}},
    {$set: {"company_ids": []}}
);
print("✓ Agregado company_ids=[] a " + r1.modifiedCount + " usuarios");

// Actualizar usuarios sin assigned_corporation  
var r2 = db.users.updateMany(
    {"assigned_corporation": {$exists: false}},
    {$set: {"assigned_corporation": null}}
);
print("✓ Agregado assigned_corporation=null a " + r2.modifiedCount + " usuarios");

// Verificar
var total = db.users.count();
var fixed = db.users.count({
    "company_ids": {$exists: true},
    "assigned_corporation": {$exists: true}
});

print("\n✅ COMPLETADO:");
print("   Total: " + total + " usuarios");
print("   Arreglados: " + fixed + " usuarios");

if (fixed === total) {
    print("\n🎉 ¡LISTO! Ahora recarga tu aplicación");
}
'

echo ""
echo "============================================================"
echo "Reiniciando backend..."
echo "============================================================"
sudo supervisorctl restart backend
echo "✓ Backend reiniciado"
echo ""
echo "Ahora recarga tu navegador con Ctrl+Shift+R"

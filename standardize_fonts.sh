#!/bin/bash

# Script para estandarizar todas las fuentes a Inter

echo "🔄 Eliminando referencias a Playfair Display en archivos JS..."
find /app/frontend/src/components -name "*.js" -type f -exec sed -i \
  -e "s/style={{ fontFamily: 'Playfair Display' }}//g" \
  -e "s/fontFamily: 'Playfair Display'//g" \
  -e "s/, fontFamily: 'Playfair Display', serif//g" \
  -e "s/font-family: 'Playfair Display', serif;//g" \
  {} \;

echo "🔄 Actualizando App.css..."
sed -i "s/font-family: 'Playfair Display', serif;/font-family: 'Inter', sans-serif;/g" /app/frontend/src/App.css

echo "✅ Estandarización de fuentes completada!"
echo "✅ Todas las fuentes ahora usan Inter"

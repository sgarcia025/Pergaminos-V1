#!/bin/bash

# Script para reemplazar colores emerald con la paleta de ePergaminos

# Colores a reemplazar:
# emerald-600 (#059669) -> gold (#D4A61D) 
# emerald-700 (#047857) -> gold-dark (#B8901A)
# emerald-500 (#10b981) -> gold-light (#E8C54D)
# emerald-50 (#ecfdf5) -> gold-light background (#FFF8E7)
# emerald-100 (#d1fae5) -> gold-lighter (#FFF4D6)

find /app/frontend/src/components -name "*.js" -type f -exec sed -i \
  -e 's/bg-emerald-600/bg-yellow-600/g' \
  -e 's/text-emerald-600/text-yellow-700/g' \
  -e 's/hover:bg-emerald-700/hover:bg-yellow-700/g' \
  -e 's/border-emerald-600/border-yellow-600/g' \
  -e 's/emerald-600/yellow-600/g' \
  -e 's/emerald-700/yellow-700/g' \
  -e 's/emerald-500/yellow-500/g' \
  -e 's/emerald-50/yellow-50/g' \
  -e 's/emerald-100/yellow-100/g' \
  -e 's/emerald-200/yellow-200/g' \
  -e 's/emerald-300/yellow-300/g' \
  -e 's/emerald-400/yellow-400/g' \
  -e 's/emerald-800/yellow-800/g' \
  -e 's/emerald-900/yellow-900/g' \
  {} \;

echo "✅ Colores reemplazados en todos los componentes"

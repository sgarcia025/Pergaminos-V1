# Instrucciones para Resolver Errores de OCR en Deployment

## Problema
El OCR (tanto Tesseract como GPT-4o Vision) falla con el error:
```
Unable to get page count. Is poppler installed and in PATH?
```

## Causa
Las dependencias de sistema (poppler-utils, tesseract-ocr) NO están instaladas en el contenedor de deployment.

## Solución

### Opción 1: Ejecutar script de instalación (Recomendado)
Si tienes acceso al contenedor deployado:

```bash
# Ejecutar el script de instalación
bash /app/install-ocr-deps.sh
```

### Opción 2: Instalación manual
Si prefieres instalar manualmente:

```bash
# Actualizar repositorios
apt-get update

# Instalar dependencias
apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng

# Verificar instalación
pdfinfo -v
tesseract --version
tesseract --list-langs
```

### Opción 3: Configuración permanente en Dockerfile
Para que las dependencias persistan en futuros deploys, agrega esto al Dockerfile:

```dockerfile
# Install OCR system dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
```

## Verificación
Después de instalar, verifica que funcione:

```bash
# Verificar poppler
which pdfinfo
pdfinfo -v

# Verificar tesseract
which tesseract
tesseract --version
tesseract --list-langs
```

Deberías ver:
- pdfinfo: /usr/bin/pdfinfo
- tesseract: /usr/bin/tesseract
- Languages: eng, osd, spa

## Reiniciar servicios
Después de instalar las dependencias:

```bash
# Reiniciar backend para que tome las nuevas dependencias
sudo supervisorctl restart backend
```

## Notas
- Estas dependencias son necesarias para convertir PDFs a imágenes (poppler) y extraer texto con OCR (tesseract)
- Sin ellas, solo funcionará la extracción normal de PDFs con texto incrustado
- Los PDFs escaneados o sin texto NO se procesarán correctamente sin estas dependencias

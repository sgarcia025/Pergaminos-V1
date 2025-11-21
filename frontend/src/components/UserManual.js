import React, { useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const UserManual = () => {
  const [activeSection, setActiveSection] = useState('intro');
  const [chatQuestion, setChatQuestion] = useState('');
  const [chatAnswer, setChatAnswer] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState('');

  const sections = [
    {
      id: 'intro',
      title: '📘 Introducción',
      content: `Bienvenido al Manual de Usuario del Sistema Pergaminos - Digitalización Inteligente.
      
Este sistema está diseñado para gestionar empresas, proyectos de digitalización y el procesamiento inteligente de documentos PDF usando IA.`
    },
    {
      id: 'dashboard',
      title: '📊 Dashboard',
      content: `Vista general del sistema que muestra estadísticas clave:

• Número total de empresas
• Proyectos activos
• Documentos totales procesados
• Documentos en proceso
• Documentos fallidos
• Revisión de QA pendiente
• QA aprobados y fallidos

**Nuevo: Filtros de fecha**
• Filtra estadísticas por rango de fechas
• Haz clic en las cards de estado para filtrar proyectos

Proporciona accesos rápidos a las funciones principales del sistema.`
    },
    {
      id: 'empresas',
      title: '🏢 Empresas',
      content: `Módulo de gestión de empresas cliente.

**Funciones principales:**
• Crear nuevas empresas
• Editar información de empresas existentes
• Ver proyectos asociados a cada empresa
• Filtrar por corporación y estado (Activa/Inactiva)

**Campos disponibles:**
• Nombre de la empresa
• **Múltiples contactos** (nombre, email, teléfono)
• Asesor comercial asignado
• Segmento/Industria
• Corporación
• Dirección

**Gestión de contactos:**
• Agrega varios contactos por empresa
• Cada contacto tiene: nombre, email y teléfono (+502)
• Edita o elimina contactos fácilmente

⚠️ **Importante:** Las empresas inactivas no permiten el login de sus usuarios.`
    },
    {
      id: 'proyectos',
      title: '📁 Proyectos',
      content: `Gestión de proyectos de digitalización asociados a cada empresa.

**Características:**
• Cada proyecto contiene documentos PDF para procesar
• Estados: Activo o Completado
• **Código de proyecto alfanumérico único**
• Instrucciones semánticas para guiar la IA
• Filtros por empresa y corporación

**Tres pestañas principales:**
1. **Documentos:** Subir y gestionar PDFs
2. **PDF Manager IA:** Renombrar y reordenar múltiples PDFs
3. **PDF Manager IA por Página:** Reordenar o extraer páginas de PDFs`
    },
    {
      id: 'documentos',
      title: '📄 Subir y Procesar Documentos',
      content: `Proceso de carga y procesamiento de PDFs:

**1. Subida de archivos:**
• Arrastra o selecciona archivos PDF
• Hasta 10 archivos simultáneos
• Límites: 500MB por archivo, 1GB por lote

**2. Procesamiento automático:**
• Control de calidad (QA) según reglas configuradas
• Extracción de datos con IA si pasa QA
• **Mensajes de progreso en tiempo real**

**Estados del documento:**
• ⬆️ Subido
• 🔄 QA en Proceso
• ✅ QA Aprobado → IA Processing
• ❌ QA Falló
• 🤖 Extracción IA (con barra de progreso)
• ✓ Completado
• ⚠️ Necesita Revisión Manual

**Mensajes de progreso:**
Verás mensajes descriptivos durante el procesamiento:
• "📄 Iniciando procesamiento..."
• "🔍 Extrayendo texto con OCR..."
• "🤖 Extrayendo datos del chunk X/Y..."
• "✅ Procesamiento completado"`
    },
    {
      id: 'pdf-manager',
      title: '🤖 PDF Manager IA',
      content: `Herramienta para renombrar y reordenar múltiples PDFs usando lenguaje natural.

**Proceso:**
1. **Instrucción:** Escribe en lenguaje natural
   Ejemplo: "Renombrar con formato Empresa-Fecha-Tipo y ordenar por fecha"
   
2. **Plan:** La IA genera un plan con vista previa de cambios

3. **Revisión:** Verifica las operaciones de renombrado y el nuevo orden

4. **Ejecución:** Aplica los cambios

5. **Descarga:** Obtén ZIP con todos los archivos o descarga individuales

**Nivel de confianza:** El sistema muestra un % de confianza del plan generado.`
    },
    {
      id: 'pdf-page-manager',
      title: '📑 PDF Manager IA por Página',
      content: `Reordena o extrae páginas DENTRO de un PDF específico.

**Dos modos de operación:**

**1. 🔄 Reordenar Páginas**
Reorganiza el orden de las páginas dentro del PDF.

Proceso:
1. Selecciona un PDF del proyecto
2. Describe el reordenamiento deseado
   Ejemplo: "Mover la página con notas importantes al inicio"
3. La IA lee el contenido y genera un plan
4. Ejecuta para crear el PDF reordenado
5. Descarga el PDF con nuevo orden

**2. ✂️ Extraer Páginas**
Crea un NUEVO PDF con solo las páginas que necesitas.

Dos formas de especificar páginas:

**A. Rango Manual:**
Escribe directamente qué páginas extraer:
• "1-20" → Páginas 1 a 20
• "1,5,10,15" → Solo páginas 1, 5, 10 y 15
• "1-10,15-20" → Páginas 1-10 y 15-20

**B. Lenguaje Natural:**
Describe qué extraer:
• "Extraer solo las primeras 20 páginas"
• "Crear PDF con páginas 10 a 50"
• "Solo páginas con información financiera"

**Ventaja:** La IA analiza el contenido real de cada página para tomar decisiones informadas (requiere OCR para PDFs escaneados).`
    },
    {
      id: 'qa-agents',
      title: '✅ Agentes QA',
      content: `Configura reglas de control de calidad para validar PDFs.

**Propósito:**
• Validar documentos ANTES del procesamiento con IA
• Evitar procesar documentos de baja calidad
• Definir criterios de aceptación

**Ejemplos de reglas:**
• Verificar presencia de fechas
• Comprobar palabras clave específicas
• Validar formato de documento
• Detectar campos requeridos

Los documentos que fallan QA van a "Hallazgos QA" para revisión manual.`
    },
    {
      id: 'qa-findings',
      title: '🔍 Hallazgos QA',
      content: `Visualiza documentos que fallaron el control de calidad automático.

**Información mostrada:**
• Documento que falló
• Hallazgos específicos detectados
• Motivo del fallo
• Proyecto asociado

**Acciones recomendadas:**
• Revisar el documento manualmente
• Corregir el documento fuente
• Ajustar las reglas de QA si es necesario
• Re-subir el documento corregido`
    },
    {
      id: 'extracted-data',
      title: '📊 Datos Extraídos',
      content: `Consulta centralizada de información extraída por IA.

**Datos típicamente extraídos:**
• Fechas de documentos
• Montos y valores monetarios
• Nombres de clientes
• Tipos de documento
• Números de factura/contrato
• Proyectos asociados
• Datos específicos según instrucciones del proyecto

**Funciones:**
• Búsqueda y filtrado
• Exportación de datos
• Vista consolidada por proyecto`
    },
    {
      id: 'segmentos',
      title: '🏷️ Segmentos',
      content: `Define y gestiona segmentos de industria.

**Propósito:**
• Clasificar empresas por industria/sector
• Organizar clientes
• Generar reportes segmentados

**Ejemplos de segmentos:**
• Tecnología Avanzada
• Salud y Farmacéutica
• Finanzas y Banca
• Retail y Comercio
• Manufactura
• Educación

**Gestión:**
• Crear nuevos segmentos
• Editar existentes
• Activar/desactivar segmentos`
    },
    {
      id: 'ai-config',
      title: '⚙️ Configuración IA',
      content: `Configura API keys de OpenAI a nivel de proyecto.

**Tres tipos de configuración:**
1. **Extracción de Datos:** Para procesar y extraer información de PDFs
2. **Agente QA:** Para control de calidad automático
3. **Reordenamiento y Renombrado:** Para PDF Manager

**Proceso:**
1. Selecciona una empresa
2. Selecciona un proyecto
3. Elige el tipo de configuración
4. Selecciona modelo de OpenAI (solo OpenAI soportado)
5. Ingresa tu API key de OpenAI

🔒 **Seguridad:** Las claves se encriptan antes de almacenarse en la base de datos.

📝 **Nota:** Solo se acepta OpenAI como proveedor de IA.`
    },
    {
      id: 'ocr-config',
      title: '🔍 Configuración OCR Global',
      content: `Configura cómo el sistema extrae texto de PDFs escaneados (sin texto incrustado).

**¿Cuándo se usa OCR?**
El sistema primero intenta extraer texto normalmente. Si el PDF está escaneado o es una imagen, automáticamente usa OCR.

**Dos métodos disponibles:**

**1. 🔧 Tesseract OCR (Por defecto)**
✅ Ventajas:
• Gratuito y rápido
• Procesa páginas en segundos
• Ideal para documentos simples

⚠️ Desventajas:
• Menor precisión con documentos complejos
• Puede fallar con mala calidad de escaneo

**2. 🤖 GPT-4o Vision**
✅ Ventajas:
• Máxima precisión y calidad
• Excelente con documentos complejos
• Entiende contexto y layout

⚠️ Desventajas:
• Usa tokens de OpenAI (tiene costo)
• Más lento (~7 segundos por página)
• Requiere API key configurada

**¿Cuál elegir?**
• **Tesseract:** Para documentos de buena calidad y procesamiento rápido
• **GPT-4o Vision:** Para documentos críticos o mala calidad de escaneo

**Ubicación:** Configuración IA → Sección superior "Configuración OCR Global"`
    },
    {
      id: 'users',
      title: '👥 Usuarios',
      content: `Gestión de usuarios del sistema.

**Roles disponibles:**

**1. Staff (Administrador)**
• Acceso completo al sistema
• Gestiona empresas, proyectos, usuarios
• Configura segmentos y agentes QA
• Puede resetear contraseñas de usuarios

**2. Asesor**
• Asignado a empresas específicas
• Acceso a empresas asignadas y sus proyectos
• No puede eliminar usuarios ni modificar configuraciones globales

**3. Cliente**
• Acceso solo a su empresa
• Ve proyectos de su empresa
• Acceso de solo lectura a documentos

**Funciones administrativas:**
• Crear nuevos usuarios
• Editar información de usuarios
• Activar/desactivar usuarios
• **Resetear contraseña:** Staff puede resetear contraseñas a "password123"

⚠️ **Protección:** El usuario admin@pergaminos.com no puede ser eliminado.

🔒 **Acceso de clientes:** Los clientes solo pueden ver, no editar ni subir documentos.`
    }
  ];

  const handleAskQuestion = async () => {
    if (!chatQuestion.trim()) {
      setChatError('Por favor escribe una pregunta');
      return;
    }

    setChatLoading(true);
    setChatError('');
    setChatAnswer('');

    try {
      const response = await axios.post(`${API}/manual/chat`, {
        question: chatQuestion
      });

      setChatAnswer(response.data.answer);
    } catch (error) {
      setChatError(error.response?.data?.detail || 'Error al consultar con la IA');
    } finally {
      setChatLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const response = await axios.get(`${API}/manual/download-pdf`, {
        responseType: 'blob'
      });

      // Create blob link to download
      const blob = new Blob([response.data]);
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = 'Manual_Pergaminos.pdf';
      link.click();

      // Cleanup
      window.URL.revokeObjectURL(link.href);
    } catch (error) {
      console.error('Error downloading manual:', error);
      alert('Error al descargar el manual');
    }
  };

  const currentSection = sections.find(s => s.id === activeSection);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" >
            📚 Manual de Usuario
          </h1>
          <p className="text-gray-600 mt-1">
            Guía completa del Sistema Pergaminos
          </p>
        </div>
        <button
          onClick={handleDownloadPDF}
          className="btn-primary"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          Descargar PDF
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar - Table of Contents */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 sticky top-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Contenido</h3>
            <nav className="space-y-1">
              {sections.map((section) => (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                    activeSection === section.id
                      ? 'bg-yellow-100 text-yellow-700 font-medium'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  {section.title}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Section Content */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h2 className="text-2xl font-bold text-gray-900 mb-4" >
              {currentSection?.title}
            </h2>
            <div className="prose max-w-none">
              <div className="text-gray-700 whitespace-pre-line leading-relaxed">
                {currentSection?.content}
              </div>
            </div>
          </div>

          {/* AI Assistant Chat */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              🤖 Asistente IA - Pregunta sobre el sistema
            </h3>
            
            <div className="space-y-4">
              <div>
                <label htmlFor="chat-question" className="block text-sm font-medium text-gray-700 mb-2">
                  ¿Tienes alguna pregunta sobre cómo usar el sistema?
                </label>
                <textarea
                  id="chat-question"
                  value={chatQuestion}
                  onChange={(e) => setChatQuestion(e.target.value)}
                  className="form-textarea w-full h-24"
                  placeholder="Ejemplo: ¿Cómo puedo cambiar el estado de una empresa a inactiva?"
                  disabled={chatLoading}
                />
              </div>

              <button
                onClick={handleAskQuestion}
                disabled={chatLoading || !chatQuestion.trim()}
                className="btn-primary"
              >
                {chatLoading ? (
                  <>
                    <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Consultando...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                    </svg>
                    Preguntar a la IA
                  </>
                )}
              </button>

              {chatError && (
                <div className="alert alert-error">{chatError}</div>
              )}

              {chatAnswer && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-yellow-900 mb-2">Respuesta de la IA:</h4>
                  <div className="text-sm text-yellow-800 whitespace-pre-line">
                    {chatAnswer}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UserManual;

import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DocumentProcessor = ({ user }) => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [documents, setDocuments] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [instructions, setInstructions] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [processResult, setProcessResult] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState('');

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      fetchDocuments();
    }
  }, [selectedProject]);

  const fetchProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setProjects(response.data);
    } catch (error) {
      console.error('Error fetching projects:', error);
      setError('Error al cargar proyectos');
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/projects/${selectedProject}/documents`);
      const completedDocs = response.data.filter(doc => doc.status === 'completed');
      setDocuments(completedDocs);
    } catch (error) {
      console.error('Error fetching documents:', error);
      setError('Error al cargar documentos');
    }
  };

  const handleProcess = async () => {
    if (!selectedProject || !instructions.trim()) {
      setError('Selecciona un proyecto e ingresa instrucciones');
      return;
    }

    if (documents.length === 0) {
      setError('No hay documentos completados en este proyecto');
      return;
    }

    setProcessing(true);
    setError('');
    setSuccess('');

    try {
      const formData = new FormData();
      formData.append('semantic_instructions', instructions);
      
      const response = await axios.post(`${API}/projects/${selectedProject}/documents/process-reorder`, formData);
      
      setSuccess('Procesamiento iniciado con IA');
      setProcessResult(response.data);
      
      // Poll for completion
      pollProcessStatus(response.data.task_id);
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al procesar documentos');
      setProcessing(false);
    }
  };

  const pollProcessStatus = async (taskId) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/projects/${selectedProject}/process-status/${taskId}`);
        const status = response.data;
        
        if (status.status === 'completed') {
          clearInterval(pollInterval);
          setProcessing(false);
          setSuccess('Documentos procesados exitosamente');
          setDownloadUrl(status.download_url);
          fetchDocuments(); // Refresh document list
        } else if (status.status === 'failed') {
          clearInterval(pollInterval);
          setProcessing(false);
          setError(`Error en procesamiento: ${status.error}`);
        }
      } catch (error) {
        clearInterval(pollInterval);
        setProcessing(false);
        setError('Error al obtener estado del procesamiento');
      }
    }, 3000);

    // Clear interval after 10 minutes
    setTimeout(() => clearInterval(pollInterval), 600000);
  };

  const handleDownload = async () => {
    if (!downloadUrl) return;
    
    try {
      const response = await axios.get(downloadUrl, {
        responseType: 'blob'
      });
      
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `documentos_procesados_${selectedProject}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      setError('Error al descargar el archivo');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Procesador de Documentos
          </h1>
          <p className="text-gray-600 mt-1">
            Renombra y reordena documentos con IA
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Project Selection */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Seleccionar Proyecto</h2>
        </div>
        
        <div className="form-group">
          <label htmlFor="project-select" className="form-label">
            Proyecto *
          </label>
          <select
            id="project-select"
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            className="form-input"
          >
            <option value="">Seleccionar proyecto...</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name} ({project.company_id})
              </option>
            ))}
          </select>
        </div>

        {selectedProject && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mt-4">
            <h3 className="text-emerald-900 font-semibold mb-2">
              Documentos Disponibles: {documents.length}
            </h3>
            <div className="space-y-2">
              {documents.slice(0, 5).map((doc, index) => (
                <div key={doc.id} className="text-emerald-800 text-sm">
                  {index + 1}. {doc.original_filename}
                </div>
              ))}
              {documents.length > 5 && (
                <div className="text-emerald-700 text-sm">
                  ... y {documents.length - 5} documentos más
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Processing Instructions */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Instrucciones de Procesamiento</h2>
        </div>
        
        <div className="form-group">
          <label htmlFor="instructions" className="form-label">
            Instrucciones para IA *
          </label>
          <textarea
            id="instructions"
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            className="form-textarea"
            rows="6"
            placeholder="Ejemplo: Ordena los documentos cronológicamente por fecha de creación, comenzando por los más recientes. Renombra usando el formato 'DOC_[TIPO]_[FECHA]_[NUMERO]'. Agrupa documentos similares juntos."
          />
          <p className="text-xs text-gray-500 mt-1">
            Describe detalladamente cómo quieres que la IA organice, renombre y procese los documentos.
          </p>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="text-blue-900 font-medium mb-2">Ejemplos de Instrucciones:</h4>
          <div className="space-y-2 text-blue-800 text-sm">
            <div>• "Ordena por tipo de documento: contratos primero, facturas después, certificados al final"</div>
            <div>• "Renombra con formato: [EMPRESA]_[TIPO]_[FECHA]_[CONSECUTIVO]"</div>
            <div>• "Agrupa documentos del mismo cliente y ordena cronológicamente"</div>
            <div>• "Separa documentos firmados de los que necesitan firma"</div>
          </div>
        </div>

        <div className="flex justify-end space-x-3 pt-4">
          <button
            onClick={handleProcess}
            disabled={processing || !selectedProject || !instructions.trim()}
            className="btn-primary"
          >
            {processing ? (
              <div className="flex items-center">
                <div className="spinner mr-2" style={{ width: '16px', height: '16px' }}></div>
                Procesando...
              </div>
            ) : (
              'Procesar Documentos'
            )}
          </button>
        </div>
      </div>

      {/* Processing Status */}
      {processing && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Estado del Procesamiento</h2>
          </div>
          
          <div className="flex items-center">
            <div className="w-8 h-8 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin mr-4"></div>
            <div>
              <p className="text-gray-900 font-medium">La IA está procesando los documentos</p>
              <p className="text-gray-600 text-sm">Esto puede tomar varios minutos dependiendo del número de documentos</p>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {downloadUrl && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Procesamiento Completado</h2>
          </div>
          
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center">
                <svg className="w-6 h-6 text-green-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div>
                  <h4 className="text-green-900 font-medium">Documentos Procesados Exitosamente</h4>
                  <p className="text-green-800 text-sm">Los documentos han sido reordenados y renombrados según las instrucciones</p>
                </div>
              </div>
            </div>

            <button
              onClick={handleDownload}
              className="btn-primary w-full"
            >
              <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-4-4m4 4l4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Descargar PDF Procesado
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentProcessor;
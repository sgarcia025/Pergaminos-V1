import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const DocumentProcessor = ({ user }) => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [documents, setDocuments] = useState([]);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [processResult, setProcessResult] = useState(null);
  const [downloadUrl, setDownloadUrl] = useState('');
  
  // New state for individual document management
  const [documentChanges, setDocumentChanges] = useState({});
  const [globalRenamePattern, setGlobalRenamePattern] = useState('');
  const [globalOrderInstructions, setGlobalOrderInstructions] = useState('');

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
      
      // Initialize document changes state
      const initialChanges = {};
      completedDocs.forEach((doc, index) => {
        initialChanges[doc.id] = {
          newName: doc.original_filename,
          newOrder: index + 1,
          currentName: doc.original_filename,
          currentOrder: doc.display_order || index + 1
        };
      });
      setDocumentChanges(initialChanges);
    } catch (error) {
      console.error('Error fetching documents:', error);
      setError('Error al cargar documentos');
    }
  };

  const handleDocumentChange = (docId, field, value) => {
    setDocumentChanges(prev => ({
      ...prev,
      [docId]: {
        ...prev[docId],
        [field]: value
      }
    }));
  };

  const applyGlobalRenamePattern = () => {
    if (!globalRenamePattern.trim()) {
      setError('Ingresa un patrón de renombrado');
      return;
    }

    const updatedChanges = { ...documentChanges };
    documents.forEach((doc, index) => {
      const newName = globalRenamePattern
        .replace('{numero}', index + 1)
        .replace('{orden}', index + 1)
        .replace('{nombre_original}', doc.original_filename.replace('.pdf', ''))
        .replace('{fecha}', new Date().toISOString().split('T')[0])
        .replace('{proyecto}', projects.find(p => p.id === selectedProject)?.name || 'Proyecto');
      
      updatedChanges[doc.id].newName = newName.endsWith('.pdf') ? newName : newName + '.pdf';
    });
    
    setDocumentChanges(updatedChanges);
    setSuccess('Patrón de renombrado aplicado exitosamente');
  };

  const applyGlobalOrder = () => {
    if (!globalOrderInstructions.trim()) {
      setError('Ingresa instrucciones de ordenamiento');
      return;
    }

    // Simple alphabetical ordering for now
    const sortedDocs = [...documents].sort((a, b) => {
      if (globalOrderInstructions.toLowerCase().includes('alfabético')) {
        return a.original_filename.localeCompare(b.original_filename);
      }
      if (globalOrderInstructions.toLowerCase().includes('fecha')) {
        return new Date(a.created_at) - new Date(b.created_at);
      }
      return 0;
    });

    const updatedChanges = { ...documentChanges };
    sortedDocs.forEach((doc, index) => {
      updatedChanges[doc.id].newOrder = index + 1;
    });
    
    setDocumentChanges(updatedChanges);
    setSuccess('Orden aplicado exitosamente');
  };

  const handleProcessDocuments = async () => {
    if (!selectedProject || documents.length === 0) {
      setError('Selecciona un proyecto con documentos');
      return;
    }

    const hasChanges = Object.values(documentChanges).some(change => 
      change.newName !== change.currentName || change.newOrder !== change.currentOrder
    );

    if (!hasChanges) {
      setError('No hay cambios para procesar');
      return;
    }

    setProcessing(true);
    setError('');
    setSuccess('');

    try {
      const formData = new FormData();
      formData.append('document_changes', JSON.stringify(documentChanges));
      formData.append('project_id', selectedProject);
      
      const response = await axios.post(`${API}/projects/${selectedProject}/documents/process-rename-reorder`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      setSuccess('Procesamiento iniciado exitosamente');
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
        responseType: 'blob',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const projectName = projects.find(p => p.id === selectedProject)?.name || 'proyecto';
      link.download = `${projectName}_procesado_${new Date().toISOString().split('T')[0]}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      setSuccess('Archivo descargado exitosamente');
    } catch (error) {
      setError('Error al descargar el archivo');
    }
  };

  const resetChanges = () => {
    fetchDocuments(); // This will reset documentChanges
    setGlobalRenamePattern('');
    setGlobalOrderInstructions('');
    setSuccess('Cambios reiniciados');
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Procesador de Documentos
          </h1>
          <p className="text-gray-600 mt-1">
            Renombra y reordena documentos individualmente o en lote
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
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {selectedProject && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mt-4">
            <h3 className="text-emerald-900 font-semibold mb-2">
              Documentos Disponibles: {documents.length}
            </h3>
            {documents.length === 0 && (
              <p className="text-emerald-700 text-sm">
                No hay documentos procesados disponibles en este proyecto.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Global Operations */}
      {selectedProject && documents.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Operaciones Globales</h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Global Rename Pattern */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Patrón de Renombrado</h3>
              <div className="form-group">
                <label htmlFor="rename-pattern" className="form-label">
                  Patrón de nombres
                </label>
                <input
                  id="rename-pattern"
                  type="text"
                  value={globalRenamePattern}
                  onChange={(e) => setGlobalRenamePattern(e.target.value)}
                  className="form-input"
                  placeholder="DOC_{numero}_{proyecto}_{fecha}"
                />
                <div className="text-xs text-gray-500 mt-1">
                  Variables: {'{numero}'}, {'{proyecto}'}, {'{fecha}'}, {'{nombre_original}'}
                </div>
              </div>
              <button
                onClick={applyGlobalRenamePattern}
                className="btn-secondary w-full"
                disabled={!globalRenamePattern.trim()}
              >
                Aplicar Patrón de Nombres
              </button>
            </div>

            {/* Global Order Instructions */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">Instrucciones de Orden</h3>
              <div className="form-group">
                <label htmlFor="order-instructions" className="form-label">
                  Criterio de ordenamiento
                </label>
                <select
                  id="order-instructions"
                  value={globalOrderInstructions}
                  onChange={(e) => setGlobalOrderInstructions(e.target.value)}
                  className="form-input"
                >
                  <option value="">Seleccionar criterio...</option>
                  <option value="alfabético">Orden Alfabético</option>
                  <option value="fecha de creación">Fecha de Creación</option>
                  <option value="fecha procesamiento">Fecha de Procesamiento</option>
                </select>
              </div>
              <button
                onClick={applyGlobalOrder}
                className="btn-secondary w-full"
                disabled={!globalOrderInstructions}
              >
                Aplicar Orden Global
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Individual Document Management */}
      {selectedProject && documents.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="flex justify-between items-center">
              <h2 className="card-title">Gestión Individual de Documentos</h2>
              <button
                onClick={resetChanges}
                className="text-gray-600 hover:text-gray-800 text-sm"
              >
                Reiniciar Cambios
              </button>
            </div>
          </div>
          
          <div className="space-y-4">
            {documents.map((document) => (
              <div key={document.id} className="border border-gray-200 rounded-lg p-4">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-center">
                  {/* Document Info */}
                  <div>
                    <h4 className="font-medium text-gray-900 mb-1">
                      {document.original_filename}
                    </h4>
                    <p className="text-xs text-gray-500">
                      Subido: {new Date(document.created_at).toLocaleDateString()}
                    </p>
                    <p className="text-xs text-gray-500">
                      Orden actual: {documentChanges[document.id]?.currentOrder || 'N/A'}
                    </p>
                  </div>

                  {/* New Name Input */}
                  <div>
                    <label className="form-label text-xs">Nuevo Nombre</label>
                    <input
                      type="text"
                      value={documentChanges[document.id]?.newName || ''}
                      onChange={(e) => handleDocumentChange(document.id, 'newName', e.target.value)}
                      className="form-input text-sm"
                      placeholder="Nuevo nombre del documento"
                    />
                  </div>

                  {/* New Order Input */}
                  <div>
                    <label className="form-label text-xs">Nuevo Orden</label>
                    <input
                      type="number"
                      min="1"
                      max={documents.length}
                      value={documentChanges[document.id]?.newOrder || ''}
                      onChange={(e) => handleDocumentChange(document.id, 'newOrder', parseInt(e.target.value))}
                      className="form-input text-sm"
                      placeholder="Posición"
                    />
                  </div>
                </div>

                {/* Changes Indicator */}
                <div className="mt-3 pt-3 border-t border-gray-100">
                  {(documentChanges[document.id]?.newName !== documentChanges[document.id]?.currentName ||
                    documentChanges[document.id]?.newOrder !== documentChanges[document.id]?.currentOrder) && (
                    <div className="bg-blue-50 border border-blue-200 rounded p-2">
                      <p className="text-blue-800 text-xs">
                        <strong>Cambios pendientes:</strong>
                        {documentChanges[document.id]?.newName !== documentChanges[document.id]?.currentName && 
                          ` Nombre: "${documentChanges[document.id]?.newName}"`}
                        {documentChanges[document.id]?.newOrder !== documentChanges[document.id]?.currentOrder && 
                          ` | Orden: ${documentChanges[document.id]?.newOrder}`}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Process Button */}
          <div className="flex justify-end space-x-3 pt-6 border-t border-gray-200">
            <button
              onClick={handleProcessDocuments}
              disabled={processing}
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
      )}

      {/* Processing Status */}
      {processing && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Estado del Procesamiento</h2>
          </div>
          
          <div className="flex items-center">
            <div className="w-8 h-8 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin mr-4"></div>
            <div>
              <p className="text-gray-900 font-medium">Procesando cambios en los documentos</p>
              <p className="text-gray-600 text-sm">Aplicando nombres y orden especificados...</p>
            </div>
          </div>
        </div>
      )}

      {/* Results and Download */}
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
                  <p className="text-green-800 text-sm">Los documentos han sido renombrados y reordenados según las especificaciones</p>
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

      {/* Empty State */}
      {selectedProject && documents.length === 0 && (
        <div className="card text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay documentos procesados</h3>
          <p className="text-gray-600">
            Este proyecto no tiene documentos completados disponibles para procesar.
          </p>
        </div>
      )}
    </div>
  );
};

export default DocumentProcessor;
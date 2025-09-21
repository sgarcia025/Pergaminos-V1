import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ProjectDetail = ({ user }) => {
  const { projectId } = useParams();
  const [project, setProject] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showReorderModal, setShowReorderModal] = useState(false);
  const [reorderInstructions, setReorderInstructions] = useState('');
  const [reorderStatus, setReorderStatus] = useState(null);
  const [renamingDoc, setRenamingDoc] = useState(null);
  const [newDocName, setNewDocName] = useState('');

  useEffect(() => {
    fetchProject();
    fetchDocuments();
  }, [projectId]);

  const fetchProject = async () => {
    try {
      const response = await axios.get(`${API}/projects/${projectId}`);
      setProject(response.data);
    } catch (error) {
      console.error('Error fetching project:', error);
      setError('Error al cargar el proyecto');
    }
  };

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/projects/${projectId}/documents`);
      setDocuments(response.data);
    } catch (error) {
      console.error('Error fetching documents:', error);
      setError('Error al cargar los documentos');
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (files) => {
    if (!files || files.length === 0) return;

    const file = files[0];
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Solo se permiten archivos PDF');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post(`${API}/projects/${projectId}/documents/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setSuccess('Documento subido exitosamente');
      fetchDocuments();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al subir el documento');
    } finally {
      setUploading(false);
    }
  };

  const handleRenameDocument = async (documentId, newName) => {
    try {
      const formData = new FormData();
      formData.append('new_name', newName);
      
      await axios.put(`${API}/documents/${documentId}/rename`, formData);
      setSuccess('Documento renombrado exitosamente');
      setRenamingDoc(null);
      setNewDocName('');
      fetchDocuments();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al renombrar el documento');
    }
  };

  const handleReorderDocuments = async () => {
    if (!reorderInstructions.trim()) {
      setError('Las instrucciones de reordenación son requeridas');
      return;
    }

    try {
      const formData = new FormData();
      formData.append('semantic_instructions', reorderInstructions);
      
      const response = await axios.post(`${API}/projects/${projectId}/documents/reorder`, formData);
      
      setReorderStatus({
        taskId: response.data.task_id,
        status: 'processing',
        progress: 0
      });
      
      setShowReorderModal(false);
      setSuccess('Proceso de reordenación iniciado con IA');
      
      // Poll for status updates
      pollReorderStatus(response.data.task_id);
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al iniciar la reordenación');
    }
  };

  const pollReorderStatus = async (taskId) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/projects/${projectId}/reorder-status/${taskId}`);
        const status = response.data;
        
        setReorderStatus(status);
        
        if (status.status === 'completed') {
          clearInterval(pollInterval);
          setSuccess('Documentos reordenados exitosamente por IA');
          fetchDocuments();
        } else if (status.status === 'failed') {
          clearInterval(pollInterval);
          setError(`Error en reordenación: ${status.error}`);
        }
      } catch (error) {
        clearInterval(pollInterval);
        setError('Error al obtener estado de reordenación');
      }
    }, 2000);

    // Clear interval after 5 minutes to prevent infinite polling
    setTimeout(() => clearInterval(pollInterval), 300000);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    handleFileUpload(files);
  };

  const getStatusColor = (status) => {
    const colors = {
      'uploaded': 'status-uploaded',
      'processing': 'status-processing',
      'completed': 'status-completed',
      'failed': 'status-failed',
      'needs_review': 'status-needs_review'
    };
    return colors[status] || 'status-uploaded';
  };

  const getStatusText = (status) => {
    const texts = {
      'uploaded': 'Subido',
      'processing': 'Procesando',
      'completed': 'Completado',
      'failed': 'Fallido',
      'needs_review': 'Revisión'
    };
    return texts[status] || status;
  };

  const completedDocuments = documents.filter(doc => doc.status === 'completed');

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <h3 className="text-lg font-medium text-gray-900 mb-2">Proyecto no encontrado</h3>
        <Link to="/projects" className="text-emerald-600 hover:text-emerald-700">
          Volver a proyectos
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <nav className="flex" aria-label="Breadcrumb">
        <ol className="flex items-center space-x-4">
          <li>
            <Link to="/projects" className="text-gray-500 hover:text-gray-700">
              Proyectos
            </Link>
          </li>
          <li>
            <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
            </svg>
          </li>
          <li>
            <span className="text-gray-900 font-medium">{project.name}</span>
          </li>
        </ol>
      </nav>

      {/* Project Header */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <div className="flex justify-between items-start">
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-gray-900 mb-2" style={{ fontFamily: 'Playfair Display' }}>
              {project.name}
            </h1>
            {project.description && (
              <p className="text-gray-600 mb-4">{project.description}</p>
            )}
            
            {project.semantic_instructions && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-emerald-900 mb-2 flex items-center">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  Instrucciones para IA
                </h3>
                <p className="text-emerald-800 text-sm">{project.semantic_instructions}</p>
              </div>
            )}
          </div>
          
          <span className={`status-badge ${project.status === 'active' ? 'status-active' : 'status-completed'}`}>
            {project.status === 'active' ? 'Activo' : 'Completado'}
          </span>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Reorder Status */}
      {reorderStatus && reorderStatus.status === 'processing' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mr-3"></div>
            <div className="flex-1">
              <h4 className="text-blue-900 font-medium">Reordenando documentos con IA</h4>
              <p className="text-blue-700 text-sm">Progreso: {reorderStatus.progress || 0}%</p>
            </div>
          </div>
        </div>
      )}

      {/* File Upload Area */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-200">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Subir Documentos</h2>
        
        <div
          className={`file-upload ${dragOver ? 'active' : ''}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input').click()}
        >
          <input
            id="file-input"
            type="file"
            accept=".pdf"
            onChange={(e) => handleFileUpload(e.target.files)}
            className="hidden"
          />
          
          {uploading ? (
            <div className="flex flex-col items-center">
              <div className="spinner mb-4"></div>
              <p className="text-gray-600">Subiendo documento...</p>
            </div>
          ) : (
            <div className="text-center">
              <svg className="file-upload-icon mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="file-upload-text">
                Arrastra y suelta tus archivos PDF aquí, o <span className="text-emerald-600 font-medium">haz clic para seleccionar</span>
              </p>
              <p className="file-upload-hint">Solo se aceptan archivos PDF</p>
            </div>
          )}
        </div>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">
              Documentos ({documents.length})
            </h2>
            {completedDocuments.length > 1 && (
              <button
                onClick={() => setShowReorderModal(true)}
                className="btn-secondary flex items-center"
                disabled={reorderStatus?.status === 'processing'}
              >
                <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
                </svg>
                Reordenar con IA
              </button>
            )}
          </div>
        </div>
        
        {documents.length > 0 ? (
          <div className="divide-y divide-gray-200">
            {documents.map((document, index) => (
              <div key={document.id} className="p-6 hover:bg-gray-50 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center flex-1">
                    <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center mr-4">
                      <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center">
                        {document.display_order && (
                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 mr-2">
                            #{document.display_order}
                          </span>
                        )}
                        <h4 className="text-sm font-medium text-gray-900 truncate">
                          {renamingDoc === document.id ? (
                            <div className="flex items-center space-x-2">
                              <input
                                type="text"
                                value={newDocName}
                                onChange={(e) => setNewDocName(e.target.value)}
                                className="text-sm border border-gray-300 rounded px-2 py-1"
                                placeholder="Nuevo nombre"
                                autoFocus
                              />
                              <button
                                onClick={() => handleRenameDocument(document.id, newDocName)}
                                className="text-emerald-600 hover:text-emerald-700"
                              >
                                ✓
                              </button>
                              <button
                                onClick={() => {
                                  setRenamingDoc(null);
                                  setNewDocName('');
                                }}
                                className="text-gray-400 hover:text-gray-600"
                              >
                                ✕
                              </button>
                            </div>
                          ) : (
                            <span>{document.original_filename}</span>
                          )}
                        </h4>
                      </div>
                      <div className="flex items-center mt-1 space-x-4">
                        <span className="text-xs text-gray-500">
                          Subido {new Date(document.created_at).toLocaleDateString()}
                        </span>
                        {document.processed_at && (
                          <span className="text-xs text-gray-500">
                            Procesado {new Date(document.processed_at).toLocaleDateString()}
                          </span>
                        )}
                        {document.reordered_at && (
                          <span className="text-xs text-emerald-600">
                            Reordenado por IA
                          </span>
                        )}
                      </div>
                      {document.reorder_reasoning && (
                        <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
                          <strong>IA:</strong> {document.reorder_reasoning}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <span className={`status-badge ${getStatusColor(document.status)}`}>
                      {getStatusText(document.status)}
                    </span>
                    
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => {
                          setRenamingDoc(document.id);
                          setNewDocName(document.original_filename);
                        }}
                        className="text-gray-400 hover:text-gray-600 p-1"
                        title="Renombrar documento"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      
                      <button className="text-gray-400 hover:text-gray-600 p-1">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
                
                {document.extracted_data && (
                  <div className="mt-4 p-4 bg-gray-50 rounded-lg">
                    <h5 className="text-sm font-medium text-gray-900 mb-2">Datos Extraídos:</h5>
                    <pre className="text-xs text-gray-600 whitespace-pre-wrap">
                      {JSON.stringify(document.extracted_data, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="p-12 text-center">
            <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="text-lg font-medium text-gray-900 mb-2">No hay documentos</h3>
            <p className="text-gray-600">
              Sube tu primer documento PDF para comenzar el procesamiento con IA.
            </p>
          </div>
        )}
      </div>

      {/* Reorder Modal */}
      {showReorderModal && (
        <div className="modal-overlay" onClick={() => setShowReorderModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Reordenar Documentos con IA</h3>
              <button
                onClick={() => setShowReorderModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-blue-600 mr-2 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div>
                    <h4 className="text-blue-900 font-medium">¿Cómo funciona?</h4>
                    <p className="text-blue-800 text-sm mt-1">
                      La IA analizará el contenido de {completedDocuments.length} documentos procesados y los reordenará según tus instrucciones. También sugerirá nombres más descriptivos.
                    </p>
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="reorder-instructions" className="form-label">
                  Instrucciones de Reordenación *
                </label>
                <textarea
                  id="reorder-instructions"
                  value={reorderInstructions}
                  onChange={(e) => setReorderInstructions(e.target.value)}
                  className="form-textarea"
                  rows="4"
                  placeholder="Ejemplo: Ordena los documentos cronológicamente por fecha, con los contratos más recientes primero. Renombra usando el formato 'Contrato_[Empresa]_[Fecha]'"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Describe cómo quieres que la IA organice y renombre los documentos.
                </p>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowReorderModal(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleReorderDocuments}
                  className="btn-primary"
                  disabled={!reorderInstructions.trim()}
                >
                  Reordenar con IA
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ProjectDetail;
import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import axios from 'axios';
import PDFManager from './PDFManager';
import PDFPageManager from './PDFPageManager';

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
  const [batchUploading, setBatchUploading] = useState(false);
  const [batchTaskId, setBatchTaskId] = useState(null);
  const [batchProgress, setBatchProgress] = useState({});
  const [uploadProgress, setUploadProgress] = useState([]);
  const [activeTab, setActiveTab] = useState('documents'); // documents, pdf-manager, or pdf-page-manager
  
  // QA Review Modal
  const [showQAModal, setShowQAModal] = useState(false);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [qaComments, setQaComments] = useState('');
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    fetchProject();
    fetchDocuments();
  }, [projectId]);

  // Auto-refresh documents when there are processing documents
  useEffect(() => {
    const processingDocs = documents.filter(doc => 
      doc.status === 'processing' || 
      doc.status === 'qa_pending' || 
      doc.status === 'uploaded'
    );

    if (processingDocs.length > 0) {
      // Poll every 3 seconds when documents are processing
      const interval = setInterval(() => {
        fetchDocuments();
      }, 3000);

      return () => clearInterval(interval);
    }
  }, [documents, projectId]);

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

    // Validate all files are PDFs
    const nonPdfFiles = Array.from(files).filter(file => !file.name.toLowerCase().endsWith('.pdf'));
    if (nonPdfFiles.length > 0) {
      setError(`Los siguientes archivos no son PDFs: ${nonPdfFiles.map(f => f.name).join(', ')}`);
      return;
    }

    // Limit to 10 files
    if (files.length > 10) {
      setError('Máximo 10 archivos permitidos por lote');
      return;
    }

    setError('');
    setSuccess('');

    // Single file upload (legacy)
    if (files.length === 1) {
      setUploading(true);
      const formData = new FormData();
      formData.append('file', files[0]);

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
    } else {
      // Batch upload for multiple files
      setBatchUploading(true);
      
      // Initialize upload progress tracking
      const progressTracking = Array.from(files).map(file => ({
        name: file.name,
        status: 'pending',
        progress: 0
      }));
      setUploadProgress(progressTracking);

      const formData = new FormData();
      Array.from(files).forEach(file => {
        formData.append('files', file);
      });

      try {
        const response = await axios.post(`${API}/projects/${projectId}/documents/batch-upload`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        
        setSuccess(`${files.length} documentos subidos exitosamente. Procesando...`);
        setBatchTaskId(response.data.batch_task_id);
        
        // Start polling for batch status
        pollBatchStatus(response.data.batch_task_id);
        
      } catch (error) {
        setError(error.response?.data?.detail || 'Error al subir los documentos');
        setBatchUploading(false);
      }
    }
  };

  const pollBatchStatus = async (taskId) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await axios.get(`${API}/projects/${projectId}/batch-status/${taskId}`);
        const status = response.data;
        
        setBatchProgress(status);
        
        // Update individual file progress
        const updatedProgress = uploadProgress.map(item => {
          const docStatus = status.document_statuses.find(doc => 
            doc.filename === item.name
          );
          return {
            ...item,
            status: docStatus ? docStatus.status : 'pending',
            progress: docStatus ? (docStatus.status === 'completed' ? 100 : docStatus.status === 'processing' ? 50 : 0) : 0
          };
        });
        setUploadProgress(updatedProgress);
        
        // Stop polling when batch is completed
        if (status.status === 'completed' || status.status === 'failed') {
          clearInterval(pollInterval);
          setBatchUploading(false);
          setBatchTaskId(null);
          fetchDocuments();
          
          if (status.status === 'completed') {
            setSuccess(`Procesamiento completado: ${status.completed_documents} exitosos, ${status.failed_documents} fallidos`);
          } else {
            setError('Error en el procesamiento del lote');
          }
        }
      } catch (error) {
        console.error('Error polling batch status:', error);
        clearInterval(pollInterval);
        setBatchUploading(false);
      }
    }, 2000); // Poll every 2 seconds
  };

  const handleRenameDocument = async (documentId, newName) => {
    try {
      await axios.put(`${API}/documents/${documentId}/rename`, {
        new_name: newName
      });
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

  const handleQABadgeClick = (document) => {
    setSelectedDocument(document);
    setQaComments(document.qa_review_comments || '');
    setShowQAModal(true);
  };

  const handleQAReview = async (action) => {
    if (!selectedDocument) return;
    
    try {
      setSubmittingReview(true);
      await axios.post(
        `${API}/projects/${projectId}/documents/${selectedDocument.id}/qa-review`,
        {
          action: action,  // "approved" or "rejected"
          comments: qaComments
        }
      );
      
      setSuccess(`Documento ${action === 'approved' ? 'aprobado' : 'rechazado'} exitosamente`);
      setShowQAModal(false);
      setSelectedDocument(null);
      setQaComments('');
      fetchDocuments();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al procesar la revisión QA');
    } finally {
      setSubmittingReview(false);
    }
  };

  const getStatusColor = (status) => {
    const colors = {
      'uploaded': 'status-uploaded',
      'qa_pending': 'status-processing',
      'qa_failed': 'status-failed',
      'qa_passed': 'status-completed',
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
      'qa_pending': 'QA en Proceso',
      'qa_failed': 'QA Falló',
      'qa_passed': 'QA ✓ → IA Processing',
      'processing': 'Extracción IA',
      'completed': 'Completado',
      'failed': 'Fallido',
      'needs_review': 'Revisión Manual'
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

      {/* Read-only notice for clients */}
      {user && user.role === 'client' && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-blue-400 mt-0.5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h4 className="text-sm font-medium text-blue-800 mb-1">
                Modo de Solo Consulta
              </h4>
              <p className="text-sm text-blue-700">
                Como cliente, tienes acceso de solo lectura a los proyectos. Para realizar cambios o subir documentos, contacta a tu asesor o administrador.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('documents')}
            className={`${
              activeTab === 'documents'
                ? 'border-emerald-500 text-emerald-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
          >
            📄 Documentos
          </button>
          {/* PDF Manager tabs only for staff and asesor */}
          {user && (user.role === 'staff' || user.role === 'asesor') && (
            <>
              <button
                onClick={() => setActiveTab('pdf-manager')}
                className={`${
                  activeTab === 'pdf-manager'
                    ? 'border-emerald-500 text-emerald-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
              >
                🤖 PDF Manager IA
              </button>
              <button
                onClick={() => setActiveTab('pdf-page-manager')}
                className={`${
                  activeTab === 'pdf-page-manager'
                    ? 'border-emerald-500 text-emerald-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm`}
              >
                📄 PDF Manager IA por Página
              </button>
            </>
          )}
        </nav>
      </div>

      {error && <div className="alert alert-error">{typeof error === 'string' ? error : JSON.stringify(error)}</div>}
      {success && <div className="alert alert-success">{typeof success === 'string' ? success : JSON.stringify(success)}</div>}

      {/* Tab Content: PDF Manager */}
      {activeTab === 'pdf-manager' && (
        <PDFManager projectId={projectId} user={user} />
      )}

      {/* Tab Content: PDF Page Manager */}
      {activeTab === 'pdf-page-manager' && (
        <PDFPageManager projectId={projectId} user={user} />
      )}

      {/* Tab Content: Documents */}
      {activeTab === 'documents' && (
        <>
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

      {/* File Upload Area - Only for staff and asesor */}
      {user && (user.role === 'staff' || user.role === 'asesor') && (
        <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Subir Documentos</h2>
          
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
              multiple
              onChange={(e) => handleFileUpload(e.target.files)}
              className="hidden"
            />
            
            {uploading ? (
              <div className="flex flex-col items-center">
                <div className="spinner mb-4"></div>
                <p className="text-gray-600">Subiendo documento...</p>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center">
                <svg className="file-upload-icon mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
                <p className="file-upload-text mb-1">
                  Arrastra archivos PDF o <span className="text-emerald-600 font-medium">haz clic</span>
                </p>
                <p className="file-upload-hint">
                  Máximo 10 archivos simultáneos • 500 MB por archivo • 1 GB por lote
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Para proyectos grandes (+1GB), sube en múltiples lotes
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Batch Upload Progress */}
      {(batchUploading || uploadProgress.length > 0) && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Procesando Lote de Documentos
              </h2>
              {batchProgress.progress !== undefined && (
                <div className="flex items-center space-x-2">
                  <div className="w-32 bg-gray-200 rounded-full h-2">
                    <div 
                      className="bg-emerald-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${batchProgress.progress}%` }}
                    ></div>
                  </div>
                  <span className="text-sm text-gray-600">{batchProgress.progress}%</span>
                </div>
              )}
            </div>

            {batchProgress.status && (
              <div className="mb-4 text-sm text-gray-600">
                Estado: <span className="font-medium">{batchProgress.status}</span> • 
                Completados: {batchProgress.completed_documents || 0} • 
                Fallidos: {batchProgress.failed_documents || 0} • 
                Total: {batchProgress.total_documents || 0}
              </div>
            )}

            <div className="space-y-2">
              {uploadProgress.map((file, index) => (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <div className="flex-shrink-0">
                      {file.status === 'completed' ? (
                        <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      ) : file.status === 'failed' ? (
                        <svg className="w-5 h-5 text-red-500" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                        </svg>
                      ) : file.status === 'processing' ? (
                        <svg className="animate-spin w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="m4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                      ) : (
                        <svg className="w-5 h-5 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm0 2h12v8H4V6z" clipRule="evenodd" />
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {file.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {file.status === 'completed' ? 'Procesado exitosamente' :
                         file.status === 'processing' ? 'Procesando con IA...' :
                         file.status === 'failed' ? 'Error en procesamiento' :
                         'Esperando...'}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Documents List */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-900">
              Documentos ({documents.length})
            </h2>
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
                            <span>{document.original_filename || 'Documento sin nombre'}</span>
                          )}
                        </h4>
                      </div>
                      <div className="flex items-center mt-1 space-x-4">
                        <span className="text-xs text-gray-500">
                          Subido {document.created_at ? new Date(document.created_at).toLocaleDateString() : 'Fecha no disponible'}
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
                      {document.reorder_reasoning && typeof document.reorder_reasoning === 'string' && (
                        <div className="mt-2 text-xs text-gray-600 bg-gray-50 rounded p-2">
                          <strong>IA:</strong> {document.reorder_reasoning}
                        </div>
                      )}
                      {/* Progress Message */}
                      {document.processing_message && document.status === 'processing' && (
                        <div className="mt-2">
                          <div className="flex items-center space-x-2">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-emerald-600"></div>
                            <span className="text-sm text-emerald-700 font-medium">
                              {document.processing_message}
                            </span>
                          </div>
                          {document.processing_progress > 0 && (
                            <div className="mt-2 w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-emerald-600 h-2 rounded-full transition-all duration-300"
                                style={{ width: `${document.processing_progress}%` }}
                              ></div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    <span className={`status-badge ${getStatusColor(document.status)}`}>
                      {getStatusText(document.status)}
                    </span>
                    
                    {/* QA Status Indicator - Clickeable */}
                    {document.qa_status && document.qa_results && (
                      <button
                        onClick={() => handleQABadgeClick(document)}
                        className="text-xs text-gray-600 bg-blue-50 border border-blue-200 rounded px-2 py-1 hover:bg-blue-100 transition-colors cursor-pointer"
                      >
                        {typeof document.qa_results.overall_score === 'number' && (
                          <span className={`font-medium ${
                            document.qa_results.overall_score >= 80 ? 'text-green-600' :
                            document.qa_results.overall_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                          }`}>
                            QA: {document.qa_results.overall_score.toFixed(0)}%
                          </span>
                        )}
                        {document.qa_findings && Array.isArray(document.qa_findings) && document.qa_findings.length > 0 && (
                          <span className="text-red-600 ml-1">({document.qa_findings.length} hallazgos)</span>
                        )}
                        <svg className="w-3 h-3 inline ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      </button>
                    )}
                    
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => {
                          setRenamingDoc(document.id);
                          setNewDocName(document.original_filename || '');
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

      {/* QA Review Modal */}
      {showQAModal && selectedDocument && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h3 className="text-2xl font-bold text-gray-900">
                    Revisión de Calidad (QA)
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    {selectedDocument.original_filename}
                  </p>
                </div>
                <button
                  onClick={() => {
                    setShowQAModal(false);
                    setSelectedDocument(null);
                    setQaComments('');
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* QA Score */}
              {selectedDocument.qa_results && (
                <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700">Puntuación General</h4>
                      <p className={`text-3xl font-bold ${
                        selectedDocument.qa_results.overall_score >= 80 ? 'text-green-600' :
                        selectedDocument.qa_results.overall_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {selectedDocument.qa_results.overall_score.toFixed(1)}%
                      </p>
                    </div>
                    <div className="text-right">
                      <span className={`px-3 py-1 rounded-full text-sm font-semibold ${
                        selectedDocument.qa_results.overall_score >= 80 ? 'bg-green-100 text-green-800' :
                        selectedDocument.qa_results.overall_score >= 60 ? 'bg-yellow-100 text-yellow-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {selectedDocument.qa_results.overall_score >= 80 ? 'Aprobado' :
                         selectedDocument.qa_results.overall_score >= 60 ? 'Revisión Requerida' : 'Fallido'}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* QA Findings */}
              {selectedDocument.qa_results && selectedDocument.qa_results.agent_results && (
                <div className="mb-6">
                  <h4 className="text-lg font-semibold text-gray-900 mb-3">Hallazgos</h4>
                  <div className="space-y-3">
                    {selectedDocument.qa_results.agent_results.map((agentResult, idx) => (
                      <div key={idx} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                        <div className="flex items-start justify-between mb-2">
                          <h5 className="font-medium text-gray-900">{agentResult.agent_name}</h5>
                          <span className="text-sm text-gray-600">
                            Score: {agentResult.score?.toFixed(1) || 'N/A'}%
                          </span>
                        </div>
                        {agentResult.findings && agentResult.findings.length > 0 && (
                          <ul className="space-y-2 mt-3">
                            {agentResult.findings.map((finding, findingIdx) => (
                              <li key={findingIdx} className="flex items-start">
                                <span className={`inline-block w-2 h-2 rounded-full mt-1.5 mr-2 ${
                                  finding.severity === 'critical' ? 'bg-red-500' :
                                  finding.severity === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
                                }`}></span>
                                <div className="flex-1">
                                  <p className="text-sm text-gray-700">{finding.description}</p>
                                  {finding.suggestion && (
                                    <p className="text-xs text-gray-500 mt-1">
                                      <strong>Sugerencia:</strong> {finding.suggestion}
                                    </p>
                                  )}
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Previous Review Info */}
              {selectedDocument.qa_review_action && (
                <div className="mb-6 bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2">Revisión Anterior</h4>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-gray-600">
                        <strong>Acción:</strong> 
                        <span className={`ml-2 px-2 py-1 rounded text-xs font-semibold ${
                          selectedDocument.qa_review_action === 'approved' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {selectedDocument.qa_review_action === 'approved' ? 'Aprobado' : 'Rechazado'}
                        </span>
                      </p>
                      <p className="text-sm text-gray-600 mt-1">
                        <strong>Por:</strong> {selectedDocument.qa_reviewed_by_name || 'N/A'}
                      </p>
                    </div>
                    <div className="text-right text-xs text-gray-500">
                      {selectedDocument.qa_approved_at && new Date(selectedDocument.qa_approved_at).toLocaleString('es-ES')}
                    </div>
                  </div>
                  {selectedDocument.qa_review_comments && (
                    <div className="mt-2 pt-2 border-t border-gray-200">
                      <p className="text-sm text-gray-600">
                        <strong>Comentarios:</strong>
                      </p>
                      <p className="text-sm text-gray-700 mt-1">{selectedDocument.qa_review_comments}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Comments Section */}
              {user.role === 'staff' && (
                <div className="mb-6">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Comentarios de Revisión
                  </label>
                  <textarea
                    value={qaComments}
                    onChange={(e) => setQaComments(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                    rows="4"
                    placeholder="Agrega comentarios sobre la revisión (opcional)"
                  />
                </div>
              )}

              {/* Action Buttons */}
              {user.role === 'staff' && (
                <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                  <button
                    onClick={() => {
                      setShowQAModal(false);
                      setSelectedDocument(null);
                      setQaComments('');
                    }}
                    disabled={submittingReview}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                  >
                    Cerrar
                  </button>
                  <button
                    onClick={() => handleQAReview('rejected')}
                    disabled={submittingReview}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50"
                  >
                    {submittingReview ? 'Procesando...' : 'Rechazar'}
                  </button>
                  <button
                    onClick={() => handleQAReview('approved')}
                    disabled={submittingReview}
                    className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50"
                  >
                    {submittingReview ? 'Procesando...' : 'Aprobar'}
                  </button>
                </div>
              )}

              {/* Info for non-staff users */}
              {user.role !== 'staff' && (
                <div className="flex justify-end pt-4 border-t border-gray-200">
                  <button
                    onClick={() => {
                      setShowQAModal(false);
                      setSelectedDocument(null);
                    }}
                    className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                  >
                    Cerrar
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};

export default ProjectDetail;
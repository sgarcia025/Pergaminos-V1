import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const QAFindings = ({ user }) => {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [findings, setFindings] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [approvalData, setApprovalData] = useState({
    action: 'approve',
    comments: ''
  });
  
  // Bulk selection states
  const [selectedDocuments, setSelectedDocuments] = useState([]);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [bulkAction, setBulkAction] = useState(''); // 'approve' or 'reject'
  const [bulkComments, setBulkComments] = useState('');
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      fetchFindings();
    }
  }, [selectedProject]);

  const fetchProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setProjects(response.data);
      if (response.data.length > 0) {
        setSelectedProject(response.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
      setError('Error al cargar proyectos');
    } finally {
      setLoading(false);
    }
  };

  const fetchFindings = async () => {
    if (!selectedProject) return;

    try {
      setError('');
      const response = await axios.get(`${API}/projects/${selectedProject}/qa-findings`);
      setFindings(response.data);
    } catch (error) {
      console.error('Error fetching QA findings:', error);
      setError('Error al cargar hallazgos de QA');
    }
  };

  const handleApproval = async () => {
    if (!selectedDocument) return;

    try {
      await axios.post(`${API}/documents/${selectedDocument.document_id}/qa-approve`, approvalData);
      setSuccess(`Documento ${approvalData.action === 'approve' ? 'aprobado' : 'rechazado'} exitosamente`);
      setShowApprovalModal(false);
      setSelectedDocument(null);
      setApprovalData({ action: 'approve', comments: '' });
      fetchFindings(); // Refresh findings
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al procesar aprobación');
    }
  };

  const handleDocumentToggle = (documentId) => {
    setSelectedDocuments(prev => {
      if (prev.includes(documentId)) {
        return prev.filter(id => id !== documentId);
      } else {
        return [...prev, documentId];
      }
    });
  };

  const handleSelectAll = () => {
    if (selectedDocuments.length === findings.documents_with_findings.length) {
      setSelectedDocuments([]);
    } else {
      setSelectedDocuments(findings.documents_with_findings.map(doc => doc.document_id));
    }
  };

  const handleBulkAction = (action) => {
    if (selectedDocuments.length === 0) {
      setError('Por favor selecciona al menos un documento');
      return;
    }
    setBulkAction(action);
    setBulkComments('');
    setShowBulkModal(true);
  };

  const handleBulkApproval = async () => {
    if (!bulkComments.trim()) {
      setError('Por favor agrega un comentario para el procesamiento masivo');
      return;
    }

    setProcessing(true);
    setError('');
    
    try {
      const promises = selectedDocuments.map(docId => {
        return axios.post(
          `${API}/projects/${selectedProject}/documents/${docId}/qa-review`,
          {
            action: bulkAction === 'approve' ? 'approved' : 'rejected',
            comments: bulkComments
          }
        );
      });

      await Promise.all(promises);
      
      setSuccess(`${selectedDocuments.length} documento(s) ${bulkAction === 'approve' ? 'aprobado(s)' : 'rechazado(s)'} exitosamente`);
      setShowBulkModal(false);
      setBulkComments('');
      setSelectedDocuments([]);
      fetchFindings();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al procesar documentos');
    } finally {
      setProcessing(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      'failed': { color: 'bg-red-100 text-red-800', text: 'QA Falló' },
      'manual_review': { color: 'bg-yellow-100 text-yellow-800', text: 'Revisión Manual' }
    };
    
    const config = statusConfig[status] || { color: 'bg-gray-100 text-gray-800', text: status };
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color}`}>
        {config.text}
      </span>
    );
  };

  const getSeverityColor = (type) => {
    const colors = {
      'critical': 'text-red-600 bg-red-50',
      'warning': 'text-yellow-600 bg-yellow-50',
      'info': 'text-blue-600 bg-blue-50'
    };
    return colors[type] || 'text-gray-600 bg-gray-50';
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  if (user.role === 'client') {
    return (
      <div className="text-center py-12">
        <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Acceso Restringido</h3>
        <p className="text-gray-600">
          Solo el personal staff puede revisar hallazgos de QA.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Hallazgos de Control de Calidad
          </h1>
          <p className="text-gray-600 mt-1">
            Documentos que requieren revisión manual después del proceso QA
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Project Selector */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <label htmlFor="project-select" className="block text-sm font-medium text-gray-700 mb-2">
          Seleccionar Proyecto
        </label>
        <select
          id="project-select"
          value={selectedProject}
          onChange={(e) => setSelectedProject(e.target.value)}
          className="form-input w-full md:w-1/2"
        >
          <option value="">Seleccione un proyecto</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>

      {/* Findings Summary */}
      {findings.summary && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Resumen de Hallazgos</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-red-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-red-600">{findings.summary.failed_qa}</div>
              <div className="text-red-700 text-sm">QA Falló</div>
            </div>
            <div className="bg-yellow-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-yellow-600">{findings.summary.manual_review}</div>
              <div className="text-yellow-700 text-sm">Revisión Manual</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-4">
              <div className="text-2xl font-bold text-gray-600">{findings.summary.total_documents_with_issues}</div>
              <div className="text-gray-700 text-sm">Total con Problemas</div>
            </div>
          </div>
        </div>
      )}

      {/* Documents with Findings */}
      {findings.documents_with_findings && findings.documents_with_findings.length > 0 ? (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">
                Documentos con Hallazgos ({findings.documents_with_findings.length})
                {selectedDocuments.length > 0 && (
                  <span className="ml-2 text-sm font-normal text-emerald-600">
                    ({selectedDocuments.length} seleccionados)
                  </span>
                )}
              </h3>
              
              {/* Bulk Action Buttons */}
              {selectedDocuments.length > 0 && (
                <div className="flex gap-2">
                  <button
                    onClick={() => handleBulkAction('approve')}
                    className="px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
                  >
                    ✓ Aprobar Seleccionados ({selectedDocuments.length})
                  </button>
                  <button
                    onClick={() => handleBulkAction('reject')}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors"
                  >
                    ✗ Rechazar Seleccionados ({selectedDocuments.length})
                  </button>
                </div>
              )}
            </div>
          </div>
          
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left">
                    <input
                      type="checkbox"
                      checked={selectedDocuments.length === findings.documents_with_findings.length}
                      onChange={handleSelectAll}
                      className="w-4 h-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500"
                    />
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Documento
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Estado QA
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Puntaje
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Hallazgos
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Fecha
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {findings.documents_with_findings.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <input
                        type="checkbox"
                        checked={selectedDocuments.includes(doc.document_id)}
                        onChange={() => handleDocumentToggle(doc.document_id)}
                        className="w-4 h-4 text-emerald-600 border-gray-300 rounded focus:ring-emerald-500"
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {doc.filename}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {getStatusBadge(doc.qa_status)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className={`text-sm font-medium ${
                        doc.qa_score >= 80 ? 'text-green-600' :
                        doc.qa_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {doc.qa_score.toFixed(1)}/100
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="space-y-1">
                        {doc.critical_findings.slice(0, 2).map((finding, idx) => (
                          <div key={idx} className={`text-xs px-2 py-1 rounded ${getSeverityColor(finding.finding.type)}`}>
                            {finding.finding.description}
                          </div>
                        ))}
                        {doc.critical_findings.length > 2 && (
                          <div className="text-xs text-gray-500">
                            +{doc.critical_findings.length - 2} más
                          </div>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {doc.qa_processed_at ? new Date(doc.qa_processed_at).toLocaleString() : 'N/A'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                      <button
                        onClick={() => {
                          setSelectedDocument(doc);
                          setShowApprovalModal(true);
                        }}
                        className="text-blue-600 hover:text-blue-900"
                      >
                        Revisar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : selectedProject ? (
        <div className="text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay hallazgos</h3>
          <p className="text-gray-600">
            Todos los documentos de este proyecto han pasado el control de calidad.
          </p>
        </div>
      ) : null}

      {/* Approval Modal */}
      {showApprovalModal && selectedDocument && (
        <div className="modal-overlay" onClick={() => setShowApprovalModal(false)}>
          <div className="modal max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Revisar Documento: {selectedDocument.filename}</h3>
              <button
                onClick={() => setShowApprovalModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <div className="space-y-6">
              {/* Document Info */}
              <div className="bg-gray-50 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-700">Estado QA:</label>
                    <div className="mt-1">{getStatusBadge(selectedDocument.qa_status)}</div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Puntaje:</label>
                    <div className={`mt-1 text-lg font-semibold ${
                      selectedDocument.qa_score >= 80 ? 'text-green-600' :
                      selectedDocument.qa_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                    }`}>
                      {selectedDocument.qa_score.toFixed(1)}/100
                    </div>
                  </div>
                </div>
              </div>

              {/* Critical Findings */}
              <div>
                <h4 className="text-lg font-semibold text-gray-900 mb-3">Hallazgos Críticos</h4>
                <div className="space-y-3">
                  {selectedDocument.critical_findings.map((finding, idx) => (
                    <div key={idx} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(finding.finding.type)}`}>
                              {finding.finding.type.toUpperCase()}
                            </span>
                            <span className="text-sm font-medium text-gray-700">
                              {finding.finding.category}
                            </span>
                          </div>
                          <p className="text-gray-900 mb-2">{finding.finding.description}</p>
                          {finding.finding.location && (
                            <p className="text-sm text-gray-600">Ubicación: {finding.finding.location}</p>
                          )}
                          {finding.finding.recommendation && (
                            <p className="text-sm text-blue-600 mt-2">
                              Recomendación: {finding.finding.recommendation}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Approval Actions */}
              <div>
                <h4 className="text-lg font-semibold text-gray-900 mb-3">Decisión de Revisión</h4>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Acción
                    </label>
                    <div className="space-y-2">
                      <label className="flex items-center">
                        <input
                          type="radio"
                          value="approve"
                          checked={approvalData.action === 'approve'}
                          onChange={(e) => setApprovalData({ ...approvalData, action: e.target.value })}
                          className="mr-2"
                        />
                        <span className="text-green-700">Aprobar y continuar con procesamiento IA</span>
                      </label>
                      <label className="flex items-center">
                        <input
                          type="radio"
                          value="reject"
                          checked={approvalData.action === 'reject'}
                          onChange={(e) => setApprovalData({ ...approvalData, action: e.target.value })}
                          className="mr-2"
                        />
                        <span className="text-red-700">Rechazar documento</span>
                      </label>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Comentarios
                    </label>
                    <textarea
                      value={approvalData.comments}
                      onChange={(e) => setApprovalData({ ...approvalData, comments: e.target.value })}
                      className="form-textarea w-full"
                      rows="3"
                      placeholder="Comentarios sobre la decisión tomada..."
                    />
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowApprovalModal(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleApproval}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    approvalData.action === 'approve'
                      ? 'bg-green-600 text-white hover:bg-green-700'
                      : 'bg-red-600 text-white hover:bg-red-700'
                  }`}
                >
                  {approvalData.action === 'approve' ? 'Aprobar' : 'Rechazar'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Action Confirmation Modal */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full">
            <div className="p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-xl font-bold text-gray-900">
                    {bulkAction === 'approve' ? '✓ Aprobar Documentos' : '✗ Rechazar Documentos'}
                  </h3>
                  <p className="text-sm text-gray-600 mt-1">
                    Vas a {bulkAction === 'approve' ? 'aprobar' : 'rechazar'} {selectedDocuments.length} documento(s)
                  </p>
                </div>
                <button
                  onClick={() => setShowBulkModal(false)}
                  disabled={processing}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Selected Documents Preview */}
              <div className="mb-4 bg-gray-50 rounded-lg p-4 max-h-40 overflow-y-auto">
                <h4 className="text-sm font-semibold text-gray-700 mb-2">Documentos seleccionados:</h4>
                <ul className="space-y-1">
                  {selectedDocuments.map(docId => {
                    const doc = findings.documents_with_findings.find(d => d.document_id === docId);
                    return (
                      <li key={docId} className="text-sm text-gray-600 flex items-center">
                        <svg className="w-4 h-4 mr-2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {doc?.filename || 'Documento'}
                      </li>
                    );
                  })}
                </ul>
              </div>

              {/* Comments Input */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Comentarios * (obligatorio para procesamiento masivo)
                </label>
                <textarea
                  value={bulkComments}
                  onChange={(e) => setBulkComments(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  rows="4"
                  placeholder={`Escribe el motivo por el cual ${bulkAction === 'approve' ? 'apruebas' : 'rechazas'} estos documentos...`}
                  disabled={processing}
                />
                <p className="text-xs text-gray-500 mt-1">
                  Este comentario se aplicará a todos los documentos seleccionados
                </p>
              </div>

              {/* Warning Message */}
              <div className={`mb-4 p-4 rounded-lg ${bulkAction === 'approve' ? 'bg-green-50' : 'bg-red-50'}`}>
                <div className="flex items-start">
                  <svg className={`w-5 h-5 mr-2 mt-0.5 ${bulkAction === 'approve' ? 'text-green-600' : 'text-red-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="flex-1">
                    <p className={`text-sm font-medium ${bulkAction === 'approve' ? 'text-green-800' : 'text-red-800'}`}>
                      {bulkAction === 'approve' 
                        ? '¿Confirmas que deseas aprobar todos estos documentos?'
                        : '¿Confirmas que deseas rechazar todos estos documentos?'}
                    </p>
                    <p className={`text-xs mt-1 ${bulkAction === 'approve' ? 'text-green-700' : 'text-red-700'}`}>
                      Esta acción {bulkAction === 'approve' ? 'continuará el procesamiento de estos documentos' : 'marcará estos documentos como fallidos'}.
                    </p>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => setShowBulkModal(false)}
                  disabled={processing}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleBulkApproval}
                  disabled={processing || !bulkComments.trim()}
                  className={`px-6 py-2 text-sm font-medium text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                    bulkAction === 'approve' 
                      ? 'bg-green-600 hover:bg-green-700' 
                      : 'bg-red-600 hover:bg-red-700'
                  }`}
                >
                  {processing ? (
                    <>
                      <svg className="animate-spin h-4 w-4 inline mr-2" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Procesando...
                    </>
                  ) : (
                    <>
                      {bulkAction === 'approve' ? '✓ Aprobar Todo' : '✗ Rechazar Todo'}
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QAFindings;
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PDFManager = ({ projectId, user }) => {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentJob, setCurrentJob] = useState(null);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [executing, setExecuting] = useState(false);
  const [showAuditDrawer, setShowAuditDrawer] = useState(false);
  const [recentJobs, setRecentJobs] = useState([]);

  useEffect(() => {
    if (projectId) {
      fetchRecentJobs();
    }
  }, [projectId]);

  const fetchRecentJobs = async () => {
    try {
      const response = await axios.get(`${API}/projects/${projectId}/pdf-manager/jobs?limit=5`);
      setRecentJobs(response.data.jobs || []);
    } catch (error) {
      console.error('Error fetching recent jobs:', error);
    }
  };

  const handleGeneratePlan = async () => {
    if (!instruction.trim()) {
      setError('Por favor ingresa una instrucción');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setPlan(null);

    try {
      const response = await axios.post(`${API}/projects/${projectId}/pdf-manager/plan`, {
        project_id: projectId,
        instruction: instruction
      });

      setCurrentJob(response.data);
      setPlan(response.data.plan);
      setSuccess(`Plan generado con ${response.data.plan.rename_operations.length} renombrados y ${response.data.plan.reorder_ids.length} documentos reordenados`);
      fetchRecentJobs();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al generar el plan');
    } finally {
      setLoading(false);
    }
  };

  const handleExecutePlan = async () => {
    if (!currentJob || !currentJob.job_id) {
      setError('No hay plan para ejecutar');
      return;
    }

    if (user.role === 'client') {
      setError('Los clientes no pueden ejecutar planes. Contacta a tu asesor o administrador.');
      return;
    }

    setExecuting(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(`${API}/projects/${projectId}/pdf-manager/execute`, {
        job_id: currentJob.job_id
      });

      setCurrentJob(response.data);
      setSuccess('Plan ejecutado exitosamente. Los archivos están listos para descargar.');
      fetchRecentJobs();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al ejecutar el plan');
    } finally {
      setExecuting(false);
    }
  };

  const handleLoadJob = async (jobId) => {
    try {
      const response = await axios.get(`${API}/projects/${projectId}/pdf-manager/jobs/${jobId}`);
      setCurrentJob(response.data);
      setPlan(response.data.plan);
      setInstruction(response.data.instruction);
      setError('');
    } catch (error) {
      setError('Error al cargar el trabajo');
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const handleDownloadFile = async (url, filename) => {
    try {
      const response = await axios.get(`${BACKEND_URL}${url}`, {
        responseType: 'blob'
      });
      
      // Create blob link to download
      const blob = new Blob([response.data]);
      const link = document.createElement('a');
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      
      // Cleanup
      window.URL.revokeObjectURL(link.href);
    } catch (error) {
      console.error('Error downloading file:', error);
      setError('Error al descargar el archivo. Por favor intenta nuevamente.');
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-2xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            🤖 PDF Manager con IA
          </h2>
          <p className="text-gray-600 mt-1">
            Renombra y reordena documentos usando instrucciones en lenguaje natural
          </p>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-start">
          <svg className="w-5 h-5 text-blue-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-blue-800">Cómo funciona</h3>
            <p className="text-sm text-blue-700 mt-1">
              1) Escribe una instrucción en lenguaje natural (ej: "Renombrar con Proyecto - Fecha - Cliente y ordenar por fecha más reciente")
              <br />
              2) Genera el plan con IA para revisar los cambios
              <br />
              3) Si estás conforme, aplica los cambios para renombrar y generar el ZIP ordenado
            </p>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Instruction Input */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <label htmlFor="instruction" className="block text-sm font-medium text-gray-700 mb-2">
          Instrucción en Lenguaje Natural *
        </label>
        <textarea
          id="instruction"
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          className="form-textarea w-full h-32"
          placeholder="Ejemplo: Renombrar PDFs con patrón Proyecto - Fecha - Cliente y ordenar por fecha más reciente"
          disabled={loading || executing}
        />
        
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-gray-500">
            Usa palabras clave como: proyecto, fecha, cliente, ordenar, alfabético, más reciente, etc.
          </p>
          <button
            onClick={handleGeneratePlan}
            disabled={loading || !instruction.trim()}
            className="btn-primary"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Generando Plan...
              </>
            ) : (
              <>
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Generar Plan con IA
              </>
            )}
          </button>
        </div>
      </div>

      {/* Plan Preview */}
      {plan && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">📋 Vista Previa del Plan</h3>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">
                Confianza: {(plan.validation.confidence * 100).toFixed(0)}%
              </span>
              <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${plan.validation.confidence > 0.8 ? 'bg-green-500' : plan.validation.confidence > 0.6 ? 'bg-yellow-500' : 'bg-red-500'}`}
                  style={{ width: `${plan.validation.confidence * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* Conflicts and Warnings */}
          {(plan.validation.conflicts.length > 0 || plan.validation.warnings.length > 0) && (
            <div className="mb-4 space-y-2">
              {plan.validation.conflicts.map((conflict, idx) => (
                <div key={idx} className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-800">
                  ⚠️ {conflict}
                </div>
              ))}
              {plan.validation.warnings.map((warning, idx) => (
                <div key={idx} className="bg-yellow-50 border border-yellow-200 rounded p-3 text-sm text-yellow-800">
                  ⚡ {warning}
                </div>
              ))}
            </div>
          )}

          {/* Rename Operations Table */}
          {plan.rename_operations.length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-700 mb-3">Operaciones de Renombrado ({plan.rename_operations.length})</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Nombre Actual</th>
                      <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">→</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Nombre Nuevo</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {plan.rename_operations.slice(0, 10).map((op, idx) => (
                      <tr key={idx}>
                        <td className="px-4 py-2 text-sm text-gray-600">{op.from_name}</td>
                        <td className="px-4 py-2 text-center text-emerald-600">→</td>
                        <td className="px-4 py-2 text-sm font-medium text-gray-900">{op.to_name}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {plan.rename_operations.length > 10 && (
                  <p className="text-xs text-gray-500 mt-2 text-center">
                    ... y {plan.rename_operations.length - 10} más
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Reorder Info */}
          <div className="mb-4 p-3 bg-gray-50 rounded">
            <p className="text-sm text-gray-700">
              📑 {plan.reorder_ids.length} documentos serán reordenados según tu instrucción
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-4 border-t border-gray-200">
            <button
              onClick={() => setShowAuditDrawer(true)}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              📜 Ver Detalles del Job
            </button>
            
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setPlan(null);
                  setCurrentJob(null);
                  setInstruction('');
                }}
                className="btn-secondary"
                disabled={executing}
              >
                Cancelar
              </button>
              <button
                onClick={handleExecutePlan}
                disabled={executing || plan.validation.conflicts.length > 0 || currentJob?.status === 'completed'}
                className="btn-primary"
              >
                {executing ? (
                  <>
                    <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Ejecutando...
                  </>
                ) : currentJob?.status === 'completed' ? (
                  '✓ Ya Ejecutado'
                ) : (
                  <>
                    <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Aplicar Cambios
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Results - Download Links */}
      {currentJob?.result_urls && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">✅ Resultados</h3>
          
          {/* ZIP Download */}
          <div className="mb-6 p-4 bg-emerald-50 border border-emerald-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-emerald-900">📦 Archivo ZIP Completo</h4>
                <p className="text-sm text-emerald-700 mt-1">
                  {currentJob.result_urls.zip_filename} ({formatFileSize(currentJob.result_urls.zip_size)})
                </p>
              </div>
              <button
                onClick={() => handleDownloadFile(currentJob.result_urls.zip_url, currentJob.result_urls.zip_filename)}
                className="btn-primary"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Descargar ZIP
              </button>
            </div>
          </div>

          {/* Individual Files */}
          <h4 className="text-sm font-medium text-gray-700 mb-3">Archivos Individuales ({currentJob.result_urls.total_files})</h4>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {currentJob.result_urls.files.slice(0, 20).map((file, idx) => (
              <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded hover:bg-gray-100">
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900">{file.name}</p>
                  <p className="text-xs text-gray-500">{formatFileSize(file.size)}</p>
                </div>
                <button
                  onClick={() => handleDownloadFile(file.url, file.name)}
                  className="text-emerald-600 hover:text-emerald-700 text-sm cursor-pointer"
                  title="Descargar archivo"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Jobs */}
      {recentJobs.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">📚 Trabajos Recientes</h3>
          <div className="space-y-2">
            {recentJobs.map((job) => (
              <div
                key={job.id}
                className="flex items-center justify-between p-3 bg-gray-50 rounded hover:bg-gray-100 cursor-pointer"
                onClick={() => handleLoadJob(job.id)}
              >
                <div className="flex-1">
                  <p className="text-sm font-medium text-gray-900 truncate">{job.instruction}</p>
                  <p className="text-xs text-gray-500">
                    {new Date(job.created_at).toLocaleString()} • {job.status}
                  </p>
                </div>
                <span className={`status-badge ${
                  job.status === 'completed' ? 'status-completed' : 
                  job.status === 'failed' ? 'status-failed' : 
                  'status-processing'
                }`}>
                  {job.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Audit Drawer */}
      {showAuditDrawer && currentJob && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div className="absolute inset-0 bg-gray-500 bg-opacity-75" onClick={() => setShowAuditDrawer(false)}></div>
          <div className="fixed inset-y-0 right-0 max-w-2xl w-full bg-white shadow-xl">
            <div className="h-full flex flex-col">
              <div className="px-6 py-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-gray-900">Detalles del Job</h3>
                  <button
                    onClick={() => setShowAuditDrawer(false)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6">
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Job ID</h4>
                    <p className="text-sm text-gray-900 font-mono">{currentJob.job_id || currentJob.id}</p>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Estado</h4>
                    <span className={`status-badge ${
                      currentJob.status === 'completed' ? 'status-completed' : 
                      currentJob.status === 'failed' ? 'status-failed' : 
                      'status-processing'
                    }`}>
                      {currentJob.status}
                    </span>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Instrucción</h4>
                    <p className="text-sm text-gray-900 mt-1">{currentJob.instruction}</p>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-medium text-gray-700">Creado</h4>
                    <p className="text-sm text-gray-900">{new Date(currentJob.created_at).toLocaleString()}</p>
                  </div>
                  
                  {currentJob.logs && currentJob.logs.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Logs</h4>
                      <div className="space-y-2">
                        {currentJob.logs.map((log, idx) => (
                          <div key={idx} className="text-xs bg-gray-50 p-2 rounded font-mono">
                            <span className="text-gray-500">{log.timestamp}</span>
                            <span className="mx-2">•</span>
                            <span className="text-gray-900">{log.event}</span>
                            {log.details && (
                              <p className="text-gray-600 mt-1">{log.details}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PDFManager;

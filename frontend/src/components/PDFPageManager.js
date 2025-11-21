import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const PDFPageManager = ({ projectId, user }) => {
  const [documents, setDocuments] = useState([]);
  const [selectedPdfs, setSelectedPdfs] = useState([]); // Changed to array for multiple selection
  const [mode, setMode] = useState('reorder'); // 'reorder' or 'extract'
  const [instruction, setInstruction] = useState('');
  const [manualRange, setManualRange] = useState(''); // For extract mode
  const [loading, setLoading] = useState(false);
  const [currentJob, setCurrentJob] = useState(null);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [executing, setExecuting] = useState(false);
  
  // Batch processing states
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [batchProgress, setBatchProgress] = useState([]);
  const [currentBatchIndex, setCurrentBatchIndex] = useState(0);

  useEffect(() => {
    if (projectId) {
      fetchDocuments();
    }
  }, [projectId]);

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/projects/${projectId}/documents`);
      // Filter only completed documents
      const completedDocs = response.data.filter(doc => 
        ['completed', 'processed', 'qa_passed'].includes(doc.status)
      );
      setDocuments(completedDocs);
    } catch (error) {
      console.error('Error fetching documents:', error);
      setError('Error al cargar los documentos');
    }
  };

  const handlePdfToggle = (pdfFilename) => {
    setSelectedPdfs(prev => {
      if (prev.includes(pdfFilename)) {
        return prev.filter(p => p !== pdfFilename);
      } else {
        return [...prev, pdfFilename];
      }
    });
  };

  const handleSelectAll = () => {
    if (selectedPdfs.length === documents.length) {
      setSelectedPdfs([]);
    } else {
      setSelectedPdfs(documents.map(doc => doc.original_filename));
    }
  };

  const processSinglePdf = async (pdfFilename, index, total) => {
    try {
      // Update progress
      setBatchProgress(prev => {
        const updated = [...prev];
        updated[index] = { status: 'generating_plan', filename: pdfFilename };
        return updated;
      });

      // Step 1: Generate plan
      const planResponse = await axios.post(`${API}/projects/${projectId}/pdf-page-manager/plan`, {
        project_id: projectId,
        pdf_filename: pdfFilename,
        instruction: instruction || (mode === 'extract' ? `Extraer páginas: ${manualRange}` : 'Reordenar'),
        mode: mode,
        manual_range: mode === 'extract' && manualRange.trim() ? manualRange.trim() : null
      });

      // Check if operation was auto-executed by backend (split operation)
      if (planResponse.data.auto_executed) {
        console.log('Auto-executed operation detected in batch processing');
        setBatchProgress(prev => {
          const updated = [...prev];
          updated[index] = { 
            status: 'completed', 
            filename: pdfFilename,
            autoExecuted: true
          };
          return updated;
        });
        return { success: true, filename: pdfFilename, autoExecuted: true };
      }

      const jobId = planResponse.data.job_id;
      
      // Validate job_id exists
      if (!jobId) {
        throw new Error('No se recibió job_id del servidor');
      }

      // Update progress
      setBatchProgress(prev => {
        const updated = [...prev];
        updated[index] = { status: 'executing', filename: pdfFilename, jobId };
        return updated;
      });

      // Step 2: Execute plan
      const executeResponse = await axios.post(
        `${API}/projects/${projectId}/pdf-page-manager/execute`,
        { job_id: jobId }
      );

      // Update progress with correct result structure
      setBatchProgress(prev => {
        const updated = [...prev];
        updated[index] = { 
          status: 'completed', 
          filename: pdfFilename, 
          jobId,
          resultUrl: executeResponse.data.result_url,
          resultFilename: executeResponse.data.result_filename
        };
        return updated;
      });

      return { success: true, filename: pdfFilename };
    } catch (error) {
      // Update progress with error
      setBatchProgress(prev => {
        const updated = [...prev];
        updated[index] = { 
          status: 'failed', 
          filename: pdfFilename,
          error: error.response?.data?.detail || error.message
        };
        return updated;
      });

      return { success: false, filename: pdfFilename, error: error.message };
    }
  };

  const handleBatchProcess = async () => {
    if (selectedPdfs.length === 0) {
      setError('Por favor selecciona al menos un PDF');
      return;
    }
    if (!instruction.trim() && !manualRange.trim()) {
      setError('Por favor ingresa una instrucción o un rango de páginas');
      return;
    }

    setBatchProcessing(true);
    setError('');
    setSuccess('');
    setBatchProgress(selectedPdfs.map(pdf => ({ status: 'pending', filename: pdf })));
    setCurrentBatchIndex(0);

    const results = [];

    // Process PDFs sequentially
    for (let i = 0; i < selectedPdfs.length; i++) {
      setCurrentBatchIndex(i + 1);
      const result = await processSinglePdf(selectedPdfs[i], i, selectedPdfs.length);
      results.push(result);
    }

    // Summary
    const successCount = results.filter(r => r.success).length;
    const failedCount = results.filter(r => !r.success).length;

    if (failedCount === 0) {
      setSuccess(`✅ Procesamiento completo: ${successCount} PDF(s) procesados exitosamente`);
    } else {
      setError(`⚠️ Procesamiento completo: ${successCount} exitosos, ${failedCount} fallidos`);
    }

    setBatchProcessing(false);
  };

  const handleGeneratePlan = async () => {
    // This is now for single PDF preview only
    if (selectedPdfs.length === 0) {
      setError('Por favor selecciona un PDF');
      return;
    }
    if (!instruction.trim() && !manualRange.trim()) {
      setError('Por favor ingresa una instrucción o un rango de páginas');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');
    setPlan(null);

    try {
      const response = await axios.post(`${API}/projects/${projectId}/pdf-page-manager/plan`, {
        project_id: projectId,
        pdf_filename: selectedPdfs[0], // Use first selected PDF for preview
        instruction: instruction || (mode === 'extract' ? `Extraer páginas: ${manualRange}` : 'Reordenar'),
        mode: mode,
        manual_range: mode === 'extract' && manualRange.trim() ? manualRange.trim() : null
      });

      console.log('=== FULL RESPONSE FROM PLAN GENERATION ===');
      console.log('Full response:', JSON.stringify(response.data, null, 2));
      console.log('==========================================');
      
      // Check if operation was auto-executed by backend
      if (response.data.auto_executed) {
        console.log('✅ OPERATION WAS AUTO-EXECUTED BY BACKEND');
        setLoading(false);
        setSuccess(response.data.message || 'Operación completada exitosamente');
        setCurrentJob(null);
        setPlan(null);
        setInstruction('');
        setSelectedPdfs([]);
        setExecuting(false);
        setBatchProcessing(false);
        return;
      }
      
      // Check if it's a split operation (multiple jobs) - legacy code
      if (response.data.is_split && response.data.job_ids && response.data.job_ids.length > 0) {
        console.log('✅ ENTERING SPLIT OPERATION BRANCH');
        setSuccess(`✅ Operación de división detectada: Se crearon ${response.data.num_splits} planes de extracción. Ejecutando automáticamente...`);
        
        // Wait a moment for DB to be consistent
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Execute all jobs automatically with progress tracking
        setExecuting(true);
        let successCount = 0;
        let failCount = 0;
        
        console.log('Split operation - job_ids received:', response.data.job_ids);
        
        for (let i = 0; i < response.data.job_ids.length; i++) {
          const jobId = response.data.job_ids[i];
          
          console.log(`Attempting to execute job ${i + 1}/${response.data.job_ids.length}, job_id:`, jobId);
          
          try {
            setSuccess(`📄 Procesando PDF ${i + 1} de ${response.data.job_ids.length}...`);
            
            const executePayload = { job_id: jobId };
            console.log('Execute payload:', executePayload);
            
            const executeResponse = await axios.post(`${API}/projects/${projectId}/pdf-page-manager/execute`, executePayload);
            
            console.log(`Job ${jobId} executed successfully:`, executeResponse.data);
            successCount++;
            
            // Small delay between executions to avoid overwhelming the server
            if (i < response.data.job_ids.length - 1) {
              await new Promise(resolve => setTimeout(resolve, 500));
            }
          } catch (err) {
            console.error(`Error executing job ${jobId}:`, err);
            console.error('Error details:', err.response?.data);
            console.error('Full error:', err);
            failCount++;
          }
        }
        
        setExecuting(false);
        
        if (failCount === 0) {
          setSuccess(`✅ ¡Operación completada! Se crearon ${successCount} documentos PDF exitosamente. Revisa el historial de PDFs.`);
        } else {
          setError(`⚠️ Se crearon ${successCount} documentos, pero ${failCount} fallaron. Revisa el historial de PDFs para más detalles.`);
        }
        
        // Clear for next operation
        setCurrentJob(null);
        setPlan(null);
        setInstruction('');
        setSelectedPdfs([]);
        
      } else {
        // Single job (original behavior)
        console.log('❌ NOT A SPLIT OPERATION - Using single job flow');
        
        // Check if the response includes success message from split operation
        if (response.data.message && response.data.message.includes('completada')) {
          // This is actually a split operation that was executed automatically
          setSuccess(response.data.message);
          setCurrentJob(null);
          setPlan(null);
          setInstruction('');
          setSelectedPdfs([]);
          return;
        }
        
        setCurrentJob(response.data);
        setPlan(response.data.plan || response.data.extract_plan);
        
        if (mode === 'extract') {
          const pagesCount = response.data.plan?.pages_to_extract?.length || response.data.extract_plan?.pages_to_extract?.length || 0;
          setSuccess(`Plan de extracción generado para "${selectedPdfs[0]}": ${pagesCount} páginas serán extraídas`);
        } else {
          setSuccess(`Plan de reordenamiento generado para "${selectedPdfs[0]}": ${response.data.plan.total_pages} páginas`);
        }
      }
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al generar el plan');
    } finally {
      setLoading(false);
    }
  };

  const handleExecutePlan = async () => {
    if (!currentJob) {
      setError('No hay plan para ejecutar');
      return;
    }
    
    // Check if job_id exists
    if (!currentJob.job_id) {
      setError('El plan no tiene un job_id válido. Por favor, genera el plan nuevamente.');
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
      const response = await axios.post(`${API}/projects/${projectId}/pdf-page-manager/execute`, {
        job_id: currentJob.job_id
      });

      setCurrentJob(response.data);
      setSuccess('Plan ejecutado exitosamente. El PDF reordenado está listo para descargar.');
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al ejecutar el plan');
    } finally {
      setExecuting(false);
    }
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
          <h2 className="text-2xl font-bold text-gray-900" >
            📄 PDF Manager IA por Página
          </h2>
          <p className="text-gray-600 mt-1">
            Reordena páginas dentro de un PDF o extrae páginas específicas para crear nuevos documentos
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
              1) Selecciona uno o varios PDFs del proyecto y elige el modo (Reordenar o Extraer)
              <br />
              2) Escribe una instrucción en lenguaje natural o usa rangos manuales
              <br />
              3) Haz clic en "Procesar X PDFs" para procesar todos los seleccionados en secuencia
              <br />
              4) Descarga cada PDF procesado cuando esté listo
            </p>
          </div>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* PDF Selection and Instruction */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-4">
        {/* PDF Multi-Selector with Checkboxes */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="block text-sm font-medium text-gray-700">
              Seleccionar PDFs * ({selectedPdfs.length} seleccionados)
            </label>
            {documents.length > 0 && (
              <button
                onClick={handleSelectAll}
                className="text-sm text-yellow-700 hover:text-yellow-700 font-medium"
                disabled={loading || executing || batchProcessing}
              >
                {selectedPdfs.length === documents.length ? 'Deseleccionar Todos' : 'Seleccionar Todos'}
              </button>
            )}
          </div>
          
          {documents.length === 0 ? (
            <p className="text-sm text-gray-500 p-4 bg-gray-50 rounded-lg">
              No hay PDFs procesados en este proyecto
            </p>
          ) : (
            <div className="border border-gray-200 rounded-lg max-h-64 overflow-y-auto">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
                >
                  <input
                    type="checkbox"
                    id={`pdf-${doc.id}`}
                    checked={selectedPdfs.includes(doc.original_filename)}
                    onChange={() => handlePdfToggle(doc.original_filename)}
                    disabled={loading || executing || batchProcessing}
                    className="w-4 h-4 text-yellow-700 border-gray-300 rounded focus:ring-yellow-500"
                  />
                  <label
                    htmlFor={`pdf-${doc.id}`}
                    className="ml-3 text-sm text-gray-700 cursor-pointer flex-1"
                  >
                    {doc.original_filename}
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Mode Selector */}
        <div className="border-t pt-4">
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Modo de Operación *
          </label>
          <div className="flex gap-4">
            <button
              onClick={() => setMode('reorder')}
              disabled={loading || executing}
              className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                mode === 'reorder'
                  ? 'border-yellow-500 bg-yellow-50 text-yellow-700'
                  : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
              }`}
            >
              <div className="font-semibold">🔄 Reordenar Páginas</div>
              <div className="text-xs mt-1">Reorganizar el orden de las páginas</div>
            </button>
            <button
              onClick={() => setMode('extract')}
              disabled={loading || executing}
              className={`flex-1 px-4 py-3 rounded-lg border-2 transition-all ${
                mode === 'extract'
                  ? 'border-yellow-500 bg-yellow-50 text-yellow-700'
                  : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
              }`}
            >
              <div className="font-semibold">✂️ Extraer Páginas</div>
              <div className="text-xs mt-1">Crear nuevo PDF con páginas específicas</div>
            </button>
          </div>
        </div>

        {/* Manual Range (only for extract mode) */}
        {mode === 'extract' && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <label htmlFor="manual-range" className="block text-sm font-medium text-gray-700 mb-2">
              Rango Manual (Opcional)
            </label>
            <input
              type="text"
              id="manual-range"
              value={manualRange}
              onChange={(e) => setManualRange(e.target.value)}
              placeholder='Ej: "1-20" o "1,5,10,15-20"'
              className="form-input w-full"
              disabled={loading || executing}
            />
            <p className="text-xs text-gray-600 mt-2">
              💡 Puedes especificar el rango manualmente o usar lenguaje natural abajo.
              <br />Ejemplos: "1-20" (páginas 1 a 20), "1,5,10" (páginas 1, 5 y 10), "1-10,15-20" (combinado)
            </p>
          </div>
        )}

        {/* Instruction Input */}
        <div>
          <label htmlFor="instruction" className="block text-sm font-medium text-gray-700 mb-2">
            {mode === 'extract' ? 'Instrucción en Lenguaje Natural (Opcional si usas rango manual)' : 'Instrucción en Lenguaje Natural *'}
          </label>
          <textarea
            id="instruction"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            className="form-textarea w-full h-32"
            placeholder={
              mode === 'extract'
                ? 'Ejemplo: "Extraer solo las primeras 20 páginas" o "Crear un PDF con las páginas 10 a 50"'
                : 'Ejemplo: "Mover la página 3 al inicio del documento y la página 5 al final"'
            }
            disabled={loading || executing}
          />
          <p className="text-xs text-gray-500 mt-1">
            {mode === 'extract'
              ? 'Describe qué páginas quieres extraer para crear un nuevo PDF'
              : 'Describe cómo quieres reordenar las páginas del PDF seleccionado'}
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3">
          {/* Preview Plan Button (optional) */}
          <button
            onClick={handleGeneratePlan}
            disabled={loading || selectedPdfs.length === 0 || (!instruction.trim() && !manualRange.trim()) || batchProcessing}
            className="px-4 py-2 text-sm font-medium text-yellow-700 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Generando...' : 'Vista Previa (Primer PDF)'}
          </button>

          {/* Batch Process Button */}
          <button
            onClick={handleBatchProcess}
            disabled={batchProcessing || selectedPdfs.length === 0 || (!instruction.trim() && !manualRange.trim())}
            className="btn-primary"
          >
            {batchProcessing ? (
              <>
                <svg className="animate-spin h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Procesando {currentBatchIndex}/{selectedPdfs.length}...
              </>
            ) : (
              <>
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                Procesar {selectedPdfs.length} PDF{selectedPdfs.length !== 1 ? 's' : ''}
              </>
            )}
          </button>
        </div>
      </div>

      {/* Batch Progress Display */}
      {batchProgress.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Progreso de Procesamiento ({currentBatchIndex}/{selectedPdfs.length})
          </h3>
          <div className="space-y-3">
            {batchProgress.map((item, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center flex-1">
                  {item.status === 'pending' && (
                    <div className="w-5 h-5 border-2 border-gray-300 rounded-full mr-3"></div>
                  )}
                  {item.status === 'generating_plan' && (
                    <div className="w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mr-3"></div>
                  )}
                  {item.status === 'executing' && (
                    <div className="w-5 h-5 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin mr-3"></div>
                  )}
                  {item.status === 'completed' && (
                    <svg className="w-5 h-5 text-green-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                  {item.status === 'failed' && (
                    <svg className="w-5 h-5 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  )}
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900">{item.filename}</p>
                    {item.status === 'generating_plan' && (
                      <p className="text-xs text-blue-600">Generando plan...</p>
                    )}
                    {item.status === 'executing' && (
                      <p className="text-xs text-yellow-700">Ejecutando...</p>
                    )}
                    {item.status === 'completed' && item.resultUrl && (
                      <p className="text-xs text-green-600">Completado - Listo para descargar</p>
                    )}
                    {item.status === 'failed' && (
                      <p className="text-xs text-red-600">{item.error || 'Error al procesar'}</p>
                    )}
                  </div>
                </div>
                {item.status === 'completed' && item.resultUrl && (
                  <button
                    onClick={() => handleDownloadFile(item.resultUrl, item.resultFilename)}
                    className="ml-3 px-3 py-1 text-xs font-medium text-yellow-700 bg-yellow-100 rounded hover:bg-yellow-200"
                  >
                    Descargar
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Plan Preview (for single PDF preview) */}
      {plan && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              📋 Vista Previa del Plan {mode === 'extract' ? '(Extracción)' : '(Reordenamiento)'}
            </h3>
            <div className="flex items-center space-x-2">
              <span className="text-sm text-gray-600">
                Confianza: {(plan.confidence * 100).toFixed(0)}%
              </span>
              <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
                <div 
                  className={`h-full ${plan.confidence > 0.8 ? 'bg-green-500' : plan.confidence > 0.6 ? 'bg-yellow-500' : 'bg-red-500'}`}
                  style={{ width: `${plan.confidence * 100}%` }}
                />
              </div>
            </div>
          </div>

          {/* Plan Info */}
          <div className="mb-4 space-y-3">
            <div className="p-3 bg-gray-50 rounded">
              <p className="text-sm text-gray-700">
                <strong>PDF:</strong> {plan.pdf_filename || plan.new_filename || selectedPdf}
              </p>
              <p className="text-sm text-gray-700 mt-1">
                <strong>Total de páginas:</strong> {plan.total_pages}
              </p>
              {mode === 'extract' && plan.pages_to_extract && (
                <p className="text-sm text-gray-700 mt-1">
                  <strong>Páginas a extraer:</strong> {plan.pages_to_extract.length}
                </p>
              )}
            </div>

            <div className="p-3 bg-blue-50 border border-blue-200 rounded">
              <p className="text-sm text-blue-900">
                <strong>Razonamiento de IA:</strong>
              </p>
              <p className="text-sm text-blue-800 mt-1">
                {plan.reasoning}
              </p>
            </div>

            {/* Pages Display */}
            {mode === 'extract' && plan.pages_to_extract ? (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded">
                <p className="text-sm text-amber-900 mb-2">
                  <strong>Páginas que se extraerán:</strong>
                </p>
                <div className="flex flex-wrap gap-2">
                  {plan.pages_to_extract.map((pageNum, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-amber-100 text-amber-800"
                    >
                      {pageNum}
                    </span>
                  ))}
                </div>
                {plan.new_filename && (
                  <p className="text-sm text-amber-700 mt-2">
                    <strong>Nombre del nuevo PDF:</strong> {plan.new_filename}
                  </p>
                )}
              </div>
            ) : plan.new_page_sequence ? (
              <div className="p-3 bg-yellow-50 border border-yellow-200 rounded">
                <p className="text-sm text-yellow-900 mb-2">
                  <strong>Nuevo orden de páginas:</strong>
                </p>
                <div className="flex flex-wrap gap-2">
                  {plan.new_page_sequence.map((pageNum, idx) => (
                    <span
                      key={idx}
                      className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                      pageNum === idx + 1
                        ? 'bg-gray-200 text-gray-700'
                        : 'bg-yellow-100 text-yellow-800'
                    }`}
                    >
                      {idx + 1}: Pág {pageNum}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-end pt-4 border-t border-gray-200 space-x-3">
            <button
              onClick={() => {
                setPlan(null);
                setCurrentJob(null);
              }}
              className="btn-secondary"
              disabled={executing}
            >
              Cancelar
            </button>
            <button
              onClick={handleExecutePlan}
              disabled={executing || currentJob?.status === 'completed'}
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
                  Aplicar Reordenamiento
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Results - Download Link */}
      {currentJob?.result_url && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">✅ Resultado</h3>
          
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-medium text-yellow-900">📄 PDF Reordenado</h4>
                <p className="text-sm text-yellow-700 mt-1">
                  {currentJob.result_filename}
                </p>
              </div>
              <button
                onClick={() => handleDownloadFile(currentJob.result_url, currentJob.result_filename)}
                className="btn-primary"
              >
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
                Descargar PDF
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PDFPageManager;

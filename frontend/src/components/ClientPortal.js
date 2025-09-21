import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ClientPortal = ({ user }) => {
  const [projects, setProjects] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [question, setQuestion] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchClientProjects();
  }, []);

  useEffect(() => {
    if (selectedProject) {
      fetchProjectDocuments();
    }
  }, [selectedProject]);

  const fetchClientProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setProjects(response.data);
      if (response.data.length > 0) {
        setSelectedProject(response.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching projects:', error);
      setError('Error al cargar proyectos');
    }
  };

  const fetchProjectDocuments = async () => {
    try {
      const response = await axios.get(`${API}/projects/${selectedProject}/documents`);
      const completedDocs = response.data.filter(doc => doc.status === 'completed' && doc.extracted_data);
      setDocuments(completedDocs);
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };

  const handleAskQuestion = async () => {
    if (!question.trim() || !selectedProject) return;

    setLoading(true);
    const userMessage = { type: 'user', content: question };
    setChatHistory(prev => [...prev, userMessage]);

    try {
      const response = await axios.post(`${API}/projects/${selectedProject}/ask-ai`, {
        question: question,
        include_context: true
      });

      const aiMessage = { 
        type: 'ai', 
        content: response.data.answer,
        sources: response.data.sources || []
      };
      setChatHistory(prev => [...prev, aiMessage]);
      setQuestion('');
    } catch (error) {
      const errorMessage = { 
        type: 'error', 
        content: 'Error al procesar la pregunta. Por favor intenta de nuevo.' 
      };
      setChatHistory(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const formatExtractedData = (data) => {
    if (!data || typeof data !== 'object') return 'No hay datos extraídos';
    
    return Object.entries(data)
      .filter(([key, value]) => key !== 'raw_response' && value !== null && value !== '')
      .map(([key, value]) => `${key}: ${JSON.stringify(value)}`)
      .join('\n');
  };

  const getProjectStats = () => {
    const totalDocs = documents.length;
    const docsWithData = documents.filter(doc => doc.extracted_data && Object.keys(doc.extracted_data).length > 1).length;
    return { totalDocs, docsWithData };
  };

  const stats = getProjectStats();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Portal del Cliente
          </h1>
          <p className="text-gray-600 mt-1">
            Consulta tus documentos procesados y haz preguntas a la IA
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Project Selection */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Mis Proyectos</h2>
        </div>
        
        {projects.length > 0 ? (
          <div className="space-y-4">
            <div className="form-group">
              <label htmlFor="project-select" className="form-label">
                Proyecto Activo
              </label>
              <select
                id="project-select"
                value={selectedProject}
                onChange={(e) => setSelectedProject(e.target.value)}
                className="form-input"
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>

            {selectedProject && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-2xl font-bold text-emerald-800">{stats.totalDocs}</div>
                    <div className="text-emerald-600 text-sm">Documentos Procesados</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-emerald-800">{stats.docsWithData}</div>
                    <div className="text-emerald-600 text-sm">Con Datos Extraídos</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-600">No tienes proyectos asignados aún.</p>
          </div>
        )}
      </div>

      {/* AI Chat Interface */}
      {selectedProject && documents.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Consulta con IA</h2>
            <p className="text-gray-600 text-sm">
              Haz preguntas sobre los datos extraídos de tus documentos
            </p>
          </div>
          
          {/* Chat History */}
          <div className="max-h-96 overflow-y-auto mb-4 space-y-3">
            {chatHistory.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p>Inicia una conversación preguntando sobre tus documentos</p>
                <div className="mt-4 text-sm space-y-1">
                  <p><strong>Ejemplos:</strong></p>
                  <p>• "¿Cuáles son los montos totales de los contratos?"</p>
                  <p>• "¿Qué documentos tienen fecha de vencimiento próxima?"</p>
                  <p>• "Resume las condiciones de pago encontradas"</p>
                </div>
              </div>
            )}
            
            {chatHistory.map((message, index) => (
              <div key={index} className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-3xl px-4 py-3 rounded-lg ${
                  message.type === 'user' 
                    ? 'bg-emerald-600 text-white' 
                    : message.type === 'error'
                    ? 'bg-red-100 text-red-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  {message.sources && message.sources.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-300">
                      <p className="text-xs font-medium">Fuentes consultadas:</p>
                      {message.sources.map((source, idx) => (
                        <p key={idx} className="text-xs">• {source}</p>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 text-gray-800 px-4 py-3 rounded-lg">
                  <div className="flex items-center">
                    <div className="spinner mr-2" style={{ width: '16px', height: '16px' }}></div>
                    La IA está analizando tus documentos...
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Question Input */}
          <div className="flex space-x-3">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleAskQuestion()}
              placeholder="Pregunta sobre tus documentos..."
              className="form-input flex-1"
              disabled={loading}
            />
            <button
              onClick={handleAskQuestion}
              disabled={loading || !question.trim()}
              className="btn-primary"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Documents Summary */}
      {selectedProject && documents.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Resumen de Documentos</h2>
          </div>
          
          <div className="space-y-4">
            {documents.slice(0, 5).map((document) => (
              <div key={document.id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-2">
                  <h4 className="font-medium text-gray-900">{document.original_filename}</h4>
                  <span className="status-badge status-completed">Procesado</span>
                </div>
                
                {document.extracted_data && (
                  <div className="bg-gray-50 rounded p-3">
                    <h5 className="text-sm font-medium text-gray-700 mb-2">Datos Extraídos:</h5>
                    <pre className="text-xs text-gray-600 whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {formatExtractedData(document.extracted_data)}
                    </pre>
                  </div>
                )}
                
                <div className="mt-2 text-xs text-gray-500">
                  Procesado el {new Date(document.processed_at).toLocaleDateString()}
                </div>
              </div>
            ))}
            
            {documents.length > 5 && (
              <div className="text-center pt-4">
                <Link 
                  to={`/projects/${selectedProject}`}
                  className="text-emerald-600 hover:text-emerald-700 font-medium"
                >
                  Ver todos los {documents.length} documentos →
                </Link>
              </div>
            )}
          </div>
        </div>
      )}

      {selectedProject && documents.length === 0 && (
        <div className="card text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay documentos procesados</h3>
          <p className="text-gray-600">
            Los documentos aparecerán aquí una vez que sean procesados por el sistema.
          </p>
        </div>
      )}
    </div>
  );
};

export default ClientPortal;
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const QAAgents = ({ user }) => {
  const [agents, setAgents] = useState([]);
  const [projects, setProjects] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    qa_instructions: '',
    project_ids: [],
    is_universal: false,
    quality_checks: {
      image_clarity: false,
      document_orientation: false,
      signature_detection: false,
      seal_detection: false,
      text_readability: false,
      completeness_check: false
    }
  });

  useEffect(() => {
    fetchAgents();
    fetchProjects();
  }, []);

  const fetchAgents = async () => {
    try {
      const response = await axios.get(`${API}/qa-agents`);
      setAgents(response.data);
    } catch (error) {
      console.error('Error fetching QA agents:', error);
      setError('Error al cargar agentes QA');
    } finally {
      setLoading(false);
    }
  };

  const fetchProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setProjects(response.data);
    } catch (error) {
      console.error('Error fetching projects:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      await axios.post(`${API}/qa-agents`, formData);
      setSuccess('Agente QA creado exitosamente');
      setShowModal(false);
      setFormData({
        name: '',
        description: '',
        qa_instructions: '',
        project_ids: [],
        is_universal: false,
        quality_checks: {
          image_clarity: false,
          document_orientation: false,
          signature_detection: false,
          seal_detection: false,
          text_readability: false,
          completeness_check: false
        }
      });
      fetchAgents();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al crear agente QA');
    }
  };

  const handleQualityCheckChange = (check) => {
    setFormData({
      ...formData,
      quality_checks: {
        ...formData.quality_checks,
        [check]: !formData.quality_checks[check]
      }
    });
  };

  const handleProjectSelection = (projectId) => {
    const currentProjects = [...formData.project_ids];
    const index = currentProjects.indexOf(projectId);
    
    if (index > -1) {
      currentProjects.splice(index, 1);
    } else {
      currentProjects.push(projectId);
    }
    
    setFormData({
      ...formData,
      project_ids: currentProjects
    });
  };

  const runQACheck = async (agentId) => {
    try {
      setSuccess('Iniciando verificación de calidad...');
      await axios.post(`${API}/qa-agents/${agentId}/run`);
      setSuccess('Verificación de calidad iniciada exitosamente');
      
      // Refresh agents to update status
      setTimeout(() => fetchAgents(), 2000);
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al ejecutar verificación QA');
    }
  };

  const getQualityChecksText = (checks) => {
    const activeChecks = Object.entries(checks)
      .filter(([_, active]) => active)
      .map(([check, _]) => {
        const labels = {
          image_clarity: 'Claridad de Imágenes',
          document_orientation: 'Orientación',
          signature_detection: 'Detección de Firmas',
          seal_detection: 'Detección de Sellos',
          text_readability: 'Legibilidad de Texto',
          completeness_check: 'Verificación de Completitud'
        };
        return labels[check] || check;
      });
    
    return activeChecks.length > 0 ? activeChecks.join(', ') : 'Ninguna verificación seleccionada';
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Agentes de Control de Calidad
          </h1>
          <p className="text-gray-600 mt-1">
            Gestiona agentes de IA para verificar la calidad de documentos procesados
          </p>
        </div>
        
        {user.role === 'staff' && (
          <button
            onClick={() => setShowModal(true)}
            className="btn-primary"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Nuevo Agente QA
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* QA Agents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map((agent) => (
          <div key={agent.id} className="card hover:shadow-lg transition-all">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {agent.name}
                </h3>
                {agent.description && (
                  <p className="text-gray-600 text-sm mb-3">
                    {agent.description}
                  </p>
                )}
              </div>
              <span className={`status-badge ${agent.is_universal ? 'status-completed' : 'status-active'}`}>
                {agent.is_universal ? 'Universal' : 'Específico'}
              </span>
            </div>
            
            <div className="space-y-3 mb-4">
              <div>
                <h4 className="text-sm font-medium text-gray-700 mb-1">Verificaciones:</h4>
                <p className="text-xs text-gray-600">
                  {getQualityChecksText(agent.quality_checks)}
                </p>
              </div>
              
              {!agent.is_universal && agent.project_ids && agent.project_ids.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-1">Proyectos:</h4>
                  <p className="text-xs text-gray-600">
                    {agent.project_ids.length} proyecto(s) asignado(s)
                  </p>
                </div>
              )}

              {agent.qa_instructions && (
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-1">Instrucciones:</h4>
                  <p className="text-xs text-gray-600 line-clamp-2">
                    {agent.qa_instructions}
                  </p>
                </div>
              )}
            </div>
            
            <div className="pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-500">
                  Creado {new Date(agent.created_at).toLocaleDateString()}
                </div>
                <button
                  onClick={() => runQACheck(agent.id)}
                  className="text-emerald-600 hover:text-emerald-700 text-sm font-medium flex items-center"
                >
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Ejecutar QA
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {agents.length === 0 && (
        <div className="text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay agentes QA creados</h3>
          <p className="text-gray-600">
            {user.role === 'staff' ? 'Comienza creando tu primer agente de control de calidad.' : 'Los agentes QA serán mostrados aquí cuando estén disponibles.'}
          </p>
        </div>
      )}

      {/* Create QA Agent Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Nuevo Agente QA</h3>
              <button
                onClick={() => setShowModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="form-group">
                <label htmlFor="name" className="form-label">
                  Nombre del Agente *
                </label>
                <input
                  id="name"
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="description" className="form-label">
                  Descripción
                </label>
                <textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="form-textarea"
                  rows="3"
                />
              </div>

              <div className="form-group">
                <label className="flex items-center">
                  <input
                    type="checkbox"
                    checked={formData.is_universal}
                    onChange={(e) => setFormData({ ...formData, is_universal: e.target.checked })}
                    className="form-checkbox mr-2"
                  />
                  <span className="form-label mb-0">Agente Universal (aplica a todos los proyectos)</span>
                </label>
              </div>

              {!formData.is_universal && (
                <div className="form-group">
                  <label className="form-label">Proyectos a Aplicar</label>
                  <div className="max-h-40 overflow-y-auto border border-gray-300 rounded-lg p-3">
                    {projects.map((project) => (
                      <label key={project.id} className="flex items-center py-2">
                        <input
                          type="checkbox"
                          checked={formData.project_ids.includes(project.id)}
                          onChange={() => handleProjectSelection(project.id)}
                          className="form-checkbox mr-2"
                        />
                        <span className="text-sm text-gray-700">{project.name}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <div className="form-group">
                <label className="form-label">Verificaciones de Calidad</label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.quality_checks.image_clarity}
                      onChange={() => handleQualityCheckChange('image_clarity')}
                      className="form-checkbox mr-2"
                    />
                    <span className="text-sm">Claridad de Imágenes</span>
                  </label>
                  
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.quality_checks.document_orientation}
                      onChange={() => handleQualityCheckChange('document_orientation')}
                      className="form-checkbox mr-2"
                    />
                    <span className="text-sm">Orientación Correcta</span>
                  </label>
                  
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.quality_checks.signature_detection}
                      onChange={() => handleQualityCheckChange('signature_detection')}
                      className="form-checkbox mr-2"
                    />
                    <span className="text-sm">Detección de Firmas</span>
                  </label>
                  
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.quality_checks.seal_detection}
                      onChange={() => handleQualityCheckChange('seal_detection')}
                      className="form-checkbox mr-2"
                    />
                    <span className="text-sm">Detección de Sellos</span>
                  </label>
                  
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.quality_checks.text_readability}
                      onChange={() => handleQualityCheckChange('text_readability')}
                      className="form-checkbox mr-2"
                    />
                    <span className="text-sm">Legibilidad de Texto</span>
                  </label>
                  
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.quality_checks.completeness_check}
                      onChange={() => handleQualityCheckChange('completeness_check')}
                      className="form-checkbox mr-2"
                    />
                    <span className="text-sm">Completitud</span>
                  </label>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="qa_instructions" className="form-label">
                  Instrucciones Específicas para IA
                </label>
                <textarea
                  id="qa_instructions"
                  value={formData.qa_instructions}
                  onChange={(e) => setFormData({ ...formData, qa_instructions: e.target.value })}
                  className="form-textarea"
                  rows="4"
                  placeholder="Instrucciones específicas sobre qué verificar en los documentos..."
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Crear Agente QA
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default QAAgents;
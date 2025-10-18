import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AIConfiguration = ({ user }) => {
  const [companies, setCompanies] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState('');
  const [selectedProject, setSelectedProject] = useState('');
  const [configurations, setConfigurations] = useState({});
  const [modelRecommendations, setModelRecommendations] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState(null);
  const [formData, setFormData] = useState({
    config_type: 'data_extraction',
    provider: 'openai',
    api_key: '',
    model_name: 'gpt-4o',
    model_config: {}
  });

  const configTypes = {
    'data_extraction': {
      title: '📊 Extracción de Datos',
      description: 'Configuración para extraer información estructurada de documentos',
      icon: '🔍'
    },
    'qa_processing': {
      title: '✅ Control de Calidad',
      description: 'Configuración para análisis automático de calidad de documentos',
      icon: '🔍'
    },
    'document_processing': {
      title: '📄 Procesamiento General',
      description: 'Configuración para tareas generales de procesamiento de documentos',
      icon: '⚙️'
    }
  };

  useEffect(() => {
    fetchCompanies();
    fetchModelRecommendations();
  }, []);

  useEffect(() => {
    if (selectedCompany) {
      fetchProjects();
      setSelectedProject(''); // Reset project selection when company changes
      setConfigurations({});
    }
  }, [selectedCompany]);

  useEffect(() => {
    if (selectedProject) {
      fetchConfigurations();
    }
  }, [selectedProject]);

  const fetchCompanies = async () => {
    try {
      const response = await axios.get(`${API}/companies`);
      setCompanies(response.data);
      
      // Auto-select for single company or client users
      if (user.role === 'client' && user.company_id) {
        setSelectedCompany(user.company_id);
      } else if (response.data.length === 1) {
        setSelectedCompany(response.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching companies:', error);
      setError('Error al cargar empresas');
    }
  };

  const fetchConfigurations = async () => {
    if (!selectedCompany) return;
    
    setLoading(true);
    try {
      const response = await axios.get(`${API}/companies/${selectedCompany}/ai-config`);
      
      // Organize configurations by type
      const configsByType = {};
      response.data.configurations.forEach(config => {
        configsByType[config.config_type] = config;
      });
      
      setConfigurations(configsByType);
      setError('');
    } catch (error) {
      console.error('Error fetching configurations:', error);
      setError('Error al cargar configuraciones');
    } finally {
      setLoading(false);
    }
  };

  const fetchModelRecommendations = async () => {
    try {
      const response = await axios.get(`${API}/ai-models/recommendations`);
      setModelRecommendations(response.data);
    } catch (error) {
      console.error('Error fetching model recommendations:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (editingConfig) {
        await axios.put(`${API}/companies/${selectedCompany}/ai-config/${editingConfig.id}`, {
          provider: formData.provider,
          api_key: formData.api_key || undefined,
          model_name: formData.model_name,
          model_config: formData.model_config
        });
        setSuccess('Configuración actualizada exitosamente');
      } else {
        await axios.post(`${API}/companies/${selectedCompany}/ai-config`, formData);
        setSuccess('Configuración creada exitosamente');
      }
      
      setShowModal(false);
      setEditingConfig(null);
      resetForm();
      fetchConfigurations();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al guardar configuración');
    }
  };

  const resetForm = () => {
    setFormData({
      config_type: 'data_extraction',
      provider: 'openai',
      api_key: '',
      model_name: 'gpt-4o',
      model_config: {}
    });
  };

  const handleEditClick = (configType) => {
    const config = configurations[configType];
    if (config) {
      setEditingConfig(config);
      setFormData({
        config_type: configType,
        provider: config.provider,
        api_key: '', // Don't pre-fill for security
        model_name: config.model_name,
        model_config: config.model_config || {}
      });
    } else {
      setEditingConfig(null);
      setFormData({
        ...formData,
        config_type: configType
      });
    }
    setShowModal(true);
  };

  const handleDeleteClick = async (configType) => {
    const config = configurations[configType];
    if (!config) return;

    if (window.confirm('¿Estás seguro de que deseas eliminar esta configuración?')) {
      try {
        await axios.delete(`${API}/companies/${selectedCompany}/ai-config/${config.id}`);
        setSuccess('Configuración eliminada exitosamente');
        fetchConfigurations();
      } catch (error) {
        setError('Error al eliminar configuración');
      }
    }
  };

  const getModelsByProvider = (provider, taskType) => {
    if (!modelRecommendations[taskType]) return [];
    return modelRecommendations[taskType].recommended || [];
  };

  const getConfigStatusBadge = (configType) => {
    const config = configurations[configType];
    if (config && config.is_active) {
      return <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded-full">Configurado</span>;
    }
    return <span className="bg-gray-100 text-gray-800 text-xs px-2 py-1 rounded-full">Sin Configurar</span>;
  };

  if (user.role !== 'staff') {
    return (
      <div className="text-center py-12">
        <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Acceso Restringido</h3>
        <p className="text-gray-600">
          Solo el personal staff puede configurar integraciones de IA.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Configuración de IA
          </h1>
          <p className="text-gray-600 mt-1">
            Configura las API keys y modelos de IA por tipo de tarea
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Company Selector */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <label htmlFor="company-select" className="block text-sm font-medium text-gray-700 mb-2">
          Seleccionar Empresa
        </label>
        <select
          id="company-select"
          value={selectedCompany}
          onChange={(e) => setSelectedCompany(e.target.value)}
          className="form-input w-full md:w-1/2"
        >
          <option value="">Seleccione una empresa</option>
          {companies.map((company) => (
            <option key={company.id} value={company.id}>
              {company.name}
            </option>
          ))}
        </select>
      </div>

      {selectedCompany && (
        <>
          {/* Info Banner */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-blue-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-blue-800">Configuración por Tarea</h3>
                <p className="text-sm text-blue-700 mt-1">
                  Configure diferentes modelos de IA y API keys para optimizar cada tipo de tarea. 
                  Si no configura una tarea específica, se usará la clave universal del sistema.
                </p>
              </div>
            </div>
          </div>

          {/* Configuration Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(configTypes).map(([configType, typeInfo]) => {
              const config = configurations[configType];
              return (
                <div key={configType} className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <span className="text-2xl">{typeInfo.icon}</span>
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">
                          {typeInfo.title}
                        </h3>
                      </div>
                    </div>
                    {getConfigStatusBadge(configType)}
                  </div>

                  <p className="text-gray-600 text-sm mb-4">
                    {typeInfo.description}
                  </p>

                  {config ? (
                    <div className="space-y-3">
                      <div className="bg-gray-50 rounded-lg p-3">
                        <div className="text-xs text-gray-500 mb-1">Modelo Configurado:</div>
                        <div className="font-medium text-gray-900">{config.model_name}</div>
                        <div className="text-xs text-gray-500 mt-1">
                          Proveedor: {config.provider === 'openai' ? 'OpenAI' : 'Sistema Universal'}
                        </div>
                      </div>
                      
                      <div className="flex space-x-2">
                        <button
                          onClick={() => handleEditClick(configType)}
                          className="flex-1 text-blue-600 border border-blue-200 rounded-lg px-3 py-2 text-sm hover:bg-blue-50"
                        >
                          Editar
                        </button>
                        <button
                          onClick={() => handleDeleteClick(configType)}
                          className="text-red-600 border border-red-200 rounded-lg px-3 py-2 text-sm hover:bg-red-50"
                        >
                          Eliminar
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                        <div className="text-sm text-yellow-800">
                          🔄 Usando configuración del sistema
                        </div>
                        <div className="text-xs text-yellow-600 mt-1">
                          Se usará la clave universal con modelo por defecto
                        </div>
                      </div>
                      
                      <button
                        onClick={() => handleEditClick(configType)}
                        className="w-full bg-emerald-600 text-white rounded-lg px-4 py-2 text-sm hover:bg-emerald-700"
                      >
                        Configurar
                      </button>
                    </div>
                  )}

                  {/* Model Recommendations */}
                  {modelRecommendations[configType] && (
                    <div className="mt-4 pt-4 border-t border-gray-200">
                      <div className="text-xs font-medium text-gray-700 mb-2">
                        Modelos Recomendados:
                      </div>
                      <div className="space-y-1">
                        {getModelsByProvider('openai', configType).slice(0, 2).map((model, idx) => (
                          <div key={idx} className="text-xs bg-blue-50 rounded px-2 py-1">
                            <span className="font-medium">{model.model}</span>
                            <span className="text-blue-600 ml-1">({model.cost_level})</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* Configuration Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal max-w-4xl" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {editingConfig ? 'Editar' : 'Nueva'} Configuración de IA
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Task Type */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h4 className="text-sm font-semibold text-gray-800 mb-2">
                  Tipo de Tarea: {configTypes[formData.config_type]?.title}
                </h4>
                <p className="text-sm text-gray-600">
                  {configTypes[formData.config_type]?.description}
                </p>
              </div>

              {/* Provider Selection */}
              <div className="form-group">
                <label className="form-label">Proveedor de IA</label>
                <div className="space-y-3">
                  <label className="flex items-center space-x-3">
                    <input
                      type="radio"
                      value="openai"
                      checked={formData.provider === 'openai'}
                      onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                      className="form-radio"
                    />
                    <div>
                      <div className="font-medium">OpenAI (API Key Personalizada)</div>
                      <div className="text-sm text-gray-500">
                        Use su propia API key de OpenAI para control total y costos directos
                      </div>
                    </div>
                  </label>
                  <label className="flex items-center space-x-3">
                    <input
                      type="radio"
                      value="emergent"
                      checked={formData.provider === 'emergent'}
                      onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                      className="form-radio"
                    />
                    <div>
                      <div className="font-medium">Sistema Universal</div>
                      <div className="text-sm text-gray-500">
                        Use la clave universal del sistema (por defecto)
                      </div>
                    </div>
                  </label>
                </div>
              </div>

              {/* API Key Input (only for OpenAI) */}
              {formData.provider === 'openai' && (
                <div className="form-group">
                  <label htmlFor="api_key" className="form-label">
                    API Key de OpenAI
                  </label>
                  <input
                    id="api_key"
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    className="form-input"
                    placeholder={editingConfig ? "Dejar vacío para mantener la key actual" : "sk-..."}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Su API key se almacenará de forma encriptada y segura
                  </p>
                </div>
              )}

              {/* Model Selection */}
              <div className="form-group">
                <label htmlFor="model_name" className="form-label">
                  Modelo de IA
                </label>
                <select
                  id="model_name"
                  value={formData.model_name}
                  onChange={(e) => setFormData({ ...formData, model_name: e.target.value })}
                  className="form-input"
                >
                  {getModelsByProvider(formData.provider, formData.config_type).map((model) => (
                    <option key={model.model} value={model.model}>
                      {model.model} - {model.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Model Recommendations */}
              {modelRecommendations[formData.config_type] && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h4 className="text-sm font-semibold text-blue-800 mb-3">
                    💡 Recomendaciones de Modelos
                  </h4>
                  <div className="space-y-3">
                    {getModelsByProvider('openai', formData.config_type).map((model, idx) => (
                      <div key={idx} className="bg-white rounded-lg p-3 border border-blue-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-medium text-blue-900">{model.model}</span>
                          <span className={`text-xs px-2 py-1 rounded-full ${
                            model.cost_level === 'low' ? 'bg-green-100 text-green-800' :
                            model.cost_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {model.cost_level === 'low' ? 'Económico' :
                             model.cost_level === 'medium' ? 'Balanceado' : 'Premium'}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600 mb-1">{model.description}</p>
                        <p className="text-xs text-blue-600">Ideal para: {model.use_case}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

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
                  {editingConfig ? 'Actualizar' : 'Crear'} Configuración
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIConfiguration;
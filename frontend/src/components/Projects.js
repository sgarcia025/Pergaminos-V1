import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Projects = ({ user }) => {
  const location = useLocation();
  const [projects, setProjects] = useState([]);
  const [filteredProjects, setFilteredProjects] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    company_id: '',
    semantic_instructions: ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState(null);
  const [filterCompany, setFilterCompany] = useState('');
  const [filterCorporacion, setFilterCorporacion] = useState('');
  const [dashboardFilters, setDashboardFilters] = useState(null);

  useEffect(() => {
    fetchProjects();
    fetchCompanies();
    
    // Check if filters were passed from Dashboard
    if (location.state?.filters) {
      setDashboardFilters(location.state.filters);
    }
  }, []);

  useEffect(() => {
    // Check if there's a company filter in URL params
    const searchParams = new URLSearchParams(location.search);
    const companyParam = searchParams.get('company');
    if (companyParam) {
      setFilterCompany(companyParam);
    }
  }, [location]);

  useEffect(() => {
    applyFilters();
  }, [projects, companies, filterCompany, filterCorporacion, dashboardFilters]);

  const fetchProjects = async () => {
    try {
      const response = await axios.get(`${API}/projects`);
      setProjects(response.data);
    } catch (error) {
      console.error('Error fetching projects:', error);
      setError('Error al cargar los proyectos');
    } finally {
      setLoading(false);
    }
  };

  const fetchCompanies = async () => {
    try {
      const response = await axios.get(`${API}/companies`);
      setCompanies(response.data);
    } catch (error) {
      console.error('Error fetching companies:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      await axios.post(`${API}/projects`, formData);
      setSuccess('Proyecto creado exitosamente');
      setShowModal(false);
      setFormData({
        name: '',
        description: '',
        company_id: '',
        semantic_instructions: ''
      });
      fetchProjects();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al crear el proyecto');
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const getCompanyName = (companyId) => {
    const company = companies.find(c => c.id === companyId);
    return company ? company.name : 'Empresa desconocida';
  };

  const getCompanyCorporacion = (companyId) => {
    const company = companies.find(c => c.id === companyId);
    return company?.corporacion || '';
  };

  const getStatusColor = (status) => {
    const colors = {
      'active': 'status-active',
      'completed': 'status-completed',
      'paused': 'status-processing'
    };
    return colors[status] || 'status-active';
  };

  const applyFilters = () => {
    let filtered = [...projects];

    // Filter by company
    if (filterCompany) {
      filtered = filtered.filter(p => p.company_id === filterCompany);
    }

    // Filter by corporacion
    if (filterCorporacion) {
      filtered = filtered.filter(p => {
        const companyCorporacion = getCompanyCorporacion(p.company_id);
        return companyCorporacion === filterCorporacion;
      });
    }

    setFilteredProjects(filtered);
  };
  
  const getStatusLabel = (status) => {
    const labels = {
      'completed': 'Documentos Completados',
      'processing': 'Documentos en Proceso',
      'failed': 'Documentos Fallidos',
      'needs_review': 'Documentos en Revisión',
      'qa_passed': 'QA Aprobado',
      'qa_failed': 'QA Fallido',
      'qa_pending': 'QA Pendiente'
    };
    return labels[status] || status;
  };

  const uniqueCorporaciones = [...new Set(
    companies.map(c => c.corporacion).filter(Boolean)
  )];

  const handleDeleteClick = (e, project) => {
    e.preventDefault(); // Prevenir la navegación del Link
    e.stopPropagation();
    setProjectToDelete(project);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!projectToDelete) return;

    try {
      await axios.delete(`${API}/projects/${projectToDelete.id}`);
      setSuccess('Proyecto eliminado exitosamente');
      setShowDeleteModal(false);
      setProjectToDelete(null);
      fetchProjects();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al eliminar el proyecto');
      setShowDeleteModal(false);
      setProjectToDelete(null);
    }
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
            Proyectos de Digitalización
          </h1>
          <p className="text-gray-600 mt-1">
            Gestiona los proyectos de procesamiento de documentos
          </p>
        </div>
        
        <button
          onClick={() => setShowModal(true)}
          className="btn-primary"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Nuevo Proyecto
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Dashboard Filters Info Banner */}
      {dashboardFilters && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start justify-between">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-blue-400 mt-0.5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <h4 className="text-sm font-medium text-blue-800 mb-1">
                  Filtros aplicados desde el Dashboard
                </h4>
                <p className="text-sm text-blue-700">
                  Mostrando proyectos con: <strong>{getStatusLabel(dashboardFilters.status)}</strong>
                  {dashboardFilters.start_date && ` desde ${dashboardFilters.start_date}`}
                  {dashboardFilters.end_date && ` hasta ${dashboardFilters.end_date}`}
                </p>
                <p className="text-xs text-blue-600 mt-1">
                  Haz click en un proyecto para ver los documentos en este estado
                </p>
              </div>
            </div>
            <button
              onClick={() => setDashboardFilters(null)}
              className="text-blue-600 hover:text-blue-800"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filtros</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="filterCompany" className="block text-sm font-medium text-gray-700 mb-2">
              Empresa
            </label>
            <select
              id="filterCompany"
              value={filterCompany}
              onChange={(e) => setFilterCompany(e.target.value)}
              className="form-input w-full"
            >
              <option value="">Todas las empresas</option>
              {companies.map((company) => (
                <option key={company.id} value={company.id}>
                  {company.name}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label htmlFor="filterCorporacion" className="block text-sm font-medium text-gray-700 mb-2">
              Corporación
            </label>
            <select
              id="filterCorporacion"
              value={filterCorporacion}
              onChange={(e) => setFilterCorporacion(e.target.value)}
              className="form-input w-full"
            >
              <option value="">Todas las corporaciones</option>
              {uniqueCorporaciones.map((corp) => (
                <option key={corp} value={corp}>
                  {corp}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {(filterCompany || filterCorporacion) && (
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Mostrando {filteredProjects.length} de {projects.length} proyectos
            </p>
            <button
              onClick={() => {
                setFilterCompany('');
                setFilterCorporacion('');
              }}
              className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
            >
              Limpiar filtros
            </button>
          </div>
        )}
      </div>

      {/* Projects Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredProjects.map((project) => (
          <Link key={project.id} to={`/projects/${project.id}`}>
            <div className="card hover:shadow-lg transition-all cursor-pointer">
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    {project.name}
                  </h3>
                  {project.description && (
                    <p className="text-gray-600 text-sm mb-3">
                      {project.description}
                    </p>
                  )}
                </div>
                <span className={`status-badge ${getStatusColor(project.status)}`}>
                  {project.status === 'active' ? 'Activo' : 
                   project.status === 'completed' ? 'Completado' : 'Pausado'}
                </span>
              </div>
              
              <div className="space-y-2 mb-4">
                <div className="flex items-center text-sm text-gray-500">
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2-2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                  {getCompanyName(project.company_id)}
                </div>
                
                {project.semantic_instructions && (
                  <div className="flex items-start text-sm text-gray-500">
                    <svg className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span className="line-clamp-2">
                      IA: {project.semantic_instructions.substring(0, 80)}
                      {project.semantic_instructions.length > 80 && '...'}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-gray-500">
                    Creado {new Date(project.created_at).toLocaleDateString()}
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="flex items-center text-emerald-600 text-sm font-medium">
                      Ver detalles
                      <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                    {user.role === 'staff' && (
                      <button
                        onClick={(e) => handleDeleteClick(e, project)}
                        className="text-red-600 hover:text-red-700 text-sm font-medium"
                        title="Eliminar proyecto"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {projects.length === 0 && (
        <div className="text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay proyectos registrados</h3>
          <p className="text-gray-600">
            Comienza creando tu primer proyecto de digitalización.
          </p>
        </div>
      )}

      {/* Create Project Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Nuevo Proyecto</h3>
              <button
                onClick={() => setShowModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="form-group">
                <label htmlFor="name" className="form-label">
                  Nombre del Proyecto *
                </label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={formData.name}
                  onChange={handleChange}
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="company_id" className="form-label">
                  Empresa Cliente *
                </label>
                <select
                  id="company_id"
                  name="company_id"
                  value={formData.company_id}
                  onChange={handleChange}
                  className="form-input"
                  required
                >
                  <option value="">Seleccionar empresa...</option>
                  {companies.map((company) => (
                    <option key={company.id} value={company.id}>
                      {company.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label htmlFor="description" className="form-label">
                  Descripción
                </label>
                <textarea
                  id="description"
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                  className="form-textarea"
                  rows="3"
                />
              </div>

              <div className="form-group">
                <label htmlFor="semantic_instructions" className="form-label">
                  Instrucciones para IA
                </label>
                <textarea
                  id="semantic_instructions"
                  name="semantic_instructions"
                  value={formData.semantic_instructions}
                  onChange={handleChange}
                  className="form-textarea"
                  rows="4"
                  placeholder="Describe qué datos debe extraer la IA de los documentos de este proyecto..."
                />
                <p className="text-xs text-gray-500 mt-1">
                  Define semánticamente qué información debe extraer la IA de los documentos subidos a este proyecto.
                </p>
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
                  Crear Proyecto
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && projectToDelete && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Eliminar Proyecto</h3>
              <button
                onClick={() => setShowDeleteModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <div className="space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex">
                  <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-red-800">
                      ¿Estás seguro de que deseas eliminar este proyecto?
                    </h3>
                    <div className="mt-2 text-sm text-red-700">
                      <p>Esta acción eliminará permanentemente:</p>
                      <ul className="list-disc list-inside mt-1">
                        <li><strong>{projectToDelete.name}</strong></li>
                        <li>Todos los documentos subidos al proyecto</li>
                        <li>Todos los datos procesados</li>
                        <li>Todas las tareas de procesamiento</li>
                      </ul>
                      <p className="mt-2 font-medium">Esta acción no se puede deshacer.</p>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowDeleteModal(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleDeleteConfirm}
                  className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors"
                >
                  Eliminar
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Projects;
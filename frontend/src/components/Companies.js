import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Companies = ({ user }) => {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState([]);
  const [filteredCompanies, setFilteredCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    razon_social: '',
    nit: '',
    description: '',
    contacto: '',
    contact_email: '',
    telefono: '',
    direccion: '',
    asesor_comercial_id: '',
    segmento: '',
    corporacion: '',
    is_active: true,
    contactos: []
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [companyToDelete, setCompanyToDelete] = useState(null);
  const [editingCompany, setEditingCompany] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [asesores, setAsesores] = useState([]);
  const [segmentos, setSegmentos] = useState([]);
  const [corporations, setCorporations] = useState([]);
  const [newCorporationName, setNewCorporationName] = useState('');
  const [showNewCorporationInput, setShowNewCorporationInput] = useState(false);
  const [filterCorporacion, setFilterCorporacion] = useState('');
  const [filterEstado, setFilterEstado] = useState('');

  useEffect(() => {
    fetchCompanies();
    fetchAsesores();
    fetchSegmentos();
    fetchCorporations();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [companies, filterCorporacion, filterEstado]);

  const fetchCompanies = async () => {
    try {
      const response = await axios.get(`${API}/companies`);
      setCompanies(response.data);
    } catch (error) {
      console.error('Error fetching companies:', error);
      setError('Error al cargar las empresas');
    } finally {
      setLoading(false);
    }
  };

  const fetchAsesores = async () => {
    try {
      const response = await axios.get(`${API}/users/asesores`);
      setAsesores(response.data);
    } catch (error) {
      console.error('Error fetching asesores:', error);
    }
  };

  const fetchSegmentos = async () => {
    try {
      const response = await axios.get(`${API}/segmentos`);
      // Remove duplicates based on segment name
      const uniqueSegmentos = response.data.filter((segmento, index, self) =>
        index === self.findIndex((s) => s.nombre === segmento.nombre)
      );
      setSegmentos(uniqueSegmentos);
    } catch (error) {
      console.error('Error fetching segmentos:', error);
    }
  };

  const fetchCorporations = async () => {
    try {
      const response = await axios.get(`${API}/corporations`);
      setCorporations(response.data);
    } catch (error) {
      console.error('Error fetching corporations:', error);
    }
  };

  const handleCreateCorporation = async () => {
    if (!newCorporationName.trim()) {
      setError('Por favor ingresa un nombre para la corporación');
      return;
    }

    try {
      const response = await axios.post(`${API}/corporations`, {
        name: newCorporationName.trim()
      });
      
      // Add new corporation to list
      setCorporations([...corporations, response.data]);
      
      // Set it as selected
      setFormData({ ...formData, corporacion: response.data.name });
      
      // Reset and hide input
      setNewCorporationName('');
      setShowNewCorporationInput(false);
      setSuccess('Corporación creada exitosamente');
      setTimeout(() => setSuccess(''), 3000);
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al crear la corporación');
    }
  };

  const applyFilters = () => {
    let filtered = [...companies];

    // Filter by corporacion
    if (filterCorporacion) {
      filtered = filtered.filter(c => c.corporacion === filterCorporacion);
    }

    // Filter by estado (is_active)
    if (filterEstado !== '') {
      const isActive = filterEstado === 'true';
      filtered = filtered.filter(c => (c.is_active !== false) === isActive);
    }

    setFilteredCompanies(filtered);
  };

  const uniqueCorporaciones = [...new Set(
    companies.map(c => c.corporacion).filter(Boolean)
  )];

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (isEditing && editingCompany) {
        await axios.put(`${API}/companies/${editingCompany.id}`, formData);
        setSuccess('Empresa actualizada exitosamente');
      } else {
        await axios.post(`${API}/companies`, formData);
        setSuccess('Empresa creada exitosamente');
      }
      
      setShowModal(false);
      setIsEditing(false);
      setEditingCompany(null);
      setShowNewCorporationInput(false);
      setNewCorporationName('');
      setFormData({
        name: '',
        razon_social: '',
        nit: '',
        description: '',
        contacto: '',
        contact_email: '',
        telefono: '',
        direccion: '',
        asesor_comercial_id: '',
        segmento: '',
        corporacion: '',
        is_active: true,
        contactos: []
      });
      fetchCompanies();
    } catch (error) {
      setError(error.response?.data?.detail || (isEditing ? 'Error al actualizar la empresa' : 'Error al crear la empresa'));
    }
  };

  const handleAddContact = () => {
    setFormData({
      ...formData,
      contactos: [...formData.contactos, { nombre: '', email: '', telefono: '' }]
    });
  };

  const handleRemoveContact = (index) => {
    const newContactos = formData.contactos.filter((_, i) => i !== index);
    setFormData({
      ...formData,
      contactos: newContactos
    });
  };

  const handleContactChange = (index, field, value) => {
    const newContactos = [...formData.contactos];
    newContactos[index][field] = value;
    setFormData({
      ...formData,
      contactos: newContactos
    });
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleDeleteClick = (company) => {
    setCompanyToDelete(company);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!companyToDelete) return;

    try {
      await axios.delete(`${API}/companies/${companyToDelete.id}`);
      setSuccess('Empresa eliminada exitosamente');
      setShowDeleteModal(false);
      setCompanyToDelete(null);
      fetchCompanies();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al eliminar la empresa');
      setShowDeleteModal(false);
      setCompanyToDelete(null);
    }
  };

  const handleEditClick = (company) => {
    setEditingCompany(company);
    setIsEditing(true);
    setFormData({
      name: company.name || '',
      razon_social: company.razon_social || '',
      nit: company.nit || '',
      description: company.description || '',
      contacto: company.contacto || '',
      contact_email: company.contact_email || '',
      telefono: company.telefono || '',
      direccion: company.direccion || '',
      asesor_comercial_id: company.asesor_comercial_id || '',
      segmento: company.segmento || '',
      corporacion: company.corporacion || '',
      is_active: company.is_active !== undefined ? company.is_active : true,
      contactos: company.contactos || []
    });
    setShowModal(true);
  };

  const handleViewProjects = (companyId) => {
    navigate(`/projects?company=${companyId}`);
  };

  const handleNewClick = () => {
    setIsEditing(false);
    setEditingCompany(null);
    setFormData({
      name: '',
      razon_social: '',
      nit: '',
      description: '',
      contacto: '',
      contact_email: '',
      telefono: '',
      direccion: '',
      asesor_comercial_id: '',
      segmento: '',
      corporacion: '',
      is_active: true,
      contactos: []
    });
    setShowModal(true);
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
            Empresas
          </h1>
          <p className="text-gray-600 mt-1">
            Gestiona los clientes del sistema
          </p>
        </div>
        
        {user.role === 'staff' && (
          <button
            onClick={handleNewClick}
            className="btn-primary"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Nueva Empresa
          </button>
        )}
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Filters */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filtros</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          
          <div>
            <label htmlFor="filterEstado" className="block text-sm font-medium text-gray-700 mb-2">
              Estado
            </label>
            <select
              id="filterEstado"
              value={filterEstado}
              onChange={(e) => setFilterEstado(e.target.value)}
              className="form-input w-full"
            >
              <option value="">Todas</option>
              <option value="true">Activas</option>
              <option value="false">Inactivas</option>
            </select>
          </div>
        </div>
        
        {(filterCorporacion || filterEstado !== '') && (
          <div className="mt-4 flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Mostrando {filteredCompanies.length} de {companies.length} empresas
            </p>
            <button
              onClick={() => {
                setFilterCorporacion('');
                setFilterEstado('');
              }}
              className="text-sm text-emerald-600 hover:text-emerald-700 font-medium"
            >
              Limpiar filtros
            </button>
          </div>
        )}
      </div>

      {/* Companies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredCompanies.map((company) => (
          <div key={company.id} className="card hover:shadow-lg transition-all">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {company.name}
                </h3>
                {company.description && (
                  <p className="text-gray-600 text-sm mb-3">
                    {company.description}
                  </p>
                )}
                <div className="space-y-1">
                  {company.contact_email && (
                    <div className="flex items-center text-sm text-gray-500">
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                      </svg>
                      {company.contact_email}
                    </div>
                  )}
                  {company.telefono && (
                    <div className="flex items-center text-sm text-gray-500">
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                      </svg>
                      {company.telefono}
                    </div>
                  )}
                  
                  {/* Contactos Adicionales */}
                  {company.contactos && company.contactos.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <p className="text-xs font-medium text-gray-600 mb-2">Contactos Adicionales:</p>
                      {company.contactos.map((contacto, idx) => (
                        <div key={idx} className="ml-2 mb-3 text-xs bg-gray-50 p-2 rounded">
                          {contacto.nombre && (
                            <div className="flex items-center text-gray-700 font-medium mb-1">
                              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                              </svg>
                              {contacto.nombre}
                            </div>
                          )}
                          <div className="flex items-center text-gray-500 mb-1">
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 12a4 4 0 10-8 0 4 4 0 008 0zm0 0v1.5a2.5 2.5 0 005 0V12a9 9 0 10-9 9m4.5-1.206a8.959 8.959 0 01-4.5 1.207" />
                            </svg>
                            {contacto.email}
                          </div>
                          <div className="flex items-center text-gray-500">
                            <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                            </svg>
                            {contacto.telefono}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <span className={`status-badge ${company.is_active !== false ? 'status-active' : 'status-inactive'}`}>
                {company.is_active !== false ? 'Activa' : 'Inactiva'}
              </span>
            </div>
            
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-500">
                  Creada {new Date(company.created_at).toLocaleDateString()}
                </div>
                <div className="flex items-center space-x-2">
                  <button 
                    onClick={() => handleViewProjects(company.id)}
                    className="text-emerald-600 hover:text-emerald-700 text-sm font-medium"
                  >
                    Ver Proyectos
                  </button>
                  {user.role === 'staff' && (
                    <>
                      <button
                        onClick={() => handleEditClick(company)}
                        className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                        title="Editar empresa"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleDeleteClick(company)}
                        className="text-red-600 hover:text-red-700 text-sm font-medium"
                        title="Eliminar empresa"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {companies.length === 0 && (
        <div className="text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2-2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay empresas registradas</h3>
          <p className="text-gray-600">
            {user.role === 'staff' ? 'Comienza creando tu primera empresa cliente.' : 'Contacta con el administrador para obtener acceso.'}
          </p>
        </div>
      )}

      {/* Create Company Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">{isEditing ? 'Editar Empresa' : 'Nueva Empresa'}</h3>
              <button
                onClick={() => setShowModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-4 max-h-96 overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="form-group">
                  <label htmlFor="name" className="form-label">
                    Nombre Comercial *
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
                  <label htmlFor="razon_social" className="form-label">
                    Razón Social
                  </label>
                  <input
                    id="razon_social"
                    name="razon_social"
                    type="text"
                    value={formData.razon_social}
                    onChange={handleChange}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="nit" className="form-label">
                    NIT
                  </label>
                  <input
                    id="nit"
                    name="nit"
                    type="text"
                    value={formData.nit}
                    onChange={handleChange}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="contacto" className="form-label">
                    Contacto
                  </label>
                  <input
                    id="contacto"
                    name="contacto"
                    type="text"
                    value={formData.contacto}
                    onChange={handleChange}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="contact_email" className="form-label">
                    Correo Electrónico
                  </label>
                  <input
                    id="contact_email"
                    name="contact_email"
                    type="email"
                    value={formData.contact_email}
                    onChange={handleChange}
                    className="form-input"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="telefono" className="form-label">
                    Teléfono
                  </label>
                  <input
                    id="telefono"
                    name="telefono"
                    type="tel"
                    value={formData.telefono}
                    onChange={handleChange}
                    className="form-input"
                  />
                </div>

                {/* Contactos Adicionales */}
                <div className="form-group col-span-2 border-t border-gray-200 pt-4 mt-4">
                  <div className="flex justify-between items-center mb-3">
                    <label className="form-label mb-0">
                      Contactos Adicionales
                    </label>
                    <button
                      type="button"
                      onClick={handleAddContact}
                      className="btn-secondary text-sm"
                    >
                      <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                      </svg>
                      Agregar Contacto
                    </button>
                  </div>

                  {formData.contactos && formData.contactos.length > 0 && (
                    <div className="space-y-3">
                      {formData.contactos.map((contacto, index) => (
                        <div key={index} className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                          <div className="flex items-start justify-between mb-3">
                            <h4 className="text-sm font-medium text-gray-700">Contacto {index + 1}</h4>
                            <button
                              type="button"
                              onClick={() => handleRemoveContact(index)}
                              className="text-red-600 hover:text-red-800"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                          <div className="space-y-3">
                            <div>
                              <label className="block text-xs text-gray-600 mb-1">
                                Nombre del Contacto *
                              </label>
                              <input
                                type="text"
                                value={contacto.nombre || ''}
                                onChange={(e) => handleContactChange(index, 'nombre', e.target.value)}
                                className="form-input text-sm"
                                placeholder="Nombre completo"
                                required
                              />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className="block text-xs text-gray-600 mb-1">
                                  Correo Electrónico *
                                </label>
                                <input
                                  type="email"
                                  value={contacto.email}
                                  onChange={(e) => handleContactChange(index, 'email', e.target.value)}
                                  className="form-input text-sm"
                                  placeholder="correo@ejemplo.com"
                                  required
                                />
                              </div>
                              <div>
                                <label className="block text-xs text-gray-600 mb-1">
                                  Teléfono *
                                </label>
                                <input
                                  type="tel"
                                  value={contacto.telefono}
                                  onChange={(e) => handleContactChange(index, 'telefono', e.target.value)}
                                  className="form-input text-sm"
                                  placeholder="+502 1234 5678"
                                  required
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {(!formData.contactos || formData.contactos.length === 0) && (
                    <p className="text-sm text-gray-500 text-center py-4 bg-gray-50 rounded-lg">
                      No hay contactos adicionales. Haz clic en "Agregar Contacto" para añadir uno.
                    </p>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="asesor_comercial_id" className="form-label">
                    Asesor Comercial
                  </label>
                  <select
                    id="asesor_comercial_id"
                    name="asesor_comercial_id"
                    value={formData.asesor_comercial_id}
                    onChange={handleChange}
                    className="form-input"
                  >
                    <option value="">Sin asesor asignado</option>
                    {asesores.map((asesor) => (
                      <option key={asesor.id} value={asesor.id}>
                        {asesor.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="segmento" className="form-label">
                    Segmento/Industria
                  </label>
                  <select
                    id="segmento"
                    name="segmento"
                    value={formData.segmento}
                    onChange={handleChange}
                    className="form-input"
                  >
                    <option value="">Seleccionar segmento</option>
                    {segmentos.map((segmento) => (
                      <option key={segmento.id} value={segmento.nombre}>
                        {segmento.nombre}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="corporacion" className="form-label">
                    Corporación
                  </label>
                  {!showNewCorporationInput ? (
                    <div className="flex gap-2">
                      <select
                        id="corporacion"
                        name="corporacion"
                        value={formData.corporacion}
                        onChange={(e) => {
                          if (e.target.value === '__new__') {
                            setShowNewCorporationInput(true);
                            setFormData({ ...formData, corporacion: '' });
                          } else {
                            handleChange(e);
                          }
                        }}
                        className="form-input flex-1"
                      >
                        <option value="">-- Selecciona una corporación --</option>
                        {corporations.map((corp) => (
                          <option key={corp.id} value={corp.name}>
                            {corp.name}
                          </option>
                        ))}
                        <option value="__new__">➕ Agregar nueva corporación</option>
                      </select>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={newCorporationName}
                          onChange={(e) => setNewCorporationName(e.target.value)}
                          placeholder="Nombre de la nueva corporación"
                          className="form-input flex-1"
                          autoFocus
                        />
                        <button
                          type="button"
                          onClick={handleCreateCorporation}
                          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
                        >
                          Crear
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setShowNewCorporationInput(false);
                            setNewCorporationName('');
                          }}
                          className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
                        >
                          Cancelar
                        </button>
                      </div>
                      <p className="text-xs text-gray-500">
                        La nueva corporación se agregará a la lista para uso futuro
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="direccion" className="form-label">
                  Dirección
                </label>
                <textarea
                  id="direccion"
                  name="direccion"
                  value={formData.direccion}
                  onChange={handleChange}
                  className="form-textarea"
                  rows="2"
                />
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
                <label htmlFor="is_active" className="form-label">
                  Estado de la Empresa *
                </label>
                <select
                  id="is_active"
                  name="is_active"
                  value={formData.is_active}
                  onChange={handleChange}
                  className="form-input"
                  required
                >
                  <option value={true}>Activa</option>
                  <option value={false}>Inactiva</option>
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Solo los usuarios de empresas activas pueden acceder al sistema
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
                  {isEditing ? 'Actualizar Empresa' : 'Crear Empresa'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && companyToDelete && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Eliminar Empresa</h3>
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
                      ¿Estás seguro de que deseas eliminar esta empresa?
                    </h3>
                    <div className="mt-2 text-sm text-red-700">
                      <p>Esta acción eliminará permanentemente:</p>
                      <ul className="list-disc list-inside mt-1">
                        <li><strong>{companyToDelete.name}</strong></li>
                        <li>Todos sus datos asociados</li>
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

export default Companies;
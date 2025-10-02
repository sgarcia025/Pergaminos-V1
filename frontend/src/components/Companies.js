import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Companies = ({ user }) => {
  const [companies, setCompanies] = useState([]);
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
    estado: '',
    corporacion: ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [companyToDelete, setCompanyToDelete] = useState(null);
  const [asesores, setAsesores] = useState([]);
  const [segmentos, setSegmentos] = useState([]);

  useEffect(() => {
    fetchCompanies();
    fetchAsesores();
    fetchSegmentos();
  }, []);

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
      setSegmentos(response.data);
    } catch (error) {
      console.error('Error fetching segmentos:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      await axios.post(`${API}/companies`, formData);
      setSuccess('Empresa creada exitosamente');
      setShowModal(false);
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
        estado: '',
        corporacion: ''
      });
      fetchCompanies();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al crear la empresa');
    }
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
            onClick={() => setShowModal(true)}
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

      {/* Companies Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {companies.map((company) => (
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
                  {company.contact_phone && (
                    <div className="flex items-center text-sm text-gray-500">
                      <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                      </svg>
                      {company.contact_phone}
                    </div>
                  )}
                </div>
              </div>
              <span className="status-badge status-active">
                Activa
              </span>
            </div>
            
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-500">
                  Creada {new Date(company.created_at).toLocaleDateString()}
                </div>
                <div className="flex items-center space-x-2">
                  <button className="text-emerald-600 hover:text-emerald-700 text-sm font-medium">
                    Ver Proyectos
                  </button>
                  {user.role === 'staff' && (
                    <button
                      onClick={() => handleDeleteClick(company)}
                      className="text-red-600 hover:text-red-700 text-sm font-medium"
                      title="Eliminar empresa"
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
              <h3 className="modal-title">Nueva Empresa</h3>
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
                  <label htmlFor="estado" className="form-label">
                    Estado
                  </label>
                  <input
                    id="estado"
                    name="estado"
                    type="text"
                    value={formData.estado}
                    onChange={handleChange}
                    className="form-input"
                    placeholder="ej: Activa, Potencial, etc."
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="corporacion" className="form-label">
                    Corporación
                  </label>
                  <input
                    id="corporacion"
                    name="corporacion"
                    type="text"
                    value={formData.corporacion}
                    onChange={handleChange}
                    className="form-input"
                  />
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
                  Crear Empresa
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
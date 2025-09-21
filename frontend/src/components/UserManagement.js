import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const UserManagement = ({ user }) => {
  const [users, setUsers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    password: '',
    role: 'client',
    company_id: ''
  });

  useEffect(() => {
    if (user.role === 'staff') {
      fetchUsers();
      fetchCompanies();
    }
  }, [user]);

  const fetchUsers = async () => {
    try {
      const response = await axios.get(`${API}/users`);
      setUsers(response.data);
    } catch (error) {
      console.error('Error fetching users:', error);
      setError('Error al cargar usuarios');
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
      await axios.post(`${API}/auth/register`, formData);
      setSuccess('Usuario creado exitosamente');
      setShowModal(false);
      setFormData({
        email: '',
        name: '',
        password: '',
        role: 'client',
        company_id: ''
      });
      fetchUsers();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al crear usuario');
    }
  };

  const toggleUserStatus = async (userId, isActive) => {
    try {
      await axios.put(`${API}/users/${userId}/toggle-status`, { is_active: !isActive });
      setSuccess(`Usuario ${!isActive ? 'activado' : 'desactivado'} exitosamente`);
      fetchUsers();
    } catch (error) {
      setError('Error al cambiar estado del usuario');
    }
  };

  const generateTestCredentials = async () => {
    const testClient = {
      email: 'cliente@empresademo.com',
      name: 'Cliente Demo',
      password: 'cliente123',
      role: 'client',
      company_id: companies.length > 0 ? companies[0].id : ''
    };

    try {
      await axios.post(`${API}/auth/register`, testClient);
      setSuccess('Usuario cliente de prueba creado: cliente@empresademo.com / cliente123');
      fetchUsers();
    } catch (error) {
      if (error.response?.status === 400) {
        setError('El usuario cliente de prueba ya existe');
      } else {
        setError('Error al crear usuario de prueba');
      }
    }
  };

  if (user.role !== 'staff') {
    return (
      <div className="text-center py-12">
        <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <h3 className="text-lg font-medium text-gray-900 mb-2">Acceso Restringido</h3>
        <p className="text-gray-600">
          Solo el personal staff puede gestionar usuarios del sistema.
        </p>
      </div>
    );
  }

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
            Gestión de Usuarios
          </h1>
          <p className="text-gray-600 mt-1">
            Administra usuarios del sistema y sus permisos
          </p>
        </div>
        
        <div className="flex space-x-3">
          <button
            onClick={generateTestCredentials}
            className="btn-secondary"
          >
            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Cliente Prueba
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="btn-primary"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Nuevo Usuario
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Users Table */}
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Usuario</th>
              <th>Email</th>
              <th>Rol</th>
              <th>Empresa</th>
              <th>Estado</th>
              <th>Creado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map((userItem) => (
              <tr key={userItem.id}>
                <td>
                  <div className="flex items-center">
                    <div className="w-8 h-8 bg-emerald-100 rounded-full flex items-center justify-center mr-3">
                      <span className="text-emerald-700 font-semibold text-xs">
                        {userItem.name.split(' ').map(n => n[0]).join('').substring(0, 2)}
                      </span>
                    </div>
                    <div>
                      <div className="font-medium text-gray-900">{userItem.name}</div>
                    </div>
                  </div>
                </td>
                <td className="text-gray-600">{userItem.email}</td>
                <td>
                  <span className={`status-badge ${userItem.role === 'staff' ? 'status-completed' : 'status-active'}`}>
                    {userItem.role === 'staff' ? 'Staff' : 'Cliente'}
                  </span>
                </td>
                <td className="text-gray-600">
                  {userItem.company_id ? (
                    companies.find(c => c.id === userItem.company_id)?.name || 'N/A'
                  ) : (
                    'N/A'
                  )}
                </td>
                <td>
                  <span className={`status-badge ${userItem.is_active ? 'status-active' : 'status-failed'}`}>
                    {userItem.is_active ? 'Activo' : 'Inactivo'}
                  </span>
                </td>
                <td className="text-gray-600">
                  {new Date(userItem.created_at).toLocaleDateString()}
                </td>
                <td>
                  <button
                    onClick={() => toggleUserStatus(userItem.id, userItem.is_active)}
                    className={`text-sm font-medium ${
                      userItem.is_active 
                        ? 'text-red-600 hover:text-red-700' 
                        : 'text-green-600 hover:text-green-700'
                    }`}
                  >
                    {userItem.is_active ? 'Desactivar' : 'Activar'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {users.length === 0 && (
        <div className="text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay usuarios registrados</h3>
          <p className="text-gray-600">
            Comienza creando el primer usuario del sistema.
          </p>
        </div>
      )}

      {/* Create User Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Nuevo Usuario</h3>
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
                  Nombre Completo *
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
                <label htmlFor="email" className="form-label">
                  Email *
                </label>
                <input
                  id="email"
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="form-input"
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="password" className="form-label">
                  Contraseña *
                </label>
                <input
                  id="password"
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  className="form-input"
                  required
                  minLength="6"
                />
              </div>

              <div className="form-group">
                <label htmlFor="role" className="form-label">
                  Rol *
                </label>
                <select
                  id="role"
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  className="form-input"
                  required
                >
                  <option value="client">Cliente</option>
                  <option value="staff">Staff</option>
                </select>
              </div>

              {formData.role === 'client' && (
                <div className="form-group">
                  <label htmlFor="company_id" className="form-label">
                    Empresa
                  </label>
                  <select
                    id="company_id"
                    value={formData.company_id}
                    onChange={(e) => setFormData({ ...formData, company_id: e.target.value })}
                    className="form-input"
                  >
                    <option value="">Sin empresa asignada</option>
                    {companies.map((company) => (
                      <option key={company.id} value={company.id}>
                        {company.name}
                      </option>
                    ))}
                  </select>
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
                  Crear Usuario
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserManagement;
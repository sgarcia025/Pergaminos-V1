import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const UserManagement = ({ user }) => {
  const [users, setUsers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [corporations, setCorporations] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);
  const [showResetPasswordModal, setShowResetPasswordModal] = useState(false);
  const [userToResetPassword, setUserToResetPassword] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [formData, setFormData] = useState({
    email: '',
    name: '',
    password: '',
    role: 'client',
    company_id: '',
    company_ids: [],
    assigned_corporation: ''
  });

  useEffect(() => {
    if (user.role === 'staff') {
      fetchUsers();
      fetchCompanies();
      fetchCorporations();
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

  const fetchCorporations = async () => {
    try {
      const response = await axios.get(`${API}/corporations`);
      setCorporations(response.data);
    } catch (error) {
      console.error('Error fetching corporations:', error);
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
        company_id: '',
        company_ids: [],
        assigned_corporation: ''
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

  const handleDeleteClick = (userToDelete) => {
    setUserToDelete(userToDelete);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!userToDelete) return;

    try {
      await axios.delete(`${API}/users/${userToDelete.id}`);
      setSuccess('Usuario eliminado exitosamente');
      setShowDeleteModal(false);
      setUserToDelete(null);
      fetchUsers();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al eliminar usuario');
      setShowDeleteModal(false);
      setUserToDelete(null);
    }
  };


  const handleResetPasswordClick = (selectedUser) => {
    setUserToResetPassword(selectedUser);
    setNewPassword('');
    setConfirmPassword('');
    setShowResetPasswordModal(true);
  };

  const handleResetPasswordConfirm = async () => {
    if (!userToResetPassword) return;

    // Validate passwords match
    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden');
      return;
    }

    // Validate password length
    if (newPassword.length < 6) {
      setError('La contraseña debe tener al menos 6 caracteres');
      return;
    }

    try {
      await axios.post(`${API}/users/${userToResetPassword.id}/reset-password`, {
        new_password: newPassword
      });
      setSuccess(`Contraseña reiniciada exitosamente para ${userToResetPassword.email}`);
      setShowResetPasswordModal(false);
      setUserToResetPassword(null);
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al reiniciar contraseña');
      setShowResetPasswordModal(false);
      setUserToResetPassword(null);
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
                    <div className="w-8 h-8 bg-yellow-100 rounded-full flex items-center justify-center mr-3">
                      <span className="text-yellow-700 font-semibold text-xs">
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
                  <span className={`status-badge ${
                    userItem.role === 'staff' ? 'status-completed' : 
                    userItem.role === 'asesor' ? 'status-processing' : 
                    'status-active'
                  }`}>
                    {userItem.role === 'staff' ? 'Staff' : 
                     userItem.role === 'asesor' ? 'Asesor' : 'Cliente'}
                  </span>
                </td>
                <td className="text-gray-600">
                  {userItem.role === 'client' ? (
                    <div className="space-y-1">
                      {userItem.assigned_corporation && (
                        <div className="flex items-center">
                          <svg className="w-4 h-4 text-blue-500 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                          </svg>
                          <span className="text-sm font-medium text-blue-600">
                            Corp: {userItem.assigned_corporation}
                          </span>
                        </div>
                      )}
                      {userItem.company_ids && userItem.company_ids.length > 0 ? (
                        <div className="text-sm text-gray-700">
                          <span className="font-medium">{userItem.company_ids.length} empresa(s)</span>
                          <div className="text-xs text-gray-500 mt-1">
                            {userItem.company_ids.slice(0, 2).map(id => 
                              companies.find(c => c.id === id)?.name
                            ).filter(Boolean).join(', ')}
                            {userItem.company_ids.length > 2 && ` +${userItem.company_ids.length - 2} más`}
                          </div>
                        </div>
                      ) : userItem.company_id ? (
                        <span className="text-sm">
                          {companies.find(c => c.id === userItem.company_id)?.name || 'N/A'}
                        </span>
                      ) : (
                        !userItem.assigned_corporation && <span className="text-gray-400">Sin asignar</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-gray-400">N/A</span>
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
                  <div className="flex items-center space-x-2">
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
                    <button
                      onClick={() => handleResetPasswordClick(userItem)}
                      className="text-blue-600 hover:text-blue-700 text-sm font-medium"
                      title="Reiniciar contraseña"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                      </svg>
                    </button>
                    <button
                      onClick={() => handleDeleteClick(userItem)}
                      className="text-red-600 hover:text-red-700 text-sm font-medium"
                      title="Eliminar usuario"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
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
                  <option value="asesor">Asesor Comercial</option>
                  <option value="staff">Staff</option>
                </select>
              </div>

              {formData.role === 'client' && (
                <>
                  {/* Corporation Assignment */}
                  <div className="form-group">
                    <label htmlFor="assigned_corporation" className="form-label">
                      Corporación (acceso a todas las empresas de la corporación)
                    </label>
                    <select
                      id="assigned_corporation"
                      value={formData.assigned_corporation}
                      onChange={(e) => setFormData({ ...formData, assigned_corporation: e.target.value })}
                      className="form-input"
                    >
                      <option value="">Sin corporación asignada</option>
                      {corporations.map((corp) => (
                        <option key={corp.name} value={corp.name}>
                          {corp.name} ({corp.usage_count} empresas)
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Multiple Companies Assignment */}
                  <div className="form-group">
                    <label className="form-label">
                      Empresas Específicas (selección múltiple)
                    </label>
                    <div className="border border-gray-300 rounded-lg p-3 max-h-60 overflow-y-auto">
                      {companies.length === 0 ? (
                        <p className="text-sm text-gray-500">No hay empresas disponibles</p>
                      ) : (
                        companies.map((company) => (
                          <label key={company.id} className="flex items-center py-2 hover:bg-gray-50 px-2 rounded cursor-pointer">
                            <input
                              type="checkbox"
                              checked={formData.company_ids.includes(company.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setFormData({
                                    ...formData,
                                    company_ids: [...formData.company_ids, company.id]
                                  });
                                } else {
                                  setFormData({
                                    ...formData,
                                    company_ids: formData.company_ids.filter(id => id !== company.id)
                                  });
                                }
                              }}
                              className="w-4 h-4 text-yellow-700 border-gray-300 rounded focus:ring-yellow-500 mr-3"
                            />
                            <span className="text-sm text-gray-700">
                              {company.name}
                              {company.corporacion && (
                                <span className="text-xs text-gray-500 ml-2">
                                  ({company.corporacion})
                                </span>
                              )}
                            </span>
                          </label>
                        ))
                      )}
                    </div>
                    {formData.company_ids.length > 0 && (
                      <p className="text-sm text-gray-600 mt-2">
                        {formData.company_ids.length} empresa(s) seleccionada(s)
                      </p>
                    )}
                  </div>

                  {formData.assigned_corporation && formData.company_ids.length > 0 && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                      <p className="text-sm text-blue-800">
                        <strong>Nota:</strong> Este usuario tendrá acceso a todas las empresas de la corporación "{formData.assigned_corporation}" 
                        más las {formData.company_ids.length} empresa(s) específica(s) seleccionada(s).
                      </p>
                    </div>
                  )}
                </>
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

      {/* Delete Confirmation Modal */}
      {showDeleteModal && userToDelete && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Eliminar Usuario</h3>
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
                      ¿Estás seguro de que deseas eliminar este usuario?
                    </h3>
                    <div className="mt-2 text-sm text-red-700">
                      <p>Esta acción eliminará permanentemente:</p>
                      <ul className="list-disc list-inside mt-1">
                        <li><strong>{userToDelete.name}</strong> ({userToDelete.email})</li>
                        <li>Todos sus datos del sistema</li>
                        {userToDelete.role === 'asesor' && (
                          <li>Sus asignaciones como asesor comercial</li>
                        )}
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


      {/* Reset Password Modal */}
      {showResetPasswordModal && userToResetPassword && (
        <div className="modal-overlay" onClick={() => setShowResetPasswordModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Reiniciar Contraseña</h3>
              <button
                onClick={() => setShowResetPasswordModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start">
                  <svg className="w-5 h-5 text-blue-400 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <div className="ml-3">
                    <p className="text-sm text-blue-800">
                      Estás a punto de reiniciar la contraseña para:
                    </p>
                    <p className="text-sm font-semibold text-blue-900 mt-1">
                      {userToResetPassword.name} ({userToResetPassword.email})
                    </p>
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="newPassword" className="form-label">
                  Nueva Contraseña *
                </label>
                <input
                  id="newPassword"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="form-input"
                  placeholder="Mínimo 6 caracteres"
                  autoComplete="new-password"
                />
              </div>

              <div className="form-group">
                <label htmlFor="confirmPassword" className="form-label">
                  Confirmar Contraseña *
                </label>
                <input
                  id="confirmPassword"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="form-input"
                  placeholder="Confirmar nueva contraseña"
                  autoComplete="new-password"
                />
              </div>

              {newPassword && confirmPassword && newPassword !== confirmPassword && (
                <div className="text-sm text-red-600">
                  Las contraseñas no coinciden
                </div>
              )}

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowResetPasswordModal(false)}
                  className="btn-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleResetPasswordConfirm}
                  disabled={!newPassword || !confirmPassword || newPassword !== confirmPassword || newPassword.length < 6}
                  className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Reiniciar Contraseña
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default UserManagement;
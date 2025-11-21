import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Segmentos = ({ user }) => {
  const [segmentos, setSegmentos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [segmentoToDelete, setSegmentoToDelete] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editingSegmento, setEditingSegmento] = useState(null);
  const [formData, setFormData] = useState({
    nombre: '',
    descripcion: ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (user.role === 'staff') {
      fetchSegmentos();
    }
  }, [user]);

  const fetchSegmentos = async () => {
    try {
      const response = await axios.get(`${API}/segmentos`);
      setSegmentos(response.data);
    } catch (error) {
      console.error('Error fetching segmentos:', error);
      setError('Error al cargar los segmentos');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      if (isEditing && editingSegmento) {
        await axios.put(`${API}/segmentos/${editingSegmento.id}`, formData);
        setSuccess('Segmento actualizado exitosamente');
      } else {
        await axios.post(`${API}/segmentos`, formData);
        setSuccess('Segmento creado exitosamente');
      }
      
      setShowModal(false);
      setIsEditing(false);
      setEditingSegmento(null);
      setFormData({
        nombre: '',
        descripcion: ''
      });
      fetchSegmentos();
    } catch (error) {
      setError(error.response?.data?.detail || (isEditing ? 'Error al actualizar el segmento' : 'Error al crear el segmento'));
    }
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleNewClick = () => {
    setIsEditing(false);
    setEditingSegmento(null);
    setFormData({
      nombre: '',
      descripcion: ''
    });
    setShowModal(true);
  };

  const handleEditClick = (segmento) => {
    setIsEditing(true);
    setEditingSegmento(segmento);
    setFormData({
      nombre: segmento.nombre || '',
      descripcion: segmento.descripcion || ''
    });
    setShowModal(true);
  };

  const handleDeleteClick = (segmento) => {
    setSegmentoToDelete(segmento);
    setShowDeleteModal(true);
  };

  const handleDeleteConfirm = async () => {
    if (!segmentoToDelete) return;

    try {
      await axios.delete(`${API}/segmentos/${segmentoToDelete.id}`);
      setSuccess('Segmento eliminado exitosamente');
      setShowDeleteModal(false);
      setSegmentoToDelete(null);
      fetchSegmentos();
    } catch (error) {
      setError(error.response?.data?.detail || 'Error al eliminar el segmento');
      setShowDeleteModal(false);
      setSegmentoToDelete(null);
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
          Solo el personal staff puede gestionar segmentos de industria.
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
          <h1 className="text-3xl font-bold text-gray-900" >
            Segmentos de Industria
          </h1>
          <p className="text-gray-600 mt-1">
            Gestiona los segmentos de industria para clasificar empresas
          </p>
        </div>
        
        <button
          onClick={handleNewClick}
          className="btn-primary"
        >
          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Nuevo Segmento
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* Segmentos Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {segmentos.map((segmento) => (
          <div key={segmento.id} className="card hover:shadow-lg transition-all">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  {segmento.nombre}
                </h3>
                {segmento.descripcion && (
                  <p className="text-gray-600 text-sm mb-3">
                    {segmento.descripcion}
                  </p>
                )}
              </div>
              <span className="status-badge status-active">
                Activo
              </span>
            </div>
            
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-xs text-gray-500">
                  Creado {new Date(segmento.created_at).toLocaleDateString()}
                </div>
                <div className="flex items-center space-x-3">
                  <button
                    onClick={() => handleEditClick(segmento)}
                    className="text-yellow-700 hover:text-yellow-700 text-sm font-medium"
                    title="Editar segmento"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={() => handleDeleteClick(segmento)}
                    className="text-red-600 hover:text-red-700 text-sm font-medium"
                    title="Eliminar segmento"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {segmentos.length === 0 && (
        <div className="text-center py-12">
          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay segmentos registrados</h3>
          <p className="text-gray-600">
            Comienza creando el primer segmento de industria.
          </p>
        </div>
      )}

      {/* Create Segmento Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {isEditing ? 'Editar Segmento de Industria' : 'Nuevo Segmento de Industria'}
              </h3>
              <button
                onClick={() => setShowModal(false)}
                className="modal-close"
              >
                ×
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="form-group">
                <label htmlFor="nombre" className="form-label">
                  Nombre del Segmento *
                </label>
                <input
                  id="nombre"
                  name="nombre"
                  type="text"
                  value={formData.nombre}
                  onChange={handleChange}
                  className="form-input"
                  placeholder="ej: Tecnología, Salud, Manufactura..."
                  required
                />
              </div>

              <div className="form-group">
                <label htmlFor="descripcion" className="form-label">
                  Descripción
                </label>
                <textarea
                  id="descripcion"
                  name="descripcion"
                  value={formData.descripcion}
                  onChange={handleChange}
                  className="form-textarea"
                  rows="3"
                  placeholder="Descripción detallada del segmento de industria..."
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
                  {isEditing ? 'Actualizar Segmento' : 'Crear Segmento'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteModal && segmentoToDelete && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Eliminar Segmento</h3>
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
                      ¿Estás seguro de que deseas eliminar este segmento?
                    </h3>
                    <div className="mt-2 text-sm text-red-700">
                      <p>Esta acción eliminará permanentemente:</p>
                      <ul className="list-disc list-inside mt-1">
                        <li><strong>{segmentoToDelete.nombre}</strong></li>
                        <li>Podrá afectar empresas que usen este segmento</li>
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

export default Segmentos;
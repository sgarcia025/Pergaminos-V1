import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ user }) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => {
    fetchStats();
  }, [startDate, endDate]);

  const fetchStats = async () => {
    try {
      let url = `${API}/dashboard/stats`;
      const params = new URLSearchParams();
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      if (params.toString()) url += `?${params.toString()}`;
      
      const response = await axios.get(url);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCardClick = (filterType) => {
    // Navigate to projects with filter
    const filters = { status: filterType };
    if (startDate) filters.start_date = startDate;
    if (endDate) filters.end_date = endDate;
    
    navigate('/projects', { state: { filters } });
  };

  const clearFilters = () => {
    setStartDate('');
    setEndDate('');
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
          <h1 className="text-3xl font-bold text-gray-900" >
            Dashboard
          </h1>
          <p className="text-gray-600 mt-1">
            Resumen de la actividad del sistema
          </p>
        </div>
      </div>

      {/* Date Range Filter */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Fecha Inicio:</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="form-input"
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">Fecha Fin:</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="form-input"
            />
          </div>
          {(startDate || endDate) && (
            <button
              onClick={clearFilters}
              className="btn-secondary text-sm"
            >
              <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              Limpiar Filtros
            </button>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        {user.role === 'staff' ? (
          <>
            <div className="stat-card cursor-pointer hover:shadow-lg transition-shadow">
              <div className="stat-number">{stats?.companies_count || 0}</div>
              <div className="stat-label">Empresas</div>
            </div>
            <div 
              className="stat-card cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => navigate('/projects')}
            >
              <div className="stat-number">{stats?.projects_count || 0}</div>
              <div className="stat-label">Proyectos</div>
            </div>
            <div className="stat-card cursor-pointer hover:shadow-lg transition-shadow">
              <div className="stat-number">{stats?.documents_total || 0}</div>
              <div className="stat-label">Documentos Total</div>
            </div>
            <div 
              className="stat-card cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('completed')}
            >
              <div className="stat-number">{stats?.documents_completed || 0}</div>
              <div className="stat-label">Procesados</div>
            </div>
            <div 
              className="stat-card cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('processing')}
            >
              <div className="stat-number">{stats?.documents_processing || 0}</div>
              <div className="stat-label">En Proceso</div>
            </div>
            <div 
              className="stat-card cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('failed')}
            >
              <div className="stat-number">{stats?.documents_failed || 0}</div>
              <div className="stat-label">Fallidos</div>
            </div>
            <div 
              className="stat-card cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('needs_review')}
            >
              <div className="stat-number">{stats?.documents_needs_review || 0}</div>
              <div className="stat-label">Revisión</div>
            </div>
            
            {/* QA Statistics */}
            <div 
              className="stat-card bg-green-50 border-green-200 cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('qa_passed')}
            >
              <div className="stat-number text-green-600">{stats?.qa_passed || 0}</div>
              <div className="stat-label text-green-700">QA Aprobado</div>
            </div>
            <div 
              className="stat-card bg-red-50 border-red-200 cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('qa_failed')}
            >
              <div className="stat-number text-red-600">{stats?.qa_failed || 0}</div>
              <div className="stat-label text-red-700">QA Falló</div>
            </div>
            <div 
              className="stat-card bg-yellow-50 border-yellow-200 cursor-pointer hover:shadow-lg transition-shadow"
              onClick={() => handleCardClick('qa_pending')}
            >
              <div className="stat-number text-yellow-600">{stats?.qa_pending || 0}</div>
              <div className="stat-label text-yellow-700">QA Pendiente</div>
            </div>
          </>
        ) : (
          <>
            <div className="stat-card">
              <div className="stat-number">{stats?.projects_count || 0}</div>
              <div className="stat-label">Mis Proyectos</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{stats?.documents_total || 0}</div>
              <div className="stat-label">Documentos Total</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{stats?.documents_completed || 0}</div>
              <div className="stat-label">Procesados</div>
            </div>
          </>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="card hover:shadow-lg transition-all cursor-pointer">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-yellow-100 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-yellow-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2-2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">Gestionar Empresas</h3>
              <p className="text-gray-600 text-sm">Crear y administrar clientes</p>
            </div>
          </div>
        </div>

        <div className="card hover:shadow-lg transition-all cursor-pointer">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">Proyectos</h3>
              <p className="text-gray-600 text-sm">Administrar proyectos de digitalización</p>
            </div>
          </div>
        </div>

        <div className="card hover:shadow-lg transition-all cursor-pointer">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="ml-4">
              <h3 className="text-lg font-semibold text-gray-900">Documentos</h3>
              <p className="text-gray-600 text-sm">Procesar y consultar documentos</p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Actividad Reciente</h2>
        </div>
        <div className="space-y-4">
          <div className="flex items-center p-4 bg-yellow-50 rounded-lg">
            <div className="w-10 h-10 bg-yellow-100 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-yellow-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="ml-4 flex-1">
              <p className="text-sm font-medium text-gray-900">
                Sistema inicializado correctamente
              </p>
              <p className="text-xs text-gray-500">
                Listo para procesar documentos con IA
              </p>
            </div>
            <div className="text-xs text-gray-400">
              Ahora
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
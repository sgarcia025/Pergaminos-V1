import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Dashboard = ({ user }) => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedMonth, setSelectedMonth] = useState(new Date().toISOString().slice(0, 7)); // YYYY-MM format

  useEffect(() => {
    fetchStats();
  }, [selectedMonth]);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API}/dashboard/stats?month=${selectedMonth}`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    } finally {
      setLoading(false);
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
            Dashboard
          </h1>
          <p className="text-gray-600 mt-1">
            Resumen de la actividad del sistema
          </p>
        </div>

        {/* Date Filter */}
        <div className="flex items-center space-x-3">
          <label htmlFor="month-filter" className="text-sm font-medium text-gray-700">
            Filtrar por mes:
          </label>
          <input
            id="month-filter"
            type="month"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="form-input w-auto"
          />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="stats-grid">
        {user.role === 'staff' ? (
          <>
            <Link to="/companies" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.companies_count || 0}</div>
                <div className="stat-label">Empresas</div>
              </div>
            </Link>
            <Link to="/projects" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.projects_count || 0}</div>
                <div className="stat-label">Proyectos</div>
              </div>
            </Link>
            <Link to="/projects" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_total || 0}</div>
                <div className="stat-label">Documentos Total</div>
              </div>
            </Link>
            <Link to="/projects" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_completed || 0}</div>
                <div className="stat-label">Procesados</div>
              </div>
            </Link>
            <Link to="/projects" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_processing || 0}</div>
                <div className="stat-label">En Proceso</div>
              </div>
            </Link>
            <Link to="/projects" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_failed || 0}</div>
                <div className="stat-label">Fallidos</div>
              </div>
            </Link>
            <Link to="/projects" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_needs_review || 0}</div>
                <div className="stat-label">Revisión</div>
              </div>
            </Link>
          </>
        ) : (
          <>
            <Link to="/client-portal" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.projects_count || 0}</div>
                <div className="stat-label">Mis Proyectos</div>
              </div>
            </Link>
            <Link to="/client-portal" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_total || 0}</div>
                <div className="stat-label">Documentos Total</div>
              </div>
            </Link>
            <Link to="/client-portal" className="block">
              <div className="stat-card hover:shadow-lg transition-all cursor-pointer">
                <div className="stat-number">{stats?.documents_completed || 0}</div>
                <div className="stat-label">Procesados</div>
              </div>
            </Link>
          </>
        )}
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <Link to="/companies" className="block">
          <div className="card hover:shadow-lg transition-all cursor-pointer">
            <div className="flex items-center">
              <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center">
                <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2-2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                </svg>
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-semibold text-gray-900">Gestionar Empresas</h3>
                <p className="text-gray-600 text-sm">Crear y administrar clientes</p>
              </div>
            </div>
          </div>
        </Link>

        <Link to="/projects" className="block">
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
        </Link>

        <Link to="/document-processor" className="block">
          <div className="card hover:shadow-lg transition-all cursor-pointer">
            <div className="flex items-center">
              <div className="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
                <svg className="w-6 h-6 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-semibold text-gray-900">Procesador Documentos</h3>
                <p className="text-gray-600 text-sm">Renombrar y reordenar documentos</p>
              </div>
            </div>
          </div>
        </Link>
      </div>

      {/* Recent Activity */}
      <div className="card">
        <div className="card-header">
          <h2 className="card-title">Actividad Reciente - {new Date(selectedMonth).toLocaleDateString('es-ES', { year: 'numeric', month: 'long' })}</h2>
        </div>
        <div className="space-y-4">
          <div className="flex items-center p-4 bg-emerald-50 rounded-lg">
            <div className="w-10 h-10 bg-emerald-100 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <div className="ml-4 flex-1">
              <p className="text-sm font-medium text-gray-900">
                Período seleccionado: {new Date(selectedMonth).toLocaleDateString('es-ES', { year: 'numeric', month: 'long' })}
              </p>
              <p className="text-xs text-gray-500">
                Datos filtrados por fecha de creación
              </p>
            </div>
            <div className="text-xs text-gray-400">
              Filtro activo
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
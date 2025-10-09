import React, { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const ExtractedData = ({ user }) => {
  const [companies, setCompanies] = useState([]);
  const [selectedCompany, setSelectedCompany] = useState('');
  const [extractedData, setExtractedData] = useState(null);
  const [dataSummary, setDataSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('data');
  const [filters, setFilters] = useState({
    project_id: '',
    field_name: ''
  });

  useEffect(() => {
    fetchCompanies();
  }, []);

  useEffect(() => {
    if (selectedCompany) {
      fetchExtractedData();
      fetchDataSummary();
    }
  }, [selectedCompany, filters]);

  const fetchCompanies = async () => {
    try {
      const response = await axios.get(`${API}/companies`);
      setCompanies(response.data);
      
      // Auto-select company for client users
      if (user.role === 'client' && response.data.length > 0) {
        const userCompany = response.data.find(c => c.id === user.company_id);
        if (userCompany) {
          setSelectedCompany(userCompany.id);
        }
      }
    } catch (error) {
      console.error('Error fetching companies:', error);
      setError('Error al cargar empresas');
    }
  };

  const fetchExtractedData = async () => {
    if (!selectedCompany) return;
    
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.project_id) params.append('project_id', filters.project_id);
      if (filters.field_name) params.append('field_name', filters.field_name);
      
      const response = await axios.get(
        `${API}/companies/${selectedCompany}/extracted-data?${params.toString()}`
      );
      setExtractedData(response.data);
      setError('');
    } catch (error) {
      console.error('Error fetching extracted data:', error);
      setError('Error al cargar datos extraídos');
      setExtractedData(null);
    } finally {
      setLoading(false);
    }
  };

  const fetchDataSummary = async () => {
    if (!selectedCompany) return;
    
    try {
      const response = await axios.get(`${API}/companies/${selectedCompany}/data-summary`);
      setDataSummary(response.data);
    } catch (error) {
      console.error('Error fetching data summary:', error);
    }
  };

  const getFieldTypeIcon = (type) => {
    const icons = {
      'text': '📝',
      'number': '🔢',
      'date': '📅',
      'json': '🗂️',
      'email': '📧'
    };
    return icons[type] || '📄';
  };

  const getConfidenceColor = (confidence) => {
    if (!confidence) return 'text-gray-500';
    if (confidence >= 0.8) return 'text-green-600';
    if (confidence >= 0.6) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900" style={{ fontFamily: 'Playfair Display' }}>
            Datos Extraídos
          </h1>
          <p className="text-gray-600 mt-1">
            Consulta y analiza los datos extraídos de documentos por IA
          </p>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* Company Selector */}
      {user.role !== 'client' && (
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
      )}

      {selectedCompany && (
        <>
          {/* Tabs */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-200">
            <div className="border-b border-gray-200">
              <nav className="flex space-x-8 px-6">
                <button
                  onClick={() => setActiveTab('data')}
                  className={`py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'data'
                      ? 'border-emerald-500 text-emerald-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  📄 Datos por Documento
                </button>
                <button
                  onClick={() => setActiveTab('summary')}
                  className={`py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === 'summary'
                      ? 'border-emerald-500 text-emerald-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  📊 Resumen Analítico
                </button>
              </nav>
            </div>

            {/* Filters */}
            <div className="p-6 border-b border-gray-200">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Filtrar por Proyecto
                  </label>
                  <input
                    type="text"
                    placeholder="ID del proyecto..."
                    value={filters.project_id}
                    onChange={(e) => setFilters({ ...filters, project_id: e.target.value })}
                    className="form-input w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Filtrar por Campo
                  </label>
                  <input
                    type="text"
                    placeholder="Nombre del campo..."
                    value={filters.field_name}
                    onChange={(e) => setFilters({ ...filters, field_name: e.target.value })}
                    className="form-input w-full"
                  />
                </div>
              </div>
            </div>

            <div className="p-6">
              {/* Data Tab */}
              {activeTab === 'data' && (
                <>
                  {loading ? (
                    <div className="text-center py-8">
                      <div className="spinner mx-auto"></div>
                      <p className="text-gray-500 mt-2">Cargando datos...</p>
                    </div>
                  ) : extractedData ? (
                    <div className="space-y-6">
                      {/* Stats */}
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div className="bg-blue-50 rounded-lg p-4">
                          <div className="text-2xl font-bold text-blue-600">
                            {extractedData.total_documents}
                          </div>
                          <div className="text-blue-700 text-sm">Documentos Procesados</div>
                        </div>
                        <div className="bg-green-50 rounded-lg p-4">
                          <div className="text-2xl font-bold text-green-600">
                            {extractedData.total_fields}
                          </div>
                          <div className="text-green-700 text-sm">Campos Extraídos</div>
                        </div>
                        <div className="bg-purple-50 rounded-lg p-4">
                          <div className="text-2xl font-bold text-purple-600">
                            {extractedData.company_name}
                          </div>
                          <div className="text-purple-700 text-sm">Empresa</div>
                        </div>
                      </div>

                      {/* Documents */}
                      <div className="space-y-4">
                        {extractedData.documents.map((doc) => (
                          <div key={doc.document_id} className="border border-gray-200 rounded-lg p-6">
                            <div className="flex items-center justify-between mb-4">
                              <div>
                                <h3 className="text-lg font-semibold text-gray-900">
                                  {doc.document_name}
                                </h3>
                                <p className="text-sm text-gray-500">
                                  Procesado: {new Date(doc.extracted_at).toLocaleString()}
                                </p>
                              </div>
                              <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">
                                {doc.fields.length} campos
                              </span>
                            </div>

                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                              {doc.fields.map((field, idx) => (
                                <div key={idx} className="bg-gray-50 rounded-lg p-4">
                                  <div className="flex items-center justify-between mb-2">
                                    <span className="text-sm font-medium text-gray-700 flex items-center">
                                      {getFieldTypeIcon(field.field_type)}
                                      <span className="ml-2">{field.field_name}</span>
                                    </span>
                                    {field.confidence && (
                                      <span className={`text-xs ${getConfidenceColor(field.confidence)}`}>
                                        {(field.confidence * 100).toFixed(0)}%
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-gray-900 text-sm bg-white p-2 rounded border">
                                    {field.field_value}
                                  </div>
                                  {field.page_number && (
                                    <div className="text-xs text-gray-500 mt-1">
                                      Página {field.page_number}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>

                      {extractedData.documents.length === 0 && (
                        <div className="text-center py-12">
                          <svg className="w-24 h-24 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          <h3 className="text-lg font-medium text-gray-900 mb-2">No hay datos</h3>
                          <p className="text-gray-600">
                            No se han encontrado datos extraídos con los filtros aplicados.
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="text-center py-12">
                      <p className="text-gray-500">Seleccione una empresa para ver los datos extraídos.</p>
                    </div>
                  )}
                </>
              )}

              {/* Summary Tab */}
              {activeTab === 'summary' && dataSummary && (
                <div className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="bg-gradient-to-r from-emerald-50 to-teal-50 rounded-lg p-6">
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        📊 Estadísticas Generales
                      </h3>
                      <div className="space-y-2 text-sm">
                        <div>Total de campos únicos: <strong>{dataSummary.total_unique_fields}</strong></div>
                        <div>Empresa: <strong>{dataSummary.company_name}</strong></div>
                      </div>
                    </div>
                  </div>

                  {/* Field Summary Table */}
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Campo
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Frecuencia
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Valores Únicos
                          </th>
                          <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Confianza Promedio
                          </th>
                        </tr>
                      </thead>
                      <tbody className="bg-white divide-y divide-gray-200">
                        {dataSummary.field_summary.map((field, idx) => (
                          <tr key={idx}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="text-sm font-medium text-gray-900">
                                {field._id}
                              </div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                {field.count}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {field.unique_values ? field.unique_values.length : 0}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              {field.avg_confidence ? (
                                <span className={`text-sm font-medium ${getConfidenceColor(field.avg_confidence)}`}>
                                  {(field.avg_confidence * 100).toFixed(1)}%
                                </span>
                              ) : (
                                <span className="text-sm text-gray-400">N/A</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ExtractedData;
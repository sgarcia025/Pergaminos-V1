import React, { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import axios from "axios";
import "./App.css";

// Components
import Login from "./components/Login";
import Dashboard from "./components/Dashboard";
import Companies from "./components/Companies";
import Projects from "./components/Projects";
import ProjectDetail from "./components/ProjectDetail";
import DocumentProcessor from "./components/DocumentProcessor";
import QAAgents from "./components/QAAgents";
import UserManagement from "./components/UserManagement";
import ClientPortal from "./components/ClientPortal";
import Segmentos from "./components/Segmentos";
import QAFindings from "./components/QAFindings";
import ExtractedData from "./components/ExtractedData";
import AIConfiguration from "./components/AIConfiguration";
import UserManual from "./components/UserManual";
import PDFHistory from "./components/PDFHistory";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Set up axios defaults
axios.defaults.headers.common['Content-Type'] = 'application/json';
axios.defaults.timeout = 300000; // 5 minutes timeout for long-running processes (OCR)

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
    
    // Setup axios interceptor to handle 401 errors globally
    const interceptor = axios.interceptors.response.use(
      response => response,
      error => {
        if (error.response?.status === 401 && window.location.pathname !== '/') {
          console.log('Session expired, logging out...');
          localStorage.removeItem('token');
          delete axios.defaults.headers.common['Authorization'];
          window.location.href = '/';
        }
        return Promise.reject(error);
      }
    );
    
    // Cleanup interceptor on unmount
    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, []);

  const checkAuthStatus = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        const response = await axios.get(`${API}/auth/me`);
        setUser(response.data);
      } catch (error) {
        console.error('Auth check failed:', error);
        // Only remove token if it's actually invalid (401), not for network errors
        if (error.response?.status === 401 || error.response?.status === 403) {
          localStorage.removeItem('token');
          delete axios.defaults.headers.common['Authorization'];
        } else {
          console.warn('Network error during auth check, keeping token');
        }
      }
    }
    setLoading(false);
  };

  const login = async (email, password) => {
    try {
      const response = await axios.post(`${API}/auth/login`, { email, password });
      const { access_token, user: userData } = response.data;
      
      localStorage.setItem('token', access_token);
      axios.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      setUser(userData);
      return { success: true };
    } catch (error) {
      return { 
        success: false, 
        error: error.response?.data?.detail || 'Login failed' 
      };
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    delete axios.defaults.headers.common['Authorization'];
    setUser(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-emerald-600"></div>
      </div>
    );
  }

  if (!user) {
    return <Login onLogin={login} />;
  }

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 flex">
        <Sidebar user={user} />
        <div className="flex-1 flex flex-col">
          <Header user={user} onLogout={logout} />
          <main className="flex-1 p-6">
            <Routes>
              <Route path="/" element={user.role === 'client' ? <ClientPortal user={user} /> : <Dashboard user={user} />} />
              <Route path="/dashboard" element={<Dashboard user={user} />} />
              <Route path="/client-portal" element={<ClientPortal user={user} />} />
              <Route path="/companies" element={<Companies user={user} />} />
              <Route path="/projects" element={<Projects user={user} />} />
              <Route path="/projects/:projectId" element={<ProjectDetail user={user} />} />
              <Route path="/document-processor" element={<DocumentProcessor user={user} />} />
              <Route path="/qa-agents" element={<QAAgents user={user} />} />
              <Route path="/user-management" element={<UserManagement user={user} />} />
              <Route path="/manual" element={<UserManual user={user} />} />
              <Route path="/segmentos" element={<Segmentos user={user} />} />
              <Route path="/qa-findings" element={<QAFindings user={user} />} />
              <Route path="/extracted-data" element={<ExtractedData user={user} />} />
              <Route path="/pdf-history" element={<PDFHistory user={user} />} />
              <Route path="/ai-configuration" element={<AIConfiguration user={user} />} />
              <Route path="*" element={user.role === 'client' ? <ClientPortal user={user} /> : <Dashboard user={user} />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

export default App;
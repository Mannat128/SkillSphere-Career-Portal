import React, { useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from './Navbar';
import Sidebar from './Sidebar';
import './AdminLayout.css';

export default function ProtectedRoute({ allowedRoles }) {
  const { user, token, loading } = useAuth();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'var(--background-lavender)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: '40px', height: '40px', border: '4px solid var(--primary-powder-blue)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 12px' }} />
          <p style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>Loading SkillSphere...</p>
        </div>
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!token || !user) return <Navigate to="/login" replace />;

  const role = String(user?.role || '').toUpperCase();
  const allowed = allowedRoles ? allowedRoles.map(item => item.toUpperCase()) : null;

  if (allowed && !allowed.includes(role)) {
    if (role === 'ADMIN') return <Navigate to="/admin/dashboard" replace />;
    if (role === 'RECRUITER') return <Navigate to="/recruiter/dashboard" replace />;
    return <Navigate to="/candidate/dashboard" replace />;
  }

  const isAdmin = role === 'ADMIN';
  const sidebarWidth = sidebarCollapsed ? 68 : 232;

  return (
    <div className={`app-layout${isAdmin ? ' admin-layout' : ''}${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(value => !value)}
      />

      <div
        className="main-content"
        style={{
          marginLeft: `${sidebarWidth}px`,
          width: `calc(100% - ${sidebarWidth}px)`,
          minWidth: 0,
          padding: 0,
          transition: 'margin-left 220ms ease, width 220ms ease'
        }}
      >
        <Navbar />
        <main className={isAdmin ? 'admin-page-content' : undefined}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

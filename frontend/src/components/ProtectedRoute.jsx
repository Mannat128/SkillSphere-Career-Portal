import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import Navbar from './Navbar';
import Sidebar from './Sidebar';

export default function ProtectedRoute({ allowedRoles }) {
  const { user, token, loading } = useAuth();

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

  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  const userRoleUpper = user?.role ? user.role.toUpperCase() : '';
  const allowedUpper = allowedRoles ? allowedRoles.map((r) => r.toUpperCase()) : null;

  if (allowedUpper && !allowedUpper.includes(userRoleUpper)) {
    // Redirect to their default dashboard
    if (userRoleUpper === 'ADMIN') return <Navigate to="/admin/dashboard" replace />;
    if (userRoleUpper === 'RECRUITER') return <Navigate to="/recruiter/dashboard" replace />;
    return <Navigate to="/candidate/dashboard" replace />;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content" style={{ padding: 0 }}>
        <Navbar />
        <main style={{ padding: '28px 36px 60px' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

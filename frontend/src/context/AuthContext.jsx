import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore session from localStorage
    const savedToken = localStorage.getItem('skillsphere_token');
    const savedUser = localStorage.getItem('skillsphere_user');
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      } catch (e) {
        localStorage.removeItem('skillsphere_token');
        localStorage.removeItem('skillsphere_user');
      }
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token, user: userData } = res.data;
    setToken(access_token);
    setUser(userData);
    localStorage.setItem('skillsphere_token', access_token);
    localStorage.setItem('skillsphere_user', JSON.stringify(userData));
    return userData;
  };

  const registerCandidate = async (formData) => {
    const res = await api.post('/auth/register', formData);
    return res.data;
  };

  const registerRecruiter = async (formData) => {
    const res = await api.post('/auth/register-recruiter', formData);
    return res.data;
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem('skillsphere_token');
    localStorage.removeItem('skillsphere_user');
  };

  const updateUser = (updatedData) => {
    const merged = { ...user, ...updatedData };
    setUser(merged);
    localStorage.setItem('skillsphere_user', JSON.stringify(merged));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        registerCandidate,
        registerRecruiter,
        logout,
        updateUser,
        isAuthenticated: !!token,
        isCandidate: user?.role === 'CANDIDATE',
        isRecruiter: user?.role === 'RECRUITER',
        isAdmin: user?.role === 'ADMIN',
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

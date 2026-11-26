import axios from 'axios';

const PRODUCTION_API_BASE_URL = 'https://skillsphere-career-portal.onrender.com/api/v1';
const DEVELOPMENT_API_BASE_URL = 'http://localhost:8000/api/v1';

const apiBaseUrl = import.meta.env.PROD
  ? PRODUCTION_API_BASE_URL
  : (import.meta.env.VITE_API_BASE_URL || DEVELOPMENT_API_BASE_URL);

const api = axios.create({
  baseURL: apiBaseUrl,
});

// Request interceptor: Attach JWT token if present
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('skillsphere_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 Unauthorized
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Only clear session and redirect if the backend indicates the token is invalid/expired
      const tokenInvalid = error.response.headers &&
        (error.response.headers['x-token-invalid'] === 'true' ||
         error.response.headers['X-Token-Invalid'] === 'true');
      if (tokenInvalid) {
        localStorage.removeItem('skillsphere_token');
        localStorage.removeItem('skillsphere_user');
        if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;


import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Eye,
  EyeOff,
  Lock,
  Mail,
  ArrowRight,
  CheckCircle2
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const user = await login(email, password);

      if (user.role === 'ADMIN') {
        navigate('/admin/dashboard');
      } else if (user.role === 'RECRUITER') {
        navigate('/recruiter/dashboard');
      } else {
        navigate('/candidate/dashboard');
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Invalid email or password. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main style={styles.page}>

      {/* LEFT BRANDING PANEL */}
      <section style={styles.hero}>
        <img
          src="/skillsphere-login-left-hq.png"
          alt="SkillSphere - Find, Assess, Get Hired"
          style={styles.heroImage}
        />
      </section>

      {/* RIGHT LOGIN PANEL */}
      <section style={styles.formSection}>
        <div style={styles.formCard}>

          <div style={styles.brandMark}>S</div>

          <p style={styles.eyebrow}>WELCOME BACK</p>

          <h1 style={styles.heading}>Sign In</h1>

          <p style={styles.subtitle}>
            Access your personalized SkillSphere workspace.
          </p>

          {error && (
            <div style={styles.error}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>

            {/* EMAIL */}
            <div style={styles.field}>
              <label style={styles.label}>
                Email Address
              </label>

              <div style={styles.inputWrapper}>
                <Mail size={18} style={styles.inputIcon} />

                <input
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="name@example.com"
                  style={styles.input}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            {/* PASSWORD */}
            <div style={styles.field}>
              <label style={styles.label}>
                Password
              </label>

              <div style={styles.inputWrapper}>
                <Lock size={18} style={styles.inputIcon} />

                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  style={styles.input}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />

                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  style={styles.eyeButton}
                  aria-label={
                    showPassword ? 'Hide password' : 'Show password'
                  }
                >
                  {showPassword
                    ? <EyeOff size={18} />
                    : <Eye size={18} />
                  }
                </button>
              </div>

              {/* FORGOT PASSWORD LINK */}
              <div style={styles.forgotWrapper}>
                <Link
                  to="/forgot-password"
                  style={styles.forgotLink}
                >
                  Forgot Password?
                </Link>
              </div>
            </div>

            {/* SIGN IN */}
            <button
              type="submit"
              disabled={loading}
              style={{
                ...styles.submitButton,
                opacity: loading ? 0.7 : 1,
                cursor: loading ? 'wait' : 'pointer'
              }}
            >
              {loading ? 'Authenticating...' : 'Sign In'}
              <ArrowRight size={19} />
            </button>

          </form>

          {/* REGISTER LINK */}
          <div style={styles.registerText}>
            Don't have an account?{' '}
            <Link to="/register" style={styles.registerLink}>
              Create Account
            </Link>
          </div>

          <div style={styles.footer}>
            © 2026 SkillSphere Portal. All rights reserved.
          </div>

        </div>
      </section>

    </main>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    display: 'grid',
    gridTemplateColumns: '1.05fr 0.95fr',
    background: '#FAF8F3',
    fontFamily: 'inherit'
  },

  hero: {
    minHeight: '100vh',
    background: '#08090B',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },

  heroImage: {
    display: 'block',
    width: '100%',
    height: '100vh',
    objectFit: 'contain',
    objectPosition: 'center'
  },

  formSection: {
    minHeight: '100vh',
    boxSizing: 'border-box',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '28px',
    background: '#FAF8F3'
  },

  formCard: {
    width: '100%',
    maxWidth: '440px',
    boxSizing: 'border-box',
    background: '#FFFFFF',
    padding: '38px 40px',
    borderRadius: '22px',
    border: '1px solid #EAE9E1',
    boxShadow: '0 20px 60px rgba(8, 9, 11, 0.08)'
  },

  brandMark: {
    width: '42px',
    height: '42px',
    borderRadius: '12px',
    background: '#CDF22B',
    color: '#08090B',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 900,
    fontSize: '23px',
    marginBottom: '24px'
  },

  eyebrow: {
    color: '#77796F',
    fontSize: '11px',
    fontWeight: 800,
    letterSpacing: '2px',
    marginBottom: '8px'
  },

  heading: {
    fontSize: '34px',
    fontWeight: 800,
    color: '#08090B',
    margin: 0
  },

  subtitle: {
    fontSize: '14px',
    color: '#77796F',
    lineHeight: 1.6,
    marginTop: '9px',
    marginBottom: '28px'
  },

  field: {
    marginBottom: '20px'
  },

  label: {
    display: 'block',
    color: '#25261F',
    fontSize: '13px',
    fontWeight: 700,
    marginBottom: '9px'
  },

  inputWrapper: {
    position: 'relative',
    display: 'flex',
    alignItems: 'center'
  },

  inputIcon: {
    position: 'absolute',
    left: '14px',
    color: '#77796F',
    pointerEvents: 'none'
  },

  input: {
    width: '100%',
    height: '48px',
    boxSizing: 'border-box',
    border: '1px solid #DEDCD2',
    borderRadius: '10px',
    padding: '0 44px',
    fontSize: '14px',
    outlineColor: '#CDF22B',
    background: '#FFFFFF',
    color: '#08090B'
  },

  eyeButton: {
    position: 'absolute',
    right: '12px',
    border: 'none',
    background: 'transparent',
    color: '#77796F',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center'
  },

  forgotWrapper: {
    display: 'flex',
    justifyContent: 'flex-end',
    marginTop: '10px'
  },

  forgotLink: {
    color: '#667F00',
    fontSize: '12px',
    fontWeight: 750,
    textDecoration: 'none'
  },

  submitButton: {
    width: '100%',
    height: '50px',
    border: 'none',
    borderRadius: '10px',
    background: '#CDF22B',
    color: '#08090B',
    fontWeight: 800,
    fontSize: '15px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    marginTop: '10px',
    boxShadow: '0 6px 18px rgba(205, 242, 43, 0.22)'
  },

  error: {
    background: '#FFF0EF',
    color: '#B42318',
    padding: '12px',
    borderRadius: '8px',
    fontSize: '13px',
    marginBottom: '20px'
  },

  registerText: {
    textAlign: 'center',
    marginTop: '26px',
    color: '#77796F',
    fontSize: '13px'
  },

  registerLink: {
    color: '#08090B',
    fontWeight: 800,
    textDecoration: 'none'
  },

  footer: {
    textAlign: 'center',
    marginTop: '32px',
    color: '#96968D',
    fontSize: '11px'
  }
};


import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  Lock,
  Eye,
  EyeOff,
  CheckCircle,
  AlertCircle,
  Loader2
} from 'lucide-react';
import api from '../../services/api';

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError('Password reset token is missing. Please request a new reset link.');
      return;
    }

    if (password.length < 6) {
      setError('Password must contain at least 6 characters.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    try {
      setLoading(true);

      await api.post('/auth/reset-password', {
        token,
        new_password: password
      });

      setSuccess(true);
      setPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to reset password. Your link may be invalid or expired.'
      );
    } finally {
      setLoading(false);
    }
  };

  const inputWrapper = {
    display: 'flex',
    alignItems: 'center',
    gap: '11px',
    background: '#08090B',
    border: '1px solid #353638',
    borderRadius: '9px',
    padding: '0 14px',
    height: '49px'
  };

  const inputStyle = {
    flex: 1,
    minWidth: 0,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: '#FAF8F3',
    fontSize: '14px'
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <Link to="/login" style={styles.backLink}>
          <ArrowLeft size={17} />
          Back to Login
        </Link>

        <div style={styles.iconWrapper}>
          {success ? (
            <CheckCircle size={28} color="#CDF22B" />
          ) : (
            <Lock size={28} color="#CDF22B" />
          )}
        </div>

        <h1 style={styles.heading}>
          {success ? 'Password Updated!' : 'Create New Password'}
        </h1>

        <p style={styles.description}>
          {success
            ? 'Your password has been changed successfully. You can now sign in using your new password.'
            : 'Choose a strong new password for your SkillSphere account.'}
        </p>

        {success ? (
          <Link to="/login" style={styles.button}>
            Go to Login
          </Link>
        ) : (
          <form onSubmit={handleSubmit}>
            <label style={styles.label}>New Password</label>

            <div style={inputWrapper}>
              <Lock size={18} color="#858585" />
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter new password"
                required
                minLength={6}
                style={inputStyle}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={styles.eyeButton}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>

            <label style={{ ...styles.label, marginTop: '20px' }}>
              Confirm New Password
            </label>

            <div style={inputWrapper}>
              <Lock size={18} color="#858585" />
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm new password"
                required
                minLength={6}
                style={inputStyle}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                style={styles.eyeButton}
                aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
              >
                {showConfirmPassword ? (
                  <EyeOff size={18} />
                ) : (
                  <Eye size={18} />
                )}
              </button>
            </div>

            {error && (
              <div style={styles.errorBox}>
                <AlertCircle size={17} />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !token}
              style={{
                ...styles.button,
                opacity: loading || !token ? 0.6 : 1
              }}
            >
              {loading ? (
                <>
                  <Loader2 size={18} />
                  Updating...
                </>
              ) : (
                'Reset Password'
              )}
            </button>
          </form>
        )}

        {!success && (
          <p style={styles.footer}>
            Remember your password?{' '}
            <Link to="/login" style={styles.loginLink}>
              Sign in
            </Link>
          </p>
        )}
      </div>
    </div>
  );
}

const styles = {
  page: {
    minHeight: '100vh',
    background: '#08090B',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    fontFamily: 'inherit',
    color: '#FAF8F3'
  },
  card: {
    width: '100%',
    maxWidth: '440px',
    background: '#111214',
    border: '1px solid #292A2C',
    borderRadius: '18px',
    padding: '36px',
    boxSizing: 'border-box'
  },
  backLink: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '8px',
    color: '#B7B7B7',
    textDecoration: 'none',
    fontSize: '13px',
    marginBottom: '32px'
  },
  iconWrapper: {
    width: '58px',
    height: '58px',
    borderRadius: '15px',
    background: 'rgba(205, 242, 43, 0.10)',
    border: '1px solid rgba(205, 242, 43, 0.25)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: '24px'
  },
  heading: {
    fontSize: '28px',
    fontWeight: 700,
    margin: '0 0 12px',
    color: '#FAF8F3'
  },
  description: {
    color: '#A3A3A3',
    fontSize: '14px',
    lineHeight: 1.7,
    margin: '0 0 28px'
  },
  label: {
    display: 'block',
    color: '#E7E7E7',
    fontSize: '13px',
    marginBottom: '9px'
  },
  eyeButton: {
    background: 'transparent',
    border: 'none',
    color: '#858585',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    padding: 0
  },
  button: {
    width: '100%',
    minHeight: '49px',
    marginTop: '24px',
    border: 'none',
    borderRadius: '9px',
    background: '#CDF22B',
    color: '#08090B',
    fontSize: '14px',
    fontWeight: 700,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '9px',
    textDecoration: 'none',
    boxSizing: 'border-box'
  },
  errorBox: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '8px',
    color: '#FF7777',
    fontSize: '13px',
    marginTop: '14px'
  },
  footer: {
    textAlign: 'center',
    color: '#929292',
    fontSize: '13px',
    marginTop: '28px'
  },
  loginLink: {
    color: '#CDF22B',
    textDecoration: 'none',
    fontWeight: 600
  }
};


import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Mail, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import api from '../../services/api';

export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess(false);

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    try {
      setLoading(true);

      await api.post('/auth/forgot-password', {
        email: email.trim()
      });

      setSuccess(true);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to process your request. Please try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <Link to="/login" style={styles.backLink}>
          <ArrowLeft size={17} />
          Back to Login
        </Link>

        <div style={styles.iconWrapper}>
          <Mail size={28} color="#CDF22B" />
        </div>

        <h1 style={styles.heading}>Forgot Password?</h1>

        <p style={styles.description}>
          No worries. Enter your registered email address and
          we'll send you instructions to reset your password.
        </p>

        {success ? (
          <div style={styles.successBox}>
            <CheckCircle size={21} color="#CDF22B" />
            <p>
              If an account exists with this email, password
              reset instructions have been sent. Please check
              your inbox.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <label style={styles.label}>Email Address</label>

            <div style={styles.inputWrapper}>
              <Mail size={18} color="#858585" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Enter your registered email"
                required
                style={styles.input}
              />
            </div>

            {error && (
              <div style={styles.errorBox}>
                <AlertCircle size={17} />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              style={{
                ...styles.button,
                opacity: loading ? 0.7 : 1
              }}
            >
              {loading ? (
                <>
                  <Loader2 size={18} />
                  Sending...
                </>
              ) : (
                'Send Reset Instructions'
              )}
            </button>
          </form>
        )}

        <p style={styles.footer}>
          Remember your password?{' '}
          <Link to="/login" style={styles.loginLink}>
            Sign in
          </Link>
        </p>
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
  inputWrapper: {
    display: 'flex',
    alignItems: 'center',
    gap: '11px',
    background: '#08090B',
    border: '1px solid #353638',
    borderRadius: '9px',
    padding: '0 14px',
    height: '49px'
  },
  input: {
    flex: 1,
    minWidth: 0,
    background: 'transparent',
    border: 'none',
    outline: 'none',
    color: '#FAF8F3',
    fontSize: '14px'
  },
  button: {
    width: '100%',
    height: '49px',
    marginTop: '22px',
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
    gap: '9px'
  },
  errorBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    color: '#FF7777',
    fontSize: '13px',
    marginTop: '12px'
  },
  successBox: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '11px',
    padding: '15px',
    background: 'rgba(205, 242, 43, 0.08)',
    border: '1px solid rgba(205, 242, 43, 0.25)',
    borderRadius: '10px',
    color: '#E5E5E5',
    fontSize: '13px',
    lineHeight: 1.6
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

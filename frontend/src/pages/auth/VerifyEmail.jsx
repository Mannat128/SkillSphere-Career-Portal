
import React, { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { CheckCircle2, XCircle, LoaderCircle, Mail } from 'lucide-react';
import api from '../../services/api';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');

  const [status, setStatus] = useState('loading');
  const [message, setMessage] = useState('Verifying your email address...');

  useEffect(() => {
    let cancelled = false;

    const verifyEmail = async () => {
      if (!token) {
        setStatus('error');
        setMessage('Verification token is missing. Please open the complete verification link.');
        return;
      }

      try {
        const response = await api.post('/auth/verify-email', {
          token,
        });

        if (!cancelled) {
          setStatus('success');
          setMessage(
            response.data?.message ||
            'Your email address has been verified successfully.'
          );
        }
      } catch (error) {
        if (!cancelled) {
          const detail = error.response?.data?.detail;

          setStatus('error');
          setMessage(
            typeof detail === 'string'
              ? detail
              : 'Email verification failed. Your link may be invalid or expired.'
          );
        }
      }
    };

    verifyEmail();

    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <main className="ss-verify-page">
      <style>{`
        .ss-verify-page {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
          box-sizing: border-box;
          background: #FAF8F3;
          font-family: Inter, system-ui, sans-serif;
        }

        .ss-verify-card {
          width: 100%;
          max-width: 440px;
          padding: 42px 35px;
          text-align: center;
          background: #FFFFFF;
          border: 1px solid #E6E3DB;
          border-radius: 20px;
          box-shadow: 0 15px 45px rgba(20, 20, 10, 0.07);
        }

        .ss-verify-logo {
          font-size: 20px;
          font-weight: 850;
          color: #11120D;
          margin-bottom: 32px;
          letter-spacing: -0.6px;
        }

        .ss-verify-logo span {
          display: inline-grid;
          place-items: center;
          width: 27px;
          height: 27px;
          margin-right: 7px;
          border-radius: 8px;
          background: #CDF22B;
        }

        .ss-verify-icon {
          width: 68px;
          height: 68px;
          display: grid;
          place-items: center;
          margin: 0 auto 20px;
          border-radius: 50%;
          background: #F1F8D9;
          color: #6C8C0A;
        }

        .ss-verify-icon.error {
          background: #FFF0ED;
          color: #B33C2D;
        }

        .ss-verify-icon.loading {
          background: #F2F1E9;
          color: #686A60;
        }

        .ss-verify-card h1 {
          margin: 0 0 12px;
          font-size: 25px;
          font-weight: 850;
          letter-spacing: -0.8px;
          color: #11120D;
        }

        .ss-verify-message {
          margin: 0;
          color: #77796F;
          font-size: 13px;
          line-height: 1.7;
        }

        .ss-verify-button {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          min-height: 46px;
          margin-top: 27px;
          border-radius: 30px;
          background: #CDF22B;
          color: #11120D;
          font-size: 13px;
          font-weight: 850;
          text-decoration: none;
          box-sizing: border-box;
          transition: 0.2s ease;
        }

        .ss-verify-button:hover {
          background: #BDE51B;
          transform: translateY(-1px);
        }

        .ss-verify-note {
          margin-top: 19px;
          font-size: 11px;
          color: #92948A;
        }

        @media (prefers-reduced-motion: reduce) {
          .ss-verify-page * {
            transition: none !important;
          }
        }
      `}</style>

      <section className="ss-verify-card">
        <div className="ss-verify-logo">
          <span>S</span>
          SkillSphere
        </div>

        <div
          className={`ss-verify-icon ${
            status === 'error'
              ? 'error'
              : status === 'loading'
                ? 'loading'
                : ''
          }`}
        >
          {status === 'loading' && (
            <LoaderCircle size={34} className="animate-spin" />
          )}

          {status === 'success' && (
            <CheckCircle2 size={36} />
          )}

          {status === 'error' && (
            <XCircle size={36} />
          )}
        </div>

        <h1>
          {status === 'loading'
            ? 'Verifying Email'
            : status === 'success'
              ? 'Email Verified!'
              : 'Verification Failed'}
        </h1>

        <p className="ss-verify-message" role="status">
          {message}
        </p>

        {status !== 'loading' && (
          <Link to="/login" className="ss-verify-button">
            Go to Sign In
          </Link>
        )}

        {status === 'loading' && (
          <p className="ss-verify-note">
            <Mail size={13} style={{ verticalAlign: 'middle' }} /> Please wait while we verify your account.
          </p>
        )}
      </section>
    </main>
  );
}

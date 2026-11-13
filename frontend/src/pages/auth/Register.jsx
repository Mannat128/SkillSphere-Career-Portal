
import React, { useState, useEffect } from 'react';
import {
  Link,
  useNavigate,
  useSearchParams
} from 'react-router-dom';

import {
  User,
  Building,
  Mail,
  Lock,
  ArrowRight,
  Eye,
  EyeOff
} from 'lucide-react';

import { useAuth } from '../../context/AuthContext';

export default function Register() {
  const [searchParams] = useSearchParams();

  // Read role from URL
  const initialRole =
    searchParams.get('role')?.toUpperCase() === 'RECRUITER'
      ? 'RECRUITER'
      : 'CANDIDATE';

  const [role, setRole] = useState(initialRole);

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  // Recruiter fields
  const [companyName, setCompanyName] = useState('');
  const [designation, setDesignation] = useState('Talent Acquisition Lead');
  const [companyWebsite, setCompanyWebsite] = useState('');
  const [industry, setIndustry] = useState('Technology');

  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const {
    registerCandidate,
    registerRecruiter,
    login
  } = useAuth();

  const navigate = useNavigate();

  // Update role when URL query parameter changes
  useEffect(() => {
    setRole(initialRole);
  }, [initialRole]);

  // Registration handler
  const handleSubmit = async (e) => {
    e.preventDefault();

    setError('');
    setLoading(true);

    try {
      if (role === 'CANDIDATE') {
        await registerCandidate({
          full_name: fullName,
          email,
          password
        });

        await login(email, password);

        navigate('/candidate/dashboard');

      } else {
        await registerRecruiter({
          full_name: fullName,
          email,
          password,
          company_name: companyName,
          designation,
          company_website: companyWebsite,
          industry
        });

        await login(email, password);

        navigate('/recruiter/dashboard');
      }

    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Registration failed. Please check your details and try again.'
      );

    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="ss-register">

      <style>{`
        .ss-register {
          --ss-black: #08090B;
          --ss-ivory: #FAF8F3;
          --ss-lime: #CDF22B;
          --ss-muted: #77796F;

          min-height: 100vh;
          display: grid;
          grid-template-columns: 1.05fr 0.95fr;
          background: var(--ss-ivory);
          color: var(--ss-black);
          font-family: inherit;
        }

        .ss-register * {
          box-sizing: border-box;
        }

        /* LEFT IMAGE PANEL */

        .ss-reg-hero {
          min-height: 100vh;
          background: var(--ss-black);
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
          position: relative;
        }

        .ss-reg-hero-image {
          display: block;
          width: 100%;
          height: 100vh;
          object-fit: contain;
          object-position: center;
        }

        /* RIGHT FORM PANEL */

        .ss-reg-form-section {
          min-height: 100vh;
          padding: 32px;
          display: flex;
          justify-content: center;
          align-items: center;
          background: var(--ss-ivory);
          overflow-y: auto;
        }

        .ss-reg-card {
          width: 100%;
          max-width: 490px;
          padding: 35px 38px;
          border-radius: 21px;
          background: #FFFFFF;
          border: 1px solid #EAE9E1;
          box-shadow: 0 18px 55px rgba(8,9,11,.08);
          margin: auto;
        }

        .ss-reg-card-icon {
          width: 43px;
          height: 43px;
          border-radius: 12px;
          background: var(--ss-lime);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 22px;
          font-weight: 900;
          margin-bottom: 22px;
        }

        .ss-reg-card h2 {
          margin: 0;
          color: var(--ss-black);
          font-size: 29px;
          font-weight: 850;
          letter-spacing: -1px;
        }

        .ss-reg-subtitle {
          color: var(--ss-muted);
          font-size: 13px;
          margin: 8px 0 22px;
          line-height: 1.6;
        }

        /* ROLE SELECTOR */

        .ss-reg-role-selector {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 8px;
          padding: 5px;
          background: #F2F1EA;
          border-radius: 11px;
          margin-bottom: 24px;
        }

        .ss-reg-role {
          min-height: 43px;
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 8px;
          border: 1px solid transparent;
          border-radius: 8px;
          background: transparent;
          color: #77796F;
          font-size: 12px;
          font-weight: 750;
          cursor: pointer;
          transition: .2s;
        }

        .ss-reg-role.active {
          background: var(--ss-black);
          color: var(--ss-lime);
          border-color: var(--ss-black);
          box-shadow: 0 3px 9px rgba(8,9,11,.12);
        }

        .ss-reg-role:hover:not(.active) {
          color: var(--ss-black);
          background: #FFFFFF;
        }

        /* FORM FIELDS */

        .ss-reg-field {
          margin-bottom: 17px;
        }

        .ss-reg-field label {
          display: block;
          margin-bottom: 8px;
          color: #292A24;
          font-size: 12px;
          font-weight: 750;
        }

        .ss-reg-input-wrap {
          position: relative;
          display: flex;
          align-items: center;
        }

        .ss-reg-input-icon {
          position: absolute;
          left: 13px;
          color: #898B80;
          pointer-events: none;
        }

        .ss-reg-input {
          width: 100%;
          height: 46px;
          padding: 0 42px;
          border: 1px solid #DEDDD4;
          border-radius: 9px;
          outline: none;
          background: #FFFFFF;
          color: var(--ss-black);
          font-size: 13px;
          font-family: inherit;
          transition: border .2s, box-shadow .2s;
        }

        .ss-reg-input:focus {
          border-color: #A8CC12;
          box-shadow: 0 0 0 3px rgba(205,242,43,.17);
        }

        .ss-reg-input::placeholder {
          color: #A0A096;
        }

        .ss-reg-eye {
          position: absolute;
          right: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 4px;
          background: transparent;
          border: none;
          color: #77796F;
          cursor: pointer;
        }

        .ss-reg-recruiter-fields {
          padding-top: 2px;
          border-top: 1px solid #EEEEEA;
          margin-top: 5px;
        }

        .ss-reg-two-fields {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        /* ERROR MESSAGE */

        .ss-reg-error {
          padding: 12px 14px;
          margin-bottom: 18px;
          background: #FFF0EF;
          border: 1px solid #F3D0CD;
          border-radius: 9px;
          color: #B42318;
          font-size: 12px;
          line-height: 1.5;
        }

        /* REGISTER BUTTON */

        .ss-reg-submit {
          width: 100%;
          min-height: 49px;
          padding: 12px 18px;
          margin-top: 7px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 11px;
          border: none;
          border-radius: 9px;
          background: var(--ss-lime);
          color: var(--ss-black);
          font-family: inherit;
          font-size: 14px;
          font-weight: 850;
          cursor: pointer;
          box-shadow: 0 6px 17px rgba(170,205,25,.18);
          transition: .2s;
        }

        .ss-reg-submit:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 9px 22px rgba(170,205,25,.27);
        }

        .ss-reg-submit:disabled {
          opacity: .65;
          cursor: wait;
        }

        .ss-reg-login {
          margin-top: 22px;
          text-align: center;
          color: #77796F;
          font-size: 12px;
        }

        .ss-reg-login a {
          color: #667F00;
          font-weight: 850;
          text-decoration: none;
        }

        .ss-reg-login a:hover {
          text-decoration: underline;
        }

        /* RESPONSIVE */

        @media (max-width: 850px) {
          .ss-register {
            grid-template-columns: 1fr;
          }

          .ss-reg-hero {
            min-height: 380px;
          }

          .ss-reg-hero-image {
            height: 380px;
            object-fit: contain;
          }

          .ss-reg-form-section {
            min-height: auto;
            padding: 30px 18px;
          }
        }

        @media (max-width: 480px) {
          .ss-reg-hero {
            min-height: 280px;
          }

          .ss-reg-hero-image {
            height: 280px;
          }

          .ss-reg-card {
            padding: 27px 21px;
          }

          .ss-reg-card h2 {
            font-size: 25px;
          }

          .ss-reg-role {
            font-size: 10px;
            gap: 5px;
          }

          .ss-reg-two-fields {
            grid-template-columns: 1fr;
            gap: 0;
          }
        }
      `}</style>

      {/* LEFT SIDE - SAME IMAGE AS LOGIN */}

      <section className="ss-reg-hero">
        <img
          src="/skillsphere-login-left-hq.png"
          alt="SkillSphere - Find, Assess, Get Hired"
          className="ss-reg-hero-image"
        />
      </section>

      {/* RIGHT SIDE - REGISTRATION FORM */}

      <section className="ss-reg-form-section">

        <div className="ss-reg-card">

          <div className="ss-reg-card-icon">S</div>

          <h2>Create Account</h2>

          <p className="ss-reg-subtitle">
            Choose your account role to get started.
          </p>

          {/* ROLE SELECTOR */}

          <div className="ss-reg-role-selector">

            <button
              type="button"
              className={`ss-reg-role ${role === 'CANDIDATE' ? 'active' : ''}`}
              onClick={() => setRole('CANDIDATE')}
              aria-pressed={role === 'CANDIDATE'}
            >
              <User size={16} />
              Job Seeker
            </button>

            <button
              type="button"
              className={`ss-reg-role ${role === 'RECRUITER' ? 'active' : ''}`}
              onClick={() => setRole('RECRUITER')}
              aria-pressed={role === 'RECRUITER'}
            >
              <Building size={16} />
              Employer / Recruiter
            </button>

          </div>

          {/* ERROR */}

          {error && (
            <div className="ss-reg-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>

            {/* FULL NAME */}

            <div className="ss-reg-field">
              <label htmlFor="reg-full-name">Full Name</label>

              <div className="ss-reg-input-wrap">
                <User className="ss-reg-input-icon" size={17} />

                <input
                  id="reg-full-name"
                  type="text"
                  required
                  autoComplete="name"
                  placeholder="Enter your full name"
                  className="ss-reg-input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
            </div>

            {/* EMAIL */}

            <div className="ss-reg-field">
              <label htmlFor="reg-email">Work / Personal Email</label>

              <div className="ss-reg-input-wrap">
                <Mail className="ss-reg-input-icon" size={17} />

                <input
                  id="reg-email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="name@example.com"
                  className="ss-reg-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            {/* PASSWORD */}

            <div className="ss-reg-field">
              <label htmlFor="reg-password">Password</label>

              <div className="ss-reg-input-wrap">
                <Lock className="ss-reg-input-icon" size={17} />

                <input
                  id="reg-password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  minLength={6}
                  autoComplete="new-password"
                  placeholder="Min 6 characters"
                  className="ss-reg-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />

                <button
                  type="button"
                  className="ss-reg-eye"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? (
                    <EyeOff size={18} />
                  ) : (
                    <Eye size={18} />
                  )}
                </button>
              </div>
            </div>

            {/* RECRUITER FIELDS */}

            {role === 'RECRUITER' && (
              <div className="ss-reg-recruiter-fields">

                <div className="ss-reg-field">
                  <label htmlFor="reg-company">Company Name</label>

                  <div className="ss-reg-input-wrap">
                    <Building className="ss-reg-input-icon" size={17} />

                    <input
                      id="reg-company"
                      type="text"
                      required
                      placeholder="Company name"
                      className="ss-reg-input"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                    />
                  </div>
                </div>

                <div className="ss-reg-two-fields">

                  <div className="ss-reg-field">
                    <label htmlFor="reg-designation">Designation</label>

                    <input
                      id="reg-designation"
                      type="text"
                      placeholder="Tech Recruiter"
                      className="ss-reg-input"
                      value={designation}
                      onChange={(e) => setDesignation(e.target.value)}
                    />
                  </div>

                  <div className="ss-reg-field">
                    <label htmlFor="reg-website">Website</label>

                    <input
                      id="reg-website"
                      type="url"
                      placeholder="https://company.com"
                      className="ss-reg-input"
                      value={companyWebsite}
                      onChange={(e) => setCompanyWebsite(e.target.value)}
                    />
                  </div>

                </div>

              </div>
            )}

            {/* REGISTER BUTTON */}

            <button
              type="submit"
              className="ss-reg-submit"
              disabled={loading}
            >
              {loading
                ? 'Creating Account...'
                : `Register as ${role === 'RECRUITER' ? 'Recruiter' : 'Job Seeker'}`}

              {!loading && <ArrowRight size={18} />}
            </button>

          </form>

          <div className="ss-reg-login">
            Already registered?{' '}
            <Link to="/login">Sign In</Link>
          </div>

        </div>

      </section>

    </main>
  );
}

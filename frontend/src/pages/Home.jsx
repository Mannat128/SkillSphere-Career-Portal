
import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  Sparkles,
  FileText,
  Target,
  Users,
  Briefcase,
  Search,
  ClipboardCheck,
  TrendingUp,
  Building2,
  BarChart3,
  ShieldCheck
} from 'lucide-react';

import './Landing.css';

export default function Home() {
  return (
    <div className="landing-page">

      {/* NAVBAR */}
      <header className="landing-navbar">

        <Link to="/" className="landing-logo">
          <span className="landing-logo-mark">S</span>
          SkillSphere
        </Link>

        <nav className="landing-nav-links">
          <a href="#features">Features</a>
          <a href="#candidates">For Candidates</a>
          <a href="#recruiters">For Recruiters</a>
        </nav>

        <div className="landing-nav-actions">
          <Link to="/login" className="landing-login-link">
            Log In
          </Link>

          <Link
            to="/register"
            className="landing-nav-cta"
          >
            Get Started <ArrowRight size={16} />
          </Link>
        </div>

      </header>

      {/* HERO SECTION */}
      <section className="landing-hero">

        <div className="landing-hero-content">

          <div className="landing-eyebrow">
            <Sparkles size={15} />
            <span>YOUR NEXT CAREER STARTS HERE</span>
          </div>

          <h1>
            Discover
            <br />
            Opportunities
            <br />
            <span>Without Limits.</span>
          </h1>

          <p className="landing-description">
            Connect with opportunities that match your skills.
            Build your professional profile, showcase your talent
            and move confidently towards your dream career.
          </p>

          <div className="landing-hero-actions">

            <Link
              to="/register"
              className="landing-primary-button"
            >
              Get Started <ArrowRight size={18} />
            </Link>

            <Link
              to="/login"
              className="landing-secondary-button"
            >
              Explore Portal
            </Link>

          </div>

          <div className="landing-trust-line">
            <span className="landing-trust-dot" />
            <span>Built for candidates and recruiters</span>
          </div>

        </div>

        {/* ORIGINAL ARTWORK */}
        <div className="landing-hero-visual">

          <div className="landing-image-glow" />

          <img
            src="/skillsphere-laptop-ribbon-artwork.png"
            alt="SkillSphere laptop and ribbon artwork"
            className="landing-laptop-image"
          />

          <div className="landing-image-caption">
            <span className="caption-line" />
            FIND. ASSESS. GET HIRED.
          </div>

        </div>

      </section>

      {/* FEATURES */}
      <section className="landing-features" id="features">

        <div className="landing-section-heading">
          <span>WHY SKILLSPHERE</span>

          <h2>
            Everything you need to
            <br />
            <span>move forward.</span>
          </h2>

          <p>
            One platform connecting talent, skills and opportunities.
          </p>
        </div>

        <div className="landing-feature-grid">

          <article className="landing-feature-card">
            <div className="feature-icon">
              <FileText size={23} />
            </div>

            <h3>Smart Resume Parsing</h3>

            <p>
              Upload your resume and use intelligent OCR
              to extract and organize your profile information.
            </p>
          </article>

          <article className="landing-feature-card">
            <div className="feature-icon">
              <Target size={23} />
            </div>

            <h3>Skill-Based Assessment</h3>

            <p>
              Demonstrate your knowledge through
              recruiter-controlled assessments.
            </p>
          </article>

          <article className="landing-feature-card">
            <div className="feature-icon">
              <Users size={23} />
            </div>

            <h3>Talent Matching</h3>

            <p>
              Connect candidate skills and job requirements
              through intelligent talent matching.
            </p>
          </article>

          <article className="landing-feature-card">
            <div className="feature-icon">
              <Briefcase size={23} />
            </div>

            <h3>Career Opportunities</h3>

            <p>
              Explore job opportunities and manage your
              career journey from one workspace.
            </p>
          </article>

        </div>

      </section>

      {/* CANDIDATE SECTION */}
      <section className="landing-audience-section" id="candidates">

        <div className="landing-audience-content">

          <span className="landing-audience-label">
            FOR JOB SEEKERS
          </span>

          <h2>
            Your skills deserve
            <br />
            <span>the right opportunity.</span>
          </h2>

          <p>
            Create your professional profile, discover relevant jobs,
            showcase your abilities and manage your applications
            from one place.
          </p>

          <div className="landing-audience-points">

            <div>
              <FileText size={19} />
              <span>Build and manage your resume</span>
            </div>

            <div>
              <Search size={19} />
              <span>Explore relevant job opportunities</span>
            </div>

            <div>
              <ClipboardCheck size={19} />
              <span>Complete skill-based assessments</span>
            </div>

            <div>
              <TrendingUp size={19} />
              <span>Track your application progress</span>
            </div>

          </div>

          <div className="landing-hero-actions">

            <Link
              to="/register?role=CANDIDATE"
              className="landing-primary-button"
            >
              Join as Candidate <ArrowRight size={18} />
            </Link>

            <Link
              to="/login"
              className="landing-secondary-button"
            >
              Candidate Login
            </Link>

          </div>

        </div>

        <div className="landing-audience-visual candidate-visual">
          <div className="audience-visual-icon">
            <Users size={55} />
          </div>

          <div className="audience-visual-title">
            <span>YOUR CAREER</span>
            <strong>YOUR NEXT CHAPTER.</strong>
          </div>

          <div className="audience-visual-line" />
        </div>

      </section>

      {/* RECRUITER SECTION */}
      <section className="landing-audience-section recruiter-section" id="recruiters">

        <div className="landing-audience-visual recruiter-visual">

          <div className="audience-visual-icon">
            <Building2 size={55} />
          </div>

          <div className="audience-visual-title">
            <span>BUILD YOUR TEAM</span>
            <strong>FIND THE RIGHT TALENT.</strong>
          </div>

          <div className="audience-visual-line" />

        </div>

        <div className="landing-audience-content">

          <span className="landing-audience-label">
            FOR EMPLOYERS & RECRUITERS
          </span>

          <h2>
            Find talent that
            <br />
            <span>moves business forward.</span>
          </h2>

          <p>
            Manage job openings, discover qualified candidates,
            evaluate skills and organize your recruitment workflow
            through one centralized platform.
          </p>

          <div className="landing-audience-points">

            <div>
              <Briefcase size={19} />
              <span>Create and manage job openings</span>
            </div>

            <div>
              <Users size={19} />
              <span>Explore and manage applicants</span>
            </div>

            <div>
              <ClipboardCheck size={19} />
              <span>Configure candidate assessments</span>
            </div>

            <div>
              <BarChart3 size={19} />
              <span>Track recruitment progress</span>
            </div>

          </div>

          <div className="landing-hero-actions">

            <Link
              to="/register?role=RECRUITER"
              className="landing-primary-button"
            >
              Join as Recruiter <ArrowRight size={18} />
            </Link>

            <Link
              to="/login"
              className="landing-secondary-button"
            >
              Recruiter Login
            </Link>

          </div>

        </div>

      </section>

      {/* BOTTOM CTA */}
      <section className="landing-bottom-cta">

        <div>
          <span>READY FOR YOUR NEXT STEP?</span>
          <h2>Your future starts with one click.</h2>
        </div>

        <Link
          to="/register"
          className="landing-primary-button"
        >
          Create Your Account <ArrowRight size={18} />
        </Link>

      </section>

      {/* FOOTER */}
      <footer className="landing-footer">

        <Link to="/" className="landing-logo">
          <span className="landing-logo-mark">S</span>
          SkillSphere
        </Link>

        <p>© 2026 SkillSphere Portal. All rights reserved.</p>

        <Link to="/login" className="landing-login-link">
          Sign In
        </Link>

      </footer>

    </div>
  );
}

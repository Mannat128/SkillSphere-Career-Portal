
import React, { useEffect, useMemo, useState } from 'react';
import { Download, FileText } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';

const sectionStyle = {
  marginBottom: '24px',
};

const headingStyle = {
  fontSize: '1rem',
  fontWeight: 800,
  borderBottom: '1px solid #CBD5E1',
  paddingBottom: '5px',
  marginBottom: '10px',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};

const textStyle = {
  fontSize: '0.9rem',
  color: '#334155',
  whiteSpace: 'pre-wrap',
  overflowWrap: 'anywhere',
};

const getText = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  return '';
};

const formatDate = (value) => {
  if (!value) return '';
  return getText(value);
};

export default function ResumeBuilder() {
  const { user } = useAuth();

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    fetchProfile();
  }, []);

  const fetchProfile = async () => {
    setLoading(true);

    try {
      const res = await api.get('/candidate/profile');
      setProfile(res.data || {});
    } catch (error) {
      console.error('Resume profile loading failed:', error);
      alert(
        error.response?.data?.detail ||
        'Unable to load candidate profile.'
      );
    } finally {
      setLoading(false);
    }
  };

  const skills = useMemo(() => {
    return (profile?.skills || [])
      .map((skill) => ({
        name: getText(skill?.name || skill?.skill_name || skill?.skill?.name || skill),
        proficiency: getText(skill?.proficiency),
      }))
      .filter((skill) => skill.name);
  }, [profile]);

  const experiences = profile?.experiences || [];
  const educations = profile?.educations || [];
  const projects = profile?.projects || [];
  const certifications = profile?.certifications || [];

  const handleDownloadPdf = async () => {
    setGenerating(true);

    try {
      const res = await api.get('/candidate/resume-builder/pdf', {
        responseType: 'blob',
      });

      const blob = new Blob([res.data], {
        type: 'application/pdf',
      });

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');

      link.href = url;
      link.download = `${user?.full_name || 'Candidate'}_Resume.pdf`;

      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('PDF generation failed:', error);
      alert('Failed to generate PDF resume. Please try again.');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 50, textAlign: 'center' }}>
        Loading resume data...
      </div>
    );
  }

  const fullName = getText(user?.full_name) || 'Name not provided';
  const email = getText(user?.email);
  const contact = [
    email,
    getText(profile?.phone),
    getText(profile?.location),
  ].filter(Boolean);

  const summary = getText(profile?.bio);
  const headline = getText(profile?.headline);

  const hasContent =
    summary ||
    headline ||
    skills.length ||
    experiences.length ||
    educations.length ||
    projects.length ||
    certifications.length;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div
        className="page-header"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 16,
          flexWrap: 'wrap',
          marginBottom: 24,
        }}
      >
        <div>
          <h2 className="page-title">Resume Builder</h2>
          <p className="page-subtitle">
            Your resume is automatically generated from your candidate profile.
          </p>
        </div>

        <button
          onClick={handleDownloadPdf}
          disabled={generating}
          className="btn btn-primary"
        >
          <Download size={18} />
          {generating ? 'Generating PDF...' : 'Download PDF Resume'}
        </button>
      </div>

      <div
        className="card"
        style={{
          padding: '48px 56px',
          background: '#FFFFFF',
          boxShadow: '0 8px 30px rgba(0,0,0,0.06)',
          borderRadius: 12,
          fontFamily: 'serif',
          color: '#1E293B',
          lineHeight: 1.6,
          overflowWrap: 'anywhere',
        }}
      >
        {/* Header */}
        <div
          style={{
            textAlign: 'center',
            borderBottom: '2px solid #0F172A',
            paddingBottom: 16,
            marginBottom: 24,
          }}
        >
          <h1
            style={{
              fontSize: '2rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: 1,
              margin: 0,
            }}
          >
            {fullName}
          </h1>

          {headline && (
            <p
              style={{
                fontSize: '1rem',
                color: '#475569',
                marginTop: 5,
                fontStyle: 'italic',
              }}
            >
              {headline}
            </p>
          )}

          {contact.length > 0 && (
            <p
              style={{
                fontSize: '0.85rem',
                color: '#64748B',
                marginTop: 5,
              }}
            >
              {contact.join(' • ')}
            </p>
          )}
        </div>

        {!hasContent && (
          <div style={{ textAlign: 'center', padding: 25 }}>
            <FileText size={35} />
            <p>Your profile does not contain enough information yet.</p>
            <p>Add skills, projects, education or certifications to build your resume.</p>
          </div>
        )}

        {/* Professional Summary */}
        {(summary || headline) && (
          <section style={sectionStyle}>
            <h3 style={headingStyle}>Professional Summary</h3>
            <p style={textStyle}>{summary || headline}</p>
          </section>
        )}

        {/* Technical Skills */}
        {skills.length > 0 && (
          <section style={sectionStyle}>
            <h3 style={headingStyle}>Technical Skills</h3>
            <p style={textStyle}>
              {skills
                .map((skill) =>
                  skill.proficiency
                    ? `${skill.name} (${skill.proficiency})`
                    : skill.name
                )
                .join(' • ')}
            </p>
          </section>
        )}

        {/* Work Experience */}
        {experiences.length > 0 && (
          <section style={sectionStyle}>
            <h3 style={headingStyle}>Work Experience</h3>

            {experiences.map((exp, index) => (
              <div key={exp.id || index} style={{ marginBottom: 16 }}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    gap: 12,
                    flexWrap: 'wrap',
                  }}
                >
                  <strong>
                    {[getText(exp.position), getText(exp.company)]
                      .filter(Boolean)
                      .join(' — ')}
                  </strong>

                  <span style={{ fontSize: '0.82rem', color: '#64748B' }}>
                    {formatDate(exp.start_date)}
                    {exp.start_date || exp.end_date ? ' – ' : ''}
                    {exp.is_current ? 'Present' : formatDate(exp.end_date)}
                  </span>
                </div>

                {exp.location && (
                  <p style={{ fontSize: '0.84rem', color: '#64748B' }}>
                    {getText(exp.location)}
                  </p>
                )}

                {exp.description && (
                  <p style={textStyle}>{getText(exp.description)}</p>
                )}
              </div>
            ))}
          </section>
        )}

        {/* Projects */}
        {projects.length > 0 && (
          <section style={sectionStyle}>
            <h3 style={headingStyle}>Projects</h3>

            {projects.map((project, index) => (
              <div key={project.id || index} style={{ marginBottom: 16 }}>
                <strong style={{ fontSize: '0.95rem' }}>
                  {getText(project.title) || 'Project'}
                </strong>

                {project.description && (
                  <p style={{ ...textStyle, marginTop: 4 }}>
                    {getText(project.description)}
                  </p>
                )}

                {project.technologies && (
                  <p
                    style={{
                      fontSize: '0.85rem',
                      color: '#475569',
                      marginTop: 4,
                    }}
                  >
                    <strong>Technologies:</strong>{' '}
                    {getText(project.technologies)}
                  </p>
                )}

                {project.project_url && (
                  <p
                    style={{
                      fontSize: '0.82rem',
                      color: '#2563EB',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    Project URL: {getText(project.project_url)}
                  </p>
                )}
              </div>
            ))}
          </section>
        )}

        {/* Education */}
        {educations.length > 0 && (
          <section style={sectionStyle}>
            <h3 style={headingStyle}>Education</h3>

            {educations.map((edu, index) => (
              <div
                key={edu.id || index}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  marginBottom: 12,
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <strong>{getText(edu.institution)}</strong>

                  <p style={{ fontSize: '0.88rem', color: '#475569' }}>
                    {[getText(edu.degree), getText(edu.field_of_study)]
                      .filter(Boolean)
                      .join(' — ')}
                  </p>

                  {edu.grade && (
                    <p style={{ fontSize: '0.84rem', color: '#64748B' }}>
                      Grade: {getText(edu.grade)}
                    </p>
                  )}
                </div>

                {edu.graduation_year && (
                  <span style={{ fontSize: '0.85rem', color: '#64748B' }}>
                    {getText(edu.graduation_year)}
                  </span>
                )}
              </div>
            ))}
          </section>
        )}

        {/* Certifications */}
        {certifications.length > 0 && (
          <section style={sectionStyle}>
            <h3 style={headingStyle}>Certifications</h3>

            {certifications.map((cert, index) => (
              <div key={cert.id || index} style={{ marginBottom: 12 }}>
                <strong>{getText(cert.name)}</strong>

                <p style={{ fontSize: '0.87rem', color: '#475569' }}>
                  {getText(cert.issuing_organization)}
                  {cert.issue_date
                    ? ` • ${getText(cert.issue_date)}`
                    : ''}
                </p>

                {cert.credential_url && (
                  <p
                    style={{
                      fontSize: '0.82rem',
                      color: '#2563EB',
                      overflowWrap: 'anywhere',
                    }}
                  >
                    Credential: {getText(cert.credential_url)}
                  </p>
                )}
              </div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}

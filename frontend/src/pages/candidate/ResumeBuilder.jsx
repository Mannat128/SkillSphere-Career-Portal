import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  User,
  GraduationCap,
  Briefcase,
  Code,
  Sparkles,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import api from '../../services/api';

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
      setProfile(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPdf = async () => {
    setGenerating(true);
    try {
      const res = await api.get('/candidate/resume-builder/pdf', {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${user?.full_name || 'Candidate'}_Resume.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      alert('Failed to generate PDF resume');
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '50px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading resume data...</div>;
  }

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto' }}>
      <div className="page-header">
        <div>
          <h2 className="page-title">Resume Builder</h2>
          <p className="page-subtitle">
            Preview your structured candidate profile and generate a professional ATS-friendly PDF.
          </p>
        </div>

        <button
          onClick={handleDownloadPdf}
          disabled={generating}
          className="btn btn-primary"
        >
          <Download size={18} /> {generating ? 'Generating PDF...' : 'Download PDF Resume'}
        </button>
      </div>

      {/* Resume Document Paper Preview */}
      <div
        className="card"
        style={{
          padding: '48px 56px',
          background: '#FFFFFF',
          boxShadow: '0 8px 30px rgba(0,0,0,0.06)',
          borderRadius: '12px',
          fontFamily: 'serif',
          color: '#1E293B',
          lineHeight: 1.6,
        }}
      >
        {/* Header */}
        <div style={{ textAlign: 'center', borderBottom: '2px solid #0F172A', paddingBottom: '16px', marginBottom: '24px' }}>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px' }}>
            {user?.full_name || 'Name not provided'}
          </h1>
          <p style={{ fontSize: '1rem', color: '#475569', marginTop: '4px', fontStyle: 'italic' }}>
            {profile?.headline || ''}
          </p>
          <p style={{ fontSize: '0.85rem', color: '#64748B', marginTop: '4px' }}>
            {[user?.email, profile?.phone].filter(Boolean).join(' • ')}
          </p>
        </div>

        {/* Summary */}
        {profile?.bio && (
          <div style={{ marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 800, borderBottom: '1px solid #CBD5E1', paddingBottom: '4px', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Professional Summary
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#334155' }}>
              {profile.bio}
            </p>
          </div>
        )}

        {/* Technical Skills */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 800, borderBottom: '1px solid #CBD5E1', paddingBottom: '4px', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Technical Skills
          </h3>
          <p style={{ fontSize: '0.9rem', color: '#334155' }}>
            {(profile?.skills || []).map((s) => s.skill_name || s).join(' • ')}
          </p>
        </div>

        {/* Experience */}
        <div style={{ marginBottom: '24px' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 800, borderBottom: '1px solid #CBD5E1', paddingBottom: '4px', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Experience
          </h3>
          {(profile?.experiences || []).length === 0 ? (
            <p style={{ fontSize: '0.85rem', color: '#64748B' }}>Add experience in candidate profile to appear here.</p>
          ) : (
            profile.experiences.map((exp, i) => (
              <div key={i} style={{ marginBottom: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, fontSize: '0.95rem' }}>
                  <span>{exp.position || 'Position not provided'} — {exp.company || 'Company not provided'}</span>
                  <span style={{ fontSize: '0.85rem', color: '#64748B' }}>{exp.start_date || '—'} - {exp.is_current ? 'Present' : (exp.end_date || '—')}</span>
                </div>
                <p style={{ fontSize: '0.88rem', color: '#475569', marginTop: '2px' }}>
                  {exp.description}
                </p>
              </div>
            ))
          )}
        </div>

        {/* Education */}
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 800, borderBottom: '1px solid #CBD5E1', paddingBottom: '4px', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Education
          </h3>
          {(profile?.educations || []).length === 0 ? (
            <p style={{ fontSize: '0.85rem', color: '#64748B' }}>Add education in candidate profile to appear here.</p>
          ) : (
            profile.educations.map((edu, i) => (
              <div key={i} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.92rem' }}>{edu.institution || 'Institution not provided'}</div>
                  <div style={{ fontSize: '0.85rem', color: '#475569' }}>{[edu.degree, edu.field_of_study].filter(Boolean).join(' — ') || 'Degree not provided'}</div>
                </div>
                <span style={{ fontSize: '0.85rem', color: '#64748B' }}>{edu.graduation_year || '—'}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

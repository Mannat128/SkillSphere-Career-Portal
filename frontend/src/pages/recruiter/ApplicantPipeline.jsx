import React, { useState, useEffect } from 'react';
import {
  Users,
  CheckCircle2,
  Clock,
  FileText,
  Sparkles,
  ArrowRight,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import api from '../../services/api';

const PIPELINE_COLUMNS = [
  { key: 'APPLIED', label: 'Applied', color: 'var(--primary-powder-blue)' },
  { key: 'UNDER_REVIEW', label: 'Under Review', color: 'var(--info)' },
  { key: 'SHORTLISTED', label: 'Shortlisted (MCQ Assigned)', color: 'var(--accent-peach-dark)' },
  { key: 'INTERVIEW', label: 'Interview', color: 'var(--warning)' },
  { key: 'SELECTED', label: 'Selected', color: 'var(--success)' },
  { key: 'REJECTED', label: 'Rejected', color: 'var(--danger)' },
];

export default function ApplicantPipeline() {
  const [pipeline, setPipeline] = useState({});
  const [loading, setLoading] = useState(true);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [jobs, setJobs] = useState([]);
  const [notificationMsg, setNotificationMsg] = useState('');

  useEffect(() => {
    fetchJobs();
    fetchPipeline();
  }, [selectedJobId]);

  const fetchJobs = async () => {
    try {
      const res = await api.get('/recruiter/jobs');
      setJobs(res.data);
    } catch (e) {}
  };

  const fetchPipeline = async () => {
    setLoading(true);
    try {
      const url = selectedJobId ? `/recruiter/pipeline?job_id=${selectedJobId}` : '/recruiter/pipeline';
      const res = await api.get(url);
      setPipeline(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (appId, newStatus) => {
    try {
      await api.put(`/recruiter/applicants/${appId}/status`, {
        status: newStatus,
        notes: `Moved to ${newStatus} via Pipeline Board`,
      });

      if (newStatus === 'SHORTLISTED') {
        setNotificationMsg('Candidate Shortlisted! First Round MCQ Assessment has been automatically assigned.');
        setTimeout(() => setNotificationMsg(''), 6000);
      }

      fetchPipeline();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to update application status');
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Applicant Recruitment Pipeline</h2>
          <p className="page-subtitle">
            Progress candidates through recruitment stages. Moving an applicant to Shortlisted automatically provisions their First Round Assessment.
          </p>
        </div>

        {/* Job Filter */}
        <div style={{ width: '260px' }}>
          <select
            className="form-select"
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
          >
            <option value="">All Job Postings</option>
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>{j.title}</option>
            ))}
          </select>
        </div>
      </div>

      {notificationMsg && (
        <div style={{
          background: 'var(--accent-peach-light)',
          color: '#832709',
          padding: '12px 18px',
          borderRadius: 'var(--radius-md)',
          fontWeight: 700,
          fontSize: '0.88rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: '20px',
          border: '1px solid rgba(245, 182, 158, 0.4)'
        }}>
          <Sparkles size={18} />
          {notificationMsg}
        </div>
      )}

      {/* Kanban Board Columns */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(6, minmax(240px, 1fr))',
        gap: '16px',
        overflowX: 'auto',
        paddingBottom: '20px'
      }}>
        {PIPELINE_COLUMNS.map((col) => {
          const items = pipeline[col.key] || [];
          return (
            <div
              key={col.key}
              style={{
                background: 'rgba(255, 255, 255, 0.7)',
                backdropFilter: 'blur(6px)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-soft)',
                padding: '16px',
                minHeight: '600px',
                display: 'flex',
                flexDirection: 'column'
              }}
            >
              {/* Column Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', paddingBottom: '10px', borderBottom: '1px solid var(--border-soft)' }}>
                <span style={{ fontWeight: 800, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                  {col.label}
                </span>
                <span style={{
                  background: '#FFFFFF',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  boxShadow: 'var(--shadow-sm)'
                }}>
                  {items.length}
                </span>
              </div>

              {/* Cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
                {items.length === 0 ? (
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-light)', textAlign: 'center', marginTop: '20px' }}>
                    No candidates
                  </p>
                ) : (
                  items.map((cand) => (
                    <div
                      key={cand.id}
                      style={{
                        background: '#FFFFFF',
                        borderRadius: 'var(--radius-md)',
                        padding: '14px',
                        boxShadow: 'var(--shadow-sm)',
                        border: '1px solid var(--border-soft)'
                      }}
                    >
                      <p style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
                        {cand.candidate_name}
                      </p>
                      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {cand.candidate_email}
                      </p>
                      <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--primary-powder-blue-dark)', marginTop: '4px' }}>
                        {cand.job_title}
                      </p>

                      {cand.match_score !== null && (
                        <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#10B981' }}>
                            {cand.match_score}% Match
                          </span>
                        </div>
                      )}

                      {/* Status Selector Dropdown */}
                      <div style={{ marginTop: '12px', paddingTop: '10px', borderTop: '1px solid var(--border-soft)' }}>
                        <label style={{ fontSize: '0.7rem', color: 'var(--text-light)', display: 'block', marginBottom: '4px' }}>
                          Move stage:
                        </label>
                        <select
                          className="form-select"
                          style={{ padding: '6px 8px', fontSize: '0.78rem' }}
                          value={col.key}
                          onChange={(e) => handleStatusChange(cand.id, e.target.value)}
                        >
                          {PIPELINE_COLUMNS.map((c) => (
                            <option key={c.key} value={c.key}>{c.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

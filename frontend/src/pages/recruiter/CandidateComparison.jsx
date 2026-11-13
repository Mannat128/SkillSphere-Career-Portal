import React, { useState, useEffect } from 'react';
import {
  Users,
  Award,
  CheckCircle,
  XCircle,
  Briefcase,
  GraduationCap,
  Sparkles,
  ArrowRight,
} from 'lucide-react';
import api from '../../services/api';

export default function CandidateComparison() {
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [applicants, setApplicants] = useState([]);
  const [selectedApplicantIds, setSelectedApplicantIds] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      fetchApplicants(selectedJobId);
    }
  }, [selectedJobId]);

  const fetchJobs = async () => {
    try {
      const res = await api.get('/recruiter/jobs');
      setJobs(res.data || []);
      if (res.data && res.data.length > 0) {
        setSelectedJobId(res.data[0].id.toString());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const fetchApplicants = async (jobId) => {
    setLoading(true);
    try {
      const res = await api.get(`/recruiter/jobs/${jobId}/applicants`);
      setApplicants(res.data || []);
      // Auto-select first 2-3 applicants for immediate preview
      const initialIds = (res.data || []).slice(0, 3).map((a) => a.id);
      setSelectedApplicantIds(initialIds);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleApplicant = (id) => {
    if (selectedApplicantIds.includes(id)) {
      setSelectedApplicantIds(selectedApplicantIds.filter((item) => item !== id));
    } else {
      if (selectedApplicantIds.length >= 4) {
        alert('You can compare up to 4 candidates side-by-side.');
        return;
      }
      setSelectedApplicantIds([...selectedApplicantIds, id]);
    }
  };

  const comparedCandidates = applicants.filter((a) => selectedApplicantIds.includes(a.id));

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Candidate Side-by-Side Comparison</h2>
          <p className="page-subtitle">
            Compare shortlisted candidates across technical skills, First Round Assessment scores, and experience.
          </p>
        </div>

        {/* Job Selector */}
        <div style={{ width: '280px' }}>
          <select
            className="form-select"
            value={selectedJobId}
            onChange={(e) => setSelectedJobId(e.target.value)}
          >
            {jobs.map((j) => (
              <option key={j.id} value={j.id}>#{j.id} {j.title}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Candidate Selector Pills */}
      <div className="card" style={{ padding: '16px 20px', marginBottom: '24px' }}>
        <h4 style={{ fontSize: '0.88rem', fontWeight: 700, marginBottom: '10px', color: 'var(--text-muted)' }}>
          Select Candidates to Compare (Max 4):
        </h4>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {applicants.map((a) => {
            const isSelected = selectedApplicantIds.includes(a.id);
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => handleToggleApplicant(a.id)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '20px',
                  fontSize: '0.82rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  border: `1.5px solid ${isSelected ? 'var(--primary-powder-blue)' : 'var(--border-color)'}`,
                  background: isSelected ? 'var(--primary-powder-blue-light)' : '#FFFFFF',
                  color: isSelected ? 'var(--primary-powder-blue-dark)' : 'var(--text-secondary)',
                }}
              >
                {isSelected ? '✓ ' : '+ '}{a.candidate_name || `Applicant #${a.id}`}
              </button>
            );
          })}
        </div>
      </div>

      {/* Comparison Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
          Loading applicants...
        </div>
      ) : comparedCandidates.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Users size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 12px' }} />
          <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>No Candidates Selected</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '4px' }}>
            Select candidates from the pills above to view a comprehensive side-by-side breakdown.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${comparedCandidates.length}, 1fr)`, gap: '20px' }}>
          {comparedCandidates.map((cand) => (
            <div key={cand.id} className="card" style={{ padding: '24px' }}>
              {/* Header */}
              <div style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '14px', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {cand.candidate_name}
                </h3>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {cand.candidate_email}
                </p>
                <span
                  className="badge badge-blue"
                  style={{ marginTop: '8px', display: 'inline-block' }}
                >
                  Status: {cand.status}
                </span>
              </div>

              {/* Assessment Performance Section */}
              <div style={{ marginBottom: '20px', padding: '14px', background: 'var(--bg-lavender-white)', borderRadius: '10px' }}>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--primary-powder-blue-dark)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
                  <Award size={16} /> First Round Assessment
                </h4>

                {cand.assessment_result ? (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '4px' }}>
                      <span>Score:</span>
                      <strong>{cand.assessment_result.obtained_marks} / {cand.assessment_result.total_marks} ({cand.assessment_result.percentage.toFixed(1)}%)</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '8px' }}>
                      <span>Verdict:</span>
                      <span className={`badge ${cand.assessment_result.is_qualified ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.75rem' }}>
                        {cand.assessment_result.is_qualified ? 'QUALIFIED' : 'NOT QUALIFIED'}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Correct: {cand.assessment_result.correct_count} • Incorrect: {cand.assessment_result.incorrect_count}
                    </div>
                  </div>
                ) : (
                  <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Assessment Pending / In Progress
                  </span>
                )}
              </div>

              {/* Skills */}
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 700, marginBottom: '6px' }}>Identified Skills</h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                  {(cand.skills || ['Python', 'SQL', 'FastAPI']).map((sk, idx) => (
                    <span key={idx} className="badge" style={{ background: '#F1F5F9', fontSize: '0.75rem' }}>
                      {sk}
                    </span>
                  ))}
                </div>
              </div>

              {/* Education & Experience */}
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                <p><strong>Education:</strong> {cand.education_summary || 'B.S. in Computer Science'}</p>
                <p style={{ marginTop: '4px' }}><strong>Applied on:</strong> {new Date(cand.created_at).toLocaleDateString()}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

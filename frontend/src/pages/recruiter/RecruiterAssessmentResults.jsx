import React, { useState, useEffect } from 'react';
import {
  CheckCircle2,
  XCircle,
  Search,
  Filter,
  Eye,
  Award,
  Clock,
  Briefcase,
  User,
} from 'lucide-react';
import api from '../../services/api';

export default function RecruiterAssessmentResults() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState(''); // 'qualified', 'not_qualified'
  const [jobs, setJobs] = useState([]);
  const [selectedJobId, setSelectedJobId] = useState('');

  // Selected Result for Detail Modal
  const [activeResult, setActiveResult] = useState(null);

  useEffect(() => {
    fetchJobs();
    fetchResults();
  }, [selectedJobId, statusFilter]);

  const fetchJobs = async () => {
    try {
      const res = await api.get('/recruiter/jobs');
      setJobs(res.data);
    } catch (e) {}
  };

  const fetchResults = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedJobId) params.append('job_id', selectedJobId);
      if (statusFilter) params.append('status_filter', statusFilter);
      if (search) params.append('search', search);

      const res = await api.get(`/recruiter/assessments/results?${params.toString()}`);
      setResults(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Candidate Assessment Results</h2>
          <p className="page-subtitle">
            Review live scorecards and question breakdowns for first-round candidate MCQ screenings.
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card" style={{ marginBottom: '24px', padding: '18px 24px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'center' }}>
          <div style={{ flex: 1, minWidth: '240px', position: 'relative' }}>
            <Search size={18} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '12px' }} />
            <input
              type="text"
              placeholder="Search candidate name or email..."
              className="form-input"
              style={{ paddingLeft: '38px' }}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchResults()}
            />
          </div>

          <div style={{ width: '220px' }}>
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

          <div style={{ width: '180px' }}>
            <select
              className="form-select"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="">All Results</option>
              <option value="qualified">Qualified Only</option>
              <option value="not_qualified">Not Qualified</option>
            </select>
          </div>

          <button onClick={fetchResults} className="btn btn-outline">
            Apply Filters
          </button>
        </div>
      </div>

      {/* Results Table */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
            Loading candidate scorecards...
          </div>
        ) : results.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '50px 20px' }}>
            <Award size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 12px' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>No Assessment Results Found</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              Results will populate here automatically once shortlisted candidates complete their assessments.
            </p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Job & Assessment</th>
                <th>Score</th>
                <th>Percentage</th>
                <th>Correct / Wrong</th>
                <th>Status</th>
                <th>Submitted</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id}>
                  <td>
                    <p style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{r.candidate_name}</p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{r.candidate_email}</p>
                  </td>
                  <td>
                    <p style={{ fontWeight: 600 }}>{r.job_title}</p>
                    <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{r.assessment_title}</p>
                  </td>
                  <td>
                    <span style={{ fontWeight: 800, fontSize: '0.95rem' }}>
                      {r.obtained_marks} / {r.total_marks}
                    </span>
                    <span style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      Pass: {r.qualification_rule} {r.passing_marks}
                    </span>
                  </td>
                  <td>
                    <span style={{ fontWeight: 700 }}>{r.percentage}%</span>
                  </td>
                  <td>
                    <span style={{ color: 'var(--success)', fontWeight: 700 }}>{r.correct_count}</span>
                    {' / '}
                    <span style={{ color: 'var(--danger)', fontWeight: 700 }}>{r.incorrect_count}</span>
                    {r.unanswered_count > 0 && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}> ({r.unanswered_count} skipped)</span>
                    )}
                  </td>
                  <td>
                    {r.is_qualified ? (
                      <span className="badge badge-success" style={{ gap: '4px' }}>
                        <CheckCircle2 size={12} /> Qualified
                      </span>
                    ) : (
                      <span className="badge badge-danger" style={{ gap: '4px' }}>
                        <XCircle size={12} /> Not Qualified
                      </span>
                    )}
                  </td>
                  <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    {new Date(r.evaluated_at).toLocaleDateString()}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      onClick={() => setActiveResult(r)}
                      className="btn btn-outline"
                      style={{ padding: '6px 12px', fontSize: '0.78rem' }}
                    >
                      <Eye size={14} /> Breakdown
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Detailed Breakdown Modal */}
      {activeResult && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '750px' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '4px' }}>
              Candidate Assessment Breakdown
            </h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '18px' }}>
              {activeResult.candidate_name} ({activeResult.candidate_email}) — {activeResult.job_title}
            </p>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '12px',
              padding: '14px',
              background: 'var(--surface-subtle)',
              borderRadius: 'var(--radius-md)',
              marginBottom: '20px'
            }}>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Score</span>
                <p style={{ fontWeight: 800, fontSize: '1.1rem' }}>{activeResult.obtained_marks} / {activeResult.total_marks}</p>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Percentage</span>
                <p style={{ fontWeight: 800, fontSize: '1.1rem' }}>{activeResult.percentage}%</p>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Qualification Rule</span>
                <p style={{ fontWeight: 700, fontSize: '0.95rem' }}>{activeResult.qualification_rule} {activeResult.passing_marks} pts</p>
              </div>
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Status</span>
                <p style={{ fontWeight: 800, fontSize: '0.95rem', color: activeResult.is_qualified ? 'var(--success)' : 'var(--danger)' }}>
                  {activeResult.is_qualified ? 'QUALIFIED' : 'NOT QUALIFIED'}
                </p>
              </div>
            </div>

            <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '12px' }}>Question-by-Question Review</h4>
            <div style={{ maxHeight: '360px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {activeResult.question_breakdown?.map((q, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '12px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-soft)',
                    background: q.is_correct ? 'rgba(16, 185, 129, 0.04)' : 'rgba(239, 68, 68, 0.04)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <p style={{ fontWeight: 600, fontSize: '0.88rem', flex: 1 }}>
                      {idx + 1}. {q.question_text}
                    </p>
                    <span style={{
                      fontWeight: 700,
                      fontSize: '0.8rem',
                      color: q.is_correct ? 'var(--success)' : 'var(--danger)',
                      marginLeft: '12px'
                    }}>
                      {q.marks_awarded > 0 ? `+${q.marks_awarded}` : q.marks_awarded} pts
                    </span>
                  </div>

                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '6px' }}>
                    Candidate Selected: <strong>Option {q.selected_option || 'None (Skipped)'}</strong>
                  </p>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
              <button onClick={() => setActiveResult(null)} className="btn btn-primary">
                Close Breakdown
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

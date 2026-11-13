import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  CheckSquare,
  Clock,
  Award,
  ArrowRight,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Building,
} from 'lucide-react';
import api from '../../services/api';

export default function FirstRoundAssessments() {
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAssessments();
  }, []);

  const fetchAssessments = async () => {
    setLoading(true);
    try {
      const res = await api.get('/candidate/first-round-assessments');
      setAssessments(res.data);
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
          <h2 className="page-title">First Round Recruitment Assessments</h2>
          <p className="page-subtitle">
            Take assessments assigned to you by recruiters for shortlisted job applications.
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
          Loading your assigned assessments...
        </div>
      ) : assessments.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <CheckSquare size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>No Assessments Assigned Yet</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '6px', maxWidth: '440px', margin: '6px auto 20px' }}>
            When a recruiter reviews your job application and moves your status to Shortlisted, your First Round MCQ assessment will appear here.
          </p>
          <Link to="/candidate/jobs" className="btn btn-primary">
            Explore Open Jobs
          </Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '20px' }}>
          {assessments.map((a) => (
            <div key={a.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <span className="badge badge-peach" style={{ fontSize: '0.72rem' }}>
                    First Round MCQ
                  </span>

                  {a.status === 'QUALIFIED' ? (
                    <span className="badge badge-success" style={{ gap: '4px' }}>
                      <CheckCircle2 size={12} /> Qualified
                    </span>
                  ) : a.status === 'NOT_QUALIFIED' ? (
                    <span className="badge badge-danger" style={{ gap: '4px' }}>
                      <XCircle size={12} /> Not Qualified
                    </span>
                  ) : a.status === 'IN_PROGRESS' ? (
                    <span className="badge badge-warning">In Progress</span>
                  ) : (
                    <span className="badge badge-blue">Pending</span>
                  )}
                </div>

                <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                  {a.assessment_title}
                </h3>

                <p style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--primary-powder-blue-dark)', marginTop: '4px' }}>
                  {a.job_title}
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                  <Building size={14} /> {a.company_name}
                </p>

                {/* Metrics */}
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '10px',
                  background: 'var(--surface-subtle)',
                  padding: '12px',
                  borderRadius: 'var(--radius-md)',
                  margin: '16px 0',
                  fontSize: '0.82rem'
                }}>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Questions:</span>{' '}
                    <strong>{a.total_questions}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Duration:</span>{' '}
                    <strong>{a.duration_minutes} Mins</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Total Marks:</span>{' '}
                    <strong>{a.total_marks}</strong>
                  </div>
                  <div>
                    <span style={{ color: 'var(--text-muted)' }}>Passing:</span>{' '}
                    <strong>{a.qualification_rule} {a.passing_marks} pts</strong>
                  </div>
                </div>

                {a.negative_marking && (
                  <p style={{ fontSize: '0.75rem', color: 'var(--danger)', fontWeight: 600 }}>
                    * Negative marking enabled: -{a.negative_marks} per incorrect answer
                  </p>
                )}
              </div>

              {/* Action Button */}
              <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-soft)' }}>
                {a.is_submitted || a.status === 'QUALIFIED' || a.status === 'NOT_QUALIFIED' ? (
                  <Link
                    to={`/candidate/assessments/${a.id}/result`}
                    className="btn btn-outline"
                    style={{ width: '100%', justifyContent: 'center' }}
                  >
                    <Award size={16} /> View Result Scorecard
                  </Link>
                ) : (
                  <Link
                    to={`/candidate/assessments/${a.id}/take`}
                    className="btn btn-primary"
                    style={{ width: '100%', justifyContent: 'center' }}
                  >
                    {a.status === 'IN_PROGRESS' ? 'Resume Assessment' : 'Start Assessment'}
                    <ArrowRight size={16} />
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  CheckCircle,
  XCircle,
  Clock,
  Award,
  ChevronRight,
  Briefcase,
  ArrowLeft,
  FileText,
} from 'lucide-react';
import api from '../../services/api';

export default function AssessmentResultView() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchResult();
  }, [assignmentId]);

  const fetchResult = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/candidate/first-round-assessments/${assignmentId}/result`);
      setResult(res.data);
    } catch (err) {
      alert(err.response?.data?.detail || 'Assessment result not available yet.');
      navigate('/candidate/first-round-assessments');
    } finally {
      setLoading(false);
    }
  };

  const formatSeconds = (sec) => {
    if (!sec) return 'N/A';
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s`;
  };

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading assessment evaluation scorecard...
      </div>
    );
  }

  if (!result) return null;

  const isQualified = result.is_qualified;

  return (
    <div style={{ maxWidth: '850px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Top Breadcrumb */}
      <div style={{ marginBottom: '18px' }}>
        <Link
          to="/candidate/first-round-assessments"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', color: 'var(--text-muted)' }}
        >
          <ArrowLeft size={16} /> Back to Assessments
        </Link>
      </div>

      {/* Main Scorecard Card */}
      <div className="card" style={{ padding: '36px', textAlign: 'center', overflow: 'hidden', position: 'relative' }}>
        {/* Qualification Verdict Banner */}
        <div
          style={{
            padding: '24px',
            borderRadius: '16px',
            background: isQualified ? '#ECFDF5' : '#FEF2F2',
            border: `2px solid ${isQualified ? '#6EE7B7' : '#FCA5A5'}`,
            marginBottom: '32px',
          }}
        >
          {isQualified ? (
            <CheckCircle size={54} color="#059669" style={{ margin: '0 auto 12px' }} />
          ) : (
            <XCircle size={54} color="#DC2626" style={{ margin: '0 auto 12px' }} />
          )}

          <h2
            style={{
              fontSize: '1.45rem',
              fontWeight: 800,
              color: isQualified ? '#065F46' : '#991B1B',
              marginBottom: '8px',
            }}
          >
            {result.qualification_message}
          </h2>

          <p style={{ fontSize: '0.9rem', color: isQualified ? '#047857' : '#B91C1C' }}>
            {isQualified
              ? 'Your score met the recruiter passing criteria. The hiring team has been notified.'
              : 'Thank you for your effort. We encourage you to explore other open roles that match your skillset.'}
          </p>
        </div>

        {/* Assessment & Job Meta */}
        <div style={{ marginBottom: '28px' }}>
          <span className="badge badge-blue" style={{ fontSize: '0.85rem' }}>
            {result.job_title}
          </span>
          <h3 style={{ fontSize: '1.25rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '8px' }}>
            {result.assessment_title}
          </h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Completed in {formatSeconds(result.time_taken_seconds)}
          </p>
        </div>

        {/* Score Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '28px' }}>
          <div className="card" style={{ padding: '16px', background: 'var(--bg-lavender-white)', textAlign: 'center' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {result.obtained_marks} / {result.total_marks}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Marks Obtained
            </div>
          </div>

          <div className="card" style={{ padding: '16px', background: 'var(--bg-lavender-white)', textAlign: 'center' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--primary-powder-blue-dark)' }}>
              {result.percentage.toFixed(1)}%
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Score Percentage
            </div>
          </div>

          <div className="card" style={{ padding: '16px', background: 'var(--bg-lavender-white)', textAlign: 'center' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)' }}>
              {result.qualification_rule} {result.passing_marks}
            </div>
            <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              Passing Threshold
            </div>
          </div>

          <div className="card" style={{ padding: '16px', background: isQualified ? '#ECFDF5' : '#FEF2F2', textAlign: 'center' }}>
            <div style={{ fontSize: '1.4rem', fontWeight: 800, color: isQualified ? '#059669' : '#DC2626' }}>
              {isQualified ? 'QUALIFIED' : 'NOT QUALIFIED'}
            </div>
            <div style={{ fontSize: '0.78rem', color: isQualified ? '#065F46' : '#991B1B', marginTop: '2px' }}>
              Final Verdict
            </div>
          </div>
        </div>

        {/* Questions Accuracy Breakdown */}
        <div
          style={{
            background: '#F8FAFC',
            borderRadius: '12px',
            padding: '20px',
            marginBottom: '32px',
            display: 'flex',
            justifyContent: 'space-around',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#059669' }}>
              {result.correct_count}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Correct Answers</div>
          </div>

          <div style={{ borderLeft: '1px solid var(--border-color)' }} />

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#DC2626' }}>
              {result.incorrect_count}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Incorrect Answers</div>
          </div>

          <div style={{ borderLeft: '1px solid var(--border-color)' }} />

          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, color: '#64748B' }}>
              {result.unanswered_count}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Unanswered</div>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'center', gap: '14px' }}>
          <button
            onClick={() => navigate('/candidate/applications')}
            className="btn btn-outline"
          >
            <Briefcase size={16} /> View My Applications
          </button>
          <button
            onClick={() => navigate('/candidate/dashboard')}
            className="btn btn-primary"
          >
            Go to Dashboard <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Briefcase,
  Building,
  MapPin,
  Calendar,
  CheckCircle,
  XCircle,
  Clock,
  ArrowRight,
  AlertCircle,
  Award,
} from 'lucide-react';
import api from '../../services/api';

export default function MyApplications() {
  const [applications, setApplications] = useState([]);
  const [assessments, setAssessments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApplications();
    fetchAssessments();
  }, []);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const res = await api.get('/applications');
      setApplications(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const fetchAssessments = async () => {
    try {
      const res = await api.get('/candidate/first-round-assessments');
      setAssessments(res.data || []);
    } catch (e) {}
  };

  const handleWithdraw = async (appId) => {
    if (!window.confirm('Are you sure you want to withdraw this application?')) return;
    try {
      await api.put(`/applications/${appId}/withdraw`);
      fetchApplications();
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to withdraw application');
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">My Job Applications</h2>
          <p className="page-subtitle">
            Track your application lifecycle status from submission through First Round Assessments and Interviews.
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
          Loading your applications...
        </div>
      ) : applications.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <Briefcase size={48} color="var(--primary-powder-blue)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>No Applications Found</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '6px', marginBottom: '20px' }}>
            You haven't submitted any job applications yet.
          </p>
          <Link to="/candidate/jobs" className="btn btn-primary">
            Browse Open Jobs
          </Link>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {applications.map((app) => {
            // Find related first-round assessment for this job if any
            const relAssessment = assessments.find((a) => a.job_id === app.job_id);

            return (
              <div key={app.id} className="card" style={{ padding: '22px 28px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                        {app.job?.title || 'Engineering Role'}
                      </h3>
                      <span
                        className={`badge ${
                          app.current_status === 'SHORTLISTED'
                            ? 'badge-peach'
                            : app.current_status === 'INTERVIEW'
                            ? 'badge-blue'
                            : app.current_status === 'SELECTED'
                            ? 'badge-success'
                            : app.current_status === 'REJECTED'
                            ? 'badge-danger'
                            : 'badge-blue'
                        }`}
                        style={{ fontSize: '0.78rem' }}
                      >
                        {app.current_status}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '6px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Building size={14} /> {app.job?.company?.name || 'Company'}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <MapPin size={14} /> {app.job?.location || 'Remote'}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Calendar size={14} /> Applied on {new Date(app.applied_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>

                  {/* Actions & Next Steps */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {app.current_status === 'SHORTLISTED' && relAssessment && (
                      relAssessment.is_submitted ? (
                        <Link
                          to={`/candidate/assessments/${relAssessment.id}/result`}
                          className="btn btn-outline"
                          style={{ fontSize: '0.82rem', padding: '6px 14px' }}
                        >
                          <Award size={14} /> View Test Scorecard
                        </Link>
                      ) : (
                        <Link
                          to={`/candidate/assessments/${relAssessment.id}/take`}
                          className="btn btn-primary"
                          style={{ fontSize: '0.82rem', padding: '6px 16px', fontWeight: 700 }}
                        >
                          Take Assessment <ArrowRight size={14} />
                        </Link>
                      )
                    )}

                    {app.current_status !== 'WITHDRAWN' && app.current_status !== 'REJECTED' && (
                      <button
                        onClick={() => handleWithdraw(app.id)}
                        className="btn btn-outline"
                        style={{ fontSize: '0.82rem', padding: '6px 12px', color: 'var(--danger)' }}
                      >
                        Withdraw
                      </button>
                    )}
                  </div>
                </div>

                {/* Shortlisted Highlight Notice */}
                {app.current_status === 'SHORTLISTED' && relAssessment && !relAssessment.is_submitted && (
                  <div
                    style={{
                      background: 'var(--bg-lavender-white)',
                      borderRadius: '8px',
                      padding: '12px 16px',
                      marginTop: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                    }}
                  >
                    <Clock size={16} color="var(--primary-powder-blue)" />
                    <span style={{ fontSize: '0.84rem', color: 'var(--text-primary)' }}>
                      You have been shortlisted! Please complete your <strong>First Round Technical Assessment ({relAssessment.duration_minutes} mins)</strong> to be considered for an interview.
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  RefreshCw,
  Video,
  AlertTriangle,
  Eye,
  Search,
  Clock,
  CheckCircle2,
  XCircle
} from 'lucide-react';
import api from '../../services/api';
import '../candidate/dashboard.css';

const card = 'ss-card';

export default function AdminProctoringHistory() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [selectedViolations, setSelectedViolations] = useState(null);
  const [violations, setViolations] = useState([]);
  const [loadingViolations, setLoadingViolations] = useState(false);

  const loadSessions = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await api.get('/admin/proctoring/sessions');
      setSessions(response.data.sessions || []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load proctoring history.'
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const filteredSessions = sessions.filter(item => {
    const value = search.toLowerCase();

    return (
      String(item.candidate_name || '').toLowerCase().includes(value) ||
      String(item.candidate_email || '').toLowerCase().includes(value) ||
      String(item.job_title || '').toLowerCase().includes(value) ||
      String(item.assignment_id).includes(value)
    );
  });

  const viewViolations = async item => {
    setSelectedViolations(item);
    setViolations([]);
    setLoadingViolations(true);

    try {
      const response = await api.get(
        `/admin/proctoring/assignments/${item.assignment_id}/violations`
      );

      setViolations(response.data.violations || []);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to load violation history.'
      );
    } finally {
      setLoadingViolations(false);
    }
  };

  const viewRecording = async item => {
    try {
      const response = await api.get(
        `/admin/proctoring/assignments/${item.assignment_id}/recording`,
        { responseType: 'blob' }
      );

      const url = URL.createObjectURL(response.data);
      const opened = window.open(url, '_blank');

      if (!opened) {
        const link = document.createElement('a');
        link.href = url;
        link.download = `proctoring-${item.assignment_id}`;
        link.click();
      }

      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to access recording.'
      );
    }
  };

  const getStatusClass = status => {
    if (status === 'COMPLETED' || status === 'SUBMITTED') return 'success';
    if (status === 'IN_PROGRESS' || status === 'RECORDING') return 'warning';
    if (status === 'NOT_STARTED' || status === 'PENDING') return 'neutral';
    return 'neutral';
  };

  return (
    <div className="ss-dashboard">
      <div className="ss-heading">
        <div>
          <h1>Proctoring History</h1>
          <p>Monitor candidate assessment sessions and proctoring activity.</p>
        </div>

        <button className="ss-primary-btn" onClick={loadSessions}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {error && <div className="ss-notice">{error}</div>}

      <div className="ss-kpis">
        <div className={`${card} ss-kpi`}>
          <span className="ss-kpi-icon"><ShieldCheck size={19} /></span>
          <div>
            <b>{sessions.length}</b>
            <small>Assigned Assessments</small>
          </div>
        </div>

        <div className={`${card} ss-kpi`}>
          <span className="ss-kpi-icon"><Video size={19} /></span>
          <div>
            <b>{sessions.filter(s => s.recording_available).length}</b>
            <small>Recordings Available</small>
          </div>
        </div>

        <div className={`${card} ss-kpi`}>
          <span className="ss-kpi-icon amber"><AlertTriangle size={19} /></span>
          <div>
            <b>{sessions.filter(s => s.is_flagged_for_review).length}</b>
            <small>Flagged for Review</small>
          </div>
        </div>
      </div>

      <section className={card}>
        <div className="ss-card-head">
          <h2>Candidate Sessions</h2>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Search size={16} />
            <input
              className="ss-search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search candidate, job or ID"
            />
          </div>
        </div>

        {loading ? (
          <div className="ss-loading">Loading proctoring sessions...</div>
        ) : (
          <div className="ss-table-wrap">
            <table className="ss-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Job</th>
                  <th>Assessment</th>
                  <th>Proctoring</th>
                  <th>Warnings</th>
                  <th>Recording</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {filteredSessions.map(item => (
                  <tr key={item.assignment_id}>
                    <td>
                      <b>{item.candidate_name || 'Unknown'}</b>
                      <small>{item.candidate_email || '—'}</small>
                      <small>Assignment #{item.assignment_id}</small>
                    </td>

                    <td>{item.job_title || '—'}</td>

                    <td>
                      <span className={`ss-status-pill ${getStatusClass(item.assessment_status)}`}>
                        {item.assessment_status}
                      </span>
                    </td>

                    <td>
                      <span className={`ss-status-pill ${getStatusClass(item.session_status)}`}>
                        {item.session_status}
                      </span>
                      {item.is_flagged_for_review && (
                        <small style={{ color: '#d97706' }}>
                          <AlertTriangle size={12} /> Flagged
                        </small>
                      )}
                    </td>

                    <td>{item.warning_count}</td>

                    <td>
                      {item.recording_available ? (
                        <span><CheckCircle2 size={14} /> Available</span>
                      ) : (
                        <span><XCircle size={14} /> Unavailable</span>
                      )}
                    </td>

                    <td>
                      <div className="ss-action-group">
                        <button
                          className="ss-small-btn"
                          disabled={item.session_status === 'NOT_STARTED'}
                          onClick={() => viewViolations(item)}
                        >
                          <Eye size={13} /> History
                        </button>

                        {item.recording_available && (
                          <button
                            className="ss-small-btn"
                            onClick={() => viewRecording(item)}
                          >
                            <Video size={13} /> Recording
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {!filteredSessions.length && (
              <div className="ss-empty">No assessment sessions found.</div>
            )}
          </div>
        )}
      </section>

      {selectedViolations && (
        <section className={card} style={{ marginTop: 20 }}>
          <div className="ss-card-head">
            <div>
              <h2>Violation History</h2>
              <small>
                {selectedViolations.candidate_name} · Assignment #{selectedViolations.assignment_id}
              </small>
            </div>

            <button
              className="ss-small-btn"
              onClick={() => setSelectedViolations(null)}
            >
              Close
            </button>
          </div>

          {loadingViolations ? (
            <div className="ss-loading">Loading violation history...</div>
          ) : (
            <div className="ss-table-wrap">
              <table className="ss-table">
                <thead>
                  <tr>
                    <th>Violation</th>
                    <th>Confidence</th>
                    <th>Details</th>
                    <th>Detected At</th>
                  </tr>
                </thead>

                <tbody>
                  {violations.map(item => (
                    <tr key={item.id}>
                      <td><b>{item.violation_type}</b></td>
                      <td>{item.confidence ?? '—'}</td>
                      <td>{JSON.stringify(item.details || {})}</td>
                      <td>
                        {item.detected_at
                          ? new Date(item.detected_at).toLocaleString()
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {!violations.length && (
                <div className="ss-empty">No violations recorded.</div>
              )}
            </div>
          )}
        </section>
      )}
    </div>
  );
}

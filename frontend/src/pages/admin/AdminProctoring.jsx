import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ShieldCheck,
  RefreshCw,
  Video,
  AlertTriangle,
  Eye,
  Search,
  CheckCircle2,
  XCircle,
  X,
  Clock,
  Activity,
  FileWarning,
  Play,
  Download,
} from 'lucide-react';
import api from '../../services/api';
import '../candidate/dashboard.css';
import './AdminProctoring.css';

const card = 'ss-card';

async function getApiErrorMessage(error, fallback) {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      if (typeof parsed.detail === 'string') return parsed.detail;
    } catch {
      // The server may return a non-JSON error body.
    }
  }
  if (typeof data?.detail === 'string') return data.detail;
  return error?.message || fallback;
}

export default function AdminProctoringHistory() {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sessionsError, setSessionsError] = useState('');
  const [search, setSearch] = useState('');
  const [selectedViolations, setSelectedViolations] = useState(null);
  const [violations, setViolations] = useState([]);
  const [loadingViolations, setLoadingViolations] = useState(false);
  const [violationsError, setViolationsError] = useState('');
  const [recordingId, setRecordingId] = useState(null);
  const [recordingUrl, setRecordingUrl] = useState('');
  const [recordingName, setRecordingName] = useState('');
  const [recordingError, setRecordingError] = useState('');
  const recordingUrlRef = useRef('');

  const closeRecording = useCallback(() => {
    if (recordingUrlRef.current) {
      URL.revokeObjectURL(recordingUrlRef.current);
      recordingUrlRef.current = '';
    }
    setRecordingUrl('');
    setRecordingName('');
  }, []);

  useEffect(() => () => {
    if (recordingUrlRef.current) URL.revokeObjectURL(recordingUrlRef.current);
  }, []);

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setSessionsError('');
    try {
      const response = await api.get('/admin/proctoring/sessions');
      setSessions(Array.isArray(response.data?.sessions) ? response.data.sessions : []);
    } catch (error) {
      setSessionsError(await getApiErrorMessage(error, 'Unable to load proctoring history.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const filteredSessions = useMemo(() => {
    const value = search.trim().toLowerCase();
    if (!value) return sessions;
    return sessions.filter(item =>
      String(item.candidate_name || '').toLowerCase().includes(value) ||
      String(item.candidate_email || '').toLowerCase().includes(value) ||
      String(item.job_title || '').toLowerCase().includes(value) ||
      String(item.assignment_id || '').includes(value)
    );
  }, [sessions, search]);

  const stats = useMemo(() => ({
    total: sessions.length,
    recordings: sessions.filter(item => item.recording_available).length,
    flagged: sessions.filter(item => item.is_flagged_for_review).length,
    warnings: sessions.reduce((total, item) => total + Number(item.warning_count || 0), 0),
  }), [sessions]);

  const viewViolations = async item => {
    setSelectedViolations(item);
    setViolations([]);
    setViolationsError('');
    setLoadingViolations(true);
    try {
      const response = await api.get(
        `/admin/proctoring/assignments/${item.assignment_id}/violations`
      );
      setViolations(Array.isArray(response.data?.violations) ? response.data.violations : []);
    } catch (error) {
      setViolationsError(await getApiErrorMessage(error, 'Unable to load violation history.'));
    } finally {
      setLoadingViolations(false);
    }
  };

  const viewRecording = async item => {
    setRecordingId(item.assignment_id);
    setRecordingError('');
    closeRecording();
    try {
      const response = await api.get(
        `/admin/proctoring/assignments/${item.assignment_id}/recording`,
        { responseType: 'blob' }
      );
      if (!response.data || response.data.size === 0) {
        throw new Error('The recording file is empty or unavailable.');
      }
      const url = URL.createObjectURL(response.data);
      recordingUrlRef.current = url;
      setRecordingUrl(url);
      setRecordingName(`Assessment recording — ${item.candidate_name || `Assignment ${item.assignment_id}`}`);
    } catch (error) {
      setRecordingError(await getApiErrorMessage(error, 'Unable to access recording.'));
    } finally {
      setRecordingId(null);
    }
  };

  const downloadRecording = () => {
    if (!recordingUrl) return;
    const link = document.createElement('a');
    link.href = recordingUrl;
    link.download = `proctoring-${selectedViolations?.assignment_id || recordingId || 'recording'}.webm`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  const getStatusClass = status => {
    const value = String(status || '').toUpperCase();
    if (['COMPLETED', 'SUBMITTED', 'APPROVED'].includes(value)) return 'success';
    if (['IN_PROGRESS', 'RECORDING', 'READY', 'ACTIVE'].includes(value)) return 'warning';
    return 'neutral';
  };

  const formatDate = value => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
  };

  return (
    <div className="ss-dashboard ss-proctoring-page">
      <div className="ss-heading">
        <div>
          <div className="ss-admin-eyebrow">
            <ShieldCheck size={13} />
            ADMINISTRATION / SECURITY
          </div>
          <h1>Proctoring History</h1>
          <p>Monitor candidate assessment sessions, recording availability and security violations.</p>
        </div>
        <button className="ss-primary-btn" onClick={loadSessions} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'ss-spin' : ''} />
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {(sessionsError || recordingError) && (
        <div className="ss-notice ss-proctoring-notice" role="alert">
          <AlertTriangle size={16} />
          <span>{sessionsError || recordingError}</span>
          <button onClick={() => { setSessionsError(''); setRecordingError(''); }} aria-label="Dismiss error">
            <X size={15} />
          </button>
        </div>
      )}

      <div className="ss-proctoring-kpis">
        <div className={`${card} ss-proctoring-stat`}>
          <div className="ss-proctoring-stat-top">
            <span className="ss-proctoring-stat-icon lime"><ShieldCheck size={19} /></span>
            <span className="ss-proctoring-stat-label">TOTAL SESSIONS</span>
          </div>
          <strong>{stats.total}</strong>
          <small>Assigned assessments</small>
        </div>
        <div className={`${card} ss-proctoring-stat`}>
          <div className="ss-proctoring-stat-top">
            <span className="ss-proctoring-stat-icon dark"><Video size={19} /></span>
            <span className="ss-proctoring-stat-label">RECORDINGS</span>
          </div>
          <strong>{stats.recordings}</strong>
          <small>Available for review</small>
        </div>
        <div className={`${card} ss-proctoring-stat`}>
          <div className="ss-proctoring-stat-top">
            <span className="ss-proctoring-stat-icon amber"><AlertTriangle size={19} /></span>
            <span className="ss-proctoring-stat-label">FLAGGED CASES</span>
          </div>
          <strong>{stats.flagged}</strong>
          <small>Require admin attention</small>
        </div>
        <div className={`${card} ss-proctoring-stat`}>
          <div className="ss-proctoring-stat-top">
            <span className="ss-proctoring-stat-icon blue"><Activity size={19} /></span>
            <span className="ss-proctoring-stat-label">TOTAL WARNINGS</span>
          </div>
          <strong>{stats.warnings}</strong>
          <small>Across all sessions</small>
        </div>
      </div>

      <section className={`${card} ss-proctoring-table-card`}>
        <div className="ss-proctoring-section-head">
          <div>
            <div className="ss-proctoring-title-row">
              <h2>Candidate Sessions</h2>
              <span className="ss-proctoring-count">{filteredSessions.length} records</span>
            </div>
            <p>Review assessment status and candidate proctoring activity.</p>
          </div>
          <div className="ss-proctoring-search">
            <Search size={16} />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Search candidate, job or ID"
              aria-label="Search candidate sessions"
            />
            {search && (
              <button onClick={() => setSearch('')} aria-label="Clear search"><X size={14} /></button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="ss-proctoring-loading">
            <RefreshCw size={20} className="ss-spin" />
            <span>Loading proctoring sessions...</span>
          </div>
        ) : (
          <div className="ss-table-wrap">
            <table className="ss-table ss-proctoring-table">
              <thead>
                <tr>
                  <th>Candidate</th><th>Job</th><th>Assessment</th><th>Proctoring</th>
                  <th>Warnings</th><th>Recording</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredSessions.map(item => (
                  <tr key={item.assignment_id}>
                    <td>
                      <div className="ss-proctoring-candidate">
                        <span className="ss-proctoring-avatar">
                          {(item.candidate_name || 'U').trim().charAt(0).toUpperCase()}
                        </span>
                        <div>
                          <b>{item.candidate_name || 'Unknown'}</b>
                          <small>{item.candidate_email || '—'}</small>
                          <small>Assignment #{item.assignment_id}</small>
                        </div>
                      </div>
                    </td>
                    <td className="ss-proctoring-job">{item.job_title || '—'}</td>
                    <td>
                      <span className={`ss-status-pill ${getStatusClass(item.assessment_status)}`}>
                        {item.assessment_status || '—'}
                      </span>
                    </td>
                    <td>
                      <div className="ss-proctoring-status-cell">
                        <span className={`ss-status-pill ${getStatusClass(item.session_status)}`}>
                          {item.session_status || '—'}
                        </span>
                        {item.is_flagged_for_review && (
                          <span className="ss-proctoring-flag"><AlertTriangle size={11} />Flagged</span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`ss-warning-count ${Number(item.warning_count) > 0 ? 'has-warnings' : ''}`}>
                        {item.warning_count ?? 0}
                      </span>
                    </td>
                    <td>
                      {item.recording_available ? (
                        <span className="ss-recording-state available"><CheckCircle2 size={14} />Available</span>
                      ) : (
                        <span className="ss-recording-state unavailable"><XCircle size={14} />Unavailable</span>
                      )}
                    </td>
                    <td>
                      <div className="ss-action-group ss-proctoring-actions">
                        <button
                          className="ss-small-btn"
                          disabled={!item.session_status || item.session_status === 'NOT_STARTED'}
                          onClick={() => viewViolations(item)}
                        >
                          <Eye size={13} />History
                        </button>
                        {item.recording_available && (
                          <button
                            className="ss-small-btn ss-recording-btn"
                            disabled={recordingId === item.assignment_id}
                            onClick={() => viewRecording(item)}
                          >
                            {recordingId === item.assignment_id
                              ? <RefreshCw size={13} className="ss-spin" />
                              : <Video size={13} />}
                            Recording
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!filteredSessions.length && (
              <div className="ss-proctoring-empty">
                <div className="ss-proctoring-empty-icon"><FileWarning size={24} /></div>
                <b>No assessment sessions found</b>
                <p>{search
                  ? 'Try another candidate name, job title or assignment ID.'
                  : 'There are no proctoring sessions available yet.'}</p>
              </div>
            )}
          </div>
        )}
      </section>

      {selectedViolations && (
        <section className={`${card} ss-proctoring-violations`}>
          <div className="ss-proctoring-section-head">
            <div>
              <div className="ss-proctoring-title-row">
                <h2>Violation History</h2>
                <span className="ss-proctoring-count">{violations.length} records</span>
              </div>
              <p>{selectedViolations.candidate_name || 'Candidate'} · Assignment #{selectedViolations.assignment_id}</p>
            </div>
            <button className="ss-proctoring-close" onClick={() => {
              setSelectedViolations(null);
              setViolations([]);
              setViolationsError('');
            }}>
              <X size={15} />Close
            </button>
          </div>
          {violationsError && (
            <div className="ss-notice ss-proctoring-notice" role="alert">
              <AlertTriangle size={16} /><span>{violationsError}</span>
            </div>
          )}
          {loadingViolations ? (
            <div className="ss-proctoring-loading"><RefreshCw size={20} className="ss-spin" /><span>Loading violation history...</span></div>
          ) : (
            <div className="ss-table-wrap">
              <table className="ss-table ss-proctoring-table">
                <thead><tr><th>Violation</th><th>Confidence</th><th>Details</th><th>Detected At</th></tr></thead>
                <tbody>
                  {violations.map(item => (
                    <tr key={item.id}>
                      <td><span className="ss-violation-type"><AlertTriangle size={13} />{item.violation_type}</span></td>
                      <td>{item.confidence ?? '—'}</td>
                      <td className="ss-violation-details">{JSON.stringify(item.details || {})}</td>
                      <td><span className="ss-violation-date"><Clock size={13} />{formatDate(item.detected_at)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!violations.length && !violationsError && (
                <div className="ss-proctoring-empty compact">
                  <CheckCircle2 size={22} /><b>No violations recorded</b>
                  <p>No violation history is available for this session.</p>
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <div className="ss-proctoring-security-note">
        <ShieldCheck size={16} />
        <span>Recording access is restricted to authorized administrators. Access is handled through the protected backend endpoint.</span>
      </div>

      {recordingUrl && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Proctoring recording viewer"
          onClick={event => { if (event.target === event.currentTarget) closeRecording(); }}
          style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,.78)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
        >
          <div style={{ width: 'min(100%, 1000px)', background: '#111', color: '#fff', borderRadius: 14, padding: 16, boxShadow: '0 20px 70px rgba(0,0,0,.45)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
              <strong>{recordingName}</strong>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="ss-small-btn" onClick={downloadRecording}><Download size={14} />Download</button>
                <button className="ss-proctoring-close" onClick={closeRecording}><X size={15} />Close</button>
              </div>
            </div>
            <video src={recordingUrl} controls autoPlay playsInline style={{ display: 'block', width: '100%', maxHeight: '75vh', background: '#000', borderRadius: 8 }}>
              Your browser does not support video playback.
            </video>
            <small style={{ display: 'block', marginTop: 10, color: '#bbb' }}>This recording is private and is available only through your authorized admin session.</small>
          </div>
        </div>
      )}
    </div>
  );
}

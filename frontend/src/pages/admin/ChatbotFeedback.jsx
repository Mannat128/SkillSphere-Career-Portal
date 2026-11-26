import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw, MessageSquareWarning } from 'lucide-react';
import api from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import { loadUnansweredQuestions } from './unansweredQuestionsApi';
import '../candidate/dashboard.css';
import './AdminDashboard.css';

const cardStyle = { background: '#fff', border: '1px solid #e5e9df', borderRadius: 12, padding: 16 };

export default function ChatbotFeedback() {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState(null);
  const [feedback, setFeedback] = useState([]);
  const [unanswered, setUnanswered] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [historyOpen, setHistoryOpen] = useState({});
  const [moderationHistory, setModerationHistory] = useState({});
  const [historyLoading, setHistoryLoading] = useState({});
  const [historyErrors, setHistoryErrors] = useState({});
  const [filter, setFilter] = useState({ status: '', role: '', language: '', priority: '', category: '', search: '' });
  const [unansweredFilter, setUnansweredFilter] = useState({ language: '', min_frequency: '1' });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const params = Object.fromEntries(Object.entries(filter).filter(([, value]) => value));
      const results = await Promise.allSettled([
        api.get('/assistant/admin/analytics'),
        api.get('/assistant/admin/feedback', { params }),
        loadUnansweredQuestions(api, unansweredFilter),
        api.get('/assistant/admin/knowledge-suggestions', { params: { status: 'PENDING' } }),
      ]);
      const failures = [];
      const labels = ['analytics', 'feedback', 'unanswered questions', 'knowledge suggestions'];
      results.forEach((result, index) => {
        if (result.status === 'rejected') {
          failures.push(`${labels[index]}: ${result.reason?.response?.data?.detail || result.reason?.message || 'request failed'}`);
          return;
        }
        if (index === 0) setAnalytics(result.value.data);
        if (index === 1) setFeedback(result.value.data || []);
        if (index === 2) setUnanswered(result.value || []);
        if (index === 3) setSuggestions(result.value.data || []);
      });
      setError(failures.length ? `Some assistant feedback data could not be loaded. ${failures.join('; ')}` : '');
    } catch (err) { setError(err.response?.data?.detail || err.message || 'Unable to load assistant feedback.'); }
    finally { setBusy(false); }
  }, [filter, unansweredFilter]);

  useEffect(() => { load(); }, [load]);

  async function update(id, patch) {
    try {
      await api.patch(`/assistant/admin/feedback/${id}`, patch);
      await load();
      setModerationHistory((previous) => { const next = { ...previous }; delete next[id]; return next; });
      if (historyOpen[id]) await loadModerationHistory(id);
    }
    catch (err) { setError(err.response?.data?.detail || 'Unable to update feedback.'); }
  }

  async function loadModerationHistory(id) {
    setHistoryLoading((previous) => ({ ...previous, [id]: true }));
    setHistoryErrors((previous) => ({ ...previous, [id]: '' }));
    try {
      const { data } = await api.get(`/assistant/admin/feedback/${id}/history`);
      setModerationHistory((previous) => ({ ...previous, [id]: Array.isArray(data) ? data : [] }));
    } catch (err) {
      setHistoryErrors((previous) => ({ ...previous, [id]: err.response?.data?.detail || 'Unable to load moderation history.' }));
    } finally { setHistoryLoading((previous) => ({ ...previous, [id]: false })); }
  }

  function toggleModerationHistory(id) {
    const opening = !historyOpen[id];
    setHistoryOpen((previous) => ({ ...previous, [id]: opening }));
    if (opening && !Object.prototype.hasOwnProperty.call(moderationHistory, id)) loadModerationHistory(id);
  }

  async function reviewSuggestion(id, status) {
    try {
      await api.post(`/assistant/admin/knowledge-suggestions/${id}/review`, { status });
      await load();
    } catch (err) { setError(err.response?.data?.detail || 'Unable to review knowledge suggestion.'); }
  }

  async function draftSuggestion(row) {
    const response = window.prompt('Enter a verified answer for review. It will remain inactive until approved:');
    if (!response?.trim()) return;
    try {
      await api.post('/assistant/admin/knowledge-suggestions', {
        unanswered_id: row.id, intent_id: row.best_intent || 'reviewed_faq',
        language: ['en', 'hi', 'hinglish', 'hi_latn', 'pa', 'pa_latn'].includes(row.language) ? row.language : 'en',
        question: row.question, response: response.trim(),
      });
      await load();
    } catch (err) { setError(err.response?.data?.detail || 'Unable to save suggestion.'); }
  }

  const cards = analytics ? [
    ['Total feedback', analytics.total_feedback], ['Helpful', analytics.helpful_count],
    ['Not helpful', analytics.negative_count], ['Helpful rate', `${analytics.helpful_percentage}%`],
    ['Open issues', analytics.statuses?.OPEN || 0], ['In progress', analytics.statuses?.IN_PROGRESS || 0],
    ['Resolved', analytics.statuses?.RESOLVED || 0], ['Unanswered questions', analytics.unanswered_questions],
  ] : [];

  return <main className="ss-dashboard">
    <div className="ss-heading"><div><div className="ss-pending-eyebrow"><MessageSquareWarning size={14} /> ASSISTANT QUALITY</div><h1>Chatbot Feedback &amp; Analytics</h1><p>Review ratings and redacted unanswered-question aggregates. Private chat transcripts are not shown.</p></div><button className="ss-primary-btn" onClick={load}><RefreshCw size={14} /> Refresh</button></div>
    {error && <div role="alert" className="ss-notice">{error}</div>}
    <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 12, margin: '20px 0' }}>
      {cards.map(([label, value]) => <article key={label} style={cardStyle}><small>{label}</small><div style={{ fontSize: 26, fontWeight: 800, marginTop: 8 }}>{value}</div></article>)}
    </section>
    {analytics && <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))', gap: 12, marginBottom: 18 }}>
      {[
        ['Most reported intents', analytics.by_intent?.map((row) => [row.intent, row.count])],
        ['Feedback by language', analytics.by_language?.map((row) => [row.language, row.count])],
        ['Feedback by role', analytics.by_role?.map((row) => [row.role, row.count])],
        ['Reported categories', analytics.by_category?.map((row) => [row.category, row.count])],
      ].map(([title, rows]) => <article key={title} style={cardStyle}><h3 style={{ marginTop: 0 }}>{title}</h3>{rows?.length ? rows.slice(0, 8).map(([label, count]) => <p key={label} style={{ display: 'flex', justifyContent: 'space-between', margin: '8px 0' }}><span>{label}</span><strong>{count}</strong></p>) : <small>No data yet.</small>}</article>)}
    </section>}
    <section style={{ ...cardStyle, marginBottom: 18 }}>
      <h2 style={{ marginTop: 0 }}>Feedback records</h2>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        <input aria-label="Search feedback comments" placeholder="Search comments" value={filter.search} onChange={(e) => setFilter({ ...filter, search: e.target.value })} />
        <select aria-label="Filter status" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}><option value="">All statuses</option>{['OPEN','IN_PROGRESS','RESOLVED','CLOSED'].map((x) => <option key={x}>{x}</option>)}</select>
        <select aria-label="Filter category" value={filter.category} onChange={(e) => setFilter({ ...filter, category: e.target.value })}><option value="">All categories</option>{['incorrect','incomplete','not_understood','technical','language','other'].map((x) => <option key={x}>{x}</option>)}</select>
        <select aria-label="Filter role" value={filter.role} onChange={(e) => setFilter({ ...filter, role: e.target.value })}><option value="">All roles</option>{['candidate','recruiter','visitor','admin'].map((x) => <option key={x}>{x}</option>)}</select>
        <select aria-label="Filter language" value={filter.language} onChange={(e) => setFilter({ ...filter, language: e.target.value })}><option value="">All languages</option>{['en','hi','hinglish','hi_latn','pa','pa_latn'].map((x) => <option key={x}>{x}</option>)}</select>
        <select aria-label="Filter priority" value={filter.priority} onChange={(e) => setFilter({ ...filter, priority: e.target.value })}><option value="">All priorities</option>{['LOW','MEDIUM','HIGH','CRITICAL'].map((x) => <option key={x}>{x}</option>)}</select>
      </div>
      {busy ? <p>Loading feedback…</p> : feedback.length ? <div style={{ display: 'grid', gap: 12 }}>{feedback.map((row) => <article key={row.id} style={{ borderTop: '1px solid #e8eae2', paddingTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}><strong>{row.rating === 'helpful' ? 'Helpful' : row.category || 'Not helpful'} · {row.user_role} · {row.language}</strong><time>{new Date(row.created_at).toLocaleString()}</time></div>
        <p>{row.comment || 'No comment provided.'}</p><small>Matched intent: {row.matched_intent || 'unknown'} · confidence {Number(row.match_score).toFixed(2)}</small>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
          <select aria-label={`Status for feedback ${row.id}`} value={row.status} onChange={(e) => update(row.id, { status: e.target.value })}>{['OPEN','IN_PROGRESS','RESOLVED','CLOSED'].map((x) => <option key={x}>{x}</option>)}</select>
          <select aria-label={`Priority for feedback ${row.id}`} value={row.priority} onChange={(e) => update(row.id, { priority: e.target.value })}>{['LOW','MEDIUM','HIGH','CRITICAL'].map((x) => <option key={x}>{x}</option>)}</select>
          <button type="button" onClick={() => update(row.id, { assigned_admin_id: user?.id })} disabled={!user?.id || row.assigned_admin_id === user.id}>{row.assigned_admin_id === user?.id ? 'Assigned to me' : 'Assign to me'}</button>
          <button type="button" onClick={() => { const notes = window.prompt('Internal admin note', row.admin_notes || ''); if (notes !== null) update(row.id, { admin_notes: notes }); }}>Edit internal note</button>
          <button type="button" onClick={() => toggleModerationHistory(row.id)} aria-expanded={Boolean(historyOpen[row.id])}>
            {historyOpen[row.id] ? 'Hide moderation history' : 'Show moderation history'}
          </button>
        </div>{row.admin_notes && <p><small>Internal note: {row.admin_notes}</small></p>}
        {historyOpen[row.id] && <section aria-label={`Moderation history for feedback ${row.id}`} style={{ marginTop: 12, padding: 12, borderRadius: 8, background: '#f8faf6' }}>
          <h3 style={{ margin: '0 0 10px' }}>Moderation history</h3>
          {historyLoading[row.id] ? <p>Loading moderation history…</p>
            : historyErrors[row.id] ? <p role="alert">{historyErrors[row.id]}</p>
              : moderationHistory[row.id]?.length ? <div style={{ display: 'grid', gap: 10 }}>
                {moderationHistory[row.id].map((entry) => <article key={entry.id} style={{ borderTop: '1px solid #e1e6dd', paddingTop: 8 }}>
                  <p style={{ margin: '0 0 6px' }}><strong>Admin #{entry.admin_id ?? 'unknown'}</strong> · <time>{new Date(entry.created_at).toLocaleString()}</time></p>
                  {entry.changes?.status && <p>Status: {entry.changes.status.from ?? '—'} → {entry.changes.status.to ?? '—'}</p>}
                  {entry.changes?.priority && <p>Priority: {entry.changes.priority.from ?? '—'} → {entry.changes.priority.to ?? '—'}</p>}
                  {entry.changes?.assigned_admin_id && <p>Assignment: {entry.changes.assigned_admin_id.from ? `Admin #${entry.changes.assigned_admin_id.from}` : 'Unassigned'} → {entry.changes.assigned_admin_id.to ? `Admin #${entry.changes.assigned_admin_id.to}` : 'Unassigned'}</p>}
                  {entry.changes?.admin_notes && <div><strong>{['RESOLVED', 'CLOSED'].includes(entry.changes?.status?.to) ? 'Resolution notes' : 'Admin notes'}</strong>
                    {entry.changes.admin_notes.from && <p>Previous: {entry.changes.admin_notes.from}</p>}
                    {entry.changes.admin_notes.to && <p>New: {entry.changes.admin_notes.to}</p>}
                  </div>}
                </article>)}
              </div> : <p>No moderation actions have been recorded for this issue.</p>}
        </section>}
      </article>)}</div> : <p>No feedback matches these filters.</p>}
    </section>
    <section style={cardStyle}><h2 style={{ marginTop: 0 }}>Frequently unanswered questions</h2><p>Queries are normalized, email/phone/password-like values are redacted, and no transcript is exposed.</p>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        <select aria-label="Filter unanswered language" value={unansweredFilter.language} onChange={(e) => setUnansweredFilter({ ...unansweredFilter, language: e.target.value })}>
          <option value="">All languages</option>{[['en','English'],['hi','Hindi'],['hinglish','Hinglish'],['hi_latn','Roman Hindi'],['pa','Punjabi'],['pa_latn','Roman Punjabi']].map(([value,label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <label>Minimum occurrences <input aria-label="Minimum unanswered frequency" type="number" min="1" step="1" value={unansweredFilter.min_frequency} onChange={(e) => setUnansweredFilter({ ...unansweredFilter, min_frequency: e.target.value })} /></label>
      </div>
      {unanswered.length ? <div style={{ display: 'grid', gap: 10 }}>{unanswered.map((row) => <article key={row.id} style={{ borderTop: '1px solid #e8eae2', paddingTop: 9 }}><strong>{row.question}</strong><p>{row.language} · {row.frequency} occurrence(s) · confidence {Number(row.match_score).toFixed(2)}</p><button type="button" onClick={() => draftSuggestion(row)}>Draft verified answer for review</button></article>)}</div> : <p>No unanswered questions have been recorded.</p>}
    </section>
    <section style={{ ...cardStyle, marginTop: 18 }}><h2 style={{ marginTop: 0 }}>Pending knowledge suggestions</h2><p>Approved answers become available to matching local assistant queries after review.</p>
      {suggestions.length ? <div style={{ display: 'grid', gap: 12 }}>{suggestions.map((row) => <article key={row.id} style={{ borderTop: '1px solid #e8eae2', paddingTop: 10 }}><strong>{row.question}</strong><p>{row.language} · {row.intent_id}</p><p>{row.response}</p>{row.route && <small>Internal route: {row.route}</small>}<div style={{ display: 'flex', gap: 8, marginTop: 10 }}><button type="button" onClick={() => reviewSuggestion(row.id, 'APPROVED')}>Approve</button><button type="button" onClick={() => reviewSuggestion(row.id, 'REJECTED')}>Reject</button></div></article>)}</div> : <p>No pending knowledge suggestions.</p>}
    </section>
  </main>;
}

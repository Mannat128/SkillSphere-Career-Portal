import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Check, History, LifeBuoy, LoaderCircle, MessageCircle, Pencil, Send, Sparkles, ThumbsDown, ThumbsUp, Trash2, User, X } from 'lucide-react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import assistantAvatar from '../assets/sphera-avatar.png';
import './SkillSphereAssistant.css';

const GUEST_SESSION_KEY = 'skillsphere_assistant_guest_session';
const WELCOME_TEXT = 'Hello! I’m the SkillSphere Assistant. Ask about the platform, your account, or verified SkillSphere jobs.';
const WELCOME_SUGGESTIONS = {
  en: {
    visitor: ['About SkillSphere', 'Browse jobs', 'Create account', 'Contact support'],
    candidate: ['Find jobs', 'Check my applications', 'Build my resume', 'Assessment rules'],
    recruiter: ['Manage my jobs', 'Review applicants', 'Configure assessments', 'Question Bank'],
    admin: ['Review assistant feedback', 'Review unanswered questions', 'Manage support tickets', 'Admin dashboard'],
  },
  hi: {
    visitor: ['SkillSphere के बारे में', 'नौकरियाँ देखें', 'खाता बनाएँ', 'सहायता संपर्क'],
    candidate: ['नौकरियाँ खोजें', 'मेरे आवेदन देखें', 'Resume Builder', 'Assessment नियम'],
    recruiter: ['मेरी jobs', 'Applicants देखें', 'Assessment सेट करें', 'Question Bank'],
    admin: ['Assistant feedback देखें', 'अनुत्तरित प्रश्न देखें', 'Support tickets प्रबंधित करें', 'Admin dashboard'],
  },
  hinglish: {
    visitor: ['SkillSphere ke baare mein', 'Jobs dekhein', 'Account banayein', 'Support se contact karein'],
    candidate: ['Jobs dekhein', 'Meri applications', 'Resume Builder', 'Assessment rules'],
    recruiter: ['Meri jobs', 'Applicants kaise dekhein?', 'Assessment configure karein', 'Question Bank'],
    admin: ['Assistant feedback review karein', 'Unanswered questions dekhein', 'Support tickets manage karein', 'Admin dashboard'],
  },
  pa: {
    visitor: ['SkillSphere ਬਾਰੇ', 'ਨੌਕਰੀਆਂ ਵੇਖੋ', 'ਖਾਤਾ ਬਣਾਓ', 'ਮਦਦ ਨਾਲ ਸੰਪਰਕ'],
    candidate: ['ਨੌਕਰੀਆਂ ਲੱਭੋ', 'ਮੇਰੀਆਂ ਅਰਜ਼ੀਆਂ', 'Resume Builder', 'Assessment ਨਿਯਮ'],
    recruiter: ['ਮੇਰੀਆਂ jobs', 'Applicants ਵੇਖੋ', 'Assessment ਸੈੱਟ ਕਰੋ', 'Question Bank'],
    admin: ['Assistant feedback ਵੇਖੋ', 'ਬਿਨਾਂ ਜਵਾਬ ਵਾਲੇ ਸਵਾਲ ਵੇਖੋ', 'Support tickets ਸੰਭਾਲੋ', 'Admin dashboard'],
  },
  pa_latn: {
    visitor: ['SkillSphere bare', 'Jobs vekho', 'Account banao', 'Support naal sampark'],
    candidate: ['Jobs labho', 'Merian applications', 'Resume Builder', 'Assessment rules'],
    recruiter: ['Merian jobs', 'Applicants vekho', 'Assessment set karo', 'Question Bank'],
    admin: ['Assistant feedback vekho', 'Unanswered questions vekho', 'Support tickets sambhalo', 'Admin dashboard'],
  },
};
const LANGUAGES = [
  ['auto', 'Auto detect'], ['en', 'English'], ['hi', 'हिन्दी'],
  ['hinglish', 'Hinglish'], ['pa', 'ਪੰਜਾਬੀ'], ['pa_latn', 'Roman Punjabi'],
];
const CATEGORIES = [
  ['incorrect', 'Incorrect information'], ['incomplete', 'Incomplete answer'],
  ['not_understood', 'Did not understand'], ['technical', 'Technical issue'],
  ['language', 'Language problem'], ['other', 'Other'],
];
const roleName = (user) => String(user?.role || 'VISITOR').toUpperCase();
const welcomeMessage = (user, language = 'auto') => {
  const role = roleName(user).toLowerCase();
  const localized = WELCOME_SUGGESTIONS[language] || WELCOME_SUGGESTIONS.en;
  return {
    role: 'assistant',
    isWelcome: true,
    text: WELCOME_TEXT,
    suggestions: localized[role] || localized.visitor,
  };
};

export default function SkillSphereAssistant() {
  const { user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const scrollRef = useRef(null);
  const conversationViewRef = useRef(0);
  const sendRequestRef = useRef(0);
  const identity = user?.id ? `${user.id}:${roleName(user)}` : 'visitor';
  const [open, setOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [messages, setMessages] = useState(() => [welcomeMessage(user)]);
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [language, setLanguage] = useState('auto');
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [guestSession, setGuestSession] = useState('');
  const [feedback, setFeedback] = useState({});
  const [feedbackForm, setFeedbackForm] = useState(null);
  const [ticketForm, setTicketForm] = useState(null);
  const [ticketBusy, setTicketBusy] = useState(false);
  const [ticketSuccess, setTicketSuccess] = useState('');

  const headers = { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(!user && guestSession ? { 'X-Assistant-Session': guestSession } : {}) };
  const supportPath = ({ CANDIDATE: '/candidate/support', RECRUITER: '/recruiter/support', ADMIN: '/admin/support' })[roleName(user)] || '/login';

  useEffect(() => {
    if (authLoading) return;
    setMessages([welcomeMessage(user, language)]); setConversationId(null); setHistoryOpen(false);
    setConversations([]); setError('');
    setFeedback({}); setFeedbackForm(null); setTicketForm(null);
    if (!user) {
      let existing = sessionStorage.getItem(GUEST_SESSION_KEY);
      if (!existing) {
        api.post('/assistant/guest-session').then(({ data }) => {
          existing = data.session_token;
          sessionStorage.setItem(GUEST_SESSION_KEY, existing);
          setGuestSession(existing);
        }).catch(() => setError('A private guest session could not be started. Reload and try again.'));
      } else setGuestSession(existing);
    } else setGuestSession('');
  }, [identity, authLoading]);

  useEffect(() => {
    if (!open || authLoading || (!user && !guestSession)) return undefined;
    let active = true;
    api.get('/assistant/conversations', { headers })
      .then(({ data }) => { if (active) setConversations(data || []); })
      .catch((err) => { if (active) setError(err.response?.data?.detail || 'Unable to load chat history.'); });
    return () => { active = false; };
  }, [open, user?.id, user?.role, token, guestSession, authLoading]);

  useLayoutEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy, ticketForm, feedbackForm]);

  const switchConversationView = () => {
    conversationViewRef.current += 1;
    sendRequestRef.current += 1;
    setBusy(false);
  };

  const startNewChat = () => {
    switchConversationView();
    setConversationId(null); setMessages([welcomeMessage(user, language)]); setHistoryOpen(false);
    setError(''); setTicketSuccess(''); setFeedbackForm(null); setTicketForm(null);
  };

  const sendMessage = async (value = input) => {
    const text = String(value || '').trim();
    if (!text || busy) return;
    if (!user && !guestSession) { setError('Starting your private visitor session. Please try again in a moment.'); return; }
    if (text.length > 2000) { setError('Messages can contain up to 2,000 characters.'); return; }
    const requestView = conversationViewRef.current;
    const requestId = ++sendRequestRef.current;
    setMessages((previous) => [...previous, { role: 'user', text, createdAt: new Date().toISOString(), clientId: `user-${requestId}` }]);
    setInput(''); setError(''); setTicketSuccess(''); setBusy(true);
    try {
      const { data } = await api.post('/assistant/chat', {
        message: text,
        conversation_id: conversationId || undefined,
        language,
        context_path: location.pathname,
      }, { headers });
      if (requestView !== conversationViewRef.current) return;
      setConversationId(data.conversation_id);
      setMessages((previous) => [...previous, {
        role: 'assistant', text: data.reply, actions: data.actions || [],
        suggestions: data.suggestions || [], intent: data.intent,
        confidence: data.confidence, language: data.language,
        messageId: data.message_id, ticketSuggestion: data.ticket_suggestion,
        createdAt: data.created_at, clientId: `assistant-${requestId}`,
      }]);
      setConversations((previous) => [
        { id: data.conversation_id, title: text.slice(0, 117), updated_at: new Date().toISOString() },
        ...previous.filter((item) => item.id !== data.conversation_id),
      ]);
    } catch (err) {
      if (requestView === conversationViewRef.current) {
        setError(err.response?.data?.detail || 'Could not reach the SkillSphere Assistant. Your message was not saved. Please try again.');
      }
    } finally {
      if (requestId === sendRequestRef.current) setBusy(false);
    }
  };

  const openConversation = async (item) => {
    switchConversationView();
    const requestView = conversationViewRef.current;
    setError('');
    try {
      const { data } = await api.get(`/assistant/conversations/${item.id}`, { headers });
      if (requestView !== conversationViewRef.current) return;
      setConversationId(data.id); setLanguage(data.language || 'auto');
      const loaded = (data.messages || []).map((row) => ({ role: row.role, text: row.text, messageId: row.role === 'assistant' ? row.id : undefined, clientId: `history-${row.id}`, intent: row.intent, confidence: row.confidence, language: row.language, createdAt: row.created_at }));
      setMessages(loaded.length ? loaded : [welcomeMessage(user, language)]);
      setHistoryOpen(false);
    } catch (err) { if (requestView === conversationViewRef.current) setError(err.response?.data?.detail || 'Unable to open this conversation.'); }
  };

  const renameConversation = async (item) => {
    const title = window.prompt('Rename conversation', item.title || '');
    if (!title?.trim()) return;
    try {
      const { data } = await api.patch(`/assistant/conversations/${item.id}`, { title: title.trim() }, { headers });
      setConversations((previous) => previous.map((row) => row.id === item.id ? data : row));
    } catch (err) { setError(err.response?.data?.detail || 'Unable to rename this conversation.'); }
  };

  const deleteConversation = async (item) => {
    if (!window.confirm('Delete this conversation and its messages?')) return;
    try {
      await api.delete(`/assistant/conversations/${item.id}`, { headers });
      setConversations((previous) => previous.filter((row) => row.id !== item.id));
      if (conversationId === item.id) startNewChat();
    } catch (err) { setError(err.response?.data?.detail || 'Unable to delete this conversation.'); }
  };

  const clearChat = async () => {
    if (!window.confirm('Clear this conversation? This permanently removes its messages.')) return;
    if (conversationId) {
      try { await api.delete(`/assistant/conversations/${conversationId}`, { headers }); }
      catch (err) { setError(err.response?.data?.detail || 'Unable to clear this conversation.'); return; }
      setConversations((previous) => previous.filter((item) => item.id !== conversationId));
    }
    startNewChat();
  };

  const submitFeedback = async (message, rating, category = null, comment = '') => {
    try {
      await api.post('/assistant/feedback', {
        message_id: message.messageId, rating, category, comment: comment.trim() || undefined,
      }, { headers });
      setFeedback((previous) => ({ ...previous, [message.messageId]: rating }));
      setFeedbackForm(null);
    } catch (err) { setError(err.response?.data?.detail || 'Unable to submit feedback.'); }
  };

  const clearGuestSession = async () => {
    if (!window.confirm('Clear all conversations saved in this guest session?')) return;
    try {
      await api.delete('/assistant/guest-session', { headers });
      const { data } = await api.post('/assistant/guest-session');
      sessionStorage.setItem(GUEST_SESSION_KEY, data.session_token);
      setGuestSession(data.session_token);
      setConversations([]); setConversationId(null); setMessages([welcomeMessage(user, language)]);
      setHistoryOpen(false); setError('');
    } catch (err) { setError(err.response?.data?.detail || 'Unable to clear guest history.'); }
  };

  const submitTicket = async (event) => {
    event.preventDefault();
    const form = ticketForm;
    if (!user) { setError('Sign in to create a support ticket.'); navigate('/login'); return; }
    if (!form?.subject.trim() || !form?.description.trim()) { setError('Add a subject and describe the issue before submitting.'); return; }
    setTicketBusy(true); setError('');
    try {
      const body = new FormData();
      body.append('subject', form.subject.trim()); body.append('description', form.description.trim());
      body.append('category', form.category); body.append('priority', 'MEDIUM');
      const { data } = await api.post('/support-tickets', body);
      setTicketSuccess(`Ticket ${data.ticket.ticket_number} was created.`);
      setTicketForm(null);
    } catch (err) { setError(err.response?.data?.detail || 'Unable to create the support ticket.'); }
    finally { setTicketBusy(false); }
  };

  const handleAction = (path) => {
    setOpen(false);
    navigate(path);
  };

  return <div className="assistant-widget" data-testid="assistant-chat-widget">
    {open && <section className="assistant-window" aria-label="SkillSphere Assistant">
      <header className="assistant-header">
        <div className="assistant-header-info">
          <div className="assistant-logo-container"><img src={assistantAvatar} alt="SkillSphere Assistant" className="assistant-header-avatar" /><span className="assistant-online-dot" /></div>
          <div><h3 className="assistant-title">SkillSphere Assistant</h3><p className="assistant-subtitle">Platform &amp; Company Help</p></div>
        </div>
        <div className="assistant-header-actions">
          <button type="button" onClick={() => setHistoryOpen((value) => !value)} title="Conversation history" aria-label="Conversation history"><History size={16} /></button>
          <button type="button" onClick={startNewChat} title="New chat" aria-label="New chat"><Sparkles size={16} /></button>
          <button type="button" onClick={clearChat} title="Clear current chat" aria-label="Clear current chat"><Trash2 size={15} /></button>
          <button type="button" onClick={() => setOpen(false)} title="Close" aria-label="Close chat"><X size={19} /></button>
        </div>
      </header>

      <div className="assistant-language-row">
        <label htmlFor="assistant-language">Reply language</label>
        <select id="assistant-language" value={language} onChange={(event) => {
          const nextLanguage = event.target.value;
          setLanguage(nextLanguage);
          setMessages((previous) => previous.length === 1 && previous[0].isWelcome
            ? [welcomeMessage(user, nextLanguage)] : previous);
        }}>
          {LANGUAGES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
      </div>

      {historyOpen ? <div className="assistant-history-panel">
        <div className="assistant-history-heading"><strong>Your conversations</strong><button type="button" onClick={() => setHistoryOpen(false)} aria-label="Close conversation history"><X size={16} /></button></div>
        {!user && <button className="assistant-clear-session" type="button" onClick={clearGuestSession}>Clear guest session history</button>}
        <div className="assistant-history-list">
          {conversations.map((item) => <div className="assistant-history-item" key={item.id}>
            <button className="assistant-history-open" type="button" onClick={() => openConversation(item)}><strong>{item.title || 'New chat'}</strong><time>{item.updated_at ? new Date(item.updated_at).toLocaleString() : ''}</time></button>
            <button type="button" title="Rename" aria-label="Rename conversation" onClick={() => renameConversation(item)}><Pencil size={14} /></button>
            <button type="button" title="Delete" aria-label="Delete conversation" onClick={() => deleteConversation(item)}><Trash2 size={14} /></button>
          </div>)}
          {!conversations.length && <p className="assistant-history-empty">No saved conversations yet.</p>}
        </div>
      </div> : <>
        <div className="assistant-messages" ref={scrollRef}>
          {messages.length === 1 && <div className="assistant-welcome-banner"><img src={assistantAvatar} alt="" className="assistant-welcome-img" /><div className="assistant-welcome-text"><h4>SkillSphere Assistant</h4><p>Verified platform guidance, in your language.</p><span className="assistant-welcome-tagline">Ask. Explore. Grow.</span></div></div>}
          {messages.map((item, index) => <React.Fragment key={item.clientId || item.messageId || `message-${index}`}>
            <div className={`assistant-message-row ${item.role === 'user' ? 'assistant-user-row' : 'assistant-ai-row'}`}>
              {item.role === 'assistant' && <div className="assistant-message-avatar"><img src={assistantAvatar} alt="Assistant" className="assistant-avatar-icon" /></div>}
              <div className={`assistant-message ${item.role === 'user' ? 'assistant-user-message' : 'assistant-ai-message'}`}>
                <div>{item.text}</div>
                {item.createdAt && <time className="assistant-message-time">{new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</time>}
                {!!item.actions?.length && <div className="assistant-route-actions">{item.actions.map((action) => <button key={action.path} type="button" onClick={() => handleAction(action.path)}>{action.label}</button>)}</div>}
                {item.role === 'assistant' && item.messageId && <div className="assistant-feedback-actions" aria-label="Rate this answer">
                  {feedback[item.messageId] ? <span><Check size={13} /> Feedback received</span> : <>
                    <button type="button" title="Helpful" aria-label="Helpful answer" onClick={() => submitFeedback(item, 'helpful')}><ThumbsUp size={14} /></button>
                    <button type="button" title="Not helpful" aria-label="Not helpful answer" onClick={() => setFeedbackForm(item)}><ThumbsDown size={14} /></button>
                  </>}
                </div>}
              </div>
              {item.role === 'user' && <div className="assistant-message-avatar assistant-user-avatar"><User size={15} /></div>}
            </div>
            {feedbackForm?.messageId === item.messageId && <FeedbackForm onCancel={() => setFeedbackForm(null)} onSubmit={(category, comment) => submitFeedback(item, 'not_helpful', category, comment)} />}
            {item.role === 'assistant' && item.ticketSuggestion && !ticketForm && <div className="assistant-ticket-suggestion"><div><LifeBuoy size={18} /><div><strong>Need official support?</strong><p>Review your request before sending it to the Support Center.</p></div></div><button type="button" onClick={() => user ? setTicketForm({ subject: '', description: '', category: 'TECHNICAL' }) : navigate('/login')}>Create support ticket</button></div>}
            {!!item.suggestions?.length && index === messages.length - 1 && !busy && <div className="assistant-suggested-prompts">{item.suggestions.slice(0, 4).map((prompt) => <button type="button" key={prompt} className="assistant-prompt-btn" onClick={() => sendMessage(prompt)}>{prompt}</button>)}</div>}
          </React.Fragment>)}
          {busy && <div className="assistant-message-row assistant-ai-row"><div className="assistant-message-avatar"><img src={assistantAvatar} alt="" className="assistant-avatar-icon" /></div><div className="assistant-typing"><span /><span /><span /></div></div>}
          {ticketSuccess && <div className="assistant-ticket-success">{ticketSuccess}</div>}
          {ticketForm && <form className="assistant-ticket-form" onSubmit={submitTicket}>
            <div className="assistant-ticket-form-heading"><strong>Review support request</strong></div>
            <label htmlFor="assistant-ticket-subject">Subject</label><input id="assistant-ticket-subject" maxLength={200} value={ticketForm.subject} onChange={(event) => setTicketForm({ ...ticketForm, subject: event.target.value })} required />
            <label htmlFor="assistant-ticket-description">Description</label><textarea id="assistant-ticket-description" maxLength={5000} value={ticketForm.description} onChange={(event) => setTicketForm({ ...ticketForm, description: event.target.value })} required />
            <label htmlFor="assistant-ticket-category">Category</label><select id="assistant-ticket-category" value={ticketForm.category} onChange={(event) => setTicketForm({ ...ticketForm, category: event.target.value })}>{['TECHNICAL', 'ACCOUNT', 'JOB_APPLICATION', 'ASSESSMENT', 'OTHER'].map((value) => <option key={value} value={value}>{value.replace('_', ' ')}</option>)}</select>
            <div className="assistant-ticket-actions"><button type="button" onClick={() => setTicketForm(null)}>Cancel</button><button type="submit" disabled={ticketBusy}>{ticketBusy ? 'Submitting…' : 'Submit ticket'}</button></div>
          </form>}
          {error && <div role="alert" className="assistant-error">{error}</div>}
        </div>
        <form className="assistant-input-area" onSubmit={(event) => { event.preventDefault(); sendMessage(); }}>
          <div className="assistant-input-wrapper"><input value={input} onChange={(event) => setInput(event.target.value)} maxLength={2000} placeholder="Ask the SkillSphere Assistant…" aria-label="Message SkillSphere Assistant" data-testid="assistant-input" onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }} /><button type="submit" disabled={!input.trim() || busy || (!user && !guestSession)} aria-label="Send message" data-testid="assistant-send-btn">{busy ? <LoaderCircle size={18} className="assistant-spin" /> : <Send size={18} />}</button></div>
          <p className="assistant-disclaimer">Don’t share passwords, OTPs, API keys, financial information, or other secrets. Chat text is stored with common sensitive details redacted, but automatic detection can miss information.</p>
        </form>
      </>}
    </section>}
    <button type="button" className={`assistant-floating-button ${open ? 'assistant-floating-active' : ''}`} onClick={() => setOpen((value) => !value)} aria-label={open ? 'Close SkillSphere Assistant' : 'Open SkillSphere Assistant'} data-testid="assistant-launcher-btn">
      {open ? <X size={22} /> : <><img src={assistantAvatar} alt="" className="assistant-floating-avatar" /><span className="assistant-floating-label">Ask SkillSphere</span><MessageCircle size={17} /></>}
    </button>
  </div>;
}

function FeedbackForm({ onCancel, onSubmit }) {
  const [category, setCategory] = useState('not_understood');
  const [comment, setComment] = useState('');
  return <form className="assistant-feedback-form" onSubmit={(event) => { event.preventDefault(); onSubmit(category, comment); }}>
    <label>What went wrong?<select value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
    <label>Optional comment<textarea value={comment} maxLength={1000} onChange={(event) => setComment(event.target.value)} /></label>
    <div><button type="button" onClick={onCancel}>Cancel</button><button type="submit">Send feedback</button></div>
  </form>;
}

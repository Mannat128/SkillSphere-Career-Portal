import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bot,
  X,
  Send,
  MessageCircle,
  LifeBuoy,
  Sparkles,
  User,
  LoaderCircle,
  ArrowLeft,
  CheckCircle2,
} from 'lucide-react';

import api from '../services/api';
import { useAuth } from '../context/AuthContext';

const INITIAL_MESSAGE = {
  role: 'assistant',
  text: "Hi! I'm Sphera AI, your SkillSphere support assistant. How can I help you today?",
};

const QUICK_PROMPTS = [
  'How can I improve my profile?',
  'How do assessments work?',
  'How do I apply for jobs?',
  'I am facing a technical issue',
];

export default function SpheraChatWidget() {
  const { user, token, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [creatingTicket, setCreatingTicket] = useState(false);
  const [error, setError] = useState('');
  const [ticketSuggestion, setTicketSuggestion] = useState(false);
  const [showTicketForm, setShowTicketForm] = useState(false);
  const [ticketSuccess, setTicketSuccess] = useState('');

  const [ticketForm, setTicketForm] = useState({
    subject: '',
    description: '',
    category: 'TECHNICAL',
    priority: 'MEDIUM',
  });

  const [messages, setMessages] = useState([INITIAL_MESSAGE]);

  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
    });
  }, [messages, sending, isOpen, showTicketForm]);

  if (authLoading || !token || !user) {
    return null;
  }

  const supportPath = {
    CANDIDATE: '/candidate/support',
    RECRUITER: '/recruiter/support',
    ADMIN: '/admin/support',
  }[String(user.role || '').toUpperCase()] || '/';

  const sendMessage = async (messageText) => {
    const message = String(messageText || '').trim();

    if (!message || sending) return;

    const previousMessages = messages;

    const conversationHistory = previousMessages
      .filter((item) => item.role === 'user' || item.role === 'assistant')
      .slice(-12)
      .map((item) => ({
        role: item.role,
        text: item.text,
      }));

    setMessages((previous) => [
      ...previous,
      { role: 'user', text: message },
    ]);

    setInput('');
    setError('');
    setTicketSuggestion(false);
    setTicketSuccess('');
    setSending(true);

    try {
      const response = await api.post('/sphera-ai/chat', {
        message,
        history: conversationHistory,
      });

      const reply = response.data?.reply;

      if (!reply) {
        throw new Error('Sphera AI returned an empty response.');
      }

      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          text: reply,
        },
      ]);

      const shouldSuggestTicket =
        response.data?.ticket_suggestion === true;

      setTicketSuggestion(shouldSuggestTicket);

      if (shouldSuggestTicket) {
        setTicketForm((previous) => ({
          ...previous,
          subject: message.length > 100
            ? `${message.slice(0, 97)}...`
            : message,
          description: message,
        }));
      }
    } catch (err) {
      const errorMessage =
        err.response?.data?.detail ||
        err.message ||
        'Unable to connect to Sphera AI. Please try again.';

      setError(errorMessage);

      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          text: 'Sorry, I could not process your request right now. Please try again or contact our support team.',
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleSendMessage = (event) => {
    event.preventDefault();
    sendMessage(input);
  };

  const handleQuickPrompt = (prompt) => {
    sendMessage(prompt);
  };

  const createSupportTicket = async (event) => {
    event.preventDefault();

    if (
      !ticketForm.subject.trim() ||
      !ticketForm.description.trim()
    ) {
      setError('Please complete the ticket subject and description.');
      return;
    }

    try {
      setCreatingTicket(true);
      setError('');

      const formData = new FormData();

      formData.append('subject', ticketForm.subject.trim());
      formData.append('description', ticketForm.description.trim());
      formData.append('category', ticketForm.category);
      formData.append('priority', ticketForm.priority);

      const response = await api.post(
        '/support-tickets',
        formData
      );

      const ticketNumber =
        response.data?.ticket?.ticket_number || '';

      setTicketSuccess(
        ticketNumber
          ? `Your support ticket ${ticketNumber} has been created successfully.`
          : 'Your support ticket has been created successfully.'
      );

      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          text: ticketNumber
            ? `Your support ticket ${ticketNumber} has been created successfully. Our support team can now review your issue.`
            : 'Your support ticket has been created successfully. Our support team can now review your issue.',
        },
      ]);

      setTicketSuggestion(false);
      setShowTicketForm(false);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        'Unable to create the support ticket. Please try again.'
      );
    } finally {
      setCreatingTicket(false);
    }
  };

  const openSupport = () => {
    setIsOpen(false);
    navigate(supportPath);
  };

  const startNewChat = () => {
    setMessages([INITIAL_MESSAGE]);
    setInput('');
    setError('');
    setTicketSuggestion(false);
    setShowTicketForm(false);
    setTicketSuccess('');
    setTicketForm({
      subject: '',
      description: '',
      category: 'TECHNICAL',
      priority: 'MEDIUM',
    });
  };

  return (
    <div className="sphera-widget">

      {isOpen && (
        <section className="sphera-window">

          {/* HEADER */}
          <header className="sphera-header">
            <div className="sphera-header-info">
              <div className="sphera-logo">
                <Bot size={23} />
                <span className="sphera-online-dot" />
              </div>

              <div>
                <h3>Sphera AI</h3>
                <p>
                  <span className="sphera-status-dot" />
                  SkillSphere Support Assistant
                </p>
              </div>
            </div>

            <div className="sphera-header-actions">
              <button
                type="button"
                onClick={startNewChat}
                title="Start new chat"
                aria-label="Start new chat"
              >
                <Sparkles size={17} />
              </button>

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                title="Close chat"
                aria-label="Close chat"
              >
                <X size={20} />
              </button>
            </div>
          </header>

          {/* MESSAGES */}
          <div className="sphera-messages">

            <div className="sphera-date-label">
              <span>SKILLSPHERE AI SUPPORT</span>
            </div>

            {messages.map((item, index) => (
              <div
                key={index}
                className={`sphera-message-row ${
                  item.role === 'user'
                    ? 'sphera-user-row'
                    : 'sphera-ai-row'
                }`}
              >
                {item.role === 'assistant' && (
                  <div className="sphera-message-avatar">
                    <Bot size={16} />
                  </div>
                )}

                <div
                  className={`sphera-message ${
                    item.role === 'user'
                      ? 'sphera-user-message'
                      : 'sphera-ai-message'
                  }`}
                >
                  {item.text}
                </div>

                {item.role === 'user' && (
                  <div className="sphera-message-avatar sphera-user-avatar">
                    <User size={16} />
                  </div>
                )}
              </div>
            ))}

            {/* QUICK PROMPTS */}
            {messages.length === 1 && !sending && !showTicketForm && (
              <div
                style={{
                  padding: '8px 12px 12px 42px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 600,
                    opacity: 0.7,
                    marginBottom: '2px',
                  }}
                >
                  QUICK HELP
                </div>

                {QUICK_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => handleQuickPrompt(prompt)}
                    disabled={sending}
                    style={{
                      textAlign: 'left',
                      padding: '9px 12px',
                      borderRadius: '12px',
                      border: '1px solid rgba(128,128,128,0.25)',
                      background: 'transparent',
                      cursor: 'pointer',
                      fontSize: '12px',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            {/* TYPING INDICATOR */}
            {sending && (
              <div className="sphera-message-row sphera-ai-row">
                <div className="sphera-message-avatar">
                  <Bot size={16} />
                </div>

                <div className="sphera-typing">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}

            {/* TICKET SUGGESTION */}
            {ticketSuggestion && !sending && !showTicketForm && (
              <div className="sphera-ticket-suggestion">
                <div>
                  <LifeBuoy size={19} />

                  <div>
                    <strong>Need more help?</strong>
                    <p>
                      You can create a support ticket for our team.
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setError('');
                    setShowTicketForm(true);
                  }}
                >
                  Create Support Ticket
                </button>
              </div>
            )}

            {/* TICKET CREATION FORM */}
            {showTicketForm && (
              <form
                className="sphera-ticket-form"
                onSubmit={createSupportTicket}
              >
                <div className="sphera-ticket-form-heading">
                  <button
                    type="button"
                    onClick={() => setShowTicketForm(false)}
                    aria-label="Back to chat"
                  >
                    <ArrowLeft size={17} />
                  </button>

                  <div>
                    <strong>Create Support Ticket</strong>
                    <p>Review the details before submitting.</p>
                  </div>
                </div>

                <label htmlFor="sphera-ticket-subject">
                  Subject
                </label>

                <input
                  id="sphera-ticket-subject"
                  type="text"
                  maxLength={200}
                  required
                  value={ticketForm.subject}
                  onChange={(event) => setTicketForm({
                    ...ticketForm,
                    subject: event.target.value,
                  })}
                  placeholder="Enter issue subject"
                />

                <label htmlFor="sphera-ticket-description">
                  Description
                </label>

                <textarea
                  id="sphera-ticket-description"
                  required
                  maxLength={5000}
                  rows={4}
                  value={ticketForm.description}
                  onChange={(event) => setTicketForm({
                    ...ticketForm,
                    description: event.target.value,
                  })}
                  placeholder="Describe your issue"
                />

                <label htmlFor="sphera-ticket-category">
                  Category
                </label>

                <select
                  id="sphera-ticket-category"
                  value={ticketForm.category}
                  onChange={(event) => setTicketForm({
                    ...ticketForm,
                    category: event.target.value,
                  })}
                >
                  <option value="ACCOUNT">Account</option>
                  <option value="JOB_APPLICATION">Job Application</option>
                  <option value="ASSESSMENT">Assessment</option>
                  <option value="TECHNICAL">Technical</option>
                  <option value="PAYMENT">Payment</option>
                  <option value="OTHER">Other</option>
                </select>

                <label htmlFor="sphera-ticket-priority">
                  Priority
                </label>

                <select
                  id="sphera-ticket-priority"
                  value={ticketForm.priority}
                  onChange={(event) => setTicketForm({
                    ...ticketForm,
                    priority: event.target.value,
                  })}
                >
                  <option value="LOW">Low</option>
                  <option value="MEDIUM">Medium</option>
                  <option value="HIGH">High</option>
                  <option value="URGENT">Urgent</option>
                </select>

                <button
                  type="submit"
                  disabled={creatingTicket}
                  className="sphera-ticket-submit"
                >
                  {creatingTicket ? (
                    <>
                      <LoaderCircle size={17} className="sphera-spin" />
                      Creating Ticket...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={17} />
                      Confirm & Create Ticket
                    </>
                  )}
                </button>
              </form>
            )}

            {/* SUCCESS MESSAGE */}
            {ticketSuccess && (
              <div className="sphera-ticket-success">
                <CheckCircle2 size={17} />
                {ticketSuccess}

                <button
                  type="button"
                  onClick={openSupport}
                >
                  Open Support Center
                </button>
              </div>
            )}

            {/* ERROR */}
            {error && (
              <div className="sphera-error">
                {error}
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* CHAT INPUT */}
          {!showTicketForm && (
            <form
              className="sphera-input-area"
              onSubmit={handleSendMessage}
            >
              <div className="sphera-input-wrapper">
                <input
                  type="text"
                  placeholder="Ask Sphera anything..."
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  maxLength={2000}
                  disabled={sending}
                />

                <button
                  type="submit"
                  disabled={!input.trim() || sending}
                  aria-label="Send message"
                >
                  {sending ? (
                    <LoaderCircle
                      size={19}
                      className="sphera-spin"
                    />
                  ) : (
                    <Send size={18} />
                  )}
                </button>
              </div>

              <p className="sphera-disclaimer">
                Sphera AI can make mistakes. Never share passwords or OTPs.
              </p>
            </form>
          )}
        </section>
      )}

      {/* FLOATING BUTTON */}
      <button
        type="button"
        className={`sphera-floating-button ${
          isOpen ? 'sphera-floating-active' : ''
        }`}
        onClick={() => setIsOpen((previous) => !previous)}
        aria-label="Open Sphera AI"
      >
        {isOpen ? (
          <X size={24} />
        ) : (
          <>
            <MessageCircle size={23} />
            <span className="sphera-floating-label">
              Ask Sphera AI
            </span>
          </>
        )}
      </button>
    </div>
  );
}
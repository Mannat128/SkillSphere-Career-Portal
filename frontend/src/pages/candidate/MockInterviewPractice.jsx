import React, { useState, useEffect } from 'react';
import {
  Sparkles,
  Bot,
  MessageSquare,
  Award,
  ChevronRight,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  History,
  Send,
  ThumbsUp,
  Target,
  ArrowLeft
} from 'lucide-react';
import api from '../../services/api';

const POPULAR_TECHS = ['Python', 'React', 'SQL', 'FastAPI', 'JavaScript'];

export default function MockInterviewPractice() {
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(true);

  // New session form
  const [roleOrTech, setRoleOrTech] = useState('Python');
  const [customTech, setCustomTech] = useState('');
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState('Medium');
  const [startingSession, setStartingSession] = useState(false);

  // Active Session state
  const [activeSession, setActiveSession] = useState(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [candidateAnswer, setCandidateAnswer] = useState('');
  const [submittingAnswer, setSubmittingAnswer] = useState(false);
  const [currentFeedback, setCurrentFeedback] = useState(null);
  const [answersMap, setAnswersMap] = useState({}); // questionId -> feedback/answer record

  const [activeTab, setActiveTab] = useState('practice'); // 'practice' | 'history'
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    fetchSessions();
  }, []);

  const fetchSessions = async () => {
    setLoadingSessions(true);
    try {
      const res = await api.get('/interviews/mock/sessions');
      setSessions(res.data || []);
    } catch (err) {
      console.error('Failed to load past mock sessions', err);
    } finally {
      setLoadingSessions(false);
    }
  };

  const handleStartSession = async (e) => {
    e?.preventDefault();
    const targetTech = roleOrTech === 'Other' ? customTech.trim() : roleOrTech;
    if (!targetTech) {
      setErrorMsg('Please specify a technology or job role for the interview.');
      return;
    }

    setStartingSession(true);
    setErrorMsg('');
    try {
      const res = await api.post('/interviews/mock/start', {
        role_or_tech: targetTech,
        num_questions: parseInt(numQuestions, 10),
        difficulty: difficulty
      });

      setActiveSession(res.data);
      setCurrentQuestionIndex(0);
      setCandidateAnswer('');
      setCurrentFeedback(null);
      setAnswersMap({});
    } catch (err) {
      console.error('Failed to start interview session', err);
      const detail = err.response?.data?.detail || 'Could not start mock interview session.';
      setErrorMsg(detail);
    } finally {
      setStartingSession(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!candidateAnswer.trim()) {
      setErrorMsg('Please write an answer before submitting.');
      return;
    }

    const currentQ = activeSession.questions[currentQuestionIndex];
    if (!currentQ) return;

    setSubmittingAnswer(true);
    setErrorMsg('');
    try {
      const res = await api.post(`/interviews/mock/questions/${currentQ.id}/answer`, {
        answer_text: candidateAnswer.trim()
      });

      const feedbackData = res.data;
      setCurrentFeedback(feedbackData);
      setAnswersMap((prev) => ({
        ...prev,
        [currentQ.id]: {
          answer: candidateAnswer.trim(),
          feedback: feedbackData
        }
      }));
    } catch (err) {
      console.error('Failed to evaluate answer', err);
      setErrorMsg('Failed to submit answer. Please try again.');
    } finally {
      setSubmittingAnswer(false);
    }
  };

  const handleNextQuestion = () => {
    if (currentQuestionIndex < (activeSession.questions?.length || 0) - 1) {
      const nextIdx = currentQuestionIndex + 1;
      setCurrentQuestionIndex(nextIdx);
      const nextQ = activeSession.questions[nextIdx];
      const prevAnswerRecord = answersMap[nextQ.id];
      if (prevAnswerRecord) {
        setCandidateAnswer(prevAnswerRecord.answer);
        setCurrentFeedback(prevAnswerRecord.feedback);
      } else {
        setCandidateAnswer('');
        setCurrentFeedback(null);
      }
    } else {
      // Completed session
      fetchSessions();
    }
  };

  const handleFinishSession = () => {
    fetchSessions();
    setActiveSession(null);
    setCurrentQuestionIndex(0);
    setCurrentFeedback(null);
    setCandidateAnswer('');
    setActiveTab('history');
  };

  return (
    <div>
      {/* Page Header */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <h2 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sparkles size={28} color="var(--primary-powder-blue)" />
            AI Mock Interview Practice
          </h2>
          <p className="page-subtitle">
            Sharpen your technical interview skills with targeted questions by technology, practice structuring your responses, and review comprehensive feedback.
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px' }}>
        <button
          onClick={() => setActiveTab('practice')}
          className={`btn ${activeTab === 'practice' ? 'btn-primary' : 'btn-outline'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
        >
          <Bot size={16} /> Practice Session
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`btn ${activeTab === 'history' ? 'btn-primary' : 'btn-outline'}`}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
        >
          <History size={16} /> Session History ({sessions.length})
        </button>
      </div>

      {errorMsg && (
        <div style={{
          background: 'var(--danger-bg)',
          color: 'var(--danger)',
          padding: '12px 16px',
          borderRadius: 'var(--radius-md)',
          marginBottom: '20px',
          fontSize: '0.9rem',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          border: '1px solid rgba(239, 68, 68, 0.2)'
        }}>
          <AlertCircle size={18} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* TAB 1: PRACTICE */}
      {activeTab === 'practice' && (
        <>
          {!activeSession ? (
            /* Configure New Session Card */
            <div className="card" style={{ maxWidth: '800px', margin: '0 auto', padding: '32px' }}>
              <div style={{ textAlign: 'center', marginBottom: '28px' }}>
                <div style={{
                  width: '56px',
                  height: '56px',
                  borderRadius: '16px',
                  background: 'linear-gradient(135deg, var(--primary-powder-blue) 0%, var(--accent-peach) 100%)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 16px',
                  color: '#0F172A'
                }}>
                  <Bot size={30} />
                </div>
                <h3 style={{ fontSize: '1.35rem', fontWeight: 800 }}>Start an AI Mock Interview</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.92rem', maxWidth: '460px', margin: '8px auto 0' }}>
                  Select your technology stack, target difficulty, and the number of questions to begin your interactive practice interview.
                </p>
              </div>

              <form onSubmit={handleStartSession}>
                {/* Tech Pills */}
                <div style={{ marginBottom: '22px' }}>
                  <label style={{ display: 'block', fontSize: '0.88rem', fontWeight: 700, marginBottom: '10px', color: 'var(--text-primary)' }}>
                    Choose Technology:
                  </label>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                    {POPULAR_TECHS.map((tech) => (
                      <button
                        type="button"
                        key={tech}
                        onClick={() => setRoleOrTech(tech)}
                        style={{
                          padding: '8px 18px',
                          borderRadius: '24px',
                          border: roleOrTech === tech ? '2px solid var(--primary-powder-blue-dark)' : '1px solid var(--border-soft)',
                          background: roleOrTech === tech ? 'var(--primary-powder-blue-light)' : '#FFFFFF',
                          color: roleOrTech === tech ? '#0F172A' : 'var(--text-secondary)',
                          fontWeight: roleOrTech === tech ? 700 : 500,
                          cursor: 'pointer',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        {tech}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setRoleOrTech('Other')}
                      style={{
                        padding: '8px 18px',
                        borderRadius: '24px',
                        border: roleOrTech === 'Other' ? '2px solid var(--primary-powder-blue-dark)' : '1px solid var(--border-soft)',
                        background: roleOrTech === 'Other' ? 'var(--primary-powder-blue-light)' : '#FFFFFF',
                        color: roleOrTech === 'Other' ? '#0F172A' : 'var(--text-secondary)',
                        fontWeight: roleOrTech === 'Other' ? 700 : 500,
                        cursor: 'pointer'
                      }}
                    >
                      Custom Role...
                    </button>
                  </div>

                  {roleOrTech === 'Other' && (
                    <div style={{ marginTop: '12px' }}>
                      <input
                        type="text"
                        className="form-control"
                        placeholder="e.g. Docker, DevOps, Go, System Design"
                        value={customTech}
                        onChange={(e) => setCustomTech(e.target.value)}
                        style={{ maxWidth: '400px' }}
                      />
                    </div>
                  )}
                </div>

                {/* Difficulty & Count */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '20px', marginBottom: '28px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                      Difficulty Level:
                    </label>
                    <select
                      className="form-control"
                      value={difficulty}
                      onChange={(e) => setDifficulty(e.target.value)}
                    >
                      <option value="Easy">Easy (Foundational Concepts)</option>
                      <option value="Medium">Medium (Practical Architecture)</option>
                      <option value="Hard">Hard (Deep Dives & Edge Cases)</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                      Questions Count:
                    </label>
                    <select
                      className="form-control"
                      value={numQuestions}
                      onChange={(e) => setNumQuestions(e.target.value)}
                    >
                      <option value="3">3 Questions (Quick Drill)</option>
                      <option value="5">5 Questions (Standard Mock)</option>
                      <option value="10">10 Questions (Comprehensive)</option>
                    </select>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={startingSession}
                  className="btn btn-primary"
                  style={{ width: '100%', padding: '12px', fontSize: '1rem', fontWeight: 700 }}
                >
                  {startingSession ? (
                    <>
                      <RefreshCw size={18} className="spin" style={{ marginRight: '8px' }} />
                      Initializing Mock Session...
                    </>
                  ) : (
                    'Start Practice Session'
                  )}
                </button>
              </form>
            </div>
          ) : (
            /* Active Practice Question Runner */
            <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Stepper Header */}
              <div className="card" style={{ padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <button
                    onClick={handleFinishSession}
                    className="btn btn-outline"
                    style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                  >
                    <ArrowLeft size={14} style={{ marginRight: '4px' }} /> Leave
                  </button>
                  <div>
                    <span className="badge badge-peach" style={{ marginRight: '8px' }}>
                      {activeSession.role_or_tech}
                    </span>
                    <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      Question {currentQuestionIndex + 1} of {activeSession.questions?.length || 0}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '6px' }}>
                  {activeSession.questions?.map((q, idx) => (
                    <button
                      key={q.id}
                      onClick={() => {
                        setCurrentQuestionIndex(idx);
                        const prev = answersMap[q.id];
                        if (prev) {
                          setCandidateAnswer(prev.answer);
                          setCurrentFeedback(prev.feedback);
                        } else {
                          setCandidateAnswer('');
                          setCurrentFeedback(null);
                        }
                      }}
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '6px',
                        border: 'none',
                        background: idx === currentQuestionIndex
                          ? 'var(--primary-powder-blue)'
                          : answersMap[q.id]
                          ? '#10B981'
                          : 'var(--background-lavender)',
                        color: idx === currentQuestionIndex ? '#0F172A' : answersMap[q.id] ? '#FFFFFF' : 'var(--text-secondary)',
                        fontWeight: 700,
                        fontSize: '0.8rem',
                        cursor: 'pointer'
                      }}
                    >
                      {idx + 1}
                    </button>
                  ))}
                </div>
              </div>

              {/* Question Text Card */}
              {activeSession.questions && activeSession.questions[currentQuestionIndex] && (
                <div className="card" style={{ padding: '28px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px', marginBottom: '20px' }}>
                    <div style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'rgba(141, 185, 240, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--primary-powder-blue-dark)',
                      flexShrink: 0
                    }}>
                      <HelpCircle size={20} />
                    </div>
                    <div>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        Technical Interview Question
                      </span>
                      <h3 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px', lineHeight: 1.5 }}>
                        {activeSession.questions[currentQuestionIndex].question_text}
                      </h3>
                    </div>
                  </div>

                  {/* Candidate Answer Box */}
                  <div>
                    <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                      Your Answer:
                    </label>
                    <textarea
                      className="form-control"
                      rows={6}
                      placeholder="Type your structured technical answer here. Consider mentioning core concepts, trade-offs, and practical examples..."
                      value={candidateAnswer}
                      onChange={(e) => setCandidateAnswer(e.target.value)}
                      style={{ width: '100%', resize: 'vertical', fontSize: '0.95rem', lineHeight: 1.5, marginBottom: '8px' }}
                    />
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {candidateAnswer.trim().split(/\s+/).filter(Boolean).length} words
                      </span>
                      <button
                        onClick={handleSubmitAnswer}
                        disabled={submittingAnswer || !candidateAnswer.trim()}
                        className="btn btn-primary"
                        style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
                      >
                        {submittingAnswer ? (
                          <>
                            <RefreshCw size={16} className="spin" /> Evaluating...
                          </>
                        ) : (
                          <>
                            <Send size={16} /> Submit Answer
                          </>
                        )}
                      </button>
                    </div>
                  </div>

                  {/* Feedback Card (if submitted) */}
                  {currentFeedback && (
                    <div style={{ marginTop: '28px', borderTop: '1px solid var(--border-soft)', paddingTop: '20px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                        <h4 style={{ fontSize: '1.05rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <Bot size={18} color="var(--primary-powder-blue)" />
                          Interview Evaluation & Feedback
                        </h4>
                        {currentFeedback.score !== null && currentFeedback.score !== undefined && (
                          <span className="badge badge-success" style={{ fontSize: '0.85rem', padding: '6px 12px' }}>
                            Score: {currentFeedback.score} / 100
                          </span>
                        )}
                      </div>

                      {/* Feedback Body */}
                      <div style={{
                        background: 'var(--background-lavender-light)',
                        borderRadius: 'var(--radius-md)',
                        padding: '18px',
                        fontSize: '0.92rem',
                        lineHeight: 1.6,
                        color: 'var(--text-primary)',
                        marginBottom: '16px'
                      }}>
                        {currentFeedback.feedback}
                      </div>

                      {/* Strengths and Improvements */}
                      {(currentFeedback.strengths || currentFeedback.improvements) && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '14px', marginBottom: '16px' }}>
                          {currentFeedback.strengths && (
                            <div style={{ background: 'var(--success-bg)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
                              <strong style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', marginBottom: '6px' }}>
                                <ThumbsUp size={14} /> Strengths
                              </strong>
                              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: 0 }}>
                                {currentFeedback.strengths}
                              </p>
                            </div>
                          )}

                          {currentFeedback.improvements && (
                            <div style={{ background: 'var(--warning-bg)', padding: '14px', borderRadius: 'var(--radius-md)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                              <strong style={{ color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.85rem', marginBottom: '6px' }}>
                                <Target size={14} /> Recommended Improvements
                              </strong>
                              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: 0 }}>
                                {currentFeedback.improvements}
                              </p>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Next / Finish Navigation */}
                      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                        {currentQuestionIndex < (activeSession.questions?.length || 0) - 1 ? (
                          <button
                            onClick={handleNextQuestion}
                            className="btn btn-primary"
                            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                          >
                            Next Question <ChevronRight size={16} />
                          </button>
                        ) : (
                          <button
                            onClick={handleFinishSession}
                            className="btn btn-primary"
                            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                          >
                            <CheckCircle2 size={16} /> Complete Practice Session
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* TAB 2: SESSION HISTORY */}
      {activeTab === 'history' && (
        <div className="card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={20} color="var(--primary-powder-blue)" />
            Completed Mock Interview Sessions
          </h3>

          {loadingSessions ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              Loading your past sessions...
            </div>
          ) : sessions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              No mock sessions completed yet. Start your first session in the "Practice Session" tab!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {sessions.map((s) => (
                <div
                  key={s.id}
                  style={{
                    border: '1px solid var(--border-soft)',
                    borderRadius: 'var(--radius-md)',
                    padding: '18px 20px',
                    background: 'var(--surface-subtle)'
                  }}
                >
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '10px', marginBottom: '10px' }}>
                    <div>
                      <span className="badge badge-peach" style={{ marginRight: '8px' }}>
                        {s.role_or_tech}
                      </span>
                      <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                        Session #{s.id}
                      </strong>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '12px' }}>
                        {s.created_at ? new Date(s.created_at).toLocaleDateString() : ''}
                      </span>
                    </div>

                    <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      Total Questions: <strong>{s.questions?.length || s.total_questions || 0}</strong>
                    </span>
                  </div>

                  {/* List questions and candidate answers */}
                  {s.questions && s.questions.length > 0 && (
                    <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {s.questions.map((q, idx) => (
                        <div key={q.id} style={{ background: '#FFFFFF', padding: '10px 14px', borderRadius: '8px', fontSize: '0.88rem' }}>
                          <span style={{ fontWeight: 700, color: 'var(--primary-powder-blue-dark)', marginRight: '6px' }}>
                            Q{idx + 1}:
                          </span>
                          <span style={{ color: 'var(--text-primary)' }}>{q.question_text}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

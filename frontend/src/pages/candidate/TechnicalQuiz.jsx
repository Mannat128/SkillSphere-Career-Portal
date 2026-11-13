import React, { useState, useEffect } from 'react';
import {
  FileCode,
  CheckCircle2,
  XCircle,
  Clock,
  Award,
  ArrowRight,
  ArrowLeft,
  AlertCircle,
  HelpCircle,
  History,
  RotateCcw,
  CheckSquare,
  Play
} from 'lucide-react';
import api from '../../services/api';

export default function TechnicalQuiz() {
  const [assessments, setAssessments] = useState([]);
  const [historyList, setHistoryList] = useState([]);
  const [loading, setLoading] = useState(true);

  // Active quiz state
  const [activeQuiz, setActiveQuiz] = useState(null); // attempt payload
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({}); // question_id -> 'A' | 'B' | 'C' | 'D'
  const [timeLeft, setTimeLeft] = useState(0); // seconds
  const [submitting, setSubmitting] = useState(false);
  const [quizResult, setQuizResult] = useState(null);

  const [activeTab, setActiveTab] = useState('quizzes'); // 'quizzes' | 'history'
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    loadQuizzesAndHistory();
  }, []);

  // Timer countdown
  useEffect(() => {
    if (!activeQuiz || quizResult) return;

    if (timeLeft <= 0) {
      // Auto submit when time expires
      handleSubmitQuiz(true);
      return;
    }

    const timer = setInterval(() => {
      setTimeLeft((prev) => prev - 1);
    }, 1000);

    return () => clearInterval(timer);
  }, [activeQuiz, timeLeft, quizResult]);

  const loadQuizzesAndHistory = async () => {
    setLoading(true);
    try {
      const [assessRes, histRes] = await Promise.all([
        api.get('/assessments'),
        api.get('/assessments/attempts/history')
      ]);
      setAssessments(assessRes.data || []);
      setHistoryList(histRes.data || []);
    } catch (err) {
      console.error('Failed to load technical assessments', err);
      setErrorMsg('Could not load technical quizzes. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleStartQuiz = async (assessmentId) => {
    setErrorMsg('');
    try {
      const res = await api.post(`/assessments/${assessmentId}/start`);
      const data = res.data;
      setActiveQuiz(data);
      setCurrentQuestionIndex(0);
      setSelectedAnswers({});
      setQuizResult(null);
      setTimeLeft(data.duration_minutes * 60);
    } catch (err) {
      console.error('Failed to start quiz attempt', err);
      const detail = err.response?.data?.detail || 'Could not start quiz attempt.';
      setErrorMsg(detail);
    }
  };

  const handleSelectOption = (questionId, optionLetter) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: optionLetter
    }));
  };

  const handleSubmitQuiz = async (auto = false) => {
    if (!activeQuiz || submitting) return;

    if (!auto) {
      const totalQ = activeQuiz.questions?.length || 0;
      const answeredCount = Object.keys(selectedAnswers).length;
      if (answeredCount < totalQ) {
        const confirmSubmit = window.confirm(
          `You have answered ${answeredCount} of ${totalQ} questions. Are you sure you want to submit now?`
        );
        if (!confirmSubmit) return;
      }
    }

    setSubmitting(true);
    setErrorMsg('');

    try {
      const answersPayload = (activeQuiz.questions || []).map((q) => ({
        question_id: q.id,
        selected_option: selectedAnswers[q.id] || ''
      }));

      const res = await api.post(`/assessments/attempts/${activeQuiz.attempt_id}/submit`, {
        answers: answersPayload
      });

      setQuizResult(res.data);
      // Refresh history
      const histRes = await api.get('/assessments/attempts/history');
      setHistoryList(histRes.data || []);
    } catch (err) {
      console.error('Failed to submit quiz attempt', err);
      const detail = err.response?.data?.detail || 'Failed to submit quiz. Please try again.';
      setErrorMsg(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleLeaveQuiz = () => {
    if (!quizResult) {
      const confirmLeave = window.confirm('Are you sure you want to leave this quiz? Your current attempt will not be saved.');
      if (!confirmLeave) return;
    }
    setActiveQuiz(null);
    setQuizResult(null);
    setSelectedAnswers({});
    setCurrentQuestionIndex(0);
  };

  return (
    <div>
      {/* Header */}
      <div className="page-header" style={{ marginBottom: '24px' }}>
        <div>
          <h2 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileCode size={28} color="var(--primary-powder-blue)" />
            Standalone Technical Quiz Practice
          </h2>
          <p className="page-subtitle">
            Test your proficiency across core engineering topics, practice timed MCQ assessments, and receive immediate answer explanations.
          </p>
        </div>
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

      {/* When NO quiz is running: Show Quizzes or History Tabs */}
      {!activeQuiz && (
        <>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', borderBottom: '1px solid var(--border-soft)', paddingBottom: '12px' }}>
            <button
              onClick={() => setActiveTab('quizzes')}
              className={`btn ${activeTab === 'quizzes' ? 'btn-primary' : 'btn-outline'}`}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
            >
              <CheckSquare size={16} /> Available Quizzes ({assessments.length})
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`btn ${activeTab === 'history' ? 'btn-primary' : 'btn-outline'}`}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 18px' }}
            >
              <History size={16} /> Past Quiz Attempts ({historyList.length})
            </button>
          </div>

          {loading ? (
            <div className="card" style={{ textAlign: 'center', padding: '50px', color: 'var(--text-muted)' }}>
              Loading technical assessments...
            </div>
          ) : activeTab === 'quizzes' ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
              {assessments.map((quiz) => (
                <div key={quiz.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '24px' }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                      <span className="badge badge-peach" style={{ fontSize: '0.75rem' }}>
                        {quiz.technology}
                      </span>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={13} /> {quiz.duration_minutes} mins
                      </span>
                    </div>

                    <h3 style={{ fontSize: '1.15rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '8px' }}>
                      {quiz.title}
                    </h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.5, marginBottom: '16px' }}>
                      {quiz.description || `Evaluate your hands-on mastery in ${quiz.technology}. Timed self-assessment with automatic scoring.`}
                    </p>
                  </div>

                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '14px', borderTop: '1px solid var(--border-soft)', paddingTop: '12px' }}>
                      <span>Passing Score: <strong>{quiz.passing_score}%</strong></span>
                      <span>Total Questions: <strong>{quiz.total_questions || 5}</strong></span>
                    </div>

                    <button
                      onClick={() => handleStartQuiz(quiz.id)}
                      className="btn btn-primary"
                      style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}
                    >
                      <Play size={16} /> Start Assessment
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            /* TAB: HISTORY */
            <div className="card" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px' }}>
                Your Technical Quiz Attempt History
              </h3>

              {historyList.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', textAlign: 'center', padding: '30px 0' }}>
                  You haven't completed any technical quizzes yet. Pick a quiz from the "Available Quizzes" tab!
                </p>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-soft)', textAlign: 'left', color: 'var(--text-muted)' }}>
                        <th style={{ padding: '12px 14px' }}>Assessment</th>
                        <th style={{ padding: '12px 14px' }}>Technology</th>
                        <th style={{ padding: '12px 14px' }}>Score</th>
                        <th style={{ padding: '12px 14px' }}>Status</th>
                        <th style={{ padding: '12px 14px' }}>Completed At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyList.map((h) => (
                        <tr key={h.id} style={{ borderBottom: '1px solid var(--border-soft)' }}>
                          <td style={{ padding: '14px', fontWeight: 600 }}>{h.title}</td>
                          <td style={{ padding: '14px' }}>
                            <span className="badge badge-peach" style={{ fontSize: '0.75rem' }}>
                              {h.technology}
                            </span>
                          </td>
                          <td style={{ padding: '14px', fontWeight: 700 }}>{Math.round(h.score)}%</td>
                          <td style={{ padding: '14px' }}>
                            {h.passed ? (
                              <span className="badge badge-success" style={{ gap: '4px' }}>
                                <CheckCircle2 size={12} /> Passed
                              </span>
                            ) : (
                              <span className="badge badge-danger" style={{ gap: '4px' }}>
                                <XCircle size={12} /> Needs Practice
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '14px', color: 'var(--text-muted)' }}>
                            {h.completed_at ? new Date(h.completed_at).toLocaleDateString() : 'Incomplete'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* When Quiz is ACTIVE and NOT yet submitted */}
      {activeQuiz && !quizResult && (
        <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Top Bar with Timer and Progress */}
          <div className="card" style={{
            padding: '16px 24px',
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
            position: 'sticky',
            top: '80px',
            zIndex: 10,
            boxShadow: 'var(--shadow-md)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <button
                onClick={handleLeaveQuiz}
                className="btn btn-outline"
                style={{ padding: '6px 12px', fontSize: '0.8rem' }}
              >
                Quit Quiz
              </button>
              <div>
                <span className="badge badge-peach" style={{ marginRight: '8px' }}>
                  {activeQuiz.technology}
                </span>
                <strong style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                  {activeQuiz.title}
                </strong>
              </div>
            </div>

            {/* Countdown Display */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 14px',
              borderRadius: '20px',
              background: timeLeft < 120 ? 'var(--danger-bg)' : 'var(--background-lavender-light)',
              color: timeLeft < 120 ? 'var(--danger)' : 'var(--text-primary)',
              fontWeight: 800,
              fontSize: '1rem'
            }}>
              <Clock size={16} />
              <span>{formatTimer(timeLeft)}</span>
            </div>
          </div>

          {/* Question Stepper / Palette */}
          <div className="card" style={{ padding: '16px 20px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
              Question {currentQuestionIndex + 1} of {activeQuiz.questions?.length || 0}
            </span>

            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {activeQuiz.questions?.map((q, idx) => (
                <button
                  key={q.id}
                  onClick={() => setCurrentQuestionIndex(idx)}
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    border: 'none',
                    background: idx === currentQuestionIndex
                      ? 'var(--primary-powder-blue)'
                      : selectedAnswers[q.id]
                      ? '#10B981'
                      : 'var(--background-lavender)',
                    color: idx === currentQuestionIndex ? '#0F172A' : selectedAnswers[q.id] ? '#FFFFFF' : 'var(--text-secondary)',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer'
                  }}
                >
                  {idx + 1}
                </button>
              ))}
            </div>
          </div>

          {/* Current Question Card */}
          {activeQuiz.questions && activeQuiz.questions[currentQuestionIndex] && (
            <div className="card" style={{ padding: '32px' }}>
              {(() => {
                const q = activeQuiz.questions[currentQuestionIndex];
                const options = [
                  { letter: 'A', text: q.option_a },
                  { letter: 'B', text: q.option_b },
                  { letter: 'C', text: q.option_c },
                  { letter: 'D', text: q.option_d }
                ].filter(opt => opt.text);

                return (
                  <div>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 800, lineHeight: 1.5, marginBottom: '24px', color: 'var(--text-primary)' }}>
                      <span style={{ color: 'var(--primary-powder-blue-dark)', marginRight: '8px' }}>
                        Q{currentQuestionIndex + 1}.
                      </span>
                      {q.question_text}
                    </h3>

                    {/* Options list */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '28px' }}>
                      {options.map((opt) => {
                        const isSelected = selectedAnswers[q.id] === opt.letter;
                        return (
                          <div
                            key={opt.letter}
                            onClick={() => handleSelectOption(q.id, opt.letter)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '14px',
                              padding: '14px 18px',
                              borderRadius: 'var(--radius-md)',
                              border: isSelected
                                ? '2px solid var(--primary-powder-blue-dark)'
                                : '1px solid var(--border-soft)',
                              background: isSelected
                                ? 'var(--primary-powder-blue-light)'
                                : 'var(--surface-white)',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease'
                            }}
                          >
                            <div style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '50%',
                              border: isSelected ? '2px solid var(--primary-powder-blue-dark)' : '1px solid var(--border-soft)',
                              background: isSelected ? 'var(--primary-powder-blue-dark)' : '#FFFFFF',
                              color: isSelected ? '#FFFFFF' : 'var(--text-secondary)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 700,
                              fontSize: '0.85rem'
                            }}>
                              {opt.letter}
                            </div>
                            <span style={{ fontSize: '0.95rem', color: 'var(--text-primary)', fontWeight: isSelected ? 600 : 400 }}>
                              {opt.text}
                            </span>
                          </div>
                        );
                      })}
                    </div>

                    {/* Navigation Buttons */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-soft)', paddingTop: '20px' }}>
                      <button
                        onClick={() => setCurrentQuestionIndex((prev) => Math.max(0, prev - 1))}
                        disabled={currentQuestionIndex === 0}
                        className="btn btn-outline"
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <ArrowLeft size={16} /> Previous
                      </button>

                      {currentQuestionIndex < activeQuiz.questions.length - 1 ? (
                        <button
                          onClick={() => setCurrentQuestionIndex((prev) => prev + 1)}
                          className="btn btn-primary"
                          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                        >
                          Next <ArrowRight size={16} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleSubmitQuiz(false)}
                          disabled={submitting}
                          className="btn btn-primary"
                          style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#10B981', borderColor: '#10B981', color: '#FFFFFF' }}
                        >
                          {submitting ? 'Evaluating Score...' : 'Submit Assessment'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      )}

      {/* QUIZ RESULT SCREEN */}
      {quizResult && (
        <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Result Score Banner */}
          <div className="card" style={{
            padding: '36px',
            textAlign: 'center',
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, var(--background-lavender-light) 100%)',
            border: '1px solid var(--border-soft)'
          }}>
            <div style={{
              width: '80px',
              height: '80px',
              borderRadius: '50%',
              margin: '0 auto 16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: quizResult.passed ? 'var(--success-bg)' : 'var(--danger-bg)',
              color: quizResult.passed ? 'var(--success)' : 'var(--danger)'
            }}>
              {quizResult.passed ? <CheckCircle2 size={44} /> : <XCircle size={44} />}
            </div>

            <span className="badge badge-peach" style={{ marginBottom: '8px' }}>
              {quizResult.technology} Assessment
            </span>
            <h3 style={{ fontSize: '1.6rem', fontWeight: 800, margin: '6px 0' }}>
              {quizResult.passed ? 'Assessment Passed!' : 'Practice Needed'}
            </h3>

            <div style={{ fontSize: '2.5rem', fontWeight: 900, color: quizResult.passed ? 'var(--success)' : 'var(--danger)', margin: '12px 0' }}>
              {Math.round(quizResult.score)}%
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', maxWidth: '480px', margin: '0 auto 20px' }}>
              {quizResult.passed
                ? 'Congratulations! You demonstrated solid technical understanding across tested competencies.'
                : 'Keep practicing! Review the detailed answers and explanations below to improve your score.'}
            </p>

            <button
              onClick={handleLeaveQuiz}
              className="btn btn-primary"
              style={{ padding: '10px 24px', fontWeight: 700 }}
            >
              Back to All Quizzes
            </button>
          </div>

          {/* Detailed Question Review */}
          <div className="card" style={{ padding: '28px' }}>
            <h4 style={{ fontSize: '1.15rem', fontWeight: 800, marginBottom: '20px' }}>
              Question Review & Explanations ({quizResult.question_results?.length || 0})
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              {quizResult.question_results?.map((qr, idx) => (
                <div
                  key={qr.question_id || idx}
                  style={{
                    border: '1px solid var(--border-soft)',
                    borderRadius: 'var(--radius-md)',
                    padding: '18px 20px',
                    borderLeft: `4px solid ${qr.is_correct ? 'var(--success)' : 'var(--danger)'}`,
                    background: qr.is_correct ? '#FFFFFF' : 'var(--surface-subtle)'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px', marginBottom: '10px' }}>
                    <h5 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                      Q{idx + 1}. {qr.question_text}
                    </h5>
                    {qr.is_correct ? (
                      <span className="badge badge-success" style={{ gap: '4px', flexShrink: 0 }}>
                        <CheckCircle2 size={12} /> Correct
                      </span>
                    ) : (
                      <span className="badge badge-danger" style={{ gap: '4px', flexShrink: 0 }}>
                        <XCircle size={12} /> Incorrect
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '20px', fontSize: '0.88rem', margin: '8px 0', color: 'var(--text-secondary)' }}>
                    <span>
                      Your Answer: <strong style={{ color: qr.is_correct ? 'var(--success)' : 'var(--danger)' }}>Option {qr.selected_option || 'None'}</strong>
                    </span>
                    <span>
                      Correct Answer: <strong style={{ color: 'var(--success)' }}>Option {qr.correct_option}</strong>
                    </span>
                  </div>

                  {qr.explanation && (
                    <div style={{
                      marginTop: '10px',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'var(--background-lavender-light)',
                      fontSize: '0.85rem',
                      lineHeight: 1.5,
                      color: 'var(--text-primary)'
                    }}>
                      <strong>Explanation:</strong> {qr.explanation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

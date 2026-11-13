import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Clock,
  CheckCircle,
  AlertTriangle,
  Bookmark,
  ChevronLeft,
  ChevronRight,
  Send,
  HelpCircle,
  ShieldAlert,
} from 'lucide-react';
import api from '../../services/api';

export default function TakeAssessment() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [testData, setTestData] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [savedAnswers, setSavedAnswers] = useState({});
  const [markedForReview, setMarkedForReview] = useState([]);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // Submit Modal
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [autoSubmitted, setAutoSubmitted] = useState(false);

  const timerRef = useRef(null);

  useEffect(() => {
    initTest();
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [assignmentId]);

  const initTest = async () => {
    setLoading(true);
    try {
      const res = await api.post(`/candidate/first-round-assessments/${assignmentId}/start`);
      setTestData(res.data);
      setQuestions(res.data.questions || []);
      setSavedAnswers(res.data.saved_answers || {});
      setMarkedForReview(res.data.marked_for_review || []);

      const sec = res.data.remaining_seconds || 0;
      setRemainingSeconds(sec);
      startCountdown(sec);
    } catch (err) {
      alert(err.response?.data?.detail || 'Unable to start or resume assessment.');
      navigate('/candidate/first-round-assessments');
    } finally {
      setLoading(false);
    }
  };

  const startCountdown = (initialSec) => {
    if (timerRef.current) clearInterval(timerRef.current);

    timerRef.current = setInterval(() => {
      setRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          handleAutoSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSelectOption = async (optionLetter) => {
    const currentQ = questions[currentIndex];
    if (!currentQ) return;

    const newAnswers = { ...savedAnswers, [currentQ.id]: optionLetter };
    setSavedAnswers(newAnswers);

    // Save to backend asynchronously
    try {
      await api.post(`/candidate/first-round-assessments/${assignmentId}/save-answer`, {
        question_id: currentQ.id,
        selected_option: optionLetter,
      });
    } catch (e) {
      console.error('Failed to sync answer with server', e);
    }
  };

  const handleToggleReview = async () => {
    const currentQ = questions[currentIndex];
    if (!currentQ) return;

    const isMarked = markedForReview.includes(currentQ.id);
    let newMarked;
    if (isMarked) {
      newMarked = markedForReview.filter((id) => id !== currentQ.id);
    } else {
      newMarked = [...markedForReview, currentQ.id];
    }
    setMarkedForReview(newMarked);

    try {
      await api.post(`/candidate/first-round-assessments/${assignmentId}/save-answer`, {
        question_id: currentQ.id,
        is_marked_for_review: !isMarked,
      });
    } catch (e) {
      console.error('Failed to sync review toggle', e);
    }
  };

  const handleAutoSubmit = async () => {
    setAutoSubmitted(true);
    setSubmitting(true);
    try {
      await api.post(`/candidate/first-round-assessments/${assignmentId}/submit`, {
        final_answers: savedAnswers,
      });
      alert('Time is up! Your assessment has been automatically submitted.');
      navigate(`/candidate/assessment-result/${assignmentId}`);
    } catch (e) {
      navigate(`/candidate/assessment-result/${assignmentId}`);
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinalSubmit = async () => {
    setSubmitting(true);
    try {
      await api.post(`/candidate/first-round-assessments/${assignmentId}/submit`, {
        final_answers: savedAnswers,
      });
      navigate(`/candidate/assessment-result/${assignmentId}`);
    } catch (err) {
      alert(err.response?.data?.detail || 'Error submitting assessment.');
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)' }}>
        Loading assessment environment and questions...
      </div>
    );
  }

  const currentQ = questions[currentIndex] || {};
  const currentAnswer = savedAnswers[currentQ.id];
  const isCurrentMarked = markedForReview.includes(currentQ.id);
  const answeredCount = Object.keys(savedAnswers).length;
  const unansweredCount = questions.length - answeredCount;
  const isTimeCritical = remainingSeconds < 300; // < 5 mins

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '16px' }}>
      {/* Top Header Bar */}
      <div
        className="card"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '16px 24px',
          marginBottom: '20px',
          background: '#FFFFFF',
          borderLeft: '4px solid var(--primary-powder-blue)',
        }}
      >
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {testData?.title || 'First Round Assessment'}
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            Single Attempt Examination • One Question at a Time
          </p>
        </div>

        {/* Live Timer */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 16px',
              borderRadius: '24px',
              fontWeight: 800,
              fontSize: '1.1rem',
              background: isTimeCritical ? '#FEF2F2' : 'var(--bg-lavender-white)',
              color: isTimeCritical ? '#DC2626' : 'var(--primary-powder-blue-dark)',
              border: `1.5px solid ${isTimeCritical ? '#F87171' : 'var(--border-color)'}`,
            }}
          >
            <Clock size={20} className={isTimeCritical ? 'animate-pulse' : ''} />
            <span>{formatTimer(remainingSeconds)}</span>
          </div>

          <button
            onClick={() => setShowSubmitModal(true)}
            className="btn btn-accent"
            style={{ padding: '8px 18px', fontWeight: 700 }}
          >
            <Send size={16} /> Submit Test
          </button>
        </div>
      </div>

      {/* Main Content: Question + Navigator layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 300px', gap: '20px' }}>
        {/* Left: Active Question Area */}
        <div className="card" style={{ padding: '28px', minHeight: '520px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            {/* Question Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span className="badge badge-blue" style={{ fontSize: '0.85rem' }}>
                  Question {currentIndex + 1} of {questions.length}
                </span>
                <span className="badge" style={{ background: '#F1F5F9', color: '#475569' }}>
                  {currentQ.category}
                </span>
                <span className={`badge ${currentQ.difficulty === 'Easy' ? 'badge-success' : currentQ.difficulty === 'Hard' ? 'badge-danger' : 'badge-warning'}`}>
                  {currentQ.difficulty}
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                  {currentQ.marks || 1} {currentQ.marks === 1 ? 'Mark' : 'Marks'}
                </span>
                <button
                  type="button"
                  onClick={handleToggleReview}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-color)',
                    background: isCurrentMarked ? '#FEF3C7' : '#FFFFFF',
                    color: isCurrentMarked ? '#B45309' : 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  <Bookmark size={15} fill={isCurrentMarked ? '#B45309' : 'none'} />
                  {isCurrentMarked ? 'Marked for Review' : 'Mark for Review'}
                </button>
              </div>
            </div>

            {/* Question Text */}
            <h3 style={{ fontSize: '1.18rem', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: '24px' }}>
              {currentQ.question_text}
            </h3>

            {/* Options List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {['A', 'B', 'C', 'D'].map((letter) => {
                const optKey = `option_${letter.toLowerCase()}`;
                const optText = currentQ[optKey];
                const isSelected = currentAnswer === letter;

                return (
                  <div
                    key={letter}
                    onClick={() => handleSelectOption(letter)}
                    style={{
                      padding: '14px 18px',
                      borderRadius: '10px',
                      cursor: 'pointer',
                      border: `2px solid ${isSelected ? 'var(--primary-powder-blue)' : 'var(--border-color)'}`,
                      background: isSelected ? 'var(--primary-powder-blue-light)' : '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '14px',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: '0.85rem',
                        background: isSelected ? 'var(--primary-powder-blue)' : 'var(--bg-lavender-white)',
                        color: isSelected ? '#FFFFFF' : 'var(--text-primary)',
                      }}
                    >
                      {letter}
                    </div>
                    <span style={{ fontSize: '0.95rem', color: 'var(--text-primary)', flex: 1, fontWeight: isSelected ? 600 : 400 }}>
                      {optText}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Navigation Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '20px', marginTop: '28px' }}>
            <button
              onClick={() => setCurrentIndex((prev) => Math.max(0, prev - 1))}
              disabled={currentIndex === 0}
              className="btn btn-outline"
            >
              <ChevronLeft size={16} /> Previous
            </button>

            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Auto-saved
            </span>

            {currentIndex < questions.length - 1 ? (
              <button
                onClick={() => setCurrentIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                className="btn btn-primary"
              >
                Next <ChevronRight size={16} />
              </button>
            ) : (
              <button
                onClick={() => setShowSubmitModal(true)}
                className="btn btn-accent"
              >
                Review & Submit <Send size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Right: Question Palette / Navigator */}
        <div className="card" style={{ padding: '20px', height: 'fit-content' }}>
          <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '14px', color: 'var(--text-primary)' }}>
            Question Navigator
          </h4>

          {/* Color Legend */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.75rem', marginBottom: '16px', padding: '10px', background: 'var(--bg-lavender-white)', borderRadius: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#10B981' }} />
              <span>Answered ({answeredCount})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#F59E0B' }} />
              <span>Review ({markedForReview.length})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '3px', background: '#E2E8F0', border: '1px solid #CBD5E1' }} />
              <span>Unanswered ({unansweredCount})</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ width: '12px', height: '12px', borderRadius: '3px', border: '2px solid var(--primary-powder-blue)' }} />
              <span>Current</span>
            </div>
          </div>

          {/* Grid of Question Number Buttons */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px', maxHeight: '320px', overflowY: 'auto' }}>
            {questions.map((q, idx) => {
              const isAnswered = savedAnswers[q.id] !== undefined;
              const isMarked = markedForReview.includes(q.id);
              const isCurrent = idx === currentIndex;

              let bg = '#F1F5F9';
              let textCol = 'var(--text-primary)';
              if (isMarked) {
                bg = '#FEF3C7';
                textCol = '#B45309';
              } else if (isAnswered) {
                bg = '#D1FAE5';
                textCol = '#065F46';
              }

              return (
                <button
                  key={q.id}
                  onClick={() => setCurrentIndex(idx)}
                  style={{
                    height: '38px',
                    borderRadius: '8px',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    background: bg,
                    color: textCol,
                    border: isCurrent ? '2.5px solid var(--primary-powder-blue)' : '1px solid var(--border-color)',
                    transition: 'all 0.1s ease',
                  }}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          {/* Test Info Footer */}
          <div style={{ borderTop: '1px solid var(--border-color)', marginTop: '20px', paddingTop: '14px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
            <p><strong>Total Questions:</strong> {questions.length}</p>
            <p style={{ marginTop: '4px' }}><strong>Negative Marking:</strong> {testData?.negative_marking ? `Yes (-${testData.negative_marks} pts)` : 'None'}</p>
          </div>
        </div>
      </div>

      {/* Confirmation Modal Before Submit */}
      {showSubmitModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '480px' }}>
            <div style={{ textAlign: 'center', marginBottom: '16px' }}>
              <AlertTriangle size={48} color="var(--accent-sunset-peach-dark)" style={{ margin: '0 auto 10px' }} />
              <h3 style={{ fontSize: '1.25rem', fontWeight: 800 }}>Submit Assessment?</h3>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                Once submitted, your answers will be evaluated immediately. No retakes are permitted.
              </p>
            </div>

            <div style={{ background: 'var(--bg-lavender-white)', borderRadius: '10px', padding: '16px', margin: '18px 0' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem' }}>
                <span>Total Questions:</span>
                <strong>{questions.length}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem', color: '#059669' }}>
                <span>Answered Questions:</span>
                <strong>{answeredCount}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '0.9rem', color: '#D97706' }}>
                <span>Marked for Review:</span>
                <strong>{markedForReview.length}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem', color: unansweredCount > 0 ? '#DC2626' : 'var(--text-muted)' }}>
                <span>Unanswered Questions:</span>
                <strong>{unansweredCount}</strong>
              </div>
            </div>

            {unansweredCount > 0 && (
              <p style={{ fontSize: '0.8rem', color: '#DC2626', marginBottom: '16px', textAlign: 'center' }}>
                Warning: You have {unansweredCount} unanswered question{unansweredCount > 1 ? 's' : ''}. Unanswered questions receive 0 marks.
              </p>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                type="button"
                onClick={() => setShowSubmitModal(false)}
                className="btn btn-outline"
                disabled={submitting}
              >
                Return to Test
              </button>
              <button
                type="button"
                onClick={handleFinalSubmit}
                disabled={submitting}
                className="btn btn-primary"
              >
                {submitting ? 'Evaluating Answers...' : 'Confirm Submission'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

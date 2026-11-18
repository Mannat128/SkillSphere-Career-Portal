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
  Camera,
  ShieldCheck,
  Video,
} from 'lucide-react';
import api from '../../services/api';

export default function TakeAssessment() {
  const { assignmentId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(false);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraStarting, setCameraStarting] = useState(false);
  const [cameraError, setCameraError] = useState('');
  const [cameraStream, setCameraStream] = useState(null);
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const recordingChunksRef = useRef([]);
  const recordingUploadPromiseRef = useRef(null);
  const recordingBlobRef = useRef(null);
  const submitLockRef = useRef(false);
  const [recordingActive, setRecordingActive] = useState(false);
  const [recordingError, setRecordingError] = useState('');
  const [warningCount, setWarningCount] = useState(0);
  const [lastWarning, setLastWarning] = useState('');
  const assessmentActiveRef = useRef(false);
  const intentionalStopRef = useRef(false);
  const lastViolationAtRef = useRef({});
  const fullscreenWasEnteredRef = useRef(false);
  const computerVisionTimerRef = useRef(null);
  const computerVisionVideoRef = useRef(null);
  const computerVisionRequestRef = useRef(false);
  const [aiDetectionMessage, setAiDetectionMessage] = useState('');
  const [testData, setTestData] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [savedAnswers, setSavedAnswers] = useState({});
  const savedAnswersRef = useRef({});
  const answerSaveQueueRef = useRef(Promise.resolve());
  const answerSaveErrorRef = useRef(null);
  const [markedForReview, setMarkedForReview] = useState([]);
  const markedForReviewRef = useRef([]);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // Submit Modal
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [autoSubmitted, setAutoSubmitted] = useState(false);

  const timerRef = useRef(null);

  const playWarningBeep = () => {
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      const audioContext = new AudioContextClass();
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = 880;
      gain.gain.value = 0.12;
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.22);
      oscillator.onended = () => audioContext.close();
    } catch (error) {
      console.warn('Warning sound could not be played:', error);
    }
  };

  const reportViolation = async (violationType, message) => {
    if (!assessmentActiveRef.current || submitLockRef.current) return;
    const now = Date.now();
    const previous = lastViolationAtRef.current[violationType] || 0;
    if (now - previous < 2500) return;
    lastViolationAtRef.current[violationType] = now;
    setLastWarning(message);
    playWarningBeep();
    try {
      const response = await api.post(
        `/candidate/first-round-assessments/${assignmentId}/proctoring/violation`,
        { violation_type: violationType }
      );
      if (typeof response.data?.warning_count === 'number') {
        setWarningCount(response.data.warning_count);
      } else {
        setWarningCount((count) => count + 1);
      }
    } catch (error) {
      console.error('Could not report proctoring warning:', error);
      setWarningCount((count) => count + 1);
    }
  };

  useEffect(() => {
    return () => {
      assessmentActiveRef.current = false;
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      if (timerRef.current) clearInterval(timerRef.current);
      if (computerVisionTimerRef.current) clearInterval(computerVisionTimerRef.current);
      if (computerVisionVideoRef.current) {
        computerVisionVideoRef.current.pause();
        computerVisionVideoRef.current.srcObject = null;
        computerVisionVideoRef.current = null;
      }
      if (recorderRef.current && recorderRef.current.state !== 'inactive') {
        try { recorderRef.current.stop(); } catch (error) { console.error('Could not stop recorder during cleanup', error); }
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  useEffect(() => {
    if (!cameraStream) return;

    if (videoRef.current) {
      videoRef.current.srcObject = cameraStream;
      videoRef.current.play().catch(() => {});
    }

    const videoTrack = cameraStream.getVideoTracks()[0];
    const handleCameraEnded = () => {
      setCameraReady(false);
      setCameraError('Camera connection was interrupted.');
      reportViolation('CAMERA_DISCONNECTED', 'Camera connection interrupted. Please reconnect your camera.');
    };

    videoTrack?.addEventListener('ended', handleCameraEnded);
    return () => videoTrack?.removeEventListener('ended', handleCameraEnded);
  }, [cameraStream]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        reportViolation('TAB_SWITCH', 'Warning: You switched away from the assessment tab.');
      }
    };

    const handleWindowBlur = () => {
      reportViolation('WINDOW_BLUR', 'Warning: The assessment window lost focus.');
    };

    const handleFullscreenChange = () => {
      if (document.fullscreenElement) {
        fullscreenWasEnteredRef.current = true;
      } else if (fullscreenWasEnteredRef.current) {
        reportViolation('FULLSCREEN_EXIT', 'Warning: You exited fullscreen mode.');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleWindowBlur);
    document.addEventListener('fullscreenchange', handleFullscreenChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleWindowBlur);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [assignmentId]);

  const enableCamera = async () => {
    setCameraError('');
    setCameraStarting(true);

    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Camera access is not supported by this browser. Please use an updated browser over HTTPS or localhost.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user' },
        audio: false,
      });

      streamRef.current = stream;
      setCameraStream(stream);
      setCameraReady(true);
    } catch (error) {
      let message = 'Unable to access your camera. Please allow camera permission and try again.';
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        message = 'Camera permission was denied. Please allow camera access in your browser settings, then try again.';
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        message = 'No camera was found. Connect a camera to continue.';
      } else if (error.message) {
        message = error.message;
      }
      setCameraError(message);
      setCameraReady(false);
    } finally {
      setCameraStarting(false);
    }
  };

  const getSupportedRecordingMimeType = () => {
    if (typeof MediaRecorder === 'undefined') return '';

    const candidates = [
      'video/webm;codecs=vp9',
      'video/webm;codecs=vp8',
      'video/webm',
    ];

    return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || '';
  };

  const startBrowserRecording = (stream) => {
    const mimeType = getSupportedRecordingMimeType();
    if (!mimeType) {
      throw new Error('This browser does not support the required video recording format. Please use an updated version of Chrome or Edge.');
    }

    recordingChunksRef.current = [];
    const recorder = new MediaRecorder(stream, { mimeType });
    recorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordingChunksRef.current.push(event.data);
      }
    };

    recorder.onerror = (event) => {
      console.error('Browser recording error:', event.error || event);
      setRecordingError('The browser reported a recording problem. Please keep the assessment open and contact support if it continues.');
      setRecordingActive(false);
    };

    recordingUploadPromiseRef.current = new Promise((resolve, reject) => {
      recorder.onstop = async () => {
        setRecordingActive(false);

        if (
          assessmentActiveRef.current &&
          !intentionalStopRef.current &&
          !submitLockRef.current
        ) {
          reportViolation(
            'RECORDING_STOPPED',
            'Warning: Assessment recording stopped unexpectedly.'
          );
        }

        const chunks = recordingChunksRef.current;
        recordingChunksRef.current = [];

        if (!chunks.length) {
          reject(new Error('No recording data was captured by the browser.'));
          return;
        }

        const blob = new Blob(chunks, { type: 'video/webm' });
        recordingBlobRef.current = blob;

        try {
          await uploadRecordingBlob();
          resolve(true);
        } catch (error) {
          reject(error);
        }
      };
    });

    // Prevent an unhandled rejection if an unexpected navigation happens
    // before the normal assessment submission flow awaits this promise.
    recordingUploadPromiseRef.current.catch(() => {});

    recorder.start(1000);
    setRecordingActive(true);
  };

  const uploadRecordingBlob = async () => {
    const blob = recordingBlobRef.current;

    if (!blob) {
      throw new Error('Recording data is not available for upload.');
    }

    const formData = new FormData();
    formData.append(
      'file',
      blob,
      `assessment-${assignmentId}-${Date.now()}.webm`
    );

    try {
      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/proctoring/recording/upload`,
        formData
      );

      recordingBlobRef.current = null;
      setRecordingError('');
      return true;
    } catch (error) {
      const message =
        error.response?.data?.detail ||
        error.message ||
        'Recording upload failed.';

      setRecordingError(message);
      throw error;
    }
  };

  const stopRecordingAndUpload = async () => {
    stopComputerVisionMonitoring();
    intentionalStopRef.current = true;
    assessmentActiveRef.current = false;

    const recorder = recorderRef.current;

    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }

    if (recordingUploadPromiseRef.current) {
      try {
        await recordingUploadPromiseRef.current;
      } catch (error) {
        // Keep the captured blob in memory so the upload can be retried.
        if (!recordingBlobRef.current) {
          throw error;
        }
      }
    }

    if (recordingBlobRef.current) {
      await uploadRecordingBlob();
    }
  };

  const stopComputerVisionMonitoring = () => {
    if (computerVisionTimerRef.current) {
      clearInterval(computerVisionTimerRef.current);
      computerVisionTimerRef.current = null;
    }

    if (computerVisionVideoRef.current) {
      computerVisionVideoRef.current.pause();
      computerVisionVideoRef.current.srcObject = null;
      computerVisionVideoRef.current = null;
    }

    computerVisionRequestRef.current = false;
  };

  const startComputerVisionMonitoring = async (stream) => {
    stopComputerVisionMonitoring();

    const video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.srcObject = stream;
    computerVisionVideoRef.current = video;

    try {
      await video.play();
    } catch (error) {
      console.warn('Computer vision video stream could not start:', error);
      setAiDetectionMessage('AI camera analysis could not start.');
      return;
    }

    const analyzeFrame = async () => {
      if (
        !assessmentActiveRef.current ||
        submitLockRef.current ||
        computerVisionRequestRef.current ||
        video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
        !video.videoWidth ||
        !video.videoHeight
      ) {
        return;
      }

      computerVisionRequestRef.current = true;

      try {
        const canvas = document.createElement('canvas');
        const maxWidth = 640;
        const scale = Math.min(1, maxWidth / video.videoWidth);
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);

        const context = canvas.getContext('2d');
        if (!context) return;

        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        const blob = await new Promise((resolve) => {
          canvas.toBlob(resolve, 'image/jpeg', 0.65);
        });

        if (!blob || !assessmentActiveRef.current) return;

        const formData = new FormData();
        formData.append('file', blob, `frame-${Date.now()}.jpg`);

        const response = await api.post(
          `/candidate/first-round-assessments/${assignmentId}/proctoring/analyze-frame`,
          formData
        );

        const data = response.data || {};
        if (typeof data.warning_count === 'number') {
          setWarningCount(data.warning_count);
        }

        if (data.detected_violations?.length) {
          const labels = data.detected_violations.map((item) => {
            if (item === 'AI_PHONE_DETECTED') return 'Mobile phone detected';
            if (item === 'AI_MULTIPLE_PEOPLE_DETECTED') return 'Multiple people detected';
            return item.replaceAll('_', ' ').toLowerCase();
          });

          setAiDetectionMessage(
            `AI camera check noticed: ${labels.join(' and ')}. Please ensure your assessment area is clear.`
          );

          if (data.warning_recorded) {
            setLastWarning(`AI review suggested: ${labels.join(' and ')}`);
            playWarningBeep();
          }
        } else {
          setAiDetectionMessage(
            'AI monitoring is active. No flagged objects detected in this frame.'
          );
        }
      } catch (error) {
        const status = error.response?.status;
        if (status === 401 || status === 403 || status === 404) {
          console.error('AI proctoring request was rejected:', error);
          setAiDetectionMessage(
            error.response?.data?.detail || 'AI monitoring authorization failed.'
          );
          stopComputerVisionMonitoring();
        } else {
          console.warn('AI frame analysis request failed:', error);
          setAiDetectionMessage('AI monitoring temporarily unavailable.');
        }
      } finally {
        computerVisionRequestRef.current = false;
      }
    };

    setAiDetectionMessage('AI monitoring is active.');
    // Analyse one downscaled frame every 5 seconds to limit bandwidth and CPU.
    computerVisionTimerRef.current = setInterval(analyzeFrame, 5000);
    // Send an initial frame once the video is ready.
    analyzeFrame();
  };

  const initTest = async () => {
    if (!consentAccepted || !cameraReady || !streamRef.current) {
      setCameraError('Please accept the proctoring consent and enable your camera before starting.');
      return;
    }

    if (!getSupportedRecordingMimeType()) {
      setCameraError('Your browser does not support secure video recording. Please use an updated Chrome or Edge browser.');
      return;
    }

    setLoading(true);
    let serverRecordingStarted = false;
    try {
      // Persist consent and the browser camera-permission result first.
      // The assessment start endpoint must not be called if this request fails.
      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/proctoring/consent`,
        {
          consent_given: true,
          camera_permission_granted: true,
          consent_version: 'v1',
        }
      );

      // Confirm the camera track is still active immediately before starting.
      const activeVideoTrack = streamRef.current?.getVideoTracks?.()[0];
      if (!activeVideoTrack || activeVideoTrack.readyState !== 'live') {
        setCameraReady(false);
        throw new Error('Your camera is no longer active. Please enable your camera again.');
      }

      const res = await api.post(`/candidate/first-round-assessments/${assignmentId}/start`);

      // Start the server-side proctoring session, then begin MediaRecorder.
      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/proctoring/recording/start`
      );
      serverRecordingStarted = true;

      startBrowserRecording(streamRef.current);
      assessmentActiveRef.current = true;
      serverRecordingStarted = false;
      startComputerVisionMonitoring(streamRef.current);
      if (document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(() => {
          console.warn('Fullscreen mode was not enabled by the browser.');
        });
      }

      setTestData(res.data);
      setQuestions(res.data.questions || []);
      const initialAnswers = res.data.saved_answers || {};
      const initialReview = res.data.marked_for_review || [];
      savedAnswersRef.current = initialAnswers;
      markedForReviewRef.current = initialReview;
      answerSaveQueueRef.current = Promise.resolve();
      answerSaveErrorRef.current = null;
      setSavedAnswers(initialAnswers);
      setMarkedForReview(initialReview);

      const sec = res.data.remaining_seconds || 0;
      setRemainingSeconds(sec);
      startCountdown(sec);
    } catch (err) {
      // If the backend session started but MediaRecorder could not start,
      // reset the unuploaded server session so the candidate can retry.
      const recorderState = recorderRef.current?.state;
      if (serverRecordingStarted && recorderState !== 'recording') {
        try {
          await api.post(
            `/candidate/first-round-assessments/${assignmentId}/proctoring/recording/abort`
          );
          recorderRef.current = null;
          recordingUploadPromiseRef.current = null;
          recordingChunksRef.current = [];
          setRecordingActive(false);
          assessmentActiveRef.current = false;
        } catch (abortError) {
          console.error('Could not reset the failed recording session:', abortError);
        }
      }

      const message =
        err.response?.data?.detail ||
        err.message ||
        'Unable to save consent or start the assessment.';
      setCameraError(message);
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

  const queueAnswerSave = (payload) => {
    const request = answerSaveQueueRef.current.then(() =>
      api.post(
        `/candidate/first-round-assessments/${assignmentId}/save-answer`,
        payload
      )
    );

    answerSaveQueueRef.current = request.then(
      () => {
        answerSaveErrorRef.current = null;
      },
      (error) => {
        answerSaveErrorRef.current = error;
        console.error('Failed to sync assessment data:', error);
      }
    );

    return request;
  };

  const handleSelectOption = (optionLetter) => {
    if (submitLockRef.current) return;

    const currentQ = questions[currentIndex];
    if (!currentQ) return;

    const newAnswers = {
      ...savedAnswersRef.current,
      [currentQ.id]: optionLetter,
    };

    savedAnswersRef.current = newAnswers;
    setSavedAnswers(newAnswers);

    queueAnswerSave({
      question_id: currentQ.id,
      selected_option: optionLetter,
    }).catch(() => {});
  };

  const handleToggleReview = () => {
    if (submitLockRef.current) return;

    const currentQ = questions[currentIndex];
    if (!currentQ) return;

    const isMarked = markedForReviewRef.current.includes(currentQ.id);
    const newMarked = isMarked
      ? markedForReviewRef.current.filter((id) => id !== currentQ.id)
      : [...markedForReviewRef.current, currentQ.id];

    markedForReviewRef.current = newMarked;
    setMarkedForReview(newMarked);

    queueAnswerSave({
      question_id: currentQ.id,
      is_marked_for_review: !isMarked,
    }).catch(() => {});
  };

  const handleAutoSubmit = async () => {
    if (submitLockRef.current) return;

    submitLockRef.current = true;
    setAutoSubmitted(true);
    setSubmitting(true);

    try {
      await answerSaveQueueRef.current;
      await stopRecordingAndUpload();

      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/submit`,
        { final_answers: savedAnswersRef.current }
      );

      alert('Time is up! Your assessment has been automatically submitted.');
      navigate(`/candidate/assessment-result/${assignmentId}`, {
        replace: true,
      });
    } catch (error) {
      console.error('Automatic assessment submission failed:', error);

      submitLockRef.current = false;

      alert(
        error.response?.data?.detail ||
        'Recording upload or assessment submission failed. Your answers have not been submitted. Please retry or contact support.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinalSubmit = async () => {
    if (submitLockRef.current) return;

    submitLockRef.current = true;
    setSubmitting(true);

    try {
      await answerSaveQueueRef.current;
      await stopRecordingAndUpload();

      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/submit`,
        { final_answers: savedAnswersRef.current }
      );

      navigate(`/candidate/assessment-result/${assignmentId}`, {
        replace: true,
      });
    } catch (error) {
      console.error('Assessment submission failed:', error);

      submitLockRef.current = false;

      alert(
        error.response?.data?.detail ||
        'Recording upload or assessment submission failed. Your answers have not been submitted. Please retry or contact support.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (!testData) {
    return (
      <div style={{ maxWidth: '900px', margin: '36px auto', padding: '20px' }}>
        <div className="card" style={{ padding: 'clamp(22px, 4vw, 40px)', borderRadius: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '14px', background: 'var(--bg-lavender-white)', display: 'grid', placeItems: 'center', color: 'var(--primary-powder-blue-dark)' }}>
              <ShieldCheck size={26} />
            </div>
            <div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: 0 }}>SKILLSPHERE • SECURE ASSESSMENT</p>
              <h2 style={{ color: 'var(--text-primary)', fontSize: '1.45rem', fontWeight: 800, margin: '3px 0 0' }}>Before you begin</h2>
            </div>
          </div>

          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.65, margin: '16px 0 22px' }}>
            Please review the assessment and camera requirements. Your assessment timer will not start until you give consent, enable your camera, and select Start Assessment.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginBottom: '22px' }}>
            <div style={{ padding: '18px', border: '1px solid var(--border-color)', borderRadius: '12px' }}>
              <Camera size={22} color="var(--primary-powder-blue-dark)" />
              <h3 style={{ fontSize: '0.98rem', margin: '10px 0 6px', color: 'var(--text-primary)' }}>Camera required</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem', lineHeight: 1.55, margin: 0 }}>Keep your camera enabled and your face visible during the assessment.</p>
            </div>
            <div style={{ padding: '18px', border: '1px solid var(--border-color)', borderRadius: '12px' }}>
              <Video size={22} color="var(--primary-powder-blue-dark)" />
              <h3 style={{ fontSize: '0.98rem', margin: '10px 0 6px', color: 'var(--text-primary)' }}>Proctoring notice</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem', lineHeight: 1.55, margin: 0 }}>This assessment is intended to use camera monitoring and recording for proctoring and review.</p>
            </div>
            <div style={{ padding: '18px', border: '1px solid var(--border-color)', borderRadius: '12px' }}>
              <Clock size={22} color="var(--primary-powder-blue-dark)" />
              <h3 style={{ fontSize: '0.98rem', margin: '10px 0 6px', color: 'var(--text-primary)' }}>One timed attempt</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem', lineHeight: 1.55, margin: 0 }}>The timer starts only after you press Start Assessment. Existing attempt rules still apply.</p>
            </div>
          </div>

          <div style={{ background: 'var(--bg-lavender-white)', borderRadius: '12px', padding: '16px', marginBottom: '20px' }}>
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '11px', cursor: 'pointer', color: 'var(--text-primary)', lineHeight: 1.55, fontSize: '0.9rem' }}>
              <input
                type="checkbox"
                checked={consentAccepted}
                onChange={(event) => setConsentAccepted(event.target.checked)}
                style={{ width: '18px', height: '18px', marginTop: '2px', accentColor: 'var(--primary-powder-blue)', flexShrink: 0 }}
              />
              <span>I have read and understood the proctoring notice. I consent to camera monitoring and assessment recording for proctoring, integrity review, and authorized access by the relevant recruiter and platform administrators. I understand that recordings are retained for up to 30 days under the stated policy.</span>
            </label>
          </div>

          {cameraError && (
            <div role="alert" style={{ display: 'flex', gap: '9px', alignItems: 'flex-start', padding: '12px 14px', borderRadius: '10px', background: '#FEF2F2', color: '#B91C1C', fontSize: '0.86rem', marginBottom: '16px' }}>
              <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '1px' }} />
              <span>{cameraError}</span>
            </div>
          )}

          {cameraReady && (
            <div style={{ marginBottom: '18px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#047857', fontSize: '0.88rem', fontWeight: 700, marginBottom: '9px' }}>
                <CheckCircle size={18} /> Camera connected — preview below
              </div>
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                aria-label="Camera preview"
                style={{ display: 'block', width: '100%', maxWidth: '420px', aspectRatio: '16 / 9', objectFit: 'cover', background: '#111827', borderRadius: '12px', transform: 'scaleX(-1)' }}
              />
            </div>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', justifyContent: 'space-between', alignItems: 'center' }}>
            <button type="button" className="btn btn-outline" onClick={() => navigate('/candidate/first-round-assessments')}>
              <ChevronLeft size={16} /> Back to Assessments
            </button>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
              {!cameraReady ? (
                <button type="button" className="btn btn-primary" onClick={enableCamera} disabled={!consentAccepted || cameraStarting}>
                  <Camera size={16} /> {cameraStarting ? 'Requesting Camera...' : 'Allow Camera'}
                </button>
              ) : (
                <button type="button" className="btn btn-primary" onClick={initTest} disabled={!consentAccepted || loading}>
                  {loading ? 'Starting Assessment...' : 'Start Assessment'} <ChevronRight size={16} />
                </button>
              )}
            </div>
          </div>
          {!consentAccepted && (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', textAlign: 'right', margin: '10px 0 0' }}>Please accept the proctoring consent to continue.</p>
          )}
        </div>
      </div>
    );
  }

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
      {recordingError && (
        <div role="alert" style={{ display: 'flex', gap: '9px', alignItems: 'flex-start', padding: '12px 14px', borderRadius: '10px', background: '#FEF2F2', color: '#B91C1C', fontSize: '0.86rem', marginBottom: '14px' }}>
          <AlertTriangle size={18} style={{ flexShrink: 0, marginTop: '1px' }} />
          <span>{recordingError}</span>
        </div>
      )}
      {lastWarning && (
        <div
          role="alert"
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: '12px',
            padding: '11px 14px',
            borderRadius: '10px',
            background: '#FFF7ED',
            color: '#9A3412',
            border: '1px solid #FDBA74',
            marginBottom: '12px',
            fontSize: '0.86rem',
          }}
        >
          <span><strong>Proctoring warning:</strong> {lastWarning}</span>
          <strong>Warnings: {warningCount}</strong>
        </div>
      )}
      {aiDetectionMessage && (
        <div
          role="status"
          aria-live="polite"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '9px',
            padding: '10px 14px',
            borderRadius: '10px',
            background: '#EFF6FF',
            color: '#1D4ED8',
            border: '1px solid currentColor',
            opacity: 0.92,
            marginBottom: '12px',
            fontSize: '0.84rem',
          }}
        >
          <ShieldAlert size={17} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <span>{aiDetectionMessage}</span>
            <span style={{ fontSize: '0.78rem', opacity: 0.85 }}>
              AI detection may make mistakes. These alerts are automated indicators,
              not conclusive proof of misconduct. A human review may be required.
            </span>
          </div>
        </div>
      )}
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

        {/* Recording status and live timer */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div
            aria-live="polite"
            style={{ display: 'flex', alignItems: 'center', gap: '7px', color: recordingActive ? '#B91C1C' : '#64748B', fontSize: '0.82rem', fontWeight: 700 }}
          >
            <span style={{ width: '9px', height: '9px', borderRadius: '50%', background: recordingActive ? '#DC2626' : '#94A3B8', display: 'inline-block' }} />
            {recordingActive ? 'Recording' : 'Recording stopped'}
          </div>
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

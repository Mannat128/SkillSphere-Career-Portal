import React, { useState, useEffect, useLayoutEffect, useRef } from 'react';
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
  const [recordingUploading, setRecordingUploading] = useState(false);
  const [recordingUploadProgress, setRecordingUploadProgress] = useState(0);
  const [warningCount, setWarningCount] = useState(0);
  const [lastWarning, setLastWarning] = useState('');
  const [warningAudioStatus, setWarningAudioStatus] = useState('');
  const assessmentActiveRef = useRef(false);
  const intentionalStopRef = useRef(false);
  const lastViolationAtRef = useRef({});
  const warningAudioContextRef = useRef(null);
  const lastWarningBeepAtRef = useRef({});
  const fullscreenWasEnteredRef = useRef(false);
  const computerVisionTimerRef = useRef(null);
  const computerVisionVideoRef = useRef(null);
  const computerVisionRequestRef = useRef(false);
  const faceSignalStreakRef = useRef({ noFace: 0, lookingAway: 0 });
  const faceSignalLastReportedAtRef = useRef({ noFace: 0, lookingAway: 0 });
  const [aiDetectionMessage, setAiDetectionMessage] = useState('');
  const [testData, setTestData] = useState(null);
  const [assessmentInfo, setAssessmentInfo] = useState(null);
  const [availabilityAssignmentId, setAvailabilityAssignmentId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [savedAnswers, setSavedAnswers] = useState({});
  const savedAnswersRef = useRef({});
  const answerSaveQueueRef = useRef(Promise.resolve());
  const answerSaveErrorRef = useRef(null);
  const answerSaveFailuresRef = useRef(new Map());
  const [answerSyncStatus, setAnswerSyncStatus] = useState('saved');
  const [markedForReview, setMarkedForReview] = useState([]);
  const markedForReviewRef = useRef([]);
  const [remainingSeconds, setRemainingSeconds] = useState(0);

  // Submit Modal
  const [showSubmitModal, setShowSubmitModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [autoSubmitted, setAutoSubmitted] = useState(false);

  const timerRef = useRef(null);

  const releaseCameraPreview = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setCameraStream(null);
    setCameraReady(false);
  };

  const refreshAssessmentAvailability = async () => {
    try {
      const { data } = await api.get(`/candidate/first-round-assessments/${assignmentId}`);
      if (String(data?.assignment_id) !== String(assignmentId)) {
        throw new Error('The server returned availability for a different assessment assignment.');
      }
      setAssessmentInfo(data);
      setAvailabilityAssignmentId(assignmentId);
      if (!serverAllowsAssessmentAccess(data) && !assessmentActiveRef.current) releaseCameraPreview();
      return data;
    } catch (error) {
      setAssessmentInfo({
        assignment_id: null,
        is_available: false,
        can_start: false,
        can_resume: false,
        can_access_camera: false,
        availability_status: 'unverified',
        availability_message: error.message || 'Assessment availability could not be verified. Camera access is disabled until it can be checked.',
      });
      setAvailabilityAssignmentId(assignmentId);
      if (!assessmentActiveRef.current) releaseCameraPreview();
      throw error;
    }
  };

  const serverAllowsAssessmentAccess = (data) =>
    String(data?.assignment_id) === String(assignmentId)
    && data?.can_access_camera === true
    && (data?.can_start === true || data?.can_resume === true);

  const assessmentCanProceed = availabilityAssignmentId === assignmentId
    && serverAllowsAssessmentAccess(assessmentInfo);

  // React Router can reuse this page when only the assignment ID changes. Do
  // not carry a previously verified availability result, camera preview, or
  // attempt UI into the next assignment.
  useLayoutEffect(() => {
    assessmentActiveRef.current = false;
    if (timerRef.current) clearInterval(timerRef.current);
    releaseCameraPreview();
    setAssessmentInfo(null);
    setAvailabilityAssignmentId(null);
    setTestData(null);
    setQuestions([]);
    setSavedAnswers({});
    savedAnswersRef.current = {};
    setMarkedForReview([]);
    markedForReviewRef.current = [];
    setRemainingSeconds(0);
    setConsentAccepted(false);
    setCameraError('');
  }, [assignmentId]);

  const unlockWarningAudio = () => {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      setWarningAudioStatus('Warning sound is unavailable in this browser. Visual proctoring warnings remain active.');
      return Promise.resolve(false);
    }

    try {
      if (!warningAudioContextRef.current || warningAudioContextRef.current.state === 'closed') {
        warningAudioContextRef.current = new AudioContextClass();
      }
      const audioContext = warningAudioContextRef.current;
      // Resume synchronously within the user's camera/start click handler so
      // browser autoplay rules can associate activation with a user gesture.
      return audioContext.resume().then(() => {
        if (audioContext.state !== 'running') throw new Error('Audio context did not enter the running state.');
        setWarningAudioStatus('');
        return true;
      }).catch((error) => {
        console.warn('Proctoring warning audio could not be unlocked:', error);
        setWarningAudioStatus('Warning sound is blocked by the browser. Visual proctoring warnings remain active.');
        return false;
      });
    } catch (error) {
      console.warn('Proctoring warning audio is unavailable:', error);
      setWarningAudioStatus('Warning sound is unavailable. Visual proctoring warnings remain active.');
      return Promise.resolve(false);
    }
  };

  const playWarningBeep = (eventKey = 'general', cooldownMs = 2500) => {
    const now = Date.now();
    if (now - (lastWarningBeepAtRef.current[eventKey] || 0) < cooldownMs) return;
    lastWarningBeepAtRef.current[eventKey] = now;

    const scheduleTone = (audioContext) => {
      if (audioContext.state !== 'running') {
        setWarningAudioStatus('Warning sound is blocked by the browser. Visual proctoring warnings remain active.');
        return;
      }
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = 'sine';
      oscillator.frequency.value = 880;
      const startAt = audioContext.currentTime + 0.01;
      gain.gain.setValueAtTime(0.0001, startAt);
      gain.gain.exponentialRampToValueAtTime(0.12, startAt + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, startAt + 0.24);
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start(startAt);
      oscillator.stop(startAt + 0.25);
      oscillator.onended = () => {
        oscillator.disconnect();
        gain.disconnect();
      };
      setWarningAudioStatus('');
    };

    const audioContext = warningAudioContextRef.current;
    if (!audioContext || audioContext.state === 'closed') {
      setWarningAudioStatus('Warning sound is not ready. Use the assessment start controls to enable audio; visual warnings remain active.');
      return;
    }
    if (audioContext.state === 'suspended') {
      audioContext.resume().then(() => scheduleTone(audioContext)).catch((error) => {
        console.warn('Warning sound playback was blocked:', error);
        setWarningAudioStatus('Warning sound is blocked by the browser. Visual proctoring warnings remain active.');
      });
      return;
    }
    try {
      scheduleTone(audioContext);
    } catch (error) {
      console.warn('Warning sound could not be played:', error);
      setWarningAudioStatus('Warning sound could not be played. Visual proctoring warnings remain active.');
    }
  };

  const reportViolation = async (violationType, message) => {
    if (!assessmentActiveRef.current || submitLockRef.current) return;
    const now = Date.now();
    const previous = lastViolationAtRef.current[violationType] || 0;
    if (now - previous < 2500) return;
    lastViolationAtRef.current[violationType] = now;
    setLastWarning(message);
    playWarningBeep(violationType);
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
      if (warningAudioContextRef.current && warningAudioContextRef.current.state !== 'closed') {
        warningAudioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  useEffect(() => {
    if (testData) return undefined;
    let active = true;
    let boundaryTimer;
    const checkAvailability = async () => {
      try {
        const data = await refreshAssessmentAvailability();
        if (!active) return;
        const serverNow = Date.parse(data.availability_checked_at || '');
        const nextBoundary = [data.available_from, data.available_until]
          .map((value) => value ? Date.parse(value) : NaN)
          .filter((value) => Number.isFinite(value) && value > serverNow)
          .sort((a, b) => a - b)[0];
        if (Number.isFinite(serverNow) && nextBoundary) {
          boundaryTimer = window.setTimeout(checkAvailability, Math.max(500, nextBoundary - serverNow + 500));
        }
      } catch {
        // The UI remains fail-closed; the server start endpoint is authoritative.
      }
    };
    checkAvailability();
    return () => {
      active = false;
      if (boundaryTimer) window.clearTimeout(boundaryTimer);
    };
  }, [assignmentId, testData]);

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
    const audioTrack = cameraStream.getAudioTracks()[0];
    const handleMicrophoneEnded = () => reportViolation('MICROPHONE_DISCONNECTED', 'Microphone connection interrupted. Please reconnect it.');
    audioTrack?.addEventListener('ended', handleMicrophoneEnded);
    return () => {
      videoTrack?.removeEventListener('ended', handleCameraEnded);
      audioTrack?.removeEventListener('ended', handleMicrophoneEnded);
    };
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
    if (!assessmentCanProceed) {
      setCameraError(assessmentInfo?.availability_message || 'Checking assessment availability. Camera access is disabled until the check completes.');
      return;
    }
    setCameraError('');
    setCameraStarting(true);

    try {
      // Revalidate against the server immediately before asking the browser
      // for camera/microphone access. The page may have remained open across
      // the availability deadline, or a throttled tab may have delayed its
      // boundary timer.
      const currentAvailability = await refreshAssessmentAvailability();
      if (!serverAllowsAssessmentAccess(currentAvailability)) {
        releaseCameraPreview();
        setCameraError(currentAvailability.availability_message || 'This assessment is no longer available to start or resume.');
        return;
      }

      // This button is an explicit user gesture. Unlock audio before the
      // device-permission request so later warnings can play in the browser.
      void unlockWarningAudio();
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('Camera access is not supported by this browser. Please use an updated browser over HTTPS or localhost.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 24, max: 30 } },
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const availability = await refreshAssessmentAvailability();
      if (!serverAllowsAssessmentAccess(availability)) {
        releaseCameraPreview();
        setCameraError(availability.availability_message || 'This assessment is no longer available to start or resume.');
        return;
      }

      setCameraStream(stream);
      setCameraReady(true);
    } catch (error) {
      let message = 'Unable to access your camera. Please allow camera permission and try again.';
      if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
        message = 'Camera permission was denied. Please allow camera access in your browser settings, then try again.';
      } else if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') {
        message = 'No camera was found. Connect a camera to continue.';
      } else if (error.response || assessmentInfo?.availability_status === 'unverified') {
        message = 'Assessment availability could not be verified. Camera access remains disabled; retry when the service is available.';
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
      reportViolation('RECORDING_FAILURE', 'Assessment recording failed. Please contact support and do not leave the assessment.');
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
      setRecordingUploading(true);
      setRecordingUploadProgress(0);
      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/proctoring/recording/upload`,
        formData,
        {
          timeout: 0,
          onUploadProgress: (event) => {
            if (event.total) setRecordingUploadProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
          },
        }
      );

      recordingBlobRef.current = null;
      setRecordingUploadProgress(100);
      setRecordingError('');
      return true;
    } catch (error) {
      const message =
        error.response?.data?.detail ||
        error.message ||
        'Recording upload failed.';

      setRecordingError(message);
      throw error;
    } finally {
      setRecordingUploading(false);
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
    faceSignalStreakRef.current = { noFace: 0, lookingAway: 0 };
    faceSignalLastReportedAtRef.current = { noFace: 0, lookingAway: 0 };
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

        const now = Date.now();
        const confirmedFaceSignal = async (key, active, violationType, warningText) => {
          if (active) {
            faceSignalStreakRef.current[key] += 1;
          } else {
            faceSignalStreakRef.current[key] = 0;
          }
          const confirmed = faceSignalStreakRef.current[key] >= 2;
          const cooldownPassed = now - faceSignalLastReportedAtRef.current[key] >= 15000;
          if (confirmed && cooldownPassed) {
            faceSignalLastReportedAtRef.current[key] = now;
            await reportViolation(violationType, warningText);
          }
          return confirmed;
        };

        const noFaceConfirmed = await confirmedFaceSignal(
          'noFace',
          data.face_detected === false,
          'AI_NO_FACE_DETECTED',
          'No face has been detected for two consecutive camera checks. Check your framing and lighting.'
        );
        const lookingAwayConfirmed = await confirmedFaceSignal(
          'lookingAway',
          data.face_detected === true && data.looking_away_detected === true,
          'AI_LOOKING_AWAY_DETECTED',
          'Your head appears turned away from the camera across two checks. Please face the camera.'
        );

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
          }
          // The on-screen AI warning is useful even during the server-side
          // persistence cooldown, so pair the visible event with a locally
          // rate-limited sound as well.
          playWarningBeep('AI_CAMERA_DETECTION', 10000);
        } else if (noFaceConfirmed) {
          setAiDetectionMessage('No face detected across consecutive camera checks. Please check your framing and lighting. This is a review signal only.');
        } else if (lookingAwayConfirmed) {
          setAiDetectionMessage('Your head appears turned away across consecutive camera checks. Please face the camera. This is a review signal only.');
        } else if (data.face_detected === false) {
          setAiDetectionMessage('Face not clearly detected; checking the next camera frame before warning.');
        } else if (data.face_detected === true && data.looking_away_detected === true) {
          setAiDetectionMessage('Head orientation is unclear; checking the next camera frame before warning.');
        } else if (data.object_detection_available === false) {
          setAiDetectionMessage('Face checks are active, but phone and multiple-person detection is unavailable. Please notify the proctor.');
        } else {
          setAiDetectionMessage('AI monitoring is active. No flagged objects or head-orientation signals detected in this frame.');
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
    if (!consentAccepted || !cameraReady || !streamRef.current || !assessmentCanProceed) {
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
      const availability = await refreshAssessmentAvailability();
      if (!serverAllowsAssessmentAccess(availability)) {
        releaseCameraPreview();
        setCameraError(availability.availability_message || 'This assessment is no longer available to start or resume.');
        return;
      }
      // Persist consent and the browser camera-permission result first.
      // The assessment start endpoint must not be called if this request fails.
      await api.post(
        `/candidate/first-round-assessments/${assignmentId}/proctoring/consent`,
        {
          consent_given: true,
          camera_permission_granted: true,
          microphone_permission_granted: true,
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
      answerSaveFailuresRef.current.clear();
      setAnswerSyncStatus('saved');
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
    const deadline = Date.now() + Math.max(0, Number(initialSec) || 0) * 1000;
    let autoSubmitStarted = false;
    const updateRemaining = () => {
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      setRemainingSeconds(remaining);
      if (remaining === 0 && !autoSubmitStarted) {
        autoSubmitStarted = true;
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
        void handleAutoSubmit();
      }
    };
    updateRemaining();
    if (!autoSubmitStarted) timerRef.current = setInterval(updateRemaining, 1000);
  };

  const formatTimer = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const queueAnswerSave = (payload) => {
    const failureKey = payload.question_id == null
      ? `unknown:${Date.now()}`
      : `${payload.is_marked_for_review === undefined ? 'answer' : 'review'}:${payload.question_id}`;
    setAnswerSyncStatus('saving');
    const request = answerSaveQueueRef.current.then(() =>
      api.post(
        `/candidate/first-round-assessments/${assignmentId}/save-answer`,
        payload
      )
    );

    answerSaveQueueRef.current = request.then(
      () => {
        answerSaveFailuresRef.current.delete(failureKey);
        answerSaveErrorRef.current = answerSaveFailuresRef.current.size
          ? new Error('Some assessment data has not synchronized.')
          : null;
        setAnswerSyncStatus(answerSaveErrorRef.current ? 'error' : 'saved');
      },
      (error) => {
        answerSaveFailuresRef.current.set(failureKey, payload);
        answerSaveErrorRef.current = error;
        setAnswerSyncStatus('error');
        // Keep diagnostics free of request bodies and response content.
        console.error('Assessment answer synchronization failed.');
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
      if (answerSaveErrorRef.current) {
        setAnswerSyncStatus('error');
      }
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
      if (answerSaveErrorRef.current) {
        setAnswerSyncStatus('error');
      }
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
            Please review the assessment and camera and microphone requirements. Your timer will not start until you give consent, allow both devices, and select Start Assessment.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px', marginBottom: '22px' }}>
            <div style={{ padding: '18px', border: '1px solid var(--border-color)', borderRadius: '12px' }}>
              <Camera size={22} color="var(--primary-powder-blue-dark)" />
              <h3 style={{ fontSize: '0.98rem', margin: '10px 0 6px', color: 'var(--text-primary)' }}>Camera and microphone required</h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.84rem', lineHeight: 1.55, margin: 0 }}>Keep both devices enabled during the assessment. Video capture requests 720p where supported.</p>
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
            <label style={{ display: 'flex', alignItems: 'flex-start', gap: '11px', cursor: assessmentCanProceed ? 'pointer' : 'not-allowed', opacity: assessmentCanProceed ? 1 : 0.62, color: 'var(--text-primary)', lineHeight: 1.55, fontSize: '0.9rem' }}>
              <input
                type="checkbox"
                checked={consentAccepted}
                onChange={(event) => setConsentAccepted(event.target.checked)}
                disabled={!assessmentCanProceed || loading || cameraStarting}
                aria-describedby="assessment-availability-status"
                style={{ width: '18px', height: '18px', marginTop: '2px', accentColor: 'var(--primary-powder-blue)', flexShrink: 0 }}
              />
              <span>I have read and understood the proctoring notice. I consent to camera and microphone monitoring and assessment recording for proctoring and integrity review by the recruiter responsible for this job. I understand recordings are retained for up to 15 days after assessment submission.</span>
            </label>
          </div>

          {availabilityAssignmentId === assignmentId && !assessmentCanProceed && (
            <div id="assessment-availability-status" role="status" style={{ padding: '12px 14px', borderRadius: '10px', background: '#FFF7ED', color: '#9A3412', fontSize: '0.88rem', marginBottom: '16px' }}>
              {assessmentInfo?.availability_message || 'This assessment is not currently available. Camera and microphone access are disabled.'}
            </div>
          )}

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
                <button type="button" className="btn btn-primary" onClick={enableCamera} disabled={!consentAccepted || cameraStarting || !assessmentCanProceed} aria-describedby="assessment-availability-status" style={{ opacity: !consentAccepted || cameraStarting || !assessmentCanProceed ? 0.55 : 1, cursor: !consentAccepted || cameraStarting || !assessmentCanProceed ? 'not-allowed' : 'pointer' }}>
                  <Camera size={16} /> {cameraStarting ? 'Requesting Devices...' : 'Allow Camera and Microphone'}
                </button>
              ) : (
                <button type="button" className="btn btn-primary" onClick={initTest} disabled={!consentAccepted || loading || !assessmentCanProceed} aria-describedby="assessment-availability-status" style={{ opacity: !consentAccepted || loading || !assessmentCanProceed ? 0.55 : 1, cursor: !consentAccepted || loading || !assessmentCanProceed ? 'not-allowed' : 'pointer' }}>
                  {loading ? 'Starting Assessment...' : assessmentInfo?.can_resume ? 'Resume Assessment' : 'Start Assessment'} <ChevronRight size={16} />
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
      {warningAudioStatus && testData && (
        <div role="status" aria-live="polite" style={{ color: '#9A3412', fontSize: '0.8rem', marginBottom: '10px' }}>
          {warningAudioStatus}
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
            {recordingActive ? '🔴 REC' : recordingUploading ? `Uploading ${recordingUploadProgress}%` : 'Recording stopped'}
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

            <span
              role={answerSyncStatus === 'error' ? 'alert' : 'status'}
              aria-live="polite"
              style={{
                fontSize: '0.85rem',
                color: answerSyncStatus === 'error' ? '#B91C1C' : 'var(--text-muted)',
              }}
            >
              {answerSyncStatus === 'saving' && 'Saving answer…'}
              {answerSyncStatus === 'saved' && 'Answers saved'}
              {answerSyncStatus === 'error' && 'Answer save failed — retry selection; only server-saved answers are guaranteed'}
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

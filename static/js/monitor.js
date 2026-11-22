/**
 * monitor.js
 * ----------
 * AI-Based Anti-Cheating Monitoring & Proctoring System.
 *
 * Responsibilities:
 *   1. Access student's webcam stream.
 *   2. Capture frames and send to /api/monitor/frame for AI analysis.
 *   3. Parse separate metrics:
 *      - Face Detection (Detected, Missing, Multiple)
 *      - Eye Gaze Direction (Screen, Left, Right, Up, Down)
 *      - Head Orientation (Center, Turned Left/Right, Tilted Down/Up)
 *   4. Apply temporal smoothing/debouncing to eliminate jitter.
 *   5. Update proctoring status UI in real time.
 *   6. Track sustained suspicious behavior (requires >= threshold duration).
 *   7. Persist violations to /api/monitor/event and display warnings.
 */

// -------------------------------------------------------------------
// Constants & Configuration
// -------------------------------------------------------------------
const FRAME_INTERVAL_MS     = 650;   // Capture interval
const WARNING_DISPLAY_MS    = 4000;  // Overlay banner duration
const POST_EVENT_COOLDOWN_MS = 5000; // Cooldown after event fired
const LOOK_AWAY_THRESHOLD_MS = (EXAM_CONFIG.lookAwayThreshold || 3) * 1000;

// -------------------------------------------------------------------
// DOM Elements
// -------------------------------------------------------------------
const video          = document.getElementById('webcam-feed');
const canvas         = document.getElementById('capture-canvas');
const ctx            = canvas ? canvas.getContext('2d') : null;

const statFace       = document.getElementById('stat-face');
const statGaze       = document.getElementById('stat-gaze');
const statHead       = document.getElementById('stat-head');
const statMonitoring = document.getElementById('stat-monitoring');
const monitorBadge   = document.getElementById('monitor-badge');

const warningOverlay = document.getElementById('warning-overlay');
const warningTitle   = document.getElementById('warning-title');
const warningMsg     = document.getElementById('warning-message');
const warningCountEl = document.getElementById('warning-count');
const penaltyCountEl = document.getElementById('penalty-count');

// -------------------------------------------------------------------
// State
// -------------------------------------------------------------------
let monitoringActive     = false;
let mediaStream          = null;
let frameIntervalTimer   = null;
let suspiciousStartAt    = null;  // Timestamp when continuous suspicious behavior started
let currentViolationType = null;  // Current violation being timed
let inCooldown           = false; // Cooldown flag
let warningDismissTimer  = null;

// History buffer for temporal smoothing (last 3 frames)
const recentDetections = [];
const BUFFER_SIZE      = 3;

// -------------------------------------------------------------------
// 1. Webcam Initialisation
// -------------------------------------------------------------------
async function initWebcam() {
  updateStatusDisplay({
    faceText: 'Requesting...',
    faceClass: 'badge-warning',
    gazeText: 'Initialising...',
    headText: 'Initialising...',
    monitorText: 'Connecting...',
    monitorClass: 'badge-warning'
  });

  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: 'user'
      },
      audio: false
    });

    if (video) {
      video.srcObject = mediaStream;

      video.onloadedmetadata = () => {
        if (canvas) {
          canvas.width  = video.videoWidth  || 640;
          canvas.height = video.videoHeight || 480;
        }
        monitoringActive = true;
        updateStatusDisplay({
          faceText: '● Detected',
          faceClass: 'badge-success',
          gazeText: 'Looking at Screen',
          headText: 'Center',
          monitorText: 'Normal',
          monitorClass: 'badge-success'
        });

        // Start periodic frame capture
        if (frameIntervalTimer) clearInterval(frameIntervalTimer);
        frameIntervalTimer = setInterval(captureAndAnalyse, FRAME_INTERVAL_MS);
      };
    }
  } catch (err) {
    console.error('Camera access denied or unavailable:', err);
    updateStatusDisplay({
      faceText: '❌ Offline',
      faceClass: 'badge-danger',
      gazeText: 'Camera Denied',
      headText: 'Camera Denied',
      monitorText: 'Offline',
      monitorClass: 'badge-danger'
    });
    showOverlayWarning(
      '📷 Camera Required',
      'Webcam access is required for AI proctoring. Please enable your camera in browser settings.'
    );
  }
}

// -------------------------------------------------------------------
// 2. Stop Monitoring (Teardown on Exam Submit)
// -------------------------------------------------------------------
function stopMonitoring() {
  monitoringActive = false;
  if (frameIntervalTimer) {
    clearInterval(frameIntervalTimer);
    frameIntervalTimer = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop());
    mediaStream = null;
  }
  if (video) {
    video.srcObject = null;
  }
}

// -------------------------------------------------------------------
// 3. Periodic Frame Capture & API Call
// -------------------------------------------------------------------
async function captureAndAnalyse() {
  if (!monitoringActive || !video || video.readyState < 2 || !canvas || !ctx) return;

  // Render current video frame to offscreen canvas
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const b64Frame = canvas.toDataURL('image/jpeg', 0.65);

  try {
    const resp = await fetch(EXAM_CONFIG.monitorFrameUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        result_id: EXAM_CONFIG.resultId,
        frame: b64Frame
      })
    });

    if (!resp.ok) return;
    const detection = await resp.json();
    processDetection(detection);
  } catch (err) {
    console.warn('Proctoring frame analysis error:', err);
  }
}

// -------------------------------------------------------------------
// 4. Process Detection & Temporal Smoothing
// -------------------------------------------------------------------
function processDetection(raw) {
  if (!raw || raw.violation === 'FRAME_ERROR') return;

  // Add to rolling history buffer
  recentDetections.push(raw);
  if (recentDetections.length > BUFFER_SIZE) {
    recentDetections.shift();
  }

  // Smooth detection over buffer
  const smoothed = smoothDetection(recentDetections);

  // 1. Update UI Metrics Display
  updateProctoringUI(smoothed);

  // 2. State Machine for Sustained Violations
  handleViolationTiming(smoothed);
}

function smoothDetection(buffer) {
  const latest = buffer[buffer.length - 1];
  if (!latest) return latest;

  // Check face presence across buffer
  const missingCount  = buffer.filter(d => !d.face_detected).length;
  const multipleCount = buffer.filter(d => d.face_count > 1).length;

  if (missingCount >= 2) {
    return { ...latest, face_detected: false, face_count: 0, violation: 'FACE_MISSING', is_suspicious: true };
  }
  if (multipleCount >= 2) {
    return { ...latest, face_detected: true, face_count: 2, violation: 'MULTIPLE_FACES', is_suspicious: true };
  }

  // If face is present, smooth gaze and head pose
  return latest;
}

// -------------------------------------------------------------------
// 5. Update Proctoring Status UI
// -------------------------------------------------------------------
function updateProctoringUI(d) {
  let faceText  = '● Detected';
  let faceClass = 'badge-success';

  if (!d.face_detected) {
    faceText  = '❌ Missing';
    faceClass = 'badge-danger';
  } else if (d.face_count > 1) {
    faceText  = '⚠️ Multiple';
    faceClass = 'badge-danger';
  }

  let monitorText  = 'Normal';
  let monitorClass = 'badge-success';

  if (d.is_suspicious) {
    monitorText  = 'Suspicious';
    monitorClass = 'badge-warning';
  }

  updateStatusDisplay({
    faceText:     faceText,
    faceClass:    faceClass,
    gazeText:     d.gaze_label || 'Looking at Screen',
    headText:     d.head_label || 'Center',
    monitorText:  monitorText,
    monitorClass: monitorClass
  });
}

function updateStatusDisplay({ faceText, faceClass, gazeText, headText, monitorText, monitorClass }) {
  if (statFace) {
    statFace.textContent = faceText;
    statFace.className   = 'badge ' + faceClass;
  }
  if (statGaze) {
    statGaze.textContent = gazeText;
  }
  if (statHead) {
    statHead.textContent = headText;
  }
  if (statMonitoring) {
    statMonitoring.textContent = monitorText;
    statMonitoring.className   = 'badge ' + monitorClass;
  }
  if (monitorBadge) {
    monitorBadge.textContent = monitorText;
    monitorBadge.className   = 'badge ' + monitorClass;
  }
}

// -------------------------------------------------------------------
// 6. Timing & Warning Event Generation
// -------------------------------------------------------------------
function handleViolationTiming(d) {
  const violation = d.violation;

  // If behavior is normal, immediately reset suspicious timer
  if (!violation) {
    resetSuspiciousState();
    return;
  }

  const now = Date.now();

  // If violation type changed, restart timer
  if (currentViolationType !== violation) {
    suspiciousStartAt    = now;
    currentViolationType = violation;
  } else if (suspiciousStartAt === null) {
    suspiciousStartAt = now;
  }

  const sustainedDuration = now - suspiciousStartAt;

  // Fire event ONLY after continuous suspicious duration exceeds threshold
  if (sustainedDuration >= LOOK_AWAY_THRESHOLD_MS && !inCooldown) {
    fireViolationEvent(violation);
  }
}

function resetSuspiciousState() {
  suspiciousStartAt    = null;
  currentViolationType = null;
}

// -------------------------------------------------------------------
// 7. Fire Violation Event to Server
// -------------------------------------------------------------------
async function fireViolationEvent(violationType) {
  inCooldown = true;
  resetSuspiciousState();

  try {
    const resp = await fetch(EXAM_CONFIG.monitorEventUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        result_id:      EXAM_CONFIG.resultId,
        violation_type: violationType
      })
    });

    if (!resp.ok) return;
    const data = await resp.json();

    // Update counters in UI
    if (warningCountEl && data.warning_number !== undefined) {
      warningCountEl.textContent = data.warning_number;
    }
    if (penaltyCountEl && data.total_penalty !== undefined) {
      penaltyCountEl.textContent = data.total_penalty;
    }

    // Display warning overlay
    showOverlayWarning(
      `⚠️ Warning #${data.warning_number}`,
      data.message || 'Please focus on your screen.'
    );

  } catch (err) {
    console.error('Error logging violation event:', err);
  } finally {
    // Cooldown prevents rapid-fire warnings
    setTimeout(() => {
      inCooldown = false;
    }, POST_EVENT_COOLDOWN_MS);
  }
}

// -------------------------------------------------------------------
// 8. Warning Overlay Helper
// -------------------------------------------------------------------
function showOverlayWarning(title, message) {
  if (!warningOverlay || !warningTitle || !warningMsg) return;

  warningTitle.textContent = title;
  warningMsg.textContent   = message;
  warningOverlay.classList.add('show');

  clearTimeout(warningDismissTimer);
  warningDismissTimer = setTimeout(() => {
    warningOverlay.classList.remove('show');
  }, WARNING_DISPLAY_MS);
}

// -------------------------------------------------------------------
// Boot
// -------------------------------------------------------------------
initWebcam();

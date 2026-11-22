/**
 * exam.js
 * -------
 * Handles all client-side exam interactions:
 *   - Countdown timer with colour transitions
 *   - MCQ option selection & answered state tracking
 *   - Next / Previous question navigation
 *   - Question navigator grid updates
 *   - Auto-submit when time runs out
 *   - Confirmation modal & reliable exam submission
 */

// -------------------------------------------------------------------
// State
// -------------------------------------------------------------------
let currentQuestion  = 1;
const totalQuestions = EXAM_CONFIG.totalQuestions;
let totalSecondsLeft = EXAM_CONFIG.totalSeconds;
const answeredSet    = new Set();

// -------------------------------------------------------------------
// Initialise answered questions on page load
// -------------------------------------------------------------------
function initAnsweredState() {
  const panels = document.querySelectorAll('[id^="question-panel-"]');
  panels.forEach((panel, idx) => {
    const qIndex = idx + 1;
    const checkedRadio = panel.querySelector('input[type="radio"]:checked');
    if (checkedRadio) {
      answeredSet.add(qIndex);
      const navBtn = document.getElementById(`nav-btn-${qIndex}`);
      if (navBtn) navBtn.classList.add('answered');

      const label = checkedRadio.closest('.option-label');
      if (label) label.classList.add('selected');
    }
  });
}

// -------------------------------------------------------------------
// Timer
// -------------------------------------------------------------------
const timerEl    = document.getElementById('exam-timer');
const timerBarEl = document.getElementById('timer-bar');

function formatTime(seconds) {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

function updateTimer() {
  if (!timerEl || !timerBarEl) return;

  timerEl.textContent = formatTime(Math.max(0, totalSecondsLeft));

  const pct = (totalSecondsLeft / EXAM_CONFIG.totalSeconds) * 100;
  timerBarEl.style.width = Math.max(0, Math.min(100, pct)) + '%';

  // Colour transitions
  if (pct <= 10) {
    timerEl.className    = 'exam-timer danger';
    timerBarEl.className = 'progress-bar danger';
  } else if (pct <= 25) {
    timerEl.className    = 'exam-timer warning';
    timerBarEl.className = 'progress-bar warning';
  } else {
    timerEl.className    = 'exam-timer';
    timerBarEl.className = 'progress-bar';
  }

  if (totalSecondsLeft <= 0) {
    clearInterval(timerInterval);
    autoSubmit();
    return;
  }
  totalSecondsLeft--;
}

const timerInterval = setInterval(updateTimer, 1000);
updateTimer(); // Initial render

function autoSubmit() {
  alert('⏰ Time is up! Your exam will now be submitted.');
  executeSubmit();
}

// -------------------------------------------------------------------
// Question Navigation
// -------------------------------------------------------------------
function goToQuestion(index) {
  if (index < 1 || index > totalQuestions) return;

  // Hide all panels, show target
  const currentPanel = document.getElementById(`question-panel-${currentQuestion}`);
  const targetPanel  = document.getElementById(`question-panel-${index}`);

  if (currentPanel) currentPanel.style.display = 'none';
  if (targetPanel)  targetPanel.style.display  = 'block';

  // Update navigator active class
  const currentNav = document.getElementById(`nav-btn-${currentQuestion}`);
  const targetNav  = document.getElementById(`nav-btn-${index}`);

  if (currentNav) currentNav.classList.remove('current');
  if (targetNav)  targetNav.classList.add('current');

  currentQuestion = index;
}

// -------------------------------------------------------------------
// Option Selection
// -------------------------------------------------------------------
function selectOption(labelEl) {
  if (!labelEl) return;

  const panel = labelEl.closest('[id^="question-panel-"]');
  if (!panel) return;

  // Check the radio input inside the clicked label
  const radio = labelEl.querySelector('input[type="radio"]');
  if (radio) {
    radio.checked = true;
  }

  // Highlight active label and un-highlight siblings
  const labels = panel.querySelectorAll('.option-label');
  labels.forEach(l => l.classList.remove('selected'));
  labelEl.classList.add('selected');

  // Mark question as answered in the navigator grid
  const qIndex = parseInt(panel.id.replace('question-panel-', ''), 10);
  if (!isNaN(qIndex)) {
    answeredSet.add(qIndex);
    const navBtn = document.getElementById(`nav-btn-${qIndex}`);
    if (navBtn) navBtn.classList.add('answered');
  }
}

// -------------------------------------------------------------------
// Submit Modal & Submission Handler
// -------------------------------------------------------------------
function countUnanswered() {
  return Math.max(0, totalQuestions - answeredSet.size);
}

function openSubmitModal() {
  const unanswered = countUnanswered();
  const warnEl     = document.getElementById('unanswered-warning');
  const countEl    = document.getElementById('unanswered-count');
  const modalEl    = document.getElementById('submit-modal');

  if (warnEl && countEl) {
    if (unanswered > 0) {
      warnEl.style.display = 'block';
      countEl.textContent  = unanswered;
    } else {
      warnEl.style.display = 'none';
    }
  }

  if (modalEl) {
    modalEl.style.display = 'flex';
  }
}

function closeSubmitModal() {
  const modalEl = document.getElementById('submit-modal');
  if (modalEl) {
    modalEl.style.display = 'none';
  }
}

function executeSubmit() {
  const submitBtn = document.getElementById('confirm-submit-btn');
  if (submitBtn) {
    submitBtn.disabled    = true;
    submitBtn.textContent = 'Submitting...';
  }

  // Stop monitoring stream if active
  if (typeof stopMonitoring === 'function') {
    stopMonitoring();
  }

  // Direct submit on the form
  const form = document.getElementById('exam-form');
  if (form) {
    form.submit();
  }
}

// Initialise state on script load
document.addEventListener('DOMContentLoaded', initAnsweredState);
initAnsweredState();

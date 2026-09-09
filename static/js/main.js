const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const browseBtn = document.getElementById('browseBtn');
const videoUrlInput = document.getElementById('videoUrlInput');
const videoUrlBtn = document.getElementById('videoUrlBtn');
const progressBox = document.getElementById('progressBox');
const progressStep = document.getElementById('progressStep');
const progressFill = document.getElementById('progressFill');
const cancelBtn = document.getElementById('cancelBtn');
const errorBox = document.getElementById('errorBox');
const fileMeta = document.getElementById('fileMeta');
const fileNameEl = document.getElementById('fileName');
const fileStatsEl = document.getElementById('fileStats');
const tabsEl = document.getElementById('tabs');
const panel = document.getElementById('panel');
const resetBtn = document.getElementById('resetBtn');

let state = {
  cards: [], notes: [], quiz: [],
  cardIndex: 0, flipped: false,
  quizIndex: 0, quizScore: 0, quizAnswered: false,
};
let generationController = null;

const STEP_MESSAGES = {
  pdf: ['Reading the PDF…', 'Pulling out the text…', 'Finding the key ideas…', 'Building flashcards…', 'Writing a quiz…'],
  image: ['Reading the image…', 'Running OCR…', 'Finding the key ideas…', 'Building flashcards…', 'Writing a quiz…'],
  video_url: ['Looking for captions…', 'Transcribing audio (no captions found)…', 'Finding the key ideas…', 'Building flashcards…', 'Writing a quiz…'],
  default: ['Reading your file…', 'Extracting content…', 'Finding the key ideas…', 'Building flashcards…', 'Writing a quiz…'],
};

function kindFromFilename(name) {
  const ext = name.split('.').pop().toLowerCase();
  if (ext === 'pdf') return 'pdf';
  if (['png','jpg','jpeg','bmp','tiff','webp'].includes(ext)) return 'image';
  return 'default';
}

if (uploadZone && fileInput && browseBtn) {
  browseBtn.addEventListener('click', () => fileInput.click());
  uploadZone.addEventListener('click', (e) => { if (e.target !== browseBtn) fileInput.click(); });
  fileInput.addEventListener('change', (e) => { if (e.target.files[0]) handleFile(e.target.files[0]); });

  ['dragenter', 'dragover'].forEach(evt => uploadZone.addEventListener(evt, (e) => {
    e.preventDefault(); uploadZone.classList.add('drag');
  }));
  ['dragleave', 'drop'].forEach(evt => uploadZone.addEventListener(evt, (e) => {
    e.preventDefault(); uploadZone.classList.remove('drag');
  }));
  uploadZone.addEventListener('drop', (e) => {
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });
}

if (videoUrlBtn && videoUrlInput) {
  videoUrlBtn.addEventListener('click', () => {
    const url = videoUrlInput.value.trim();
    if (url) handleVideoUrl(url);
  });
  videoUrlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); videoUrlBtn.click(); }
  });
}

if (resetBtn) resetBtn.addEventListener('click', () => window.location.reload());

cancelBtn.addEventListener('click', () => {
  if (generationController) generationController.abort();
  generationController = null;
  progressBox.style.display = 'none';
  if (resetBtn) resetBtn.style.display = 'none';
  if (uploadZone) uploadZone.style.display = '';
  const urlZone = document.querySelector('.url-zone');
  if (urlZone) urlZone.style.display = '';
  const libraryCta = document.querySelector('.library-cta');
  if (libraryCta) libraryCta.style.display = '';
  if (fileInput) fileInput.value = '';
  if (videoUrlInput) videoUrlInput.value = '';
});

// If the server preloaded a past upload's study pack (viewing it from
// My Library), render it directly — skip the upload zone entirely.
function initFromPreload() {
  const data = window.PRELOADED_STUDY_PACK;
  if (!data) return false;

  state.cards = data.cards || [];
  state.notes = data.notes || [];
  state.quiz = data.quiz || [];

  if (uploadZone) uploadZone.style.display = 'none';
  progressBox.style.display = 'none';
  if (resetBtn) {
    resetBtn.style.display = 'inline';
    resetBtn.textContent = 'upload a new file';
  }

  // populate the dedicated library-item header (filename + local date/time)
  const nameEl = document.getElementById('libViewName');
  const dateEl = document.getElementById('libViewDate');
  if (nameEl) nameEl.textContent = data.sourceName || 'Saved study pack';
  if (dateEl) {
    if (data.uploadedAtIso) {
      const d = new Date(data.uploadedAtIso);
      dateEl.textContent = isNaN(d.getTime()) ? '' : d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
      });
    } else {
      dateEl.textContent = '';
    }
  }

  fileMeta.style.display = 'none'; // filename/date now shown in the header above instead

  tabsEl.style.display = 'flex';
  panel.style.display = 'block';
  renderTab('cards');
  return true;
}

if (!initFromPreload()) {
  // normal flow — upload zone stays visible, waiting for a file
}

function showError(msg) {
  progressBox.style.display = 'none';
  if (uploadZone) uploadZone.style.display = 'none';
  const urlZone = document.querySelector('.url-zone');
  if (urlZone) urlZone.style.display = 'none';
  errorBox.style.display = 'block';
  errorBox.innerHTML = msg + '<br><button onclick="window.location.reload()">Try again</button>';
}

// Shared by file uploads and video-URL submissions: shows progress, waits
// for the fetch to resolve, then renders the result (or an error).
async function processGeneration(kind, doFetch) {
  if (uploadZone) uploadZone.style.display = 'none';
  const urlZone = document.querySelector('.url-zone');
  if (urlZone) urlZone.style.display = 'none';
  const libraryCta = document.querySelector('.library-cta');
  if (libraryCta) libraryCta.style.display = 'none';
  progressBox.style.display = 'block';
  if (resetBtn) resetBtn.style.display = 'none';
  generationController = new AbortController();

  const messages = STEP_MESSAGES[kind] || STEP_MESSAGES.default;
  let stepIdx = 0;
  progressStep.textContent = messages[0];
  progressFill.style.width = '8%';

  // Fake incremental progress while we wait on the server —
  // real progress isn't observable over a single fetch/response cycle.
  const ticker = setInterval(() => {
    if (stepIdx < messages.length - 1) stepIdx++;
    progressStep.textContent = messages[stepIdx];
    const pct = 10 + (stepIdx / messages.length) * 80;
    progressFill.style.width = pct + '%';
  }, kind === 'video_url' ? 4000 : 1800);

  try {
    const response = await doFetch(generationController.signal);
    const data = await response.json();

    clearInterval(ticker);
    generationController = null;

    if (!response.ok) {
      showError(data.error || 'Something went wrong.');
      return;
    }

    state.cards = data.cards || [];
    state.notes = data.notes || [];
    state.quiz = data.quiz || [];

    progressFill.style.width = '100%';
    progressStep.textContent = 'Done';
    if (resetBtn) resetBtn.style.display = 'inline-flex';

    fileNameEl.textContent = data.sourceName || '';
    fileStatsEl.textContent = `${state.cards.length} cards · ${state.quiz.length} quiz questions`;

    setTimeout(() => {
      progressBox.style.display = 'none';
      fileMeta.style.display = 'flex';
      tabsEl.style.display = 'flex';
      panel.style.display = 'block';
      renderTab('cards');
    }, 250);

  } catch (err) {
    clearInterval(ticker);
    generationController = null;
    if (err.name === 'AbortError') return;
    console.error(err);
    showError('Could not reach the server. Is the Flask app running?');
  }
}

function handleFile(file) {
  const kind = kindFromFilename(file.name);
  processGeneration(kind, (signal) => {
    const formData = new FormData();
    formData.append('file', file);
    return fetch('/upload', { method: 'POST', body: formData, signal });
  });
}

function handleVideoUrl(url) {
  processGeneration('video_url', (signal) => {
    return fetch('/upload-url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
      signal,
    });
  });
}

tabsEl.addEventListener('click', (e) => {
  const btn = e.target.closest('.tab');
  if (!btn) return;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  renderTab(btn.dataset.tab);
});

function renderTab(tab) {
  if (tab === 'cards') renderCards();
  else if (tab === 'notes') renderNotes();
  else if (tab === 'quiz') renderQuiz();
}

function renderCards() {
  if (state.cards.length === 0) {
    panel.innerHTML = `<p style="color:var(--ink-soft);font-size:14px;">No flashcards could be generated from this file.</p>`;
    return;
  }
  const c = state.cards[state.cardIndex];
  const dots = state.cards.map((_, i) => `<span class="dot ${i === state.cardIndex ? 'on' : ''}"></span>`).join('');
  panel.innerHTML = `
    <div class="card-stage">
      <div class="index-card ${state.flipped ? 'flipped' : ''}" id="flipCard">
        <div class="index-card-inner">
          <div class="index-face front"><span class="card-tag">term</span><div class="txt">${escapeHtml(c.front)}</div></div>
          <div class="index-face back"><span class="card-tag">context</span><div class="txt">${escapeHtml(c.back)}</div></div>
        </div>
      </div>
      <div class="card-controls">
        <button class="nav-btn" id="prevCard" ${state.cardIndex === 0 ? 'disabled' : ''}>&#8592;</button>
        <div class="dots">${dots}</div>
        <button class="nav-btn" id="nextCard" ${state.cardIndex === state.cards.length - 1 ? 'disabled' : ''}>&#8594;</button>
      </div>
      <div class="hint">Tap the card to flip · ${state.cardIndex + 1} of ${state.cards.length}</div>
    </div>
  `;
  document.getElementById('flipCard').addEventListener('click', () => {
    state.flipped = !state.flipped;
    renderCards();
  });
  const prev = document.getElementById('prevCard');
  const next = document.getElementById('nextCard');
  if (prev) prev.addEventListener('click', (e) => { e.stopPropagation(); state.cardIndex--; state.flipped = false; renderCards(); });
  if (next) next.addEventListener('click', (e) => { e.stopPropagation(); state.cardIndex++; state.flipped = false; renderCards(); });
}

function renderNotes() {
  if (state.notes.length === 0) {
    panel.innerHTML = `<p style="color:var(--ink-soft);font-size:14px;">No notes could be generated from this file.</p>`;
    return;
  }
  panel.innerHTML = state.notes.map(n => `
    <div class="note-item">
      <div class="note-mark"></div>
      <div class="note-text">${escapeHtml(n)}</div>
    </div>
  `).join('');
}

function renderQuiz() {
  if (state.quiz.length === 0) {
    panel.innerHTML = `<p style="color:var(--ink-soft);font-size:14px;">No quiz could be generated from this file.</p>`;
    return;
  }
  if (state.quizIndex >= state.quiz.length) {
    panel.innerHTML = `
      <div class="quiz-score">
        <p class="big">${state.quizScore} / ${state.quiz.length}</p>
        <p>correct answers</p>
        <button class="retry-btn" id="retryQuiz">Retake quiz</button>
      </div>
    `;
    document.getElementById('retryQuiz').addEventListener('click', () => {
      state.quizIndex = 0; state.quizScore = 0; state.quizAnswered = false; renderQuiz();
    });
    return;
  }
  const q = state.quiz[state.quizIndex];
  panel.innerHTML = `
    <div class="quiz-progress">Question ${state.quizIndex + 1} of ${state.quiz.length}</div>
    <div class="quiz-q">${escapeHtml(q.question)}</div>
    <div id="options"></div>
    <div id="explainWrap"></div>
  `;
  const optionsWrap = document.getElementById('options');
  q.options.forEach((opt, i) => {
    const b = document.createElement('button');
    b.className = 'quiz-option';
    b.textContent = opt;
    b.addEventListener('click', () => selectAnswer(i));
    optionsWrap.appendChild(b);
  });
}

function selectAnswer(i) {
  if (state.quizAnswered) return;
  state.quizAnswered = true;
  const q = state.quiz[state.quizIndex];
  const buttons = document.querySelectorAll('.quiz-option');
  buttons.forEach((b, idx) => {
    b.disabled = true;
    if (idx === q.correctIndex) b.classList.add('correct');
    else if (idx === i) b.classList.add('incorrect');
  });
  if (i === q.correctIndex) state.quizScore++;
  const wrap = document.getElementById('explainWrap');
  wrap.innerHTML = `<div class="quiz-explain">${escapeHtml(q.explanation || '')}</div>
    <button class="quiz-next" id="nextQ">${state.quizIndex === state.quiz.length - 1 ? 'See score' : 'Next question'}</button>`;
  document.getElementById('nextQ').addEventListener('click', () => {
    state.quizIndex++;
    state.quizAnswered = false;
    renderQuiz();
  });
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str == null ? '' : String(str);
  return d.innerHTML;
}

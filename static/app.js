/* ═══════════════════════════════════════════════════════════════════════════
   Chromesthesia – Frontend Logic
   Handles: image upload, drag-and-drop, option selection, MIDI generation
   via POST /generate, and file download.
   ═══════════════════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── DOM refs ──────────────────────────────────────────────────────────────
  const uploadBox       = document.getElementById('uploadBox');
  const fileInput       = document.getElementById('fileInput');
  const previewSection  = document.getElementById('previewSection');
  const previewImg      = document.getElementById('previewImg');
  const removeBtn       = document.getElementById('removeBtn');
  const prefsSection    = document.getElementById('prefsSection');
  const generateSection = document.getElementById('generateSection');
  const generateBtn     = document.getElementById('generateBtn');
  const progressContainer = document.getElementById('progressContainer');
  const progressFill    = document.getElementById('progressFill');
  const progressLabel   = document.getElementById('progressLabel');
  const errorMsg        = document.getElementById('errorMsg');
  const successMsg      = document.getElementById('successMsg');
  const successMeta     = document.getElementById('successMeta');
  const modeSelect      = document.getElementById('modeSelect');
  const modeHint        = document.getElementById('modeHint');
  const scanCard        = document.getElementById('scanCard');

  // ── State ─────────────────────────────────────────────────────────────────
  let currentFile = null;
  let objectUrl   = null;

  // ── Mode hints ────────────────────────────────────────────────────────────
  const MODE_HINTS = {
    combined: 'Two-track MIDI: strings for chords, piano for melody.',
    chords:   'Single-track MIDI: chord progression on piano.',
    melody:   'Single-track MIDI: monophonic melody on piano.',
  };

  // ── Helpers ───────────────────────────────────────────────────────────────
  function show(el)  { el.style.display = ''; }
  function hide(el)  { el.style.display = 'none'; }
  function resetStatus() { hide(errorMsg); hide(successMsg); hide(progressContainer); }

  function revealSections() {
    show(previewSection);
    show(prefsSection);
    show(generateSection);
    // Smooth scroll to preview
    previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function hideSections() {
    hide(previewSection);
    hide(prefsSection);
    hide(generateSection);
  }

  // ── Image handling ────────────────────────────────────────────────────────
  function handleFile(file) {
    if (!file || !file.type.startsWith('image/')) return;

    // Clean previous
    if (objectUrl) URL.revokeObjectURL(objectUrl);

    currentFile = file;
    objectUrl = URL.createObjectURL(file);
    previewImg.src = objectUrl;

    resetStatus();
    revealSections();
  }

  function clearImage() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    currentFile = null;
    objectUrl = null;
    previewImg.src = '';
    fileInput.value = '';
    resetStatus();
    hideSections();
  }

  // ── Upload box interactions ───────────────────────────────────────────────
  uploadBox.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', (e) => {
    handleFile(e.target.files[0]);
  });

  uploadBox.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadBox.classList.add('drag-over');
  });

  uploadBox.addEventListener('dragleave', () => {
    uploadBox.classList.remove('drag-over');
  });

  uploadBox.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadBox.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    handleFile(file);
  });

  // ── Remove image ──────────────────────────────────────────────────────────
  removeBtn.addEventListener('click', clearImage);

  // ── Mode change: update hint + toggle scan path visibility ────────────────
  modeSelect.addEventListener('change', () => {
    const mode = modeSelect.value;
    modeHint.textContent = MODE_HINTS[mode] || '';
    // Scan path is relevant for all modes (server uses it for region sampling too)
    // but we can keep it visible always since the server accepts it for all modes
  });

  // ── Generate MIDI ─────────────────────────────────────────────────────────
  generateBtn.addEventListener('click', () => {
    if (!currentFile) return;

    const mode   = modeSelect.value;
    const key    = document.getElementById('keySelect').value;
    const scale  = document.getElementById('scaleSelect').value;
    const scan   = document.getElementById('scanPathSelect').value;
    const length = document.getElementById('lengthSelect').value;

    // UI: disable button, show progress
    generateBtn.disabled = true;
    generateBtn.textContent = 'Generating…';
    generateBtn.classList.add('is-loading');
    resetStatus();
    show(progressContainer);
    progressFill.style.width = '0%';
    progressLabel.textContent = 'Uploading image…';

    // Build form data matching server.py expectations
    const formData = new FormData();
    formData.append('image', currentFile);
    formData.append('mode', mode);
    formData.append('key', key);
    formData.append('scale', scale);
    formData.append('scan', scan);
    formData.append('chords', length);  // server uses this for n_chords and n_bars
    formData.append('stride', '4');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/generate');
    xhr.responseType = 'blob';

    // ── Upload progress (0–55%) ──────────────────────────────────────────
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        const pct = Math.round((e.loaded / e.total) * 55);
        progressFill.style.width = pct + '%';
        if (pct > 40) progressLabel.textContent = 'Processing pixels…';
      }
    };

    xhr.upload.onload = () => {
      progressFill.style.width = '55%';
      progressLabel.textContent = 'Mapping colors to notes…';
      // Simulate server-side stages
      setTimeout(() => {
        progressFill.style.width = '70%';
        progressLabel.textContent = 'Building ' + (mode === 'melody' ? 'melody…' : 'chord progression…');
      }, 400);
      setTimeout(() => {
        progressFill.style.width = '85%';
        progressLabel.textContent = 'Writing MIDI file…';
      }, 800);
    };

    // ── Response ─────────────────────────────────────────────────────────
    xhr.onload = () => {
      progressFill.style.width = '100%';
      progressLabel.textContent = 'Done!';

      if (xhr.status >= 200 && xhr.status < 300) {
        // Trigger download
        const blob = xhr.response;
        const downloadName = 'chromesthesia-' + mode + '-' + key + '-' + scale + '.mid';
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = downloadName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        // Show success
        setTimeout(() => {
          hide(progressContainer);
          show(successMsg);
          successMeta.textContent =
            mode.charAt(0).toUpperCase() + mode.slice(1) +
            ' · Key of ' + key + ' ' + scale +
            ' · ' + length + ' bars' +
            ' · ' + scan + ' scan' +
            ' · 120 BPM';
          finishLoading();
        }, 500);
      } else {
        // Parse error from JSON response
        const reader = new FileReader();
        reader.onload = () => {
          let msg = 'Generation failed';
          try {
            const data = JSON.parse(reader.result);
            msg = data.error || msg;
          } catch (_) { /* keep default */ }
          showError(msg);
        };
        reader.readAsText(xhr.response);
      }
    };

    xhr.onerror = () => {
      showError('Network error - is the server running on localhost:5000?');
    };

    xhr.send(formData);
  });

  function showError(msg) {
    hide(progressContainer);
    errorMsg.textContent = msg;
    show(errorMsg);
    finishLoading();
  }

  function finishLoading() {
    generateBtn.disabled = false;
    generateBtn.textContent = 'Generate MIDI';
    generateBtn.classList.remove('is-loading');
  }

})();

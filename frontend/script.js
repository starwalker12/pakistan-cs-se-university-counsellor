/*
 * Pakistan CS & SE University Counsellor — Frontend Logic
 *
 * Flow:
 * 1. User fills profile (name, system, marks, entry test, field, city, budget)
 * 2. User saves profile
 * 3. User asks a question in the chat
 * 4. Frontend sends profile + question to the FastAPI backend
 * 5. Backend retrieves relevant docs from Chroma DB (RAG)
 * 6. Backend sends context + profile to Ollama for final answer
 * 7. Answer is displayed in the chat
 */

// =============================================
// DOM references
// =============================================
const form            = document.getElementById('profileForm');
const saveBtn         = document.getElementById('saveProfileBtn');
const chatBox         = document.getElementById('chatBox');
const userInput       = document.getElementById('userInput');
const sendBtn         = document.getElementById('sendBtn');
const statusDot       = document.getElementById('statusDot');
const providerBadge   = document.getElementById('providerBadge');
const eduSystem       = document.getElementById('educationSystem');
const matricFields    = document.getElementById('matricFields');
const olevelFields    = document.getElementById('olevelFields');

const BACKEND_URL = 'http://localhost:8000';

let studentProfile = null;

// =============================================
// Education system toggle
// =============================================
eduSystem.addEventListener('change', function () {
  if (this.value === 'olevel') {
    matricFields.style.display = 'none';
    olevelFields.style.display = 'block';
  } else {
    matricFields.style.display = 'block';
    olevelFields.style.display = 'none';
  }
});

// =============================================
// Grade to percentage mapping
// =============================================
function gradeToPct(grade) {
  const map = { 'A*': 95, 'A': 90, 'B': 80, 'C': 70, 'D': 60, 'E': 50 };
  return map[grade] || 0;
}

// =============================================
// Save profile from form
// =============================================
saveBtn.addEventListener('click', function () {
  const name = document.getElementById('studentName').value.trim();
  const field = document.getElementById('preferredField').value;
  const system = eduSystem.value;

  if (!name) { alert('Please enter your name.'); return; }
  if (!field) { alert('Please select a preferred field.'); return; }

  let profile = {
    name: name,
    education_system: system,
    preferred_field: field,
    city_preference: document.getElementById('cityPref').value,
    budget: document.getElementById('budget').value.trim(),
    entry_test: document.getElementById('entryTest').value.trim(),
    matric_marks: '',
    inter_marks: '',
    o_level_equivalence: '',
    a_level_equivalence: '',
    o_level_grade: '',
    a_level_grade: ''
  };

  if (system === 'olevel') {
    profile.o_level_equivalence = document.getElementById('olevelEquivalence').value.trim();
    profile.a_level_equivalence = document.getElementById('alevelEquivalence').value.trim();
    profile.o_level_grade = document.getElementById('olevelGrade').value;
    profile.a_level_grade = document.getElementById('alevelGrade').value;

    if (!profile.o_level_equivalence && !profile.o_level_grade &&
        !profile.a_level_equivalence && !profile.a_level_grade) {
      alert('Please provide at least one O Level or A Level grade or equivalence percentage.');
      return;
    }

    let oPct = profile.o_level_equivalence ? parseFloat(profile.o_level_equivalence) : gradeToPct(profile.o_level_grade);
    let aPct = profile.a_level_equivalence ? parseFloat(profile.a_level_equivalence) : gradeToPct(profile.a_level_grade);

    if (profile.o_level_grade && !profile.o_level_equivalence && !oPct) {
      alert('Invalid O Level grade selected.');
      return;
    }
    if (profile.a_level_grade && !profile.a_level_equivalence && !aPct) {
      alert('Invalid A Level grade selected.');
      return;
    }

    profile.matric_marks = oPct ? String(oPct) : '';
    profile.inter_marks = aPct ? String(aPct) : '';

  } else {
    profile.matric_marks = document.getElementById('matricMarks').value.trim();
    profile.inter_marks = document.getElementById('interMarks').value.trim();

    if (!profile.matric_marks) { alert('Please enter your Matric percentage.'); return; }
    if (!profile.inter_marks) { alert('Please enter your Intermediate percentage.'); return; }
  }

  studentProfile = profile;

  userInput.disabled = false;
  sendBtn.disabled = false;
  statusDot.classList.remove('offline');
  statusDot.classList.add('online');

  addMessage('bot', 'Profile saved! You can now ask me about university admissions.');
});

// =============================================
// Format inline markdown: **text** -> <b>text</b>
// =============================================
function formatMarkdown(text) {
  let s = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  s = s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  s = s.replace(/\n/g, '<br>');
  return s;
}

// =============================================
// Add a message to the chat box
// =============================================
function addMessage(sender, text, isHTML) {
  const div = document.createElement('div');
  div.classList.add('message', sender);
  if (isHTML) {
    div.innerHTML = text;
  } else {
    div.innerHTML = formatMarkdown(text);
  }
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// =============================================
// Show / remove animated typing indicator
// =============================================
let typingEl = null;

function showTyping() {
  typingEl = document.createElement('div');
  typingEl.classList.add('message', 'bot', 'typing');
  typingEl.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  chatBox.appendChild(typingEl);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function hideTyping() {
  if (typingEl) {
    typingEl.remove();
    typingEl = null;
  }
}

// =============================================
// Add source card
// =============================================
function addSourceCard(source) {
  const card = document.createElement('div');
  card.classList.add('source-card');
  let html = '<div class="source-name">' + formatMarkdown(source.university_name) + '</div>';
  if (source.source_url) {
    const url = source.source_url.split(';')[0];
    html += '<div class="source-url">' + formatMarkdown(url) + '</div>';
  }
  if (source.preview) {
    html += '<div style="font-size:0.75rem;color:#5f7a6f;margin-top:4px;">' + formatMarkdown(source.preview.slice(0, 120)) + '</div>';
  }
  card.innerHTML = html;
  chatBox.appendChild(card);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// =============================================
// Add a backend offline banner
// =============================================
function addOfflineBanner() {
  const div = document.createElement('div');
  div.classList.add('backend-offline');
  div.innerHTML = 'Backend is not running. Please start the local server and try again.';
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// =============================================
// Sample question buttons
// =============================================
document.querySelectorAll('.sample-btn').forEach(function (btn) {
  btn.addEventListener('click', function () {
    userInput.value = btn.getAttribute('data-q');
    userInput.focus();
  });
});

// =============================================
// Handle sending a question to the backend
// =============================================
async function handleSend() {
  const question = userInput.value.trim();
  if (!question) return;

  userInput.value = '';
  addMessage('user', question);

  if (!studentProfile) {
    addMessage('bot', 'Please save your profile first before asking a question.');
    return;
  }

  showTyping();

  try {
    const response = await fetch(BACKEND_URL + '/counsel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: studentProfile,
        question: question
      })
    });

    hideTyping();

    if (!response.ok) {
      addMessage('bot', 'The backend returned an error (status ' + response.status + '). Make sure the FastAPI server is running on http://localhost:8000');
      return;
    }

    const data = await response.json();
    let msg = data.answer || 'Sorry, no answer was returned.';

    if (data.provider_used) {
      providerBadge.textContent = data.provider_used;
      providerBadge.classList.add('show');
    }

    addMessage('bot', msg);

    if (data.sources && data.sources.length > 0) {
      for (const s of data.sources) {
        addSourceCard(s);
      }
    }

  } catch (err) {
    hideTyping();
    addOfflineBanner();
  }
}

// =============================================
// Event listeners
// =============================================
sendBtn.addEventListener('click', handleSend);

userInput.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') {
    handleSend();
  }
});

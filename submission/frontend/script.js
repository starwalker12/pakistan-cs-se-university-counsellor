/*
 * Pakistan CS & SE University Counsellor — Frontend Logic
 *
 * Flow:
 * 1. User fills profile (name, matric, inter, entry test, field, city, budget)
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

const BACKEND_URL = 'http://localhost:8000';

// Student profile — will be filled when user clicks Save
let studentProfile = null;

// =============================================
// Save profile from form
// =============================================
saveBtn.addEventListener('click', function () {

  // --- Light validation ---
  const name      = document.getElementById('studentName').value.trim();
  const matric    = document.getElementById('matricMarks').value.trim();
  const inter     = document.getElementById('interMarks').value.trim();
  const field     = document.getElementById('preferredField').value;

  if (!name) {
    alert('Please enter your name.');
    return;
  }
  if (!matric) {
    alert('Please enter your Matric percentage.');
    return;
  }
  if (!inter) {
    alert('Please enter your Intermediate percentage.');
    return;
  }
  if (!field) {
    alert('Please select a preferred field (Computer Science or Software Engineering).');
    return;
  }

  // Build profile object and enable chat
  studentProfile = {
    name: name,
    matric_marks: matric,
    inter_marks: inter,
    entry_test: document.getElementById('entryTest').value.trim(),
    preferred_field: field,
    city_preference: document.getElementById('cityPref').value.trim(),
    budget: document.getElementById('budget').value.trim()
  };

  userInput.disabled = false;
  sendBtn.disabled = false;
  statusDot.classList.remove('offline');
  statusDot.classList.add('online');

  addMessage('bot', 'Profile saved! You can now ask me about university admissions.');
});

// =============================================
// Format inline markdown: **text** -> <b>text</b>
// Also escape HTML to prevent XSS, then re-add bold.
// =============================================
function formatMarkdown(text) {
  // Escape HTML first
  let s = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  // Convert **text** to <b>text</b> (non-greedy across lines)
  s = s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
  // Convert newlines to <br> for display
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
// Show / remove a typing indicator
// =============================================
let typingEl = null;

function showTyping() {
  typingEl = document.createElement('div');
  typingEl.classList.add('message', 'bot', 'typing');
  typingEl.textContent = 'Thinking...';
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

  // Validate empty question
  if (!question) return;

  // Show user's message
  userInput.value = '';
  addMessage('user', question);

  // Make sure profile was saved
  if (!studentProfile) {
    addMessage('bot', 'Please save your profile first before asking a question.');
    return;
  }

  // Show loading indicator
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

    // Show provider badge in header
    if (data.provider_used) {
      providerBadge.textContent = data.provider_used;
      providerBadge.classList.add('show');
    }

    // Show answer
    addMessage('bot', msg);

    // Show sources as cards
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

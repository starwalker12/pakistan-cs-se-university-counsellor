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
  statusDot.classList.add('online');

  addMessage('bot', 'Profile saved! You can now ask me about university admissions.');
});

// =============================================
// Add a message to the chat box
// =============================================
function addMessage(sender, text) {
  const div = document.createElement('div');
  div.classList.add('message', sender);
  div.textContent = text;
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
    if (data.provider_used) {
      msg += '\n\n---\n[Provider: ' + data.provider_used + ']';
    }
    addMessage('bot', msg);
    if (data.sources && data.sources.length > 0) {
      let srcText = 'Sources:\n';
      for (const s of data.sources) {
        srcText += '• ' + s.university_name + '\n';
        if (s.source_url) srcText += '  ' + s.source_url.split(';')[0] + '\n';
      }
      addMessage('bot', srcText);
    }

  } catch (err) {
    hideTyping();
    addMessage('bot', 'Could not reach the backend. Make sure the FastAPI server is running on http://localhost:8000');
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

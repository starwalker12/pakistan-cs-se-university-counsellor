/*
 * Pakistan CS & SE University Counsellor — Frontend Logic
 *
 * Phases:
 * 1. User fills profile (matric, inter, entry test, field, city, budget)
 * 2. User asks a question in the chat
 * 3. Frontend sends profile + question to the FastAPI backend
 * 4. Backend retrieves relevant docs from Chroma DB (RAG)
 * 5. Backend sends context + profile to Ollama for final answer
 * 6. Answer is displayed in the chat
 */

// DOM references
const profileForm = document.getElementById('profileForm');
const saveProfileBtn = document.getElementById('saveProfileBtn');
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

const BACKEND_URL = 'http://localhost:8000';

// Student profile object
let studentProfile = null;

// =============================================
// Save profile from form
// =============================================
saveProfileBtn.addEventListener('click', function () {
  studentProfile = {
    matric_marks: document.getElementById('matricMarks').value,
    inter_marks: document.getElementById('interMarks').value,
    entry_test: document.getElementById('entryTest').value,
    preferred_field: document.getElementById('preferredField').value,
    city_preference: document.getElementById('cityPref').value,
    budget: document.getElementById('budget').value
  };
  userInput.disabled = false;
  sendBtn.disabled = false;
  addMessage('bot', 'Profile saved. Now ask me a question about university admissions!');
});

// =============================================
// Add message to chat box
// =============================================
function addMessage(sender, text) {
  const div = document.createElement('div');
  div.classList.add('message', sender);
  div.textContent = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// =============================================
// Handle sending a question
// =============================================
async function handleSend() {
  const question = userInput.value.trim();
  if (!question) return;

  userInput.value = '';
  addMessage('user', question);

  if (!studentProfile) {
    addMessage('bot', 'Please save your profile first.');
    return;
  }

  // Show typing indicator
  const typing = document.createElement('div');
  typing.classList.add('message', 'bot');
  typing.textContent = 'Thinking...';
  chatBox.appendChild(typing);

  try {
    const response = await fetch(BACKEND_URL + '/counsel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        profile: studentProfile,
        question: question
      })
    });

    const data = await response.json();
    typing.remove();
    addMessage('bot', data.answer || 'Sorry, no answer received.');
  } catch (err) {
    typing.remove();
    addMessage('bot', 'Could not reach the backend. Make sure the FastAPI server is running on http://localhost:8000');
  }
}

// Event listeners
sendBtn.addEventListener('click', handleSend);
userInput.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') handleSend();
});

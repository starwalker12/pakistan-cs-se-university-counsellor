/*
 * University Admission Chatbot - Main JavaScript
 * 
 * How it works:
 * 1. User types a message and clicks Send (or presses Enter)
 * 2. JavaScript searches FAQ data (data/faq.json) for keyword matches
 * 3. If match found, uses it as context for the AI response
 * 4. Tries to connect to local Ollama (Gemma model) for a natural response
 * 5. If Ollama is not available, falls back to FAQ answer
 */

// DOM element references
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');

// FAQ data will be loaded from data/faq.json
let faqData = [];

// =============================================
// Load FAQ data from JSON file on page load
// =============================================
async function loadFAQ() {
  try {
    const response = await fetch('data/faq.json');
    faqData = await response.json();
    console.log('FAQ data loaded:', faqData.length, 'items');
  } catch (error) {
    console.error('Failed to load FAQ data:', error);
  }
}

// =============================================
// Add a message to the chat box
// =============================================
function addMessage(text, sender) {
  const messageDiv = document.createElement('div');
  messageDiv.classList.add('message', sender);
  messageDiv.textContent = text;
  chatBox.appendChild(messageDiv);
  // Auto-scroll to the latest message
  chatBox.scrollTop = chatBox.scrollHeight;
}

// =============================================
// Show typing indicator while waiting for response
// =============================================
function showTypingIndicator() {
  const indicator = document.createElement('div');
  indicator.classList.add('message', 'bot', 'typing');
  indicator.id = 'typingIndicator';
  indicator.textContent = 'Typing...';
  chatBox.appendChild(indicator);
  chatBox.scrollTop = chatBox.scrollHeight;
}

// =============================================
// Remove typing indicator
// =============================================
function removeTypingIndicator() {
  const indicator = document.getElementById('typingIndicator');
  if (indicator) indicator.remove();
}

// =============================================
// Search FAQ for matching questions by keywords
// =============================================
function searchFAQ(userMessage) {
  const lowerMessage = userMessage.toLowerCase();
  const keywords = lowerMessage.split(' ').filter(word => word.length > 2);

  let bestMatch = null;
  let bestScore = 0;

  for (const item of faqData) {
    let score = 0;
    const question = item.question.toLowerCase();
    const keywords = lowerMessage.split(' ').filter(word => word.length > 2);
    for (const keyword of keywords) {
      if (question.includes(keyword)) {
        score++;
      }
    }
    if (score > bestScore) {
      bestScore = score;
      bestMatch = item;
    }
  }

  return bestMatch;
}

// =============================================
// Get AI response from local Ollama (Gemma model)
// =============================================
async function getOllamaResponse(userMessage, faqContext) {
  // Build prompt with FAQ context if available
  let prompt = `You are a university admission assistant. Answer the following question helpfully and concisely.`;
  if (faqContext) {
    prompt += `\n\nUse this information to help answer:\nQ: ${faqContext.question}\nA: ${faqContext.answer}`;
  }
  prompt += `\n\nUser question: ${userMessage}`;

  try {
    const response = await fetch('http://localhost:11434/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gemma:2b',
        prompt: prompt,
        stream: false
      })
    });

    if (!response.ok) throw new Error('Ollama response error');

    const data = await response.json();
    return data.response.trim();
  } catch (error) {
    console.warn('Ollama not available, using FAQ fallback:', error.message);
    return null; // Signal fallback to FAQ
  }
}

// =============================================
// Handle sending a message
// =============================================
async function handleSend() {
  const message = userInput.value.trim();

  // Do not process empty messages
  if (message === '') return;

  // Clear input field
  userInput.value = '';

  // Add user message to chat
  addMessage(message, 'user');

  // Show typing indicator
  showTypingIndicator();

  // Search FAQ for matching content
  const faqMatch = searchFAQ(message);

  // Try to get AI response from Ollama
  let botReply = await getOllamaResponse(message, faqMatch);

  // If Ollama fails, use FAQ fallback
  if (!botReply) {
    if (faqMatch) {
      botReply = faqMatch.answer;
    } else {
      botReply = "I'm sorry, I don't have an answer for that right now. Please contact the admissions office directly for more details.";
    }
  }

  // Remove typing indicator and show bot response
  removeTypingIndicator();
  addMessage(botReply, 'bot');
}

// =============================================
// Event listeners
// =============================================

// Send button click
sendBtn.addEventListener('click', handleSend);

// Enter key also sends message
userInput.addEventListener('keypress', function (event) {
  if (event.key === 'Enter') {
    handleSend();
  }
});

// =============================================
// Initialize - load FAQ and show welcome message
// =============================================
loadFAQ().then(() => {
  addMessage("Hello! I'm the University Admission Assistant. Ask me anything about applications, deadlines, programs, or requirements.", 'bot');
});

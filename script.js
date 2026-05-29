/*
 * University Admission Chatbot - Main JavaScript
 * 
 * How it works:
 * 1. User types a message and clicks Send (or presses Enter)
 * 2. JavaScript loads FAQ data from data/faq.json
 * 3. The searchFAQ function does simple keyword matching:
 *    - Splits user message into individual words
 *    - Counts how many words match each FAQ's question and keywords array
 *    - Returns the best matching FAQ entry
 * 4. If a good FAQ match is found, its answer is used as context
 * 5. JavaScript tries to connect to local Ollama (Gemma model) for an AI response
 * 6. If Ollama is not available, it falls back to the FAQ answer directly
 * 7. If no FAQ match exists and Ollama fails, a default fallback message is shown
 */

// DOM element references
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const quickBtns = document.querySelectorAll('.quick-btn');

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
// Simple keyword matching search (Light RAG)
// =============================================
// How it works:
// 1. Take the user's message and split it into individual words
// 2. For each FAQ in faqDataset, check how many user words match
//    - The FAQ question text
//    - Any keyword in the FAQ's keywords array
// 3. The FAQ with the highest match score is returned
// 4. This is simple counting - no AI, no embeddings, no training needed
// =============================================
function searchFAQ(userMessage) {
  // Convert user message to lowercase and split into words
  // Filter out very short words (like "is", "am", "to") that aren't useful for matching
  const userWords = userMessage.toLowerCase().split(' ').filter(word => word.length > 2);

  let bestMatch = null;
  let bestScore = 0;

  // Loop through each FAQ entry in the dataset
  for (const item of faqData) {
    let score = 0;

    // Convert the FAQ question to lowercase for case-insensitive matching
    const questionText = item.question.toLowerCase();

    // Check if any user word appears in the question text
    for (const word of userWords) {
      if (questionText.includes(word)) {
        score++;
      }
    }

    // Also check if any user word matches the predefined keywords array
    // The keywords array contains the most important search terms for this FAQ
    if (item.keywords) {
      for (const keyword of item.keywords) {
        const lowerKeyword = keyword.toLowerCase();
        for (const word of userWords) {
          if (word === lowerKeyword || lowerKeyword.includes(word)) {
            score++;
          }
        }
      }
    }

    // Keep track of the FAQ with the highest score
    if (score > bestScore) {
      bestScore = score;
      bestMatch = item;
    }
  }

  // Return the best matching FAQ (or null if no match found)
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

  // Step 1: Search FAQ using simple keyword matching (Light RAG)
  // This finds the FAQ entry whose question/keywords best match the user's message
  const faqMatch = searchFAQ(message);

  // Step 2: Try to get AI response from local Ollama (Gemma model)
  // The FAQ match is passed as context so Ollama can give a better answer
  let botReply = await getOllamaResponse(message, faqMatch);

  // Step 3: FAQ fallback - if Ollama is not available or fails
  // If a FAQ match was found, show that answer directly
  // If no match was found, show a default fallback message
  if (!botReply) {
    if (faqMatch) {
      // Use the FAQ answer as the bot reply (Ollama was not available)
      botReply = faqMatch.answer;
    } else {
      // No FAQ match and Ollama not available - show fallback
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
// Quick question buttons - click sends that question
// =============================================
quickBtns.forEach(function (btn) {
  btn.addEventListener('click', function () {
    const question = btn.getAttribute('data-question');
    userInput.value = question;
    handleSend();
  });
});

// =============================================
// Initialize - load FAQ and show welcome message
// =============================================
loadFAQ().then(() => {
  addMessage("Hello! I'm the University Admission Assistant. Ask me anything about applications, deadlines, programs, or requirements.", 'bot');
});

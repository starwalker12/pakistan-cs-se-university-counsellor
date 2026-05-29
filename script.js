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
 * 7. If on localhost, calls local Ollama (gemma4:latest) for AI response
 8. If on Vercel (or any other domain), calls /api/chat serverless function
 9. The /api/chat function uses OpenRouter API to get an AI response
10. If AI fails for any reason, falls back to FAQ answer
11. If no FAQ match exists and AI fails, a default fallback message is shown
 */

// DOM element references
const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const quickBtns = document.querySelectorAll('.quick-btn');

// FAQ data will be loaded from data/faq.json
let faqData = [];

// Prevents multiple rapid sends (race condition guard)
let isProcessing = false;

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
// Build prompt for the AI model
// =============================================
// Takes the user's question and any FAQ context we found.
// Creates a clear instruction for the AI model to follow.
// The prompt tells the model to:
//   - Act as a university admission assistant
//   - Use FAQ context if available
//   - Give a general helpful answer if FAQ context is not enough
//   - Keep answers short and simple
// =============================================
function buildPrompt(userMessage, faqContext) {
  // Start with the system instruction
  let prompt = "You are a helpful university admission assistant.\n";
  prompt += "Answer in simple and clear English.\n";
  prompt += "Keep answers short.\n";

  // If we found a matching FAQ entry, include it as context
  // This helps the AI give a more accurate answer
  if (faqContext) {
    prompt += "Use the following FAQ information if it is useful:\n";
    prompt += "Question: " + faqContext.question + "\n";
    prompt += "Answer: " + faqContext.answer + "\n";
    prompt += "If the FAQ context does not fully answer the question, give a general helpful answer.\n";
  }

  // Add the user's actual question at the end
  prompt += "\nUser question: " + userMessage;

  return prompt;
}

// =============================================
// Call Ollama API with a prompt
// =============================================
// Sends the prompt to the local Ollama server running on the same machine.
// Uses the Gemma model (gemma4:latest) which must be installed locally.
// If Ollama is not running or returns an error, returns null so the
// code can fall back to FAQ answers.
// =============================================
async function callOllama(prompt) {
  try {
    // Send POST request to Ollama's API endpoint
    const response = await fetch('http://localhost:11434/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gemma4:latest',
        prompt: prompt,
        stream: false
      })
    });

    // If the server returned an error, throw to trigger fallback
    if (!response.ok) throw new Error('Ollama server returned error');

    // Parse the JSON response and return the generated text
    const data = await response.json();
    return data.response.trim();
  } catch (error) {
    // Log the error for debugging, then return null to trigger FAQ fallback
    console.warn('Ollama not available, using FAQ fallback:', error.message);
    return null;
  }
}

// =============================================
// Call online AI via Vercel serverless function
// =============================================
// This function sends the prompt to our own /api/chat endpoint.
// The /api/chat endpoint (running on Vercel's server) then calls OpenRouter.
// This way the API key stays on the server and never reaches the browser.
// If the serverless function is not available, returns null for FAQ fallback.
// =============================================
async function callOnlineAI(userMessage, faqContext) {
  try {
    // Send a POST request to our serverless API endpoint
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        userMessage: userMessage,
        faqContext: faqContext
      })
    });

    // If the server returned an error, throw to trigger fallback
    if (!response.ok) throw new Error('Serverless function returned error');

    // Parse the JSON response and return the AI's reply
    const data = await response.json();
    return data.reply.trim();
  } catch (error) {
    // Log the error, then return null to trigger FAQ fallback
    console.warn('Online AI not available, using FAQ fallback:', error.message);
    return null;
  }
}

// =============================================
// Check if the website is running on localhost
// =============================================
// This determines which AI to use:
// - Localhost: use Ollama (local model)
// - Any other domain (Vercel, etc.): use /api/chat (online AI)
// =============================================
function isLocalhost() {
  const host = window.location.hostname;
  return host === 'localhost' || host === '127.0.0.1';
}

// =============================================
// Handle sending a message
// =============================================
async function handleSend() {
  const message = userInput.value.trim();

  // Do not process empty messages
  if (message === '') return;

  // Prevent sending a new message while another is still processing
  if (isProcessing) return;
  isProcessing = true;

  // Clear input field
  userInput.value = '';

  // Add user message to chat
  addMessage(message, 'user');

  // Show typing indicator
  showTypingIndicator();

  // Step 1: Search FAQ using simple keyword matching (Light RAG)
  // This finds the FAQ entry whose question/keywords best match the user's message
  const faqMatch = searchFAQ(message);

  // Step 2: Try to get AI response
  // If running on localhost, use local Ollama (Gemma model)
  // If running on Vercel or any other domain, use /api/chat (online AI via OpenRouter)
  let botReply;
  if (isLocalhost()) {
    // Running locally - build prompt and send to Ollama
    const prompt = buildPrompt(message, faqMatch);
    botReply = await callOllama(prompt);
  } else {
    // Running on Vercel (or other domain) - call serverless API
    botReply = await callOnlineAI(message, faqMatch);
  }

  // Step 3: FAQ fallback - if AI is not available or fails
  if (!botReply) {
    if (faqMatch) {
      // Ollama was not available but we have a FAQ match
      // Show the FAQ answer with a clear label
      botReply = "I found this from our FAQ:\n" + faqMatch.answer;
    } else {
      // No FAQ match and Ollama not available - show fallback
      botReply = "Sorry, I could not find an answer. Please contact the admission office.";
    }
  }

  // Remove typing indicator and show bot response
  removeTypingIndicator();
  addMessage(botReply, 'bot');

  // Allow sending new messages again
  isProcessing = false;
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

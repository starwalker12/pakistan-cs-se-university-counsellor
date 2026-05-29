# University Admission Chatbot — Project Report

**Team Members:** Raahim Adeel, Fardan Aatir, Muhammad Ismail

**Live Website:** https://university-admission-chatbot.vercel.app

---

## 1. Introduction

The University Admission Chatbot is a simple web-based chatbot that helps students get answers to common university admission questions. It uses keyword matching to search a stored FAQ dataset and can also generate AI-powered responses using either a local model (Ollama with Gemma) or an online API (OpenRouter).

## 2. Problem Statement

University admission offices receive hundreds of similar questions every day from prospective students. Answering each question individually takes a lot of time. Students also want answers quickly, even outside office hours. A chatbot that runs 24/7 can solve this problem by providing instant answers to common admission queries.

## 3. Project Goal

Build a simple, working chatbot website that:
- Answers admission-related questions using stored FAQ data
- Uses AI for more natural responses when available
- Works locally on a laptop and also when deployed online
- Falls back to FAQ answers if AI is not available
- Has a clean, student-friendly interface

## 4. System Workflow

1. User opens the website and types a question (or clicks a quick question button)
2. The JavaScript code searches the FAQ dataset using keyword matching
3. The best matching FAQ entry (if found) is saved as context
4. If running on localhost, the code tries to call Ollama (Gemma model)
5. If running on Vercel, the code calls a serverless function that uses OpenRouter API
6. If AI responds, the answer is shown in the chat
7. If AI fails, the FAQ answer is shown instead
8. If no FAQ match is found and AI fails, a default fallback message is shown

## 5. Technologies Used

| Technology | Role in Project |
|---|---|
| HTML | Creates the page structure (header, chat box, input area, buttons) |
| CSS | Styles the page with a university theme, responsive layout |
| JavaScript | Handles all chat logic, FAQ search, API calls, and UI updates |
| JSON | Stores 25 FAQ entries with questions, answers, keywords, and categories |
| Ollama + Gemma | Local AI model that runs on the developer's laptop |
| OpenRouter API | Online AI service called from the Vercel serverless function |
| Vercel | Hosts the website and runs the serverless function |
| Git / GitHub | Version control and code hosting |

## 6. RAG (Retrieval-Augmented Generation) Explanation

RAG is a simple way to make AI answers more accurate. Instead of sending only the user question to the AI, we first search for relevant information (retrieval) and then send both the question and the found information to the AI (generation).

In this project, RAG works like this:
- **Retrieval:** When a user asks a question, JavaScript searches the FAQ dataset by counting matching keywords between the user message and each FAQ's question and keywords array. The FAQ with the most matches is selected.
- **Augmentation:** The selected FAQ question and answer are added to the prompt that is sent to the AI model.
- **Generation:** The AI uses both the FAQ context and the user question to generate a final answer.

This is a simple form of RAG. We do not use vector databases, embeddings, or any advanced machine learning. The retrieval is done entirely through basic word matching.

## 7. AI Integration

The project has two AI paths:

### Local AI (Ollama + Gemma)
- Only works on the developer's laptop
- Requires Ollama to be installed with the Gemma model
- JavaScript calls the Ollama API directly at http://localhost:11434
- Browser CORS may block this; the chatbot falls back to FAQ automatically

### Online AI (OpenRouter)
- Works on the live Vercel website
- JavaScript calls /api/chat (a Vercel serverless function)
- The serverless function calls OpenRouter API using an environment variable for the key
- The API key is never exposed in the browser

Both paths use the same prompt structure and both produce AI answers. If either fails, the FAQ fallback is used.

## 8. Testing Summary

All features were tested and passed:
- Page loads correctly with no console errors
- FAQ data (25 entries) loads correctly
- User can type messages and press Send or Enter
- Empty messages are rejected
- User and bot messages appear on opposite sides
- Quick question buttons work
- FAQ keyword search finds correct matches
- Ollama API responds (when running)
- OpenRouter API responds (when key is set)
- FAQ fallback works when AI is unavailable
- Empty message, no match, and rapid send edge cases handled
- Responsive design works on desktop and mobile

## 9. Limitations

- The keyword matching search is simple word counting. It does not understand synonyms or sentence meaning.
- Local Ollama only works on the developer's laptop. It cannot run on Vercel.
- OpenRouter API requires an API key and internet connection.
- Without an API key, the live website only answers from FAQ data.
- The chatbot does not remember previous messages (no conversation memory).

## 10. Future Improvements

- Add conversation memory so the chatbot can follow multi-turn conversations
- Improve the search to handle synonyms and misspellings
- Add support for more AI providers (Google Gemini, Claude, etc.)
- Add a feedback system so users can rate answers
- Add support for multiple languages
- Add an admin panel to manage FAQ data from the web interface

## 11. Conclusion

The University Admission Chatbot successfully demonstrates a simple AI-powered chatbot that works both locally and online. It uses basic keyword matching for retrieval, supports two AI backends (local Ollama and online OpenRouter), and gracefully falls back to FAQ answers when AI is unavailable. The project is deployed live on Vercel and the source code is available on GitHub.

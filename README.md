# University Admission Chatbot

**Team Members:** Raahim Adeel, Fardan Aatir, Muhammad Ismail

**Live Website:** https://university-admission-chatbot.vercel.app

**GitHub Repository:** https://github.com/starwalker12/university-admission-chatbot

## Project Purpose

A simple AI-powered chatbot that helps students get answers to university admission questions. Students can ask about how to apply, required documents, deadlines, fee structure, programs, scholarships, and more. The chatbot answers using either an AI model or stored FAQ data.

## Features

- Web-based chat interface
- FAQ dataset with 25 university admission questions
- Keyword matching search to find relevant FAQ answers
- Local AI mode using Ollama with Gemma model (on your laptop)
- Online AI mode using OpenRouter API through Vercel (on the live website)
- Automatic fallback to FAQ when AI is not available
- Clean, student-friendly user interface
- Quick question buttons for common queries

## Technology Stack

| Technology | Purpose |
|---|---|
| HTML | Page structure and layout |
| CSS | Styling and responsive design |
| JavaScript | Chat logic, FAQ search, API calls |
| JSON | FAQ data storage |
| Ollama + Gemma | Local AI model (laptop only) |
| OpenRouter API | Online AI model (Vercel only) |
| Vercel | Website hosting and serverless functions |

## Folder Structure

```
├── index.html            Main HTML page
├── style.css             Styling for the chat interface
├── script.js             Chatbot logic
├── api/
│   └── chat.js           Vercel serverless function for online AI
├── data/
│   └── faq.json          FAQ dataset (25 questions)
├── docs/
│   ├── report.md         Project report
│   ├── presentation-outline.md  Presentation slides outline
│   └── testing.md        Testing report
├── .env.example          Environment variable template
├── vercel.json           Vercel deployment config
└── README.md             This file
```

## How to Run Locally

### Step 1: Start a local server
```bash
python3 -m http.server 8000
```

### Step 2: Open in browser
Go to http://localhost:8000

The chatbot will work with FAQ fallback immediately. AI features are optional.

## How Local Ollama AI Works (Laptop Only)

1. Install Ollama from https://ollama.ai
2. Download the Gemma model:
   ```bash
   ollama pull gemma4:latest
   ```
3. Run the Ollama server:
   ```bash
   ollama serve
   ```
4. When you visit http://localhost:8000, the chatbot will detect it is running locally and call Ollama directly for AI responses.

If your browser blocks the Ollama request (CORS error), run Ollama with:
```bash
OLLAMA_ORIGINS=* ollama serve
```

## How Online OpenRouter AI Works (Vercel)

When you visit the live website at https://university-admission-chatbot.vercel.app, the chatbot detects it is not on localhost. Instead of calling Ollama, it calls a serverless function at `/api/chat`. This function sends the question to OpenRouter API and returns the AI answer.

The API key is stored as a Vercel environment variable. It never appears in the browser code.

## How FAQ Fallback Works

If AI is not available (Ollama not running locally, or OpenRouter API key not set on Vercel), the chatbot automatically shows the best matching FAQ answer. It searches the FAQ dataset by counting how many words match between the user question and each FAQ entry's question and keywords.

## Important Note About API Key Security

- The OpenRouter API key is stored only in Vercel environment variables
- It is never placed in `script.js`, `index.html`, or any browser-facing file
- Only the serverless function (`api/chat.js`) can read the API key
- The `.env.example` file shows what variables are needed but contains no real key
- `.env` and `.env.local` files are ignored by git

## Testing

All features have been tested and passed. See `docs/testing.md` for the full report.

| Test Question | Expected | Status |
|---|---|---|
| How can I apply? | Explains application process | Pass |
| What documents are required? | Lists required documents | Pass |
| What is the admission deadline? | Tells deadline dates | Pass |
| Do you offer BS Computer Science? | Confirms program and curriculum | Pass |
| What is the fee structure? | Explains tuition and fees | Pass |
| Are scholarships available? | Describes scholarship options | Pass |
| Where is the admission office? | Provides office location and contact | Pass |
| How can I check application status? | Explains status tracking | Pass |
| What is the refund policy? | Explains refund rules | Pass |
| Hello | Bot responds with greeting | Pass |

## Deployment

The project is deployed on Vercel. Any push to the GitHub main branch automatically redeploys.

To deploy your own copy:
1. Fork or push this repository to GitHub
2. Go to https://vercel.com and import the repository
3. Vercel auto-detects the static site and serverless function
4. Click Deploy
5. Add `OPENROUTER_API_KEY` in Vercel dashboard → Settings → Environment Variables

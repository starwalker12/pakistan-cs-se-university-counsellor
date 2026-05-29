# University Admission Chatbot

A simple AI-powered chatbot website that helps students with university admission questions.

## Features

- Web-based chat interface
- FAQ dataset with 25+ university admission questions
- Simple keyword matching search (Light RAG with no AI needed)
- **Local mode**: AI responses using Ollama + Gemma on your laptop
- **Online mode**: AI responses using OpenRouter via Vercel serverless function
- Automatic fallback to FAQ when AI is not available
- Clean, student-friendly UI
- Quick question buttons for common queries

## How It Works

1. User types a question in the chat
2. JavaScript searches the FAQ data (`data/faq.json`) for matching keywords
3. If a match is found, it is used as context for the AI
4. **On localhost**: calls local Ollama (gemma4:latest) directly
5. **On Vercel**: calls `/api/chat` serverless function → OpenRouter API
6. If AI fails for any reason, the chatbot answers directly from the FAQ

## Project Structure

```
├── index.html          # Main HTML page
├── style.css           # Styling for the chat interface
├── script.js           # Chatbot logic
├── api/
│   └── chat.js         # Serverless function (OpenRouter API call)
├── data/
│   └── faq.json        # FAQ data
├── docs/
│   ├── report.md       # Project report
│   ├── presentation-outline.md  # Presentation outline
│   └── testing.md      # Testing report
├── .env.example        # Environment variable template
├── vercel.json         # Vercel deployment config
└── README.md           # This file
```

## Local Development

### Prerequisites
- A modern web browser (Chrome, Firefox, Edge, etc.)

### To preview locally
Open `index.html` directly in your browser, or use a local server:

```bash
# Using Python (simplest)
python3 -m http.server 8000
# Then open http://localhost:8000 in your browser
```

### Local AI with Ollama (optional)
1. Install Ollama from https://ollama.ai
2. Pull the Gemma model:
   ```bash
   ollama pull gemma4:latest
   ```
3. Make sure Ollama is running:
   ```bash
   ollama serve
   ```
4. The chatbot will automatically use Ollama when on localhost

### Browser CORS Restriction for Ollama
When running on `http://localhost:8000`, your browser may block
requests to `http://localhost:11434` (Ollama) due to CORS policy.
This is normal and the chatbot will fall back to FAQ answers automatically.

To allow Ollama responses in the browser, start Ollama with:
```bash
OLLAMA_ORIGINS=* ollama serve
```
Or access the chatbot using `http://127.0.0.1:8000` instead of `localhost`.

## Online AI with OpenRouter (on Vercel)

When deployed to Vercel, the chatbot uses a serverless function (`api/chat.js`)
to call the OpenRouter API. This keeps the API key secure on the server.

### How to Set Up OpenRouter on Vercel

1. Create an account at https://openrouter.ai
2. Generate an API key from https://openrouter.ai/keys
3. In your Vercel dashboard, go to your project → Settings → Environment Variables
4. Add these variables:

| Variable | Value | Notes |
|---|---|---|
| `OPENROUTER_API_KEY` | `sk-or-v1-...` | Your OpenRouter API key |
| `OPENROUTER_MODEL` | `openai/gpt-4o-mini` | Optional. Change model anytime |

5. Redeploy the project

### Why is the API key not in frontend code?
The API key is never placed in `script.js` or any browser-facing file.
Instead, `script.js` calls `/api/chat` on the same server.
The serverless function reads the API key from environment variables
and calls OpenRouter. The browser never sees the API key.

### Changing the AI Model
The default model is `openai/gpt-4o-mini`. To change it:
- Set `OPENROUTER_MODEL` in your Vercel environment variables
- See https://openrouter.ai/models for available models

## Testing

All features tested and verified. See `docs/testing.md` for the full report.

| Test Question | Expected | Status |
|---|---|---|
| How can I apply? | Explains application process | ✅ Pass |
| What documents are required? | Lists required documents | ✅ Pass |
| What is the admission deadline? | Tells deadline dates | ✅ Pass |
| Do you offer BS Computer Science? | Confirms program and curriculum | ✅ Pass |
| What is the fee structure? | Explains tuition and fees | ✅ Pass |
| Are scholarships available? | Describes scholarship options | ✅ Pass |
| Where is the admission office? | Provides office location and contact | ✅ Pass |
| How can I check application status? | Explains status tracking | ✅ Pass |
| What is the refund policy? | Explains refund rules | ✅ Pass |
| Hello | Bot responds with greeting | ✅ Pass |

## Deployment on Vercel

This project is ready for deployment on Vercel.

### Important Deployment Notes
- **Ollama runs only on your local machine.** On Vercel, the chatbot uses the `/api/chat` serverless function with OpenRouter.
- **Without OpenRouter key:** The chatbot still works using FAQ fallback only.
- **With OpenRouter key:** The chatbot uses online AI for smarter responses.

To deploy:
1. Push this repository to GitHub
2. Go to https://vercel.com and import the repository
3. Vercel will auto-detect it as a static site with serverless functions
4. Click Deploy — no configuration needed
5. Add environment variables (OPENROUTER_API_KEY) in Vercel dashboard

## License

This project is created for educational purposes.

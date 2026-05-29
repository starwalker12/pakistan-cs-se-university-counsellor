# University Admission Chatbot

A simple AI-powered chatbot website that helps students with university admission questions.

## Features

- Web-based chat interface
- FAQ dataset with 25+ university admission questions
- Simple keyword matching search (Light RAG with no AI needed)
- AI-powered responses using local Ollama (Gemma model)
- Automatic fallback to FAQ when Ollama is not available
- Clean, student-friendly UI
- Quick question buttons for common queries

## How It Works

1. User types a question in the chat
2. JavaScript searches the FAQ data (`data/faq.json`) for matching keywords
3. If a match is found, it is used as context for the AI
4. The app tries to connect to a local Ollama instance for an AI-generated response
5. If Ollama is not running, the chatbot answers directly from the FAQ

## Project Structure

```
├── index.html          # Main HTML page
├── style.css           # Styling for the chat interface
├── script.js           # Chatbot logic
├── data/
│   └── faq.json        # FAQ data
├── docs/
│   ├── report.md       # Project report
│   └── presentation-outline.md  # Presentation outline
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

### Optional: Local AI with Ollama
1. Install Ollama from https://ollama.ai
2. Pull the Gemma model:
   ```bash
   ollama pull gemma4:latest
   ```
3. Make sure Ollama is running:
   ```bash
   ollama serve
   ```
4. The chatbot will automatically use Ollama for AI responses

### Important Note on Local AI
Local AI works with Ollama only on the developer's laptop.
Vercel deployment will use FAQ fallback unless a hosted AI API is added later.

### Browser CORS Restriction for Ollama
When running the chatbot on `http://localhost:8000`, your browser may block
fetch requests to `http://localhost:11434` (Ollama) due to CORS policy.
This is normal and the chatbot will fall back to FAQ answers automatically.

To allow Ollama responses in the browser, start Ollama with:
```bash
OLLAMA_ORIGINS=* ollama serve
```
Or access the chatbot using `http://127.0.0.1:8000` instead of `localhost`.

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

### Important Deployment Note
**Ollama runs only on your local machine.** When deployed on Vercel, the AI model
will not be available. The chatbot will still work perfectly using the FAQ fallback.
All FAQ answers will be served directly without any AI dependency.

To deploy:
1. Push this repository to GitHub
2. Go to https://vercel.com and import the repository
3. Vercel will auto-detect it as a static site
4. Click Deploy — no configuration needed

## License

This project is created for educational purposes.

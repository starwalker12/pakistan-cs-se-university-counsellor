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
   ollama pull gemma:2b
   ```
3. Make sure Ollama is running:
   ```bash
   ollama serve
   ```
4. The chatbot will automatically use Ollama for AI responses

## Test Questions

Try asking the chatbot these questions to test it:

1. **"How can I apply?"**
   - Expected: Explains the online application process and portal.

2. **"What documents are required?"**
   - Expected: Lists the required documents for admission.

3. **"What is the admission deadline?"**
   - Expected: Tells fall and spring semester deadlines.

4. **"Do you offer BS Computer Science?"**
   - Expected: Confirms the program and describes the curriculum.

5. **"How can I contact the admission office?"**
   - Expected: Provides contact details (phone, email, address).

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

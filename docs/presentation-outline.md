# University Admission Chatbot — Presentation Outline

**Team:** Raahim Adeel, Fardan Aatir, Muhammad Ismail

---

## Slide 1: Title Slide

- Project Name: University Admission Chatbot
- Team Members: Raahim Adeel, Fardan Aatir, Muhammad Ismail
- Course / Date

## Slide 2: Problem Statement

- University admission offices get hundreds of repeated questions daily
- Students need answers outside office hours
- Staff spend too much time answering the same questions
- No 24/7 support available for admission queries

## Slide 3: Project Goal

- Build a simple AI chatbot that answers admission questions
- Works with FAQ data for reliable answers
- Uses AI for more natural responses when available
- Works locally (laptop) and online (Vercel)
- Falls back to FAQ if AI is not available

## Slide 4: System Workflow

1. User types a question or clicks a quick button
2. JavaScript searches FAQ dataset using keyword matching
3. Best matching FAQ is saved as context
4. Localhost → call Ollama (Gemma model)
5. Vercel → call /api/chat → OpenRouter API
6. AI answer is shown, or FAQ fallback if AI fails

## Slide 5: Technologies Used

| Technology | Purpose |
|---|---|
| HTML | Page structure |
| CSS | Styling and layout |
| JavaScript | Chat logic and API calls |
| JSON | FAQ data storage |
| Ollama + Gemma | Local AI on laptop |
| OpenRouter API | Online AI on Vercel |
| Vercel | Hosting and serverless functions |

## Slide 6: Light RAG (Retrieval-Augmented Generation)

- RAG = search first, then use AI
- Simple approach: no vector databases, no embeddings, no training
- How it works:
  1. Split user question into individual words
  2. Count how many words match each FAQ question and keywords
  3. Pick the FAQ with the highest match count
  4. Include the FAQ question and answer in the AI prompt
  5. AI uses both FAQ context and user question to answer

## Slide 7: AI Integration

### Local AI (Ollama)
- Runs on developer laptop only
- Model: Gemma 4 (gemma4:latest)
- JavaScript calls http://localhost:11434/api/generate
- May be blocked by browser CORS — FAQ fallback handles this

### Online AI (OpenRouter)
- Runs on Vercel live website
- JavaScript calls /api/chat serverless function
- Serverless function calls OpenRouter API
- API key stored in Vercel environment variables (not in browser code)
- Default model: gpt-4o-mini

## Slide 8: Demo

- Open the live website: https://university-admission-chatbot.vercel.app
- Show the chat interface
- Ask: "How can I apply?" (FAQ match)
- Ask: "What is the admission deadline?" (FAQ match)
- Ask: "Can you explain the admission process?" (AI response)
- Click the quick question buttons

## Slide 9: Testing

- All features tested and passed
- 10 test questions verified
- FAQ search matches correctly
- Ollama responds when running
- OpenRouter responds when API key is set
- FAQ fallback works when AI is unavailable
- Empty messages rejected, rapid sends handled
- Works on desktop and mobile

Full testing report: docs/testing.md

## Slide 10: Conclusion

- Successfully built a working AI chatbot for university admissions
- Works locally with Ollama and online with OpenRouter
- Always falls back to FAQ when AI is unavailable
- Simple, clean code that students can understand
- Deployed live on Vercel: https://university-admission-chatbot.vercel.app

**Thank you! Questions?**

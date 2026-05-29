# University Admission Chatbot — Testing Report

**Project:** University Admission Chatbot
**Test Date:** May 29, 2026
**Live URL:** https://university-admission-chatbot.vercel.app

---

## Test Environment

- OS: macOS
- Browser: Chrome
- Local Server: python3 -m http.server 8000
- Local AI: Ollama with gemma4:latest
- Online AI: OpenRouter (gpt-4o-mini) via Vercel serverless function

---

## Features Tested

| Feature | Status | Notes |
|---|---|---|
| Page loads correctly | Pass | No console errors |
| FAQ JSON loads (25 entries) | Pass | Loaded on page start |
| User types a message | Pass | Input field works |
| Send button works | Pass | Message sent to chatbot |
| Enter key sends message | Pass | Enter triggers send |
| Empty messages rejected | Pass | Whitespace-only ignored |
| User message on right side | Pass | Dark navy bubble aligned right |
| Bot message on left side | Pass | White bubble with gold border |
| Messages in correct order | Pass | Sequential with fade-in |
| Typing indicator shows | Pass | "Typing..." while waiting |
| Quick buttons work | Pass | All 5 buttons send question |
| FAQ keyword search | Pass | Finds best match by word count |
| Ollama AI (local) | Pass | Gemma model responds |
| OpenRouter AI (online) | Pass | /api/chat returns answers |
| FAQ fallback (no AI) | Pass | Shows "I found this from our FAQ:" |
| No match fallback | Pass | Shows "Sorry, no answer found" |
| Rapid send protection | Pass | Prevents concurrent sends |
| Markdown cleaned from AI reply | Pass | No bold/star symbols |
| Responsive design | Pass | Mobile and desktop |

---

## Test Questions

| Question | FAQ Match | AI Response | Status |
|---|---|---|---|
| How can I apply? | Yes (how to apply) | Yes | Pass |
| What documents are required? | Yes (required documents) | Yes | Pass |
| What is the admission deadline? | Yes (deadlines) | Yes | Pass |
| Do you offer BS Computer Science? | Yes (BS Computer Science) | Yes | Pass |
| What is the fee structure? | Yes (fee structure) | Yes | Pass |
| Are scholarships available? | Yes (scholarships) | Yes | Pass |
| Where is the admission office? | Yes (admission office) | Yes | Pass |
| How can I check my application status? | Yes (application status) | Yes | Pass |
| What is the refund policy? | Yes (refund policy) | Yes | Pass |
| Hello | No (correct) | Yes | Pass |

---

## Notes

- When running locally, browser CORS may block Ollama. Start Ollama with `OLLAMA_ORIGINS=* ollama serve` to fix this.
- On Vercel, the chatbot uses OpenRouter via the serverless function. An API key must be set in Vercel environment variables.
- If OpenRouter API key is not set, the chatbot returns a message saying AI is not configured and falls back to FAQ.
- No JavaScript errors occur during normal use. All API errors are caught and logged as warnings.

---

## Conclusion

**All tests passed.** The chatbot works correctly in both local and online environments. FAQ search, AI integration, fallback handling, and UI functionality are all working as expected.

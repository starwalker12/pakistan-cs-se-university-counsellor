# Testing Checklist — Pakistan CS & SE University Counsellor

## Prerequisites

- [ ] Ollama is running (`ollama serve` or `OLLAMA_ORIGINS=* ollama serve`)
- [ ] OR LM Studio is running with server started on port 1234
- [ ] Chroma database exists at `backend/chroma_db/` (run `python build_vector_db.py` if not)
- [ ] Python dependencies installed (`pip install -r requirements.txt`)

---

## 1. Start Backend

```bash
cd /Users/sw12/Projects/ML-Project/backend
python3 -m uvicorn app:app --reload --port 8000
```

- [ ] Backend starts without errors
- [ ] Console shows: "Chroma loaded with N documents"
- [ ] Console shows: "Uvicorn running on http://localhost:8000"

---

## 2. Start Frontend

```bash
cd /Users/sw12/Projects/ML-Project
python3 -m http.server 8080
# Open http://localhost:8080/frontend/index.html
```

- [ ] Frontend loads without console errors
- [ ] Hero section visible with badge "RAG Based Admission Counsellor"
- [ ] Steps (1-2-3) visible in sidebar
- [ ] Disclaimer box visible in sidebar
- [ ] Sample question buttons visible
- [ ] Chat input is disabled (profile not saved yet)

---

## 3. Test /health Endpoint

```bash
curl http://localhost:8000/health
```

- [ ] Returns `{"status": "ok", "chroma_docs": N, "ollama": true/false, "lm_studio": true/false}`

---

## 4. Test /providers Endpoint

```bash
curl http://localhost:8000/providers
```

- [ ] Returns list of configured providers with status

---

## 5. Test /search Endpoint

```bash
curl "http://localhost:8000/search?q=CS%20universities%20in%20Lahore"
```

- [ ] Returns JSON array with at least 3 results
- [ ] Results contain `university_name`, `category`, `text` fields

---

## 6. Test /counsel Endpoint (Full RAG)

```bash
curl -X POST http://localhost:8000/counsel \
  -H "Content-Type: application/json" \
  -d '{
    "profile": {
      "name": "Ali",
      "matric_marks": "90",
      "inter_marks": "82",
      "entry_test": "ECAT 150",
      "preferred_field": "CS",
      "city_preference": "Lahore",
      "budget": "500000"
    },
    "question": "Which universities are best for me?"
  }'
```

- [ ] Returns HTTP 200
- [ ] Response contains `answer` (string, non-empty)
- [ ] Response contains `sources` (array, at least 1)
- [ ] Response contains `retrieved_count` (number, >= 1)
- [ ] Response contains `provider_used` ("ollama", "lm_studio", or "fallback")
- [ ] Answer has line breaks and section headings (**Short Summary**, **Best Match**, etc.)

---

## 7. Test Frontend — Save Profile

- [ ] Fill all required fields (name, matric, inter, field)
- [ ] Click "Save Profile"
- [ ] Green status dot appears
- [ ] Chat input and Send button enabled
- [ ] Bot message confirms "Profile saved!"

---

## 8. Test Frontend — Sample Questions

- [ ] Click each sample question button
- [ ] Question text appears in the input box
- [ ] Press Send to submit
- [ ] User message appears as dark bubble on right
- [ ] "Thinking..." indicator appears
- [ ] Bot answer appears as light bubble on left
- [ ] Sources appear as green cards below answer
- [ ] Provider badge shows in chat header

---

## 9. Test Frontend — Backend Offline

- [ ] Stop the backend (Ctrl+C on uvicorn)
- [ ] Type a question and click Send
- [ ] Red error banner appears: "Backend is not running. Please start the local server and try again."

---

## 10. Test Sources Display

- [ ] After a successful answer, green source cards appear
- [ ] Each card shows the university name
- [ ] Each card shows the source URL
- [ ] Each card shows a short preview text

---

## 11. Test Provider Display

- [ ] After a successful answer, provider badge appears in chat header
- [ ] Badge text matches `provider_used` field from response
- [ ] Badge has a small pill shape with green border

---

## 12. Test Disclaimer

- [ ] Disclaimer box visible in sidebar at all times
- [ ] Text reads: "This tool gives guidance only. Final admission depends on official university policy and merit."

---

## 13. Test Responsive Design

- [ ] Resize browser to 768px width — layout switches to single column
- [ ] Resize browser to 480px width — everything readable, no horizontal scroll
- [ ] All buttons and inputs usable at all sizes

---

## 14. Test Validation

- [ ] Click "Save Profile" with empty name — alert shows
- [ ] Click "Save Profile" with empty matric — alert shows
- [ ] Click "Save Profile" with empty inter — alert shows
- [ ] Click "Save Profile" with no field selected — alert shows
- [ ] Try sending empty input — nothing happens

---

## Summary

| # | Test | Status |
|---|---|---|
| 1 | Backend starts |  |
| 2 | Frontend loads |  |
| 3 | /health endpoint |  |
| 4 | /providers endpoint |  |
| 5 | /search endpoint |  |
| 6 | /counsel endpoint (full RAG) |  |
| 7 | Save profile |  |
| 8 | Sample questions |  |
| 9 | Backend offline error |  |
| 10 | Sources display |  |
| 11 | Provider display |  |
| 12 | Disclaimer visible |  |
| 13 | Responsive design |  |
| 14 | Form validation |  |

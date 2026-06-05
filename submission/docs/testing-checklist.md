# DigiCounsellor — Testing Checklist

## 1. Irrelevant question blocking (frontend)

| Test | Expected | Result |
|------|----------|--------|
| Type "teach me c++" | Blocked message appears | |
| Type "Who is Elon Musk?" | Blocked message appears | |
| Type "What is the weather today?" | Blocked message appears | |
| Type "Tell me a joke" | Blocked message appears | |
| Type "How to cook biryani?" | Blocked message appears | |
| Type "Write a love poem" | Blocked message appears | |
| Type "teach me python" | Blocked message appears | |

**Exact blocked message:**
> I can only help with Computer Science and Software Engineering university admissions in Pakistan. Please ask about universities, eligibility, fees, merit, deadlines, entry tests, or admission steps.

## 2. Valid admission questions (frontend → backend)

| Test | Expected | Result |
|------|----------|--------|
| Type "How can I get admission?" | Counselling response | |
| Type "Which CS universities are best for me?" | Recommendation cards | |
| Type "Am I eligible for FAST?" | Eligibility info | |
| Type "What are NUST CS fees?" | Fee info for NUST | |
| Type "What is the admission deadline?" | Deadline info | |
| Type "Which universities offer Software Engineering in Lahore?" | Recommendations | |
| Type "hello" | Greeting reply | |
| Type "thanks" | Greeting reply | |

## 3. Scrolling behavior

| Test | Expected | Result |
|------|----------|--------|
| Desktop (1440×900) | Page fits in one screen, no body scroll, panels scroll inside | |
| Tablet (768×1024) | Responsive layout, panels scroll inside, input stays usable | |
| Mobile (390×844) | Content stacks, messages scroll, no sideways scroll | |
| Add many messages | Chat messages area scrolls, page does not scroll | |
| Profile panel has many fields | Profile panel scrolls inside itself | |

## 4. Playwright scraper

| Test | Command | Expected | Result |
|------|---------|----------|--------|
| Run scraper | `python backend/scrape_universities.py` | Runs without error, prints summary | |
| Check output | `ls backend/data/raw/` | Contains HTML files per university per category | |
| Check admission data | `ls backend/data/processed/university_admission_data.json` | Exists and contains records | |
| Check log | `ls backend/data/processed/scraping_log.json` | Exists with per-university status | |

## 5. Vector DB rebuild

| Test | Command | Expected | Result |
|------|---------|----------|--------|
| Build DB | `python backend/build_vector_db.py` | Prints chunk count, saves to chroma_db/ | |
| Verify DB | Check `backend/chroma_db/` exists | Directory has Chroma files | |

## 6. API endpoints

| Test | Command | Expected | Result |
|------|---------|----------|--------|
| Health check | `curl http://localhost:8000/health` | Returns JSON with status | |
| Irrelevant via API | `curl -X POST http://localhost:8000/recommend ... -d '{"question":"teach me c++"}'` | Returns blocked message | |
| Valid via API | `curl -X POST http://localhost:8000/recommend ... -d '{"question":"Which CS universities are best for me?"}'` | Returns recommendations | |

## 7. GitHub Actions

| Test | Expected | Result |
|------|----------|--------|
| Workflow file exists | `.github/workflows/scheduled-scrape.yml` | |
| Weekly schedule | cron `0 6 * * 0` runs Sunday 6 AM UTC | |
| Manual trigger | workflow_dispatch button in GitHub UI | |
| Playwright install | Installs chromium browser | |
| Commit on changes | Only commits if data files changed | |

# Demo Script — DigiCounsellor

## 1. Introduction (30 seconds)

> "Good morning / afternoon everyone. We are Raahim Adeel, Fardan Aatir, and Muhammad Ismail. Today we will demonstrate our project — DigiCounsellor, a RAG-based university counselling app for Pakistani students who want to get into Computer Science or Software Engineering programs."

## 2. The Problem (30 seconds)

> "Every year, thousands of students across Pakistan apply for CS and SE programs. They struggle to find reliable admission information — what marks are needed, which universities offer their field, what entry tests are required, and how much fee to expect. Our project solves this by giving personalised, data-driven counselling using official university data."

## 3. What is RAG? (30 seconds)

> "RAG stands for Retrieval-Augmented Generation. In simple words: instead of asking a chatbot that guesses from memory, RAG first searches a local database of real university admission data, retrieves the most relevant information, and then sends that data to an AI model to generate a personalised answer. This means the answer is based on actual university data, not just the AI's training."

## 4. Demo Setup (say while showing)

> "Our setup has two parts:
> - **Frontend** — a clean HTML page you can open in your browser
> - **Backend** — a Python FastAPI server running on this laptop
>
> The backend uses Chroma (a local vector database) for storing and searching university data, and Ollama (running locally) as the AI engine."

> "Before answering, the backend also checks whether the question is actually about CS/SE admissions in Pakistan. Valid follow-ups like safe options or next steps are allowed, while unrelated questions are refused before RAG or AI answer generation."

## 5. Sample Profile

Use this profile during the demo:

| Field | Value |
|---|---|
| Name | Ali |
| Matric Percentage | 90% |
| Intermediate Percentage | 82% |
| Entry Test Score | ECAT 150 |
| Preferred Field | Computer Science |
| City Preference | Lahore |
| Budget | PKR 500,000 |

## 6. Three Demo Questions

Ask these questions one at a time during the demo:

**Question 1:** *"Which universities are best for me?"*
- Recommendation cards appear first from structured RAG/scoring.
- The short local AI summary appears separately after the cards.
- Point out Best Match, Safe Options, Difficult Options, official links, and sources.

**Question 2:** *"Which universities offer CS in Lahore?"*
- Shows universities filtered by city — FAST, LUMS, ITU, Punjab University.
- Point out the city matching logic.

**Question 3:** *"Am I eligible for FAST?"*
- The AI checks the profile against FAST's requirements.
- Point out how the answer includes next steps like "prepare for the entry test".

**Follow-up:** *"What are safe options for me?"*
- This must be allowed because the student has profile/recommendation context.
- Point out that DigiCounsellor behaves like a counselling flow, not a one-shot answer box.

**Off-topic check:** *"teach me c++"*
- The backend refuses politely before RAG and before AI answer generation.

## 7. Key Features to Point Out

| When | What to show |
|---|---|
| After saving profile | The status dot turns green and chat input enables |
| While waiting | Rotating status lines show data search, profile check, ranking, and short AI summary |
| When cards appear | Recommendations show before the AI summary, so the demo does not feel stuck |
| In chat header | Provider badge shows "Local AI connected" when Ollama responds |
| Follow-up buttons | Selecting a university keeps the conversation focused on that university |
| Relevance check | Admission follow-ups pass; unrelated questions get a scoped refusal |

## 8. Closing Line (30 seconds)

> "This project shows how RAG + local AI can power a real-world counselling tool — all running on a laptop with no internet needed after setup. Thank you for watching. We are happy to answer any questions."

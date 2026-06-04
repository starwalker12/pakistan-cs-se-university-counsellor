# Demo Script — Pakistan CS & SE University Counsellor

## 1. Introduction (30 seconds)

> "Good morning / afternoon everyone. We are Raahim Adeel, Fardan Aatir, and Muhammad Ismail. Today we will demonstrate our project — a RAG-based University Counsellor for Pakistani students who want to get into Computer Science or Software Engineering programs."

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
- The AI will show a Short Summary, then Best Match, Safe Options, and Difficult Options.
- Point out how the answer mentions specific universities with reasons.

**Question 2:** *"Which universities offer CS in Lahore?"*
- Shows universities filtered by city — FAST, LUMS, ITU, Punjab University.
- Point out the city matching logic.

**Question 3:** *"Am I eligible for FAST?"*
- The AI checks the profile against FAST's requirements.
- Point out how the answer includes next steps like "prepare for the entry test".

## 7. Key Features to Point Out

| When | What to show |
|---|---|
| After saving profile | The status dot turns green and chat input enables |
| While waiting | The "Thinking..." typing indicator |
| When answer appears | Sources shown as green cards below the answer |
| In chat header | Provider badge shows "ollama" or "lm_studio" |
| In sidebar | The RAG explanation and disclaimer box |

## 8. Closing Line (30 seconds)

> "This project shows how RAG + local AI can power a real-world counselling tool — all running on a laptop with no internet needed after setup. Thank you for watching. We are happy to answer any questions."

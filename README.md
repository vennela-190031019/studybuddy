# 📚 StudyBuddy

Upload lecture notes or a textbook chapter → get a generated quiz →
take it → get graded with specific, per-question feedback.

Built to learn (and demonstrate) two core LLM engineering patterns:
**structured output** (every quiz question and grade is a validated
Pydantic schema, not free-form text) and **knowing when to call the LLM
at all** (multiple-choice is graded instantly in code; only short-answer
questions go to the model).

## How it works

```
Notes (PDF or pasted text)
        │
   chunk_text()                  src/extract.py
        │
   generate_quiz()                src/quiz_generator.py
        │  → LLM call, JSON response_format
        │  → validated into Quiz / QuizQuestion (Pydantic)
        │
   Streamlit quiz form             app.py
        │
   grade_answer() per question     src/grader.py
        │  → multiple_choice: instant string comparison
        │  → short_answer: LLM call graded against key_points rubric
        │
   Results: score + feedback per question
```

## Setup

1. **Clone and enter the project**
   ```bash
   git clone <your-repo-url>
   cd studybuddy
   ```

2. **Create a virtual environment** (recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate      # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Add your API key**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and paste your OpenAI API key. Get one at
   https://platform.openai.com/api-keys — new accounts get a small free
   credit, and `gpt-4o-mini` (the default model here) is inexpensive.

5. **Run it**
   ```bash
   streamlit run app.py
   ```
   This opens the app in your browser, usually at `http://localhost:8501`.

## Using it

1. Upload a PDF of notes, or paste text directly.
2. Click **Generate quiz**.
3. Answer the questions (multiple-choice and short-answer are mixed).
4. Click **Submit answers** — each question gets scored with feedback,
   plus an overall score.

## Project structure

```
studybuddy/
├── app.py                  # Streamlit UI — the entry point
├── requirements.txt
├── .env.example
├── src/
│   ├── extract.py          # PDF text extraction + chunking
│   ├── llm_client.py       # LLM API wrapper (swap providers here)
│   ├── quiz_generator.py   # Prompt + schema for quiz generation
│   ├── grader.py           # Instant MCQ grading + LLM short-answer grading
│   └── schemas.py          # Pydantic models — the structured output contract
```

## Possible next steps

- Swap `src/llm_client.py` to call Anthropic's Claude API instead of OpenAI
- Add a vector store (Chroma/FAISS) so it can quiz on much longer documents
  by retrieving relevant sections instead of using only the first chunk
- Track quiz history per topic to show improvement over time
- Add a "generate more questions on my weak topics" follow-up round

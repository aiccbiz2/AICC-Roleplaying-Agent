"""FastAPI 서버 — AICC 롤플레이 시뮬레이터"""
from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="AICC Roleplay Simulator")

# ── Static files ──
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Pydantic Models ──
class StartRoleplayRequest(BaseModel):
    scenario: str
    persona: str


class RoleplayRespondRequest(BaseModel):
    system_prompt: str
    history: list[dict]


class FeedbackRequest(BaseModel):
    history: list[dict]
    scenario_title: str
    persona_level: str


# ── Page Routes ──
@app.get("/")
async def page_dashboard():
    return FileResponse("static/index.html")


@app.get("/simulation")
async def page_simulation():
    return FileResponse("static/simulation.html")


@app.get("/quiz")
async def page_quiz():
    return FileResponse("static/quiz.html")


@app.get("/dictionary")
async def page_dictionary():
    return FileResponse("static/dictionary.html")


# ── API: Scenarios & Personas ──
@app.get("/api/scenarios")
async def get_scenarios():
    from roleplay import SCENARIOS
    return SCENARIOS


@app.get("/api/personas")
async def get_personas():
    from roleplay import PERSONAS
    return PERSONAS


@app.get("/api/stages")
async def get_stages():
    from roleplay import STAGES
    return STAGES


@app.get("/api/industries")
async def get_industries():
    from roleplay import INDUSTRIES
    return INDUSTRIES


# ── API: Roleplay ──
@app.post("/api/roleplay/start")
async def start_roleplay(req: StartRoleplayRequest):
    from roleplay import build_system_prompt, get_opening_message
    system_prompt = build_system_prompt(req.scenario, req.persona)
    opening = get_opening_message(system_prompt)
    return {"system_prompt": system_prompt, "opening": opening}


@app.post("/api/roleplay/respond")
async def roleplay_respond(req: RoleplayRespondRequest):
    from roleplay import get_ai_response
    response = get_ai_response(req.system_prompt, req.history)
    return {"response": response}


@app.post("/api/roleplay/feedback")
async def roleplay_feedback(req: FeedbackRequest):
    from feedback import analyze_roleplay
    result = analyze_roleplay(req.history, req.scenario_title, req.persona_level)
    return result


# ── API: Quiz ──
@app.get("/api/quiz")
async def get_quiz(category: str = None, difficulty: str = "중급"):
    from quiz import load_quiz_from_pool, generate_quiz
    quiz = load_quiz_from_pool(category=category, difficulty=difficulty)
    if quiz:
        return quiz
    return generate_quiz(category=category, difficulty=difficulty)


@app.get("/api/quiz/set")
async def get_quiz_set(category: str = None, difficulty: str = "중급", count: int = 10):
    from quiz import load_quiz_set_from_pool
    quizzes = load_quiz_set_from_pool(category=category, difficulty=difficulty, count=count)
    return {"quizzes": quizzes, "total": len(quizzes)}


@app.get("/api/quiz/categories")
async def get_quiz_categories():
    from quiz import QUIZ_CATEGORIES
    return QUIZ_CATEGORIES


# ── API: Glossary ──
@app.get("/api/glossary")
async def get_glossary():
    from config import GLOSSARY_PATH
    text = GLOSSARY_PATH.read_text(encoding="utf-8")
    categories = {}
    current_cat = None
    rows = []
    for line in text.split("\n"):
        if line.startswith("## ") and not line.startswith("## 교육"):
            if current_cat and rows:
                categories[current_cat] = rows
            current_cat = line.replace("## ", "").strip()
            rows = []
        elif line.startswith("|") and current_cat and "---" not in line and "정식 용어" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 4:
                rows.append({
                    "term": cells[0],
                    "abbr": cells[1],
                    "definition": cells[2],
                    "field_expression": cells[3],
                    "note": cells[4] if len(cells) > 4 else "",
                })
    if current_cat and rows:
        categories[current_cat] = rows
    return categories


# ── API: DB Status ──
@app.get("/api/db-status")
async def db_status():
    from config import CHROMA_DIR
    ready = CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir())
    return {"ready": ready}


@app.post("/api/build-db")
async def build_db():
    from ingest import ingest
    ingest()
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

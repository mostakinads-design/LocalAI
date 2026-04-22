from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Python LLM Bridge")


class TaskUpdate(BaseModel):
    task_id: str
    status: str
    payload: dict = {}


class PromptCreate(BaseModel):
    name: str
    prompt: str
    metadata: dict = {}


@app.get("/health")
def health():
    return {"status": "ok", "service": "python-llm-bridge"}


@app.post("/tasks/update")
def update_task(item: TaskUpdate):
    return {"accepted": True, "task": item.model_dump()}


@app.post("/prompts/create")
def create_prompt(item: PromptCreate):
    return {"accepted": True, "prompt": item.model_dump()}


@app.get("/models/options")
def model_options():
    return {
        "models": [
            {"id": "qwen3", "provider": "localai"},
            {"id": "llama3", "provider": "localai"},
        ]
    }

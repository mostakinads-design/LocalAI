from fastapi import FastAPI

app = FastAPI(title="Greswitch Bridge")


@app.get("/health")
def health():
    return {"status": "ok", "service": "greswitch-bridge"}


@app.get("/capabilities")
def capabilities():
    return {
        "supports": [
            "task-updates",
            "prompt-creation",
            "model-options",
        ]
    }

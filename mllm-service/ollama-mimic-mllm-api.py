from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import base64

app = FastAPI(title="AX-M1 OLLAMA MLLM API")

# -----------------------
# Pydantic Request Models
# -----------------------
class GenerateRequest(BaseModel):
    model: str
    prompt: str
    images: list[str] | None = None
    options: dict | None = None


class ShowRequest(BaseModel):
    name: str


# Pretend we have these models
AVAILABLE_MODELS = {
    "custom-model": {
        "name": "custom-model",
        "details": {
            "format": "gguf",
            "family": "llama",
            "parameter_size": "7B",
        }
    }
}

# -----------------------
#  Endpoints
# -----------------------

@app.post("/api/show")
async def show_model(req: ShowRequest):
    """
    Mimics: POST /api/show
    Used by Frigate to check if model exists
    """
    if req.name not in AVAILABLE_MODELS:
        return {"error": f"model '{req.name}' not found"}

    return AVAILABLE_MODELS[req.name]


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    """
    Mimics: POST /api/generate
    Used by Frigate to send prompt + images
    """
    if req.model not in AVAILABLE_MODELS:
        raise HTTPException(status_code=400, detail="Model not found")

    # Decode images (if included)
    decoded_images = []
    if req.images:
        for img_b64 in req.images:
            try:
                decoded_images.append(base64.b64decode(img_b64))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid base64 image")

    # -----------------------------------------------------
    # Here you call your actual model (M1, AX-M1, TensorRT,
    # llama.cpp, whatever). For now we return mock text.
    # -----------------------------------------------------
    response_text = f"[Mocked Response] You said: {req.prompt}"

    return {
        "model": req.model,
        "created_at": "2025-01-01T00:00:00Z",
        "response": response_text,
        "done": True,
        "eval_count": 42,
        "prompt_eval_count": 12,
    }


@app.get("/api/tags")
async def list_models():
    """
    Mimics: GET /api/tags
    """
    return {"models": list(AVAILABLE_MODELS.keys())}
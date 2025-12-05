import json
import logging
import threading
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from time import sleep
from modelhelper import ModelHelper
from llmservice import LlmService
from llmservice import LlmStatus

app = FastAPI(title="AX-M1 LLM API")

model_helper = ModelHelper()
model_helper.create_llm_services()
# Start the models async
threading.Thread(target=model_helper.start_default_llm_services, daemon=True).start()

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


class LlmGenerateRequest(BaseModel):
    model: str
    prompt: str
    images: list[str] | None = None
    options: dict | None = None

class ShowRequest(BaseModel):
    name: str


@app.post("/api/generate")
def generate(req: LlmGenerateRequest):
    """
    Forwards a prompt to the persistent model process.
    If there the model is not yet ready, wait until it is
    """
    try:
        logger.info(f"Received generate request for model '{req.model}' with prompt: {req.prompt}")
        llm_service = model_helper.get_llmservice(req.model)
        if llm_service.get_status() == LlmStatus.IDLE:
            logger.info(f"Prompt requested, but model '{req.model}' is not started yet -> starting model")
            llm_service.start_model()
        llm_service.await_readiness(timeout=300)
        response = llm_service.prompt_llm(req.prompt)
        return {"response": response}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/status/{model_name}")
def status(model_name):
    """
    Reports the current status of the given model
    """
    try:
        llm_service = model_helper.get_llmservice(model_name)
        return {
            "status": llm_service.get_status()
        }
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/status_history/{model_name}")
def status(model_name):
    """
    Reports all status transition of the given model.
    """
    try:
        llm_service = model_helper.get_llmservice(model_name)
        return {
            "status_history": llm_service.get_status_history()
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/tags")
async def list_models():
    """
    Mimics: GET /api/tags
    """
    return {"models": model_helper.get_model_descriptors()}


@app.post("/api/show")
async def show_model(req: ShowRequest):
    """
    Mimics: POST /api/show
    Used by Frigate to check if model exists
    """
    if req.name not in model_helper.get_model_descriptors():
        return {"error": f"model '{req.name}' not found"}

    return "ok"
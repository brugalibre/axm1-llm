import json
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from time import sleep
from modelhelper import ModelHelper
from llmservice import LlmService

app = FastAPI(title="AX-M1 LLM API")

model_helper = ModelHelper()
model_helper.create_llm_services()
model_helper.start_default_llm_services()

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)


class LlmPromptRequest(BaseModel):
    model_name: str
    prompt: str


@app.post("/prompt_llm")
def prompt_llm(req: LlmPromptRequest):
    """
    Forwards a prompt to the persistent model process.
    If there the model is not yet ready, wait until it is
    """
    try:
        llm_service = model_helper.get_llmservice(req.model_name)
        if llm_service.get_status() == "IDLE":
            logger.info(f"Prompt requested, but model '{req.model_name}' is not started yet -> starting model")
            llm_service.start_model()
        llm_service.await_readiness(timeout=300)
        response = llm_service.prompt_llm(req.prompt)
        return {"response": response}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/status/{model_name}")
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

@app.get("/status_history/{model_name}")
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

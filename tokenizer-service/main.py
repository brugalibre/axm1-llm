from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from modelhelper import ModelHelper
from tokenizerservice import TokenizerService

app = FastAPI(title="Tokenizer Service")

model_helper = ModelHelper()
model_helper.create_tokenizer_services()


class StartTokenizerRequest(BaseModel):
    name: str


@app.post("/start_tokenizer")
def start_tokenizer(req: StartTokenizerRequest):
    """
    Forwards a prompt to the persistent model process.
    If there the model is not yet ready, wait until it is
    """
    try:
        tokenizer_service = model_helper.get_tokenizerservice(req.name)
        response = tokenizer_service.start_tokenizer()
        return {"response": response}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/status/{tokenizer_name}")
def status(tokenizer_name):
    """
    Reports whether the tokenizer process is alive.
    """
    tokenizer_service = model_helper.get_tokenizerservice(tokenizer_name)
    return {
        "status": tokenizer_service.get_status()
    }

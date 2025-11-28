import logging
import re
import requests
import subprocess
import time
import threading
from enum import Enum
from fastapi import HTTPException
from time import sleep
from metrics import write_metrics


Status = Enum("Status", [
    ("IDLE", 1),
    ("WAIT_FOR_TOKENIZER", 2),
    ("STARTING", 3),
    ("INIT", 4),
    ("READY", 5),
    ("THINKING", 6),
    ("ANSWERING", 7),
    ("INIT_FAILED", 8)
])

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

INIT_START_PATTERN = re.compile("(.*)(LLM init start)(.*)")
INIT_OK_PATTERN = re.compile("(.*)(LLM init ok)(.*)")
INIT_FAILED_PATTERN = re.compile("(.*)(Set AXCL device failed)(.*)")
SEG_FAULT_PATTERN = re.compile("(.*)(Segmentation fault)(.*)")
THINK_PATTERN = "(.*)(</think>)"
# indicating that the model is done thinking and starts answering (answer may include thinking)
HIT_EOS_PATTERN = re.compile("(.*)(hit eos)(.*)")

TOKENIZER_STATUS_API = "http://localhost:8101/status"
TOKENIZER_START_API = "http://localhost:8101/start_tokenizer"

class LlmService:

    def __init__(self, model_name, run_cmd: str, model_path: str, tokenizer_py: str, tokenizer_path: str, tokenizer_port: int, include_thinking: bool):
        self.status_history = []
        self.status_lock = threading.Lock()
        self.__change_status(Status.IDLE)
        self.process = None
        self.model_name = model_name
        self.run_cmd = run_cmd
        self.model_path = model_path
        self.include_thinking = include_thinking
        self.tokenizer_port = tokenizer_port
        self.tokenizer_py = tokenizer_py
        self.tokenizer_path = tokenizer_path
        self.llm_response = []

    # ---------------------------------------------
    #               PROMPT HANDLER
    # ---------------------------------------------
    def prompt_llm(self, prompt: str) -> str:
        if self.get_status() != Status.READY:
            raise HTTPException(status_code=500, detail=f"Model not ready! Model status: {self.get_status()}")
        start_time = time.time()

        # Send prompt to model
        logger.info(f"Sending prompt '{prompt}'")
        self.__change_status(Status.THINKING)
        self.process.stdin.write(prompt + "\n")
        self.process.stdin.flush()

        # Wait for model to deliver final response
        logger.debug("Promt sent. Waiting for answer")
        while self.get_status() == Status.THINKING:
            sleep(1)
        logger.info(f"Done, got response: {self.llm_response}")
        response = " ".join(self.llm_response)

        # Write metrics
        write_metrics(self.model_name, time.time() - start_time, response)

        # Clean up and return response
        if self.include_thinking == False:
            response = re.sub(THINK_PATTERN, "", response)
            logger.debug(f"Removed thinking part, new response: {response}")

        self.__change_status(Status.READY)
        self.llm_response = []
        return response

    # ---------------------------------------------
    #               MODEL STARTUP
    # ---------------------------------------------
    def start_model(self):
        # Start Tokenizer
        logger.info(f"Model start '{self.model_name}' requested")
        self.__change_status(Status.WAIT_FOR_TOKENIZER)
        self.__start_tokenizer_and_await_readiness()
        self.__change_status(Status.STARTING)

        # Now start Model
        logger.info(f"Starting model {self.model_path}/{self.run_cmd} listenting at port {self.tokenizer_port}")
        self.process = subprocess.Popen(
            [self.run_cmd, str(self.tokenizer_port)], cwd=self.model_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logger.info(f"Model started, wait for readyness. Process {self.process}..")

        # Handle stdout and stderr in threads
        threading.Thread(target=self.__handle_llm_output, args=(self.process.stdout,), daemon=True).start()
        threading.Thread(target=self.__handle_llm_output, args=(self.process.stderr,), daemon=True).start()

    # ---------------------------------------------
    #               READINESS WAIT
    # ---------------------------------------------
    def await_readiness(self, timeout=120):
        logger.debug(f"Wait for {timeout}s for model {self.model_name} to become ready..")
        t0 = time.time()
        while self.get_status() != Status.READY:
            if time.time() - t0 > timeout:
                raise TimeoutError(f"{self.model_name} did not become ready in time")
            time.sleep(0.1)
        logger.debug(f"'{self.model_name}' is ready!")

    # ---------------------------------------------
    #               GETTERS
    # ---------------------------------------------
    def get_status(self):
        with self.status_lock:
            return self.status.name

    def get_status_history(self):
        with self.status_lock:
            return self.status_history

    # ---------------------------------------------
    #               LLM OUTPUT HANDLER
    # ---------------------------------------------
    def __handle_llm_output(self, pipe):
        for line in iter(pipe.readline, ''):
            if line == "\n":
                continue
            logger.debug(f"msg from llm: {line}, status: {self.get_status()}")
            if self.get_status() == Status.ANSWERING:
                self.llm_response.append(line)
            # ERROR states
            elif INIT_FAILED_PATTERN.match(line) != None or SEG_FAULT_PATTERN.match(line) != None:
                self.__change_status(Status.INIT_FAILED)
                logger.error(f"Model initialization failed with msg={line}")
            # INIT state
            elif INIT_START_PATTERN.match(line) != None:
                self.__change_status(Status.INIT)
                logger.info("Start initializing model..")
            # READY state
            elif INIT_OK_PATTERN.match(line) != None:
                self.__change_status(Status.READY)
                logger.info("Model ready!")
            # ANSWERING state
            elif HIT_EOS_PATTERN.match(line) != None:
                self.__change_status(Status.ANSWERING)
            #logger.warn(f"Msg from llm_ {line}")

    def __start_tokenizer_and_await_readiness(self):
        response = requests.get(f"{TOKENIZER_STATUS_API}/{self.model_name}")
        tokenizer_status = response.json()["status"]

        # Start tokenizer only if idle (=not yet started)
        if tokenizer_status == "IDLE":
            self.__start_tokenizer()

        # Now wait for tokenizer readyness
        while tokenizer_status != "READY":
            response = requests.get(f"{TOKENIZER_STATUS_API}/{self.model_name}")
            tokenizer_status = response.json()["status"]
            logger.debug(f"Waiting for tokenizer.. {tokenizer_status}")
            sleep(1)
        logger.debug("Tokenizer ready!")

    def __start_tokenizer(self):
        data = {
            "name": self.model_name,
            "port": self.tokenizer_port,
            "tokenizer_py": self.tokenizer_py,
            "tokenizer_path": self.tokenizer_path
        }
        logger.info("Request starting tokenizer")
        requests.post(TOKENIZER_START_API, json=data)

    def __change_status(self, new_status: Status):
        with self.status_lock:
            self.status = new_status
            self.status_history.append(new_status.name)

import io
import logging
import re
import requests
import subprocess
import time
import threading
from enum import Enum
from fastapi import HTTPException
from queue import Queue
from time import sleep
from metrics import Metrics
from tokenizerservice import TokenizerStatus

class LlmStatus(Enum):
    IDLE = 1
    WAIT_FOR_TOKENIZER = 2
    STARTING = 3
    INIT = 4
    READY = 5
    ANSWERING = 6
    ANSWERING_DONE = 7
    INIT_FAILED = 8

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

# wait max 10 minutes
PROMPT_TIME_OUT_SECONDS = 500

INIT_START_PATTERN = re.compile("(.*)(LLM init start)(.*)")
INIT_OK_PATTERN = re.compile("(.*)(LLM init ok)(.*)")
SET_AXCL_DEVICE_FAILED_PATTERN = re.compile("(.*)(Set AXCL device failed)(.*)")
INIT_FAILED_PATTERN = re.compile("(.*)(lLaMa.Init failed)(.*)")
SEG_FAULT_PATTERN = re.compile("(.*)(Segmentation fault)(.*)")
THINK_PATTERN = re.compile("(<\/think>(.*)$)")
# indicating that the model is done thinking and starts answering (answer may include thinking)
HIT_EOS_PATTERN = re.compile("(.*)(hit eos)(.*)")

TOKENIZER_STATUS_API = "http://{0}:8101/status"
TOKENIZER_START_API = "http://{0}:8101/start_tokenizer"

class LlmService:

    def __init__(self, model_name, run_cmd: str, model_path: str, tokenizer_ip: str, tokenizer_py: str, 
        tokenizer_path: str, tokenizer_port: int, include_thinking: str):

        self.ready_event = threading.Event()
        self.prompt_answered_event = threading.Event()
        self.llm_response_buffer = io.StringIO()
        self.process = None

        self.status_history = []
        self.status = None
        self.status_lock = threading.Lock()
        self.__change_status(LlmStatus.IDLE)

        # Create & prepare metrics
        self.metrics = Metrics()

        self.output_queue = Queue()
        self.output_listeners = []  # callables that receive each line
        self.output_listeners.append(self.metrics.process_llm_output)
        self.output_listeners.append(self.__process_llm_output)

        self.model_name = model_name
        self.run_cmd = run_cmd
        self.model_path = model_path
        self.include_thinking = include_thinking
        self.tokenizer_ip = tokenizer_ip
        self.tokenizer_port = tokenizer_port
        self.tokenizer_py = tokenizer_py
        self.tokenizer_path = tokenizer_path

    # ---------------------------------------------
    #               PROMPT HANDLER
    # ---------------------------------------------
    def prompt_llm(self, prompt: str) -> str:
        if self.get_status() != LlmStatus.READY:
            raise HTTPException(status_code=500, detail=f"Model not ready! Model status: {self.get_status()}")
        start_time = time.monotonic()

        # Send prompt to model
        logger.info(f"Sending prompt '{prompt}'")
        self.__change_status(LlmStatus.ANSWERING)
        self.process.stdin.write(prompt + "\n")
        self.process.stdin.flush()

        # Wait for model to deliver final response
        logger.debug("Prompt sent. Waiting for answer")
        if not self.prompt_answered_event.wait(timeout=PROMPT_TIME_OUT_SECONDS):
            raise TimeoutError(f"{self.model_name} did not answer in time")
        self.prompt_answered_event.clear()
        response = self.llm_response_buffer.getvalue()
        logger.info(f"Done, got response: {response}")

        # Write metrics
        self.metrics.write(self.model_name, time.monotonic() - start_time, response)

        # Clean up and return response
        if self.include_thinking.lower() == 'false':
            match = THINK_PATTERN.search(response)
            if match:
                response = match.group(2).strip()

        # Reset status
        self.__change_status(LlmStatus.READY)
        return response

    # ---------------------------------------------
    #               MODEL STARTUP
    # ---------------------------------------------
    def start_model(self):
        # Start Tokenizer
        logger.info(f"Model start '{self.model_name}' requested")
        self.__change_status(LlmStatus.WAIT_FOR_TOKENIZER)
        self.__start_tokenizer_and_await_readiness()
        self.__change_status(LlmStatus.STARTING)

        # Now start Model
        logger.info(f"Starting model {self.model_path}/{self.run_cmd} listening at {self.tokenizer_ip}:{self.tokenizer_port}")
        self.process = subprocess.Popen(
            [self.run_cmd, str(self.tokenizer_port)], cwd=self.model_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logger.info(f"Model started, wait for readiness. Process {self.process}..")

        # Handle stdout and stderr in threads
        threading.Thread(target=self.__read_from_llm_stdout, args=(self.process.stdout, "STDOUT",), daemon=True).start()
        threading.Thread(target=self.__read_from_llm_stdout, args=(self.process.stderr, "STDERR",), daemon=True).start()

    # ---------------------------------------------
    #               READINESS WAIT
    # ---------------------------------------------
    def await_readiness(self, timeout=120):
        logger.debug(f"Wait for {timeout}s for model {self.model_name} to become ready. Current status: {self.get_status()}, ready_event: {self.ready_event}")
        if not self.ready_event.wait(timeout=timeout):
            raise TimeoutError(f"{self.model_name} did not become ready in time")
        logger.debug(f"'{self.model_name}' became ready, done await_readiness!")

    # ---------------------------------------------
    #               GETTERS
    # ---------------------------------------------
    def get_status(self):
        with self.status_lock:
            return self.status

    def get_status_history(self):
        with self.status_lock:
            return self.status_history

    # ---------------------------------------------
    #               LLM OUTPUT HANDLER
    # ---------------------------------------------
    def __read_from_llm_stdout(self, pipe, tag):
        for line in pipe:
            line = line.rstrip("\n").strip()
            logger.debug(f"LlmService: read msg from llm: {line}, tag: {tag}, status: {self.get_status()}")

            # Push to queue and notify listeners
            self.output_queue.put(line)
            for listener in self.output_listeners:
                try:
                    listener(line)
                except Exception as e:
                    logger.error("Error during processing message from llm. line: {line}, listener: {listener}!", repr(e))

    def __process_llm_output(self, line):
        if line == None or line == '':
            return
        logger.debug(f"LlmService: process msg from llm: {line}")
        # ERROR states
        if SET_AXCL_DEVICE_FAILED_PATTERN.match(line) != None 
            or INIT_FAILED_PATTERN.match(line) != None or SEG_FAULT_PATTERN.match(line) != None:
            self.__change_status(LlmStatus.INIT_FAILED)
            logger.error(f"Model initialization failed, reason={line}")
        # INIT state
        elif INIT_START_PATTERN.match(line) != None:
            self.__change_status(LlmStatus.INIT)
            logger.info("Start initializing model..")
        # READY state
        elif INIT_OK_PATTERN.match(line) != None:
            self.__change_status(LlmStatus.READY)
            logger.info("Model is ready!")
        # ANSWERING state, first check if llm is done. If not, collect answer if still answering
        elif HIT_EOS_PATTERN.match(line) != None:
            self.__change_status(LlmStatus.ANSWERING_DONE)
            logger.info("Model has answered!")
        elif self.get_status() == LlmStatus.ANSWERING:
            self.llm_response_buffer.write(line)
        else:
            logger.debug(f"Message {line} from llm is ignored!")

    def __start_tokenizer_and_await_readiness(self):
        logger.debug(f"Start tokenizer if necessary")
        response = requests.get(f"{TOKENIZER_STATUS_API.format(self.tokenizer_ip)}/{self.model_name}")
        tokenizer_status = response.json()["status"]

        # Start tokenizer only if idle (=not yet started)
        if tokenizer_status == TokenizerStatus.IDLE.value:
            self.__start_tokenizer()

        # Now wait for tokenizer readiness. 1s steps in order to avoid segmentation fault
        while tokenizer_status != TokenizerStatus.READY.value:
            response = requests.get(f"{TOKENIZER_STATUS_API.format(self.tokenizer_ip)}/{self.model_name}")
            tokenizer_status = response.json()["status"]
            logger.debug(f"Waiting for tokenizer... Current status={tokenizer_status}")
            sleep(0.1)
        logger.debug("Tokenizer ready!")

    def __start_tokenizer(self):
        data = {
            "name": self.model_name,
            "port": self.tokenizer_port,
            "tokenizer_py": self.tokenizer_py,
            "tokenizer_path": self.tokenizer_path
        }
        logger.info("Request starting tokenizer")
        requests.post(TOKENIZER_START_API.format(self.tokenizer_ip), json=data)

    def __change_status(self, new_status: LlmStatus):
        with self.status_lock:
            self.status = new_status
        self.status_history.append(new_status)
        if new_status == LlmStatus.READY:
            self.ready_event.set()
        else:
            self.ready_event.clear()
        if new_status == LlmStatus.ANSWERING_DONE:
            self.prompt_answered_event.set()

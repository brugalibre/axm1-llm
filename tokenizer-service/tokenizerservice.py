import logging
import re
import subprocess
import threading
from enum import Enum
from fastapi import HTTPException

Status = Enum("Status", [
    ("IDLE", 1),
    ("INIT", 2),
    ("READY", 3)
])

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

# Actual I'd expect "Server running at" but somehow thats not printed although tokenizer server is ready
TOKENIZER_READY_PATTERN = re.compile("(.*)(Models won't be available and only tokenizers)(.*)")

class TokenizerService:
    def __handle_tokenizer_output(self, pipe):
        for line in iter(pipe.readline, ''):
            logger.debug(f"Tokenizer output '{line}'")
            if TOKENIZER_READY_PATTERN.match(line) != None:
                self.status = Status.READY
                logger.info(f"Tokenizer '{self.tokenizer_path}' ready!")

    def __init__(self, tokenizer_py: str, tokenizer_path: str, port: int):
        self.status = Status.IDLE
        self.process = None
        self.tokenizer_py = tokenizer_py
        self.port = port
        self.tokenizer_path = tokenizer_path
        logger.debug(f"Tokenizer {tokenizer_path}/{tokenizer_py} at port {self.port} created..")

    def __start_tokenizer_internal(self):
        logger.info(f"Starting tokenizer {self.tokenizer_path}/{self.tokenizer_py} at port {self.port}")
        self.status = Status.INIT
        self.process = subprocess.Popen(
            ["python", self.tokenizer_py, "--port", str(self.port)], cwd=self.tokenizer_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logger.debug(f"Tokenizer started, got process {self.process}..")

        # Handle stdout and stderr in threads
        threading.Thread(target=self.__handle_tokenizer_output, args=(self.process.stdout,), daemon=True).start()
        threading.Thread(target=self.__handle_tokenizer_output, args=(self.process.stderr,), daemon=True).start()

    def start_tokenizer(self) -> str:
        if self.status != Status.IDLE:
            raise HTTPException(status_code=500, detail=f"Tokenizer already started!")
        self.__start_tokenizer_internal()
        return "ok"

    def get_status(self):
        return self.status.name

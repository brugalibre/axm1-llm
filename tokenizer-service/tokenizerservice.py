import logging
import re
import subprocess
import threading
from enum import Enum
from fastapi import HTTPException
from time import sleep


class TokenizerStatus(Enum):
    IDLE = 1
    INIT = 2
    READY = 3

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

# Actual I'd expect "Server running at" but somehow that's not printed although tokenizer server is ready
TOKENIZER_READY_PATTERN = re.compile("(.*)(Models won't be available and only tokenizers)(.*)")

class TokenizerService:
    def __handle_tokenizer_output(self, pipe, tag):
        for line in pipe:
            line = line.rstrip("\n")
            logger.debug(f"Msg from tokenizer: '{line}' and tag '{tag}'")
            if TOKENIZER_READY_PATTERN.match(line) != None:
                # Wait for another 2 seconds to make sure the tokenizer is ready as soon as the llm tries to connect
                sleep(1.5)
                self.status = TokenizerStatus.READY
                logger.info(f"Tokenizer '{self.tokenizer_path}' ready!")

    def __init__(self, tokenizer_py: str, tokenizer_path: str, port: int):
        self.status = TokenizerStatus.IDLE
        self.process = None
        self.tokenizer_py = tokenizer_py
        self.port = port
        self.tokenizer_path = tokenizer_path
        logger.debug(f"Tokenizer {tokenizer_path}/{tokenizer_py} at port {self.port} created..")

    def __start_tokenizer_internal(self):
        logger.info(f"Starting tokenizer {self.tokenizer_path}/{self.tokenizer_py} at port {self.port}")
        self.status = TokenizerStatus.INIT
        self.process = subprocess.Popen(
            ["python3", self.tokenizer_py, "--port", str(self.port)], cwd=self.tokenizer_path,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        logger.debug(f"Tokenizer started, got process {self.process}..")

        # Handle stdout and stderr in threads
        threading.Thread(target=self.__handle_tokenizer_output, args=(self.process.stdout, "STDOUT",), daemon=True).start()
        threading.Thread(target=self.__handle_tokenizer_output, args=(self.process.stderr, "STDERR",), daemon=True).start()

    def start_tokenizer(self) -> str:
        if self.status != TokenizerStatus.IDLE:
            raise HTTPException(status_code=500, detail=f"Tokenizer already started!")
        self.__start_tokenizer_internal()
        return "ok"

    def get_status(self) -> TokenizerStatus:
        return self.status

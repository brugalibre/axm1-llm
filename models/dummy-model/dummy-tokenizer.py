#!/usr/bin/env python3

import logging
from time import sleep

logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.DEBUG)

def main():
    print("Dummy-Tokenizer: Dummy tokenizer started")
    sleep(2)
    print("Dummy-Tokenizer: Models won't be available and only tokenizers")
    sleep(2)
    print("Dummy-Tokenizer: Server @127.0.0.1:5110")

if __name__ == "__main__":main()
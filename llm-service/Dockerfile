FROM python:3.11-bookworm

RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libopencv-core406 \
    pciutils udev kmod git curl bash build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app


# --- Install Python dependencies ---
RUN pip install --no-cache-dir fastapi uvicorn requests

# Copie python files for service and api
COPY llm-service/main.py .
COPY llm-service/metrics.py .
COPY llm-service/llmservice.py .

COPY tokenizer-service/tokenizerservice.py .

COPY models/modelhelper.py .

# Prepare runtime directories
RUN mkdir -p /usr/lib/axcl

EXPOSE 11535

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "11535"]

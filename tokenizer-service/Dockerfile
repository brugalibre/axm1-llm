FROM python:3.11-slim

WORKDIR /app

# Prepare python environment
COPY tokenizer-service/requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir fastapi uvicorn

# Copy required ressources
COPY llm-service/metrics.py .
COPY llm-service/llmservice.py .

COPY tokenizer-service/main.py .
COPY tokenizer-service/tokenizerservice.py .

COPY models/modelhelper.py .


# Expose port & define entry-point
EXPOSE 8101
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8101"]

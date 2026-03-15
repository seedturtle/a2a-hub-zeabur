FROM python:3.11-slim

WORKDIR /app

ENV PORT=8080

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx python-multipart

# Copy application
COPY main.py .

# Run
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

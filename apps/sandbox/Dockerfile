FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

COPY src/ ./src/

ENV PORT=8000
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "sandbox.main:app", "--host", "0.0.0.0", "--port", "8000"]

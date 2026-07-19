FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY ingestion_api ./ingestion_api

EXPOSE 8001
ENV INGESTION_API_PORT=8001

CMD ["uvicorn", "ingestion_api.api.main:app", "--host", "0.0.0.0", "--port", "8001"]

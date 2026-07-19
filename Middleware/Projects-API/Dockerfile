FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY projects_api ./projects_api

EXPOSE 8003
ENV PROJECTS_API_PORT=8003

CMD ["uvicorn", "projects_api.api.main:app", "--host", "0.0.0.0", "--port", "8003"]

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY admin_api ./admin_api

EXPOSE 8002
ENV ADMIN_API_PORT=8002

CMD ["uvicorn", "admin_api.api.main:app", "--host", "0.0.0.0", "--port", "8002"]

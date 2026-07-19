# Build context must be the repo root so the sibling Agents/ package is available:
#   docker build -f Middleware/RiskAnalytics-API/Dockerfile -t risk-analytics-api .
FROM python:3.12-slim

WORKDIR /app

# Install the local agents package first, then the service.
COPY Agents /app/Agents
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir /app/Agents

COPY Middleware/RiskAnalytics-API/pyproject.toml /app/service/
RUN pip install --no-cache-dir /app/service
COPY Middleware/RiskAnalytics-API/risk_analytics_api /app/service/risk_analytics_api

WORKDIR /app/service
EXPOSE 8004
ENV RISK_ANALYTICS_API_PORT=8004

# ANTHROPIC_API_KEY must be provided at runtime (never baked into the image).
CMD ["uvicorn", "risk_analytics_api.api.main:app", "--host", "0.0.0.0", "--port", "8004"]

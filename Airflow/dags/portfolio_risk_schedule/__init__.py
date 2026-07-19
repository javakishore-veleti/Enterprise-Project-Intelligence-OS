"""Scheduled portfolio-level risk analysis DAG package.

Airflow owns *operational* work only. The tasks in this package trigger
portfolio-level (cross-project) multi-agent risk analysis by calling the
RiskAnalytics-API FastAPI boundary over HTTP — they never touch the databases
directly and never contain any agent/LLM/reasoning logic.

NOTE: the portfolio analysis endpoint is *planned* and may not yet exist in the
RiskAnalytics-API. This DAG calls the implemented endpoint; see
``tasks.py``.
"""

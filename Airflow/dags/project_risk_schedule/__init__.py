"""Scheduled per-project risk analysis DAG package.

Airflow owns *operational* work only. The tasks in this package trigger
multi-agent risk analysis for a configured set of projects by calling the
RiskAnalytics-API FastAPI boundary over HTTP — they never touch the databases
directly and never contain any agent/LLM/reasoning logic. The agents and their
prompts live behind the FastAPI/LangGraph boundary, not in the DAG.
"""

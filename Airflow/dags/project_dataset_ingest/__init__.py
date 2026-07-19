"""Project dataset ingestion DAG package.

Airflow owns *operational* work only. The tasks in this package trigger and
monitor dataset ingestion by calling the Ingestion-API FastAPI boundary over
HTTP — they never touch the databases directly and never contain any
agent/LLM/reasoning logic.
"""

"""Project dataset validation DAG package.

Airflow owns *operational* work only. The tasks in this package validate the
imported dataset records by calling the Ingestion-API FastAPI boundary over
HTTP — they never touch the databases directly and never contain any
agent/LLM/reasoning logic.
"""

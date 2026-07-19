"""Project dataset reconciliation DAG package.

Airflow owns *operational* work only. The tasks in this package reconcile
source-vs-destination record counts by calling the Ingestion-API FastAPI
boundary over HTTP — they never touch the databases directly and never contain
any agent/LLM/reasoning logic.
"""

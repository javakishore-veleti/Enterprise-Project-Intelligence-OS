"""Project dataset indexing DAG package.

Airflow owns *operational* work only. The tasks in this package create the
database indexes for the imported dataset by calling the Ingestion-API FastAPI
boundary over HTTP — they never touch the databases directly and never contain
any agent/LLM/reasoning logic.
"""

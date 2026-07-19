"""Project dataset acquisition DAG package.

Airflow owns *operational* work only. The tasks in this package acquire
(download), checksum-verify, and extract the public dataset by calling the
Ingestion-API FastAPI boundary over HTTP — they never touch the databases
directly and never contain any agent/LLM/reasoning logic.
"""

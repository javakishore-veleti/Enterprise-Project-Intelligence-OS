"""Shared pytest setup for the Airflow test suite.

Configures a throwaway ``AIRFLOW_HOME`` and points Airflow at this repo's
``dags/`` folder *before* any airflow import happens, and makes the DAG package
importable (``from project_dataset_ingest import ...``) without booting a
scheduler.
"""

import os
import sys
import tempfile
from pathlib import Path

AIRFLOW_DIR = Path(__file__).resolve().parents[1]
DAGS_DIR = AIRFLOW_DIR / "dags"

# Use an isolated, throwaway AIRFLOW_HOME so tests never touch a real install.
_airflow_home = tempfile.mkdtemp(prefix="airflow_home_")
os.environ.setdefault("AIRFLOW_HOME", _airflow_home)
os.environ["AIRFLOW__CORE__DAGS_FOLDER"] = str(DAGS_DIR)
os.environ["AIRFLOW__CORE__LOAD_EXAMPLES"] = "False"
os.environ["AIRFLOW__CORE__UNIT_TEST_MODE"] = "True"
# Keep DAG parsing fast and quiet during tests.
os.environ.setdefault("AIRFLOW__LOGGING__LOGGING_LEVEL", "ERROR")

# The dags folder must be importable so DAG modules can do package imports.
if str(DAGS_DIR) not in sys.path:
    sys.path.insert(0, str(DAGS_DIR))

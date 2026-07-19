"""Domain exception hierarchy shared across layers.

Services and DAOs raise these; the API layer's exception handlers translate
them into standard HTTP error responses. Layers never leak framework or driver
exceptions upward.
"""
from __future__ import annotations


class IngestionError(Exception):
    """Base class for all Ingestion API domain errors."""

    #: Machine-readable, stable error code returned to clients.
    code: str = "ingestion_error"
    #: Default HTTP status the API layer maps this error to.
    http_status: int = 500


class NotFoundError(IngestionError):
    code = "not_found"
    http_status = 404


class ValidationError(IngestionError):
    code = "validation_error"
    http_status = 422


class ConflictError(IngestionError):
    code = "conflict"
    http_status = 409


class DependencyUnavailableError(IngestionError):
    """A downstream dependency (database, Airflow) is unreachable."""

    code = "dependency_unavailable"
    http_status = 503

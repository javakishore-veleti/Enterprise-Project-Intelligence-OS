"""Domain exception hierarchy shared across layers.

Services and DAOs raise these; the API layer's exception handlers translate
them into standard HTTP error responses. Layers never leak framework or driver
exceptions upward.
"""
from __future__ import annotations


class AdminError(Exception):
    """Base class for all Admin API domain errors."""

    code: str = "admin_error"
    http_status: int = 500


class NotFoundError(AdminError):
    code = "not_found"
    http_status = 404


class ValidationError(AdminError):
    code = "validation_error"
    http_status = 422


class DependencyUnavailableError(AdminError):
    """A downstream dependency (database) is unreachable."""

    code = "dependency_unavailable"
    http_status = 503

"""Domain exception hierarchy shared across layers.

Services and DAOs raise these; the API layer's exception handlers translate
them into standard HTTP error responses. Layers never leak framework or driver
exceptions upward.
"""
from __future__ import annotations


class ProjectsError(Exception):
    """Base class for all Projects API domain errors."""

    code: str = "projects_error"
    http_status: int = 500


class NotFoundError(ProjectsError):
    code = "not_found"
    http_status = 404


class ValidationError(ProjectsError):
    code = "validation_error"
    http_status = 422


class ConflictError(ProjectsError):
    """A resource with the same identity already exists."""

    code = "conflict"
    http_status = 409


class DependencyUnavailableError(ProjectsError):
    """A downstream dependency (MongoDB) is unreachable."""

    code = "dependency_unavailable"
    http_status = 503

"""Domain exception hierarchy shared across layers.

Services and DAOs raise these; the API layer's exception handlers translate
them into standard HTTP error responses. Layers never leak framework or driver
exceptions upward.
"""
from __future__ import annotations


class OrgManagementError(Exception):
    """Base class for all Org-Management API domain errors."""

    #: Machine-readable, stable error code returned to clients.
    code: str = "org_management_error"
    #: Default HTTP status the API layer maps this error to.
    http_status: int = 500


class NotFoundError(OrgManagementError):
    code = "not_found"
    http_status = 404


class ValidationError(OrgManagementError):
    code = "validation_error"
    http_status = 422


class ConflictError(OrgManagementError):
    code = "conflict"
    http_status = 409


class DependencyUnavailableError(OrgManagementError):
    """A downstream dependency (database) is unreachable."""

    code = "dependency_unavailable"
    http_status = 503

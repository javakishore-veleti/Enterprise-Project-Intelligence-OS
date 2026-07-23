"""Composition root: wire DAOs -> services -> facades for injection.

Routers depend on facades via these providers. Assembly lives here so the
layered wiring is declared in exactly one place.
"""
from __future__ import annotations

from functools import lru_cache

from org_management_api.common.configuration import get_settings
from org_management_api.daos.access import PostgresAccessDao
from org_management_api.daos.connection import Database
from org_management_api.daos.members import PostgresMembersDao
from org_management_api.daos.organizations import PostgresOrganizationsDao
from org_management_api.daos.repositories import PostgresRepositoriesDao
from org_management_api.daos.users import PostgresUsersDao
from org_management_api.facades.manage_members import ManageMembersFacade
from org_management_api.facades.manage_organizations import ManageOrganizationsFacade
from org_management_api.facades.manage_repositories import ManageRepositoriesFacade
from org_management_api.facades.resolve_access import ResolveAccessFacade
from org_management_api.services.access import DefaultAccessService
from org_management_api.services.membership import DefaultMembershipService
from org_management_api.services.organizations import DefaultOrganizationService
from org_management_api.services.repositories import DefaultRepositoryService


@lru_cache
def get_database() -> Database:
    return Database(get_settings())


def provide_manage_organizations_facade() -> ManageOrganizationsFacade:
    db = get_database()
    service = DefaultOrganizationService(PostgresOrganizationsDao(db))
    return ManageOrganizationsFacade(service)


def provide_manage_members_facade() -> ManageMembersFacade:
    db = get_database()
    service = DefaultMembershipService(
        PostgresUsersDao(db), PostgresMembersDao(db), PostgresOrganizationsDao(db))
    return ManageMembersFacade(service)


def provide_manage_repositories_facade() -> ManageRepositoriesFacade:
    db = get_database()
    service = DefaultRepositoryService(
        PostgresRepositoriesDao(db), PostgresOrganizationsDao(db))
    return ManageRepositoriesFacade(service)


def provide_resolve_access_facade() -> ResolveAccessFacade:
    db = get_database()
    service = DefaultAccessService(
        PostgresAccessDao(db), PostgresUsersDao(db), PostgresOrganizationsDao(db))
    return ResolveAccessFacade(service)

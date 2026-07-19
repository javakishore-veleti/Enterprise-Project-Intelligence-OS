"""Composition root: wire DAOs -> services -> facades for injection."""
from __future__ import annotations

from functools import lru_cache

from admin_api.common.configuration import get_settings
from admin_api.daos.agent_config import PostgresAgentConfigDao
from admin_api.daos.audit import PostgresAuditDao
from admin_api.daos.connection import Database
from admin_api.facades.get_audit_history import GetAuditHistoryFacade
from admin_api.facades.get_system_health import GetSystemHealthFacade
from admin_api.facades.manage_agents import ManageAgentsFacade
from admin_api.services.agent_management import DefaultAgentManagementService
from admin_api.services.audit_management import DefaultAuditManagementService
from admin_api.services.system_health import DefaultSystemHealthService


@lru_cache
def get_database() -> Database:
    return Database(get_settings())


def _config_dao() -> PostgresAgentConfigDao:
    return PostgresAgentConfigDao(get_database())


def _audit_dao() -> PostgresAuditDao:
    return PostgresAuditDao(get_database())


def provide_manage_agents_facade() -> ManageAgentsFacade:
    return ManageAgentsFacade(DefaultAgentManagementService(_config_dao(), _audit_dao()))


def provide_get_audit_history_facade() -> GetAuditHistoryFacade:
    return GetAuditHistoryFacade(DefaultAuditManagementService(_audit_dao()))


def provide_get_system_health_facade() -> GetSystemHealthFacade:
    return GetSystemHealthFacade(
        DefaultSystemHealthService(get_database(), _config_dao(), get_settings())
    )

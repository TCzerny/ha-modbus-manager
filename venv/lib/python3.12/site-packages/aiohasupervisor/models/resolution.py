"""Models for resolution center APIs."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from .base import Options, ResponseData

# --- ENUMS ----


class SuggestionType(StrEnum):
    """SuggestionType type.

    This is an incomplete list. Supervisor regularly adds new types of suggestions as
    they are discovered. Therefore when returning a suggestion, it may have a type that
    is not in this list parsed as strings on older versions of the client.
    """

    ADOPT_DATA_DISK = "adopt_data_disk"
    CLEAR_FULL_BACKUP = "clear_full_backup"
    CREATE_FULL_BACKUP = "create_full_backup"
    DISABLE_BOOT = "disable_boot"
    EXECUTE_INTEGRITY = "execute_integrity"
    EXECUTE_REBOOT = "execute_reboot"
    EXECUTE_REBUILD = "execute_rebuild"
    EXECUTE_RELOAD = "execute_reload"
    EXECUTE_REMOVE = "execute_remove"
    EXECUTE_REPAIR = "execute_repair"
    EXECUTE_RESET = "execute_reset"
    EXECUTE_RESTART = "execute_restart"
    EXECUTE_START = "execute_start"
    EXECUTE_STOP = "execute_stop"
    EXECUTE_UPDATE = "execute_update"
    REGISTRY_LOGIN = "registry_login"
    RENAME_DATA_DISK = "rename_data_disk"


class IssueType(StrEnum):
    """IssueType type.

    This is an incomplete list. Supervisor regularly adds new types of issues as they
    are discovered. Therefore when returning an issue, it may have a type that is not
    in this list parsed as strings on older versions of the client.
    """

    BOOT_FAIL = "boot_fail"
    CORRUPT_DOCKER = "corrupt_docker"
    CORRUPT_REPOSITORY = "corrupt_repository"
    CORRUPT_FILESYSTEM = "corrupt_filesystem"
    DETACHED_ADDON_MISSING = "detached_addon_missing"
    DETACHED_ADDON_REMOVED = "detached_addon_removed"
    DEVICE_ACCESS_MISSING = "device_access_missing"
    DISABLED_DATA_DISK = "disabled_data_disk"
    DNS_LOOP = "dns_loop"
    DNS_SERVER_FAILED = "dns_server_failed"
    DNS_SERVER_IPV6_ERROR = "dns_server_ipv6_error"
    DOCKER_CONFIG = "docker_config"
    DOCKER_RATELIMIT = "docker_ratelimit"
    FATAL_ERROR = "fatal_error"
    FREE_SPACE = "free_space"
    IPV4_CONNECTION_PROBLEM = "ipv4_connection_problem"
    MISSING_IMAGE = "missing_image"
    MOUNT_FAILED = "mount_failed"
    MULTIPLE_DATA_DISKS = "multiple_data_disks"
    NO_CURRENT_BACKUP = "no_current_backup"
    PWNED = "pwned"
    REBOOT_REQUIRED = "reboot_required"
    SECURITY = "security"
    TRUST = "trust"
    UPDATE_FAILED = "update_failed"
    UPDATE_ROLLBACK = "update_rollback"


class UnsupportedReason(StrEnum):
    """UnsupportedReason type.

    This is an incomplete list. Supervisor regularly adds new unsupported
    reasons as they are discovered. Therefore when returning a list of unsupported
    reasons, some may not be in this list parsed as strings on older versions of the
    client.
    """

    APPARMOR = "apparmor"
    CGROUP_VERSION = "cgroup_version"
    CONNECTIVITY_CHECK = "connectivity_check"
    CONTENT_TRUST = "content_trust"
    DBUS = "dbus"
    DNS_SERVER = "dns_server"
    DOCKER_CONFIGURATION = "docker_configuration"
    DOCKER_VERSION = "docker_version"
    JOB_CONDITIONS = "job_conditions"
    LXC = "lxc"
    NETWORK_MANAGER = "network_manager"
    OS = "os"
    OS_AGENT = "os_agent"
    PRIVILEGED = "privileged"
    RESTART_POLICY = "restart_policy"
    SOFTWARE = "software"
    SOURCE_MODS = "source_mods"
    SUPERVISOR_VERSION = "supervisor_version"
    SYSTEMD = "systemd"
    SYSTEMD_JOURNAL = "systemd_journal"
    SYSTEMD_RESOLVED = "systemd_resolved"
    VIRTUALIZATION_IMAGE = "virtualization_image"


class UnhealthyReason(StrEnum):
    """UnhealthyReason type.

    This is an incomplete list. Supervisor regularly adds new unhealthy
    reasons as they are discovered. Therefore when returning a list of unhealthy
    reasons, some may not be in this list parsed as strings on older versions of the
    client.
    """

    DOCKER = "docker"
    OSERROR_BAD_MESSAGE = "oserror_bad_message"
    PRIVILEGED = "privileged"
    SUPERVISOR = "supervisor"
    SETUP = "setup"
    UNTRUSTED = "untrusted"


class ContextType(StrEnum):
    """ContextType type."""

    ADDON = "addon"
    CORE = "core"
    DNS_SERVER = "dns_server"
    MOUNT = "mount"
    OS = "os"
    PLUGIN = "plugin"
    SUPERVISOR = "supervisor"
    STORE = "store"
    SYSTEM = "system"


class CheckType(StrEnum):
    """CheckType type.

    This is an incomplete list. Supervisor regularly adds new checks as they are
    discovered. Therefore when returning a list of checks, some may have a type that is
    not in this list parsed as strings on older versions of the client.
    """

    ADDON_PWNED = "addon_pwned"
    BACKUPS = "backups"
    CORE_SECURITY = "core_security"
    DETACHED_ADDON_MISSING = "detached_addon_missing"
    DETACHED_ADDON_REMOVED = "detached_addon_removed"
    DISABLED_DATA_DISK = "disabled_data_disk"
    DNS_SERVER_IPV6 = "dns_server_ipv6"
    DNS_SERVER = "dns_server"
    DOCKER_CONFIG = "docker_config"
    FREE_SPACE = "free_space"
    MULTIPLE_DATA_DISKS = "multiple_data_disks"
    NETWORK_INTERFACE_IPV4 = "network_interface_ipv4"
    SUPERVISOR_TRUST = "supervisor_trust"


# --- OBJECTS ----


@dataclass(frozen=True, slots=True)
class Suggestion(ResponseData):
    """Suggestion model."""

    type: SuggestionType | str
    context: ContextType
    reference: str | None
    uuid: UUID
    auto: bool


@dataclass(frozen=True, slots=True)
class Issue(ResponseData):
    """Issue model."""

    type: IssueType | str
    context: ContextType
    reference: str | None
    uuid: UUID


@dataclass(frozen=True, slots=True)
class Check(ResponseData):
    """Check model."""

    enabled: bool
    slug: CheckType | str


@dataclass(frozen=True, slots=True)
class SuggestionsList(ResponseData):
    """SuggestionsList model."""

    suggestions: list[Suggestion]


@dataclass(frozen=True, slots=True)
class ResolutionInfo(SuggestionsList, ResponseData):
    """ResolutionInfo model."""

    unsupported: list[UnsupportedReason | str]
    unhealthy: list[UnhealthyReason | str]
    issues: list[Issue]
    checks: list[Check]


@dataclass(frozen=True, slots=True)
class CheckOptions(Options):
    """CheckOptions model."""

    enabled: bool | None = None

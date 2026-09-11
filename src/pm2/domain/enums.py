from enum import StrEnum


class PhaseCode(StrEnum):
    LAUNCH = "LAUNCH"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    CLOSING = "CLOSING"
    MONITORING_CONTROL = "MONITORING_CONTROL"


class ProjectStatus(StrEnum):
    DRAFT = "DRAFT"
    LAUNCH = "LAUNCH"
    PLANNING = "PLANNING"
    EXECUTION = "EXECUTION"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class Severity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class GateDecisionType(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPROVED_WITH_RESERVES = "APPROVED_WITH_RESERVES"


class ResponsibilityType(StrEnum):
    R = "R"
    CM = "Cm"
    S = "S"
    C = "C"
    I = "I"  # noqa: E741 - code officiel de la matrice RCmSCI


class WorkflowError(ValueError):
    """Transition métier refusée avec un message utilisable par l'interface."""

from typing import List, Tuple, Literal, Set
from enum import StrEnum
from dataclasses import dataclass, field
from intalyzer.constants import ARDUINO_WRAPPER_LINES


class AccessType(StrEnum):
    """Type of access to a variable."""

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class AccessInfo:
    """Information about a global variable access."""

    line_number: int
    statement: str
    var_name: str
    access_type: Literal[AccessType.READ, AccessType.WRITE]
    protected: bool = False

    def __post_init__(self):
        object.__setattr__(self, "line_number", self.line_number -(ARDUINO_WRAPPER_LINES))

    def __str__(self) -> str:
        return f"Line {self.line_number}: {self.access_type} of '{self.var_name}' in '{self.statement}'"


@dataclass(frozen=True)
class ReadAccessInfo(AccessInfo):
    """Information about a global variable read access."""

    access_type: Literal[AccessType.READ] = AccessType.READ


@dataclass(frozen=True)
class WriteAccessInfo(AccessInfo):
    """Information about a global variable write access."""

    access_type: Literal[AccessType.WRITE] = AccessType.WRITE


@dataclass
class InterruptInfo:
    """Information about an interrupt."""

    name: str
    reads: Set[AccessInfo] = field(default_factory=set)
    writes: Set[AccessInfo] = field(default_factory=set)

    @property
    def read_vars(self) -> Set[str]:
        """Set of variables read by the interrupt."""
        return {access.var_name for access in self.reads}

    @property
    def write_vars(self) -> Set[str]:
        """Set of variables written by the interrupt."""
        return {access.var_name for access in self.writes}

    @property
    def vars(self) -> Set[str]:
        """Set of variables read or written by the interrupt."""
        return self.read_vars | self.write_vars

    @property
    def accesses(self) -> Set[AccessInfo]:
        """Set of all variable accesses in the interrupt."""
        return self.reads | self.writes

    def __str__(self) -> str:
        read_vars = {access.var_name for access in self.reads}
        write_vars = {access.var_name for access in self.writes}
        return f"Interrupt {self.name}: Reads {read_vars}, Writes {write_vars}"


@dataclass
class MainProgramInfo:
    """Information about the main program (setup/loop)."""

    reads: Set[AccessInfo] = field(default_factory=set)
    writes: Set[AccessInfo] = field(default_factory=set)
    protected_sections: List[Tuple[int, int]] = field(
        default_factory=list
    )  # Start and end lines of protected sections

    @property
    def accesses(self) -> Set[AccessInfo]:
        """Set of all variable accesses in the main program."""
        return self.reads | self.writes

    def __str__(self) -> str:
        read_vars = {access.var_name for access in self.reads}
        write_vars = {access.var_name for access in self.writes}
        return f"Main Program: Reads {read_vars}, Writes {write_vars}"


@dataclass
class RaceCondition:
    """A race condition between an interrupt and the main program."""

    var_name: str
    interrupt_name: str
    main_program_accesses: List[AccessInfo]
    interrupt_accesses: List[AccessInfo]

    def __str__(self) -> str:
        main_program_access_str = ", ".join([str(access) for access in self.main_program_accesses])
        interrupt_access_str = ", ".join([str(access) for access in self.interrupt_accesses])
        return f"Race condition on variable '{self.var_name}' in interrupt '{self.interrupt_name}':\nMain Program: {main_program_access_str}\nInterrupt: {interrupt_access_str}"

"""Pure, deterministic render graph values.

This module deliberately has no Blender dependency. Execution code can import,
serialize, compare, and test these values outside Blender.
"""

from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import Any, Mapping


def freeze(value):
    """Convert mutable containers to stable immutable equivalents."""
    if isinstance(value, dict):
        return tuple(sorted((str(key), freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(freeze(item) for item in value))
    return value


@dataclass(frozen=True)
class Override:
    """One executor-facing setting change."""

    path: str
    value: Any
    target_type: str = ""
    target_name: str = ""

    def __post_init__(self):
        if not self.path or self.path.startswith(".") or self.path.endswith("."):
            raise ValueError("Override path must be a non-empty dotted path")
        object.__setattr__(self, "value", freeze(self.value))


@dataclass(frozen=True)
class JobSpec:
    """Immutable description of one render job."""

    name: str = "Render"
    source_scene: str = ""
    overrides: tuple = field(default_factory=tuple)
    tags: tuple = field(default_factory=tuple)
    metadata: tuple = field(default_factory=tuple)

    def with_override(self, path, value, target_type="", target_name=""):
        replacement = Override(path, value, target_type, target_name)
        kept = tuple(
            item
            for item in self.overrides
            if (item.target_type, item.target_name, item.path)
            != (target_type, target_name, path)
        )
        return replace(
            self,
            overrides=tuple(
                sorted(
                    kept + (replacement,),
                    key=lambda item: (
                        item.target_type,
                        item.target_name,
                        item.path,
                    ),
                )
            ),
        )

    def with_overrides(self, values):
        result = self
        for path, value in sorted(values.items()):
            result = result.with_override(path, value)
        return result

    def with_metadata(self, key, value):
        values = dict(self.metadata)
        values[str(key)] = freeze(value)
        return replace(self, metadata=tuple(sorted(values.items())))

    def get_override(self, path, default=None):
        for item in self.overrides:
            if item.path == path:
                return item.value
        return default

    def override_map(self):
        return MappingProxyType({item.path: item.value for item in self.overrides})


@dataclass(frozen=True)
class JobList:
    """Stable collection used by list/index nodes and executors."""

    jobs: tuple = field(default_factory=tuple)

    def __iter__(self):
        return iter(self.jobs)

    def __len__(self):
        return len(self.jobs)

    def at(self, index):
        if not self.jobs:
            raise IndexError("Cannot index an empty job list")
        return self.jobs[index]


@dataclass(frozen=True)
class CompileResult:
    """Compiler output and deterministic diagnostics."""

    jobs: tuple
    diagnostics: tuple = field(default_factory=tuple)
    node_order: tuple = field(default_factory=tuple)

    @property
    def ok(self):
        return not any(item.severity == "ERROR" for item in self.diagnostics)


@dataclass(frozen=True)
class Diagnostic:
    severity: str
    code: str
    message: str
    node_name: str = ""
    socket_name: str = ""

    def sort_key(self):
        return (
            self.severity != "ERROR",
            self.node_name,
            self.socket_name,
            self.code,
            self.message,
        )

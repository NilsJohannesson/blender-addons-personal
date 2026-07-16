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
class ValueList:
    """Typed list of variant values from list nodes. Distinct from vector tuples."""

    items: tuple = field(default_factory=tuple)

    def __post_init__(self):
        object.__setattr__(self, "items", tuple(freeze(item) for item in self.items))

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)


@dataclass(frozen=True)
class TaskSpec:
    """Immutable description of one render task."""

    name: str = "Render"
    source_scene: str = ""
    overrides: tuple = field(default_factory=tuple)
    tags: tuple = field(default_factory=tuple)
    metadata: tuple = field(default_factory=tuple)
    # Pending VariantAxis values; expanded at compile output.
    axes: tuple = field(default_factory=tuple)

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

    def with_axis(self, axis):
        """Attach a deferred variant axis (expanded at job output)."""
        return replace(self, axes=self.axes + (axis,))

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
class TaskList:
    """Stable collection used by list/index nodes and executors."""

    tasks: tuple = field(default_factory=tuple)

    def __iter__(self):
        return iter(self.tasks)

    def __len__(self):
        return len(self.tasks)

    def at(self, index):
        if not self.tasks:
            raise IndexError("Cannot index an empty task list")
        return self.tasks[index]


@dataclass(frozen=True)
class CompileResult:
    """Compiler output and deterministic diagnostics."""

    tasks: tuple
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

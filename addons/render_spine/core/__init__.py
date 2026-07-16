"""Public execution-facing graph core API."""

from .compiler import CompileContext, CompileError, compile_tree
from .model import CompileResult, Diagnostic, TaskList, TaskSpec, Override, ValueList
from .validation import validate_tree
from .variants import (
    MAX_VARIANT_JOBS,
    VariantAxis,
    VariantError,
    apply_override_or_axis,
    cartesian_tasks,
    expand_pending_axes,
)


__all__ = (
    "CompileContext",
    "CompileError",
    "CompileResult",
    "Diagnostic",
    "TaskList",
    "TaskSpec",
    "MAX_VARIANT_JOBS",
    "Override",
    "ValueList",
    "VariantAxis",
    "VariantError",
    "apply_override_or_axis",
    "cartesian_tasks",
    "compile_tree",
    "expand_pending_axes",
    "validate_tree",
)

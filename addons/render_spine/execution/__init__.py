"""Public execution API for RenderSpine."""

from .adapter import (
    CompileFailure,
    compile_jobs,
    job_name,
    job_output,
    job_overrides,
    job_source_scene,
    output_status,
    summarize_jobs,
)
from .runtime import RUNTIME
from .runtime import register as register_runtime
from .runtime import unregister as unregister_runtime
from .transaction import Transaction, TransactionError


def register():
    register_runtime()


def unregister():
    unregister_runtime()


__all__ = (
    "CompileFailure",
    "RUNTIME",
    "Transaction",
    "TransactionError",
    "compile_jobs",
    "job_name",
    "job_output",
    "job_overrides",
    "job_source_scene",
    "output_status",
    "summarize_jobs",
    "register",
    "unregister",
)

"""Cartesian product of variant axes into task lists. No Blender dependency."""

from dataclasses import dataclass, field, replace
from itertools import product

from .model import Override, TaskList, TaskSpec, ValueList, freeze
from .path_template import alias_for_override_path


MAX_VARIANT_JOBS = 256

# Pre-built Override tuples from nodes that apply multiple RNA paths per value.
OVERRIDE_BUNDLE_PATH = "__rsp_override_bundle__"


class VariantError(ValueError):
    """Invalid variant axis or product size."""


@dataclass(frozen=True)
class VariantAxis:
    """One dimension of a render variant: path + values on an optional target."""

    label: str
    path: str
    values: tuple = field(default_factory=tuple)
    target_type: str = ""
    target_name: str = ""

    def __post_init__(self):
        if self.path == OVERRIDE_BUNDLE_PATH:
            pass
        elif not self.path or self.path.startswith(".") or self.path.endswith("."):
            raise ValueError("VariantAxis path must be a non-empty dotted path")
        if not self.label:
            raise ValueError("VariantAxis label must be non-empty")
        object.__setattr__(self, "values", tuple(freeze(item) for item in self.values))


def _value_label(value):
    if isinstance(value, tuple) and value:
        if all(isinstance(item, Override) for item in value):
            for item in value:
                if item.target_type == "collections" and item.target_name:
                    return item.target_name
            return "bundle"
    name = getattr(value, "name", None)
    if isinstance(name, str) and name:
        return name
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        text = "{:g}".format(value)
        return text.replace(".", "p")
    if isinstance(value, (tuple, list)):
        parts = [_value_label(item) for item in value]
        return "x".join(parts)
    text = str(value).strip()
    for char in '\\/:"<>|*?':
        text = text.replace(char, "_")
    return text.replace(" ", "_") or "value"


def _combo_label(axes, combo):
    parts = []
    for axis, value in zip(axes, combo):
        parts.append("{}={}".format(axis.label, _value_label(value)))
    return "_".join(parts)


def _axis_label(path, label=""):
    if label:
        return label
    alias = alias_for_override_path(path)
    if alias:
        return alias
    return path.rsplit(".", 1)[-1]


def _apply_axis_value(job, axis, value):
    if axis.path != OVERRIDE_BUNDLE_PATH:
        return job.with_override(
            axis.path,
            value,
            target_type=axis.target_type,
            target_name=axis.target_name,
        )
    if not isinstance(value, tuple) or not value:
        raise VariantError("Override bundle axis requires a non-empty tuple")
    collection_name = ""
    for item in value:
        if not isinstance(item, Override):
            raise VariantError("Override bundle values must be Override tuples")
        job = job.with_override(
            item.path,
            item.value,
            target_type=item.target_type,
            target_name=item.target_name,
        )
        if item.target_type == "collections" and item.target_name:
            collection_name = item.target_name
    if collection_name:
        job = job.with_metadata("collection", collection_name)
    return job


def apply_override_or_axis(
    job, path, value, target_type="", target_name="", label=""
):
    """Scalar → override; ValueList → deferred VariantAxis on the job."""
    if not isinstance(job, TaskSpec):
        raise TypeError("apply_override_or_axis requires a TaskSpec")
    if isinstance(value, ValueList):
        if not value.items:
            raise VariantError(
                "Variant list for {!r} is empty".format(path)
            )
        return job.with_axis(
            VariantAxis(
                label=_axis_label(path, label),
                path=path,
                values=tuple(value.items),
                target_type=target_type,
                target_name=target_name,
            )
        )
    return job.with_override(
        path, value, target_type=target_type, target_name=target_name
    )


def cartesian_tasks(base_job, axes=()):
    """Expand ``base_job`` across pending + explicit ``axes`` into a TaskList."""
    if not isinstance(base_job, TaskSpec):
        raise TypeError("cartesian_tasks requires a TaskSpec base job")
    pending = tuple(base_job.axes or ())
    axes = pending + tuple(axes)
    if not axes:
        raise VariantError("Render Variants requires at least one axis")
    for axis in axes:
        if not isinstance(axis, VariantAxis):
            raise TypeError("Each axis must be a VariantAxis")
        if not axis.values:
            raise VariantError(
                "Variant axis {!r} has no values".format(axis.label)
            )

    sizes = [len(axis.values) for axis in axes]
    total = 1
    for size in sizes:
        total *= size
    if total > MAX_VARIANT_JOBS:
        raise VariantError(
            "Variant product size {} exceeds limit {}".format(
                total, MAX_VARIANT_JOBS
            )
        )

    base_name = base_job.name or "Render"
    cleared = replace(base_job, axes=())
    jobs = []
    for index, combo in enumerate(product(*(axis.values for axis in axes))):
        job = replace(cleared, name="{}_{:03d}".format(base_name, index))
        for axis, value in zip(axes, combo):
            job = _apply_axis_value(job, axis, value)
        label = _combo_label(axes, combo)
        job = job.with_metadata("variant_index", index).with_metadata(
            "variant", label
        )
        jobs.append(job)
    return TaskList(tuple(jobs))


def expand_pending_axes(job):
    """Expand deferred axes on a job, or return a one-job list."""
    if not isinstance(job, TaskSpec):
        raise TypeError("expand_pending_axes requires a TaskSpec")
    axes = tuple(job.axes or ())
    if not axes:
        return TaskList((job,))
    return cartesian_tasks(replace(job, axes=()), axes)

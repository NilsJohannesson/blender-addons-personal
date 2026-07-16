"""Pure cartesian variant expansion (runs under Blender test harness)."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import Override, TaskSpec, ValueList
from render_spine.core.variants import (
    MAX_VARIANT_JOBS,
    OVERRIDE_BUNDLE_PATH,
    VariantAxis,
    VariantError,
    apply_override_or_axis,
    cartesian_tasks,
    expand_pending_axes,
)


base = TaskSpec(name="Beauty").with_override("frame_start", 1)

colors = VariantAxis(
    label="color",
    path="data.color",
    values=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 1.0, 0.0)),
    target_type="objects",
    target_name="Area",
)
intensities = VariantAxis(
    label="intensity",
    path="data.energy",
    values=(1.0, 10.0),
    target_type="objects",
    target_name="Area",
)

# Axis order: first axis varies slowest → intensity blocks of 4 colors.
jobs = cartesian_tasks(base, (intensities, colors))
assert_equal(len(jobs), 8)
assert_equal(jobs.at(0).name, "Beauty_000")
assert_equal(jobs.at(0).get_override("data.energy"), 1.0)
assert_equal(jobs.at(0).get_override("data.color"), (1.0, 0.0, 0.0))
assert_equal(jobs.at(3).get_override("data.energy"), 1.0)
assert_equal(jobs.at(3).get_override("data.color"), (1.0, 1.0, 0.0))
assert_equal(jobs.at(4).get_override("data.energy"), 10.0)
assert_equal(jobs.at(4).get_override("data.color"), (1.0, 0.0, 0.0))

meta0 = dict(jobs.at(0).metadata)
assert_equal(meta0["variant_index"], 0)
assert_equal(meta0["variant"], "intensity=1_color=1x0x0")

# Empty axes rejected.
try:
    cartesian_tasks(base, ())
except VariantError:
    pass
else:
    raise AssertionError("Empty axes should fail")

try:
    cartesian_tasks(
        base,
        (VariantAxis(label="empty", path="cycles.samples", values=()),),
    )
except VariantError:
    pass
else:
    raise AssertionError("Empty axis values should fail")

# Product size cap.
big = VariantAxis(
    label="n",
    path="cycles.samples",
    values=tuple(range(MAX_VARIANT_JOBS + 1)),
)
try:
    cartesian_tasks(base, (big,))
except VariantError:
    pass
else:
    raise AssertionError("Oversized product should fail")

# Deterministic second compile.
again = cartesian_tasks(base, (intensities, colors))
assert_equal(jobs.tasks, again.tasks)

# Deferred axes via ValueList on a job expand at output.
deferred = apply_override_or_axis(
    TaskSpec(name="Sweep"),
    "data.color",
    ValueList(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))),
    target_type="objects",
    target_name="Area",
    label="color",
)
deferred = apply_override_or_axis(deferred, "data.energy", 5.0, "objects", "Area")
assert_equal(len(deferred.axes), 1)
assert_equal(deferred.get_override("data.energy"), 5.0)
expanded = expand_pending_axes(deferred)
assert_equal(len(expanded), 3)
assert_equal(expanded.at(0).get_override("data.color"), (1.0, 0.0, 0.0))
assert_equal(expanded.at(0).get_override("data.energy"), 5.0)
assert_equal(expanded.at(2).name, "Sweep_002")

bundle = (
    Override(
        "hide_render",
        True,
        target_type="collections",
        target_name="spot",
    ),
)
bundled = cartesian_tasks(
    TaskSpec(name="Vis"),
    (
        VariantAxis(
            label="collection",
            path=OVERRIDE_BUNDLE_PATH,
            values=(bundle,),
        ),
    ),
)
assert_equal(len(bundled), 1)
assert_equal(bundled.at(0).get_override("hide_render"), True)
assert_equal(dict(bundled.at(0).metadata).get("collection"), "spot")

extension.unregister()
finish("variants")

"""Exercise queue completion/cancellation restoration paths."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import JobSpec
from render_spine.execution.runtime import RUNTIME
from render_spine.execution.transaction import Transaction


scene = bpy.context.scene
old_frame = scene.frame_start
old_lock = scene.render.use_lock_interface
job = JobSpec(name="Queue").with_override("frame_start", old_frame + 5)

RUNTIME.configure_queue([job], [0], scene)
transaction = Transaction("Cancel")
transaction.apply(job.overrides, bpy.context, bpy)
RUNTIME.current = transaction
RUNTIME.current_scene = scene
RUNTIME.old_lock_interface = old_lock
scene.render.use_lock_interface = True

RUNTIME.signal("CANCEL")
assert_equal(scene.frame_start, old_frame)
assert_equal(scene.render.use_lock_interface, old_lock)
assert_equal(RUNTIME.consume_event(), "CANCEL")
RUNTIME.finish_queue("Cancelled")
assert_equal(scene.rsp_state.rendering, False)

RUNTIME.configure_queue([job], [0], scene)
transaction = Transaction("Complete")
transaction.apply(job.overrides, bpy.context, bpy)
RUNTIME.current = transaction
RUNTIME.current_scene = scene
RUNTIME.old_lock_interface = old_lock
RUNTIME.signal("COMPLETE")
assert_equal(scene.frame_start, old_frame)
assert_equal(RUNTIME.consume_event(), "COMPLETE")
assert_equal(RUNTIME.position, 1)
RUNTIME.finish_queue()

extension.unregister()
finish("queue_state")

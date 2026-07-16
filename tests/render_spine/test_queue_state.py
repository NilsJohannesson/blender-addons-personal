"""Exercise queue completion/cancellation restoration paths."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import TaskSpec
from render_spine.execution.runtime import RUNTIME
from render_spine.execution.transaction import Transaction


scene = bpy.context.scene
old_frame = scene.frame_start
job = TaskSpec(name="Queue").with_override("frame_start", old_frame + 5)

tree = bpy.data.node_groups.new("NRN Processor UI", "RenderSpineNodeTree")
processor = tree.nodes.new("RenderSpineNodeProcessor")

RUNTIME.configure_queue([job], [0], scene)
assert_equal(RUNTIME.queue_items(), (("Queue", "current"),))
assert_equal(processor.active, True)
assert_equal(processor.task_list, "Queue")
assert_equal(processor.cur_task, "Queue")
transaction = Transaction("Cancel")
transaction.apply(job.overrides, bpy.context, bpy)
RUNTIME.current = transaction
RUNTIME.current_scene = scene

RUNTIME.signal("CANCEL")
assert_equal(RUNTIME.consume_event(), "CANCEL")
assert_equal(scene.frame_start, old_frame)
RUNTIME.finish_queue("Cancelled")
assert_equal(scene.rsp_state.rendering, False)

RUNTIME.configure_queue([job], [0], scene)
transaction = Transaction("Complete")
transaction.apply(job.overrides, bpy.context, bpy)
RUNTIME.current = transaction
RUNTIME.current_scene = scene
RUNTIME.signal("COMPLETE")
assert_equal(RUNTIME.consume_event(), "COMPLETE")
assert_equal(scene.frame_start, old_frame)
assert_equal(RUNTIME.position, 1)
RUNTIME.finish_queue()
assert_equal(RUNTIME.queue_items(), (("Queue", "done"),))
assert_equal(RUNTIME.queue_finished, True)
assert_equal(processor.cur_task, "Queue")
assert_equal(processor.active, True)

bpy.data.node_groups.remove(tree)

extension.unregister()
finish("queue_state")

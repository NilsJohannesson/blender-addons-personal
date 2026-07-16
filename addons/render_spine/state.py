"""Persistent UI state; live object references stay in execution.runtime."""

import bpy
from bpy.props import BoolProperty, IntProperty, PointerProperty, StringProperty


class RSP_SceneState(bpy.types.PropertyGroup):
    compile_ok: BoolProperty(default=False)
    has_error: BoolProperty(default=False)
    transaction_active: BoolProperty(default=False)
    rendering: BoolProperty(default=False)
    active_job_index: IntProperty(default=0, min=0)
    job_count: IntProperty(default=0, min=0)
    queue_position: IntProperty(default=0, min=0)
    queue_total: IntProperty(default=0, min=0)
    status_message: StringProperty(default="Not compiled")
    dry_run_summary: StringProperty(default="")
    output_path: StringProperty(default="")
    output_exists: BoolProperty(default=False)
    output_status: StringProperty(default="")


_CLASSES = (RSP_SceneState,)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rsp_state = PointerProperty(type=RSP_SceneState)


def unregister():
    if hasattr(bpy.types.Scene, "rsp_state"):
        del bpy.types.Scene.rsp_state
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

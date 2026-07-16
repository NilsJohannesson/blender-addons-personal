"""Node Editor header and sidebar controls."""

import bpy

from .operators import active_tree, is_render_tree


def _draw_status(layout, state):
    row = layout.row(align=True)
    if state.has_error:
        icon = "ERROR"
    elif state.compile_ok:
        icon = "CHECKMARK"
    else:
        icon = "INFO"
    row.label(text=state.status_message, icon=icon)

    if state.task_count:
        row = layout.row(align=True)
        row.prop(
            state,
            "active_task_index",
            text=f"Task Index (0-{state.task_count - 1})",
        )
        row.label(text=f"/ {state.task_count - 1}")

    if state.rendering:
        layout.label(
            text=f"Queue {state.queue_position}/{state.queue_total}",
            icon="RENDER_ANIMATION",
        )
    if state.output_status:
        icon = "CHECKMARK" if state.output_exists else "INFO"
        layout.label(text=state.output_status, icon=icon)
        if state.output_path:
            layout.label(text=state.output_path)


def _draw_actions(layout, state):
    row = layout.row(align=True)
    row.enabled = not state.rendering
    row.operator("rsp.compile_preview", text="Preview", icon="VIEWZOOM")
    row.operator("rsp.apply", text="Apply", icon="IMPORT")
    restore = row.row(align=True)
    restore.enabled = state.transaction_active
    restore.operator("rsp.restore", text="Restore", icon="LOOP_BACK")

    row = layout.row(align=True)
    row.enabled = not state.rendering
    row.operator("rsp.render_selected", icon="RENDER_STILL")
    row.operator("rsp.render_all", icon="RENDER_ANIMATION")
    if state.rendering:
        layout.operator("rsp.cancel_render", icon="CANCEL")


def _draw_header(self, context):
    tree = active_tree(context)
    if not is_render_tree(tree):
        return
    state = getattr(context.scene, "rsp_state", None)
    if state is None:
        return
    layout = self.layout
    layout.separator_spacer()
    if state.rendering:
        layout.label(
            text=f"{state.queue_position}/{state.queue_total}",
            icon="RENDER_ANIMATION",
        )
        layout.operator("rsp.cancel_render", text="", icon="CANCEL")
    else:
        icon = "CHECKMARK" if state.compile_ok else "INFO"
        layout.label(text=f"{state.task_count} tasks", icon=icon)
        layout.operator("rsp.compile_preview", text="", icon="FILE_REFRESH")
        layout.operator("rsp.render_selected", text="", icon="RENDER_STILL")
        layout.operator("rsp.render_all", text="", icon="RENDER_ANIMATION")


class RSP_PT_render_tasks(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "RenderSpine"
    bl_label = "Render Tasks"

    @classmethod
    def poll(cls, context):
        return is_render_tree(active_tree(context))

    def draw(self, context):
        state = context.scene.rsp_state
        layout = self.layout
        _draw_status(layout, state)
        layout.separator()
        _draw_actions(layout, state)


class RSP_PT_dry_run(bpy.types.Panel):
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "RenderSpine"
    bl_label = "Dry-Run Summary"
    bl_parent_id = "RSP_PT_render_tasks"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return is_render_tree(active_tree(context))

    def draw(self, context):
        summary = context.scene.rsp_state.dry_run_summary
        column = self.layout.column(align=True)
        if not summary:
            column.label(text="Run Preview to compile tasks", icon="INFO")
            return
        for line in summary.splitlines():
            column.label(text=line)


_CLASSES = (
    RSP_PT_render_tasks,
    RSP_PT_dry_run,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.NODE_HT_header.append(_draw_header)


def unregister():
    try:
        bpy.types.NODE_HT_header.remove(_draw_header)
    except (ValueError, RuntimeError):
        pass
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

"""User operations for compiling, applying, and rendering tasks."""

import bpy

from .execution import (
    CompileFailure,
    RUNTIME,
    TransactionError,
    compile_tasks,
    task_name,
    task_overrides,
    output_status,
    summarize_tasks,
)
from .execution.adapter import last_compile_warnings
from .execution.path_expand import PathTemplateError


def active_tree(context):
    space = getattr(context, "space_data", None)
    tree = getattr(space, "edit_tree", None) or getattr(space, "node_tree", None)
    return tree


def is_render_tree(tree):
    if tree is None:
        return False
    identifier = str(getattr(tree, "bl_idname", "")).upper()
    name = str(getattr(tree, "name", "")).upper()
    return (
        identifier.startswith("RSP_")
        or "RENDERSPINE" in identifier.replace("_", "")
        or ("RENDER" in identifier and "NODE" in identifier)
        or name.startswith("RENDERSPINE")
    )


def _state(context):
    return getattr(context.scene, "rsp_state", None)


def _compile(context):
    state = _state(context)
    try:
        jobs = compile_tasks(active_tree(context), context)
    except CompileFailure as exc:
        if state:
            state.compile_ok = False
            state.has_error = True
            state.task_count = 0
            state.status_message = str(exc)
            state.dry_run_summary = ""
        raise
    if state:
        state.compile_ok = True
        state.has_error = False
        state.task_count = len(jobs)
        state.active_task_index = min(
            state.active_task_index, max(0, len(jobs) - 1)
        )
        status = f"Compiled {len(jobs)} task(s)"
        warnings = last_compile_warnings()
        if warnings:
            status = "{} · {}".format(status, warnings[0])
        state.status_message = status
        state.dry_run_summary = summarize_tasks(jobs)
    return jobs

class RSP_OT_compile_preview(bpy.types.Operator):
    bl_idname = "rsp.compile_preview"
    bl_label = "Preview"
    bl_description = "Compile and show planned changes without mutating the scene"

    @classmethod
    def poll(cls, context):
        state = _state(context)
        return is_render_tree(active_tree(context)) and not (
            state and state.rendering
        )

    def execute(self, context):
        try:
            jobs = _compile(context)
        except CompileFailure as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        state = _state(context)
        if jobs and state:
            index = min(state.active_task_index, len(jobs) - 1)
            try:
                absolute, exists, message = output_status(
                    jobs[index], context.scene, bpy
                )
            except PathTemplateError as exc:
                self.report({"ERROR"}, str(exc))
                return {"CANCELLED"}
            state.output_path = absolute
            state.output_exists = exists
            state.output_status = message
        self.report({"INFO"}, f"Compiled {len(jobs)} task(s)")
        return {"FINISHED"}


class RSP_OT_apply(bpy.types.Operator):
    bl_idname = "rsp.apply"
    bl_label = "Apply"
    bl_description = "Apply selected task overrides transactionally"

    @classmethod
    def poll(cls, context):
        state = _state(context)
        return is_render_tree(active_tree(context)) and not (
            state and state.rendering
        )

    def execute(self, context):
        try:
            jobs = _compile(context)
            if not jobs:
                raise TransactionError("No tasks to apply")
            state = _state(context)
            index = min(state.active_task_index, len(jobs) - 1)
            RUNTIME.apply_task(
                jobs[index], context, task_name(jobs[index], index)
            )
        except (CompileFailure, TransactionError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Applied {len(task_overrides(jobs[index]))} overrides")
        return {"FINISHED"}


class RSP_OT_restore(bpy.types.Operator):
    bl_idname = "rsp.restore"
    bl_label = "Restore"
    bl_description = "Reverse the currently applied task overrides"

    @classmethod
    def poll(cls, context):
        state = _state(context)
        return bool(
            RUNTIME.applied
            and not RUNTIME.running
            and (not state or not state.rendering)
        )

    def execute(self, _context):
        error = RUNTIME.restore_applied()
        if error:
            self.report({"ERROR"}, error)
            return {"CANCELLED"}
        return {"FINISHED"}


class _RSP_RenderQueueMixin:
    _timer = None
    render_all = False

    @classmethod
    def poll(cls, context):
        state = _state(context)
        return is_render_tree(active_tree(context)) and not (
            RUNTIME.running or (state and state.rendering)
        )

    def invoke(self, context, _event):
        try:
            jobs = _compile(context)
            if not jobs:
                raise TransactionError("No tasks to render")
            state = _state(context)
            selected = min(state.active_task_index, len(jobs) - 1)
            indices = list(range(len(jobs))) if self.render_all else [selected]
            RUNTIME.configure_queue(jobs, indices, context.scene)
            # Start first task before taking modal focus. A failure here used to
            # leave a modal handler registered and crash Blender's status bar.
            RUNTIME.start_next(context)
        except Exception as exc:
            RUNTIME.finish_queue(str(exc), error=True)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self._timer = context.window_manager.event_timer_add(
            0.1, window=context.window
        )
        RUNTIME.attach_timer(context.window_manager, self._timer)
        RUNTIME.refresh_processor_ui()
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type == "ESC":
            RUNTIME.request_cancel()
            return {"RUNNING_MODAL"}
        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        # Upstream redraws Processor from modal timer + node RNA writes.
        RUNTIME.refresh_processor_ui()

        queue_event = RUNTIME.consume_event()
        if queue_event and queue_event.startswith("ERROR:"):
            message = queue_event[len("ERROR:") :]
            RUNTIME.finish_queue(
                f"Render restore failed: {message}", error=True
            )
            self._remove_timer(context)
            self.report({"ERROR"}, message)
            return {"CANCELLED"}
        if queue_event == "CANCEL":
            RUNTIME.finish_queue("Render queue cancelled")
            self._remove_timer(context)
            return {"CANCELLED"}
        if queue_event != "COMPLETE":
            return {"PASS_THROUGH"}
        if RUNTIME.cancel_requested:
            RUNTIME.finish_queue("Render queue cancelled")
            self._remove_timer(context)
            return {"CANCELLED"}
        if RUNTIME.position >= len(RUNTIME.indices):
            RUNTIME.finish_queue("Render queue complete")
            self._remove_timer(context)
            return {"FINISHED"}
        try:
            RUNTIME.start_next(context)
        except Exception as exc:
            RUNTIME.finish_queue(str(exc), error=True)
            self._remove_timer(context)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        RUNTIME.request_cancel()
        RUNTIME.finish_queue("Render queue cancelled")
        self._remove_timer(context)

    def _remove_timer(self, context):
        if self._timer is not None:
            RUNTIME.remove_timer()
            self._timer = None


class RSP_OT_render_selected(_RSP_RenderQueueMixin, bpy.types.Operator):
    bl_idname = "rsp.render_selected"
    bl_label = "Render Selected"
    bl_description = "Apply, render, and restore the selected task"
    render_all = False


class RSP_OT_render_all(_RSP_RenderQueueMixin, bpy.types.Operator):
    bl_idname = "rsp.render_all"
    bl_label = "Render All"
    bl_description = "Render every compiled task sequentially"
    render_all = True


class RSP_OT_cancel_render(bpy.types.Operator):
    bl_idname = "rsp.cancel_render"
    bl_label = "Cancel"
    bl_description = "Cancel the active render queue and restore scene state"

    @classmethod
    def poll(cls, _context):
        return RUNTIME.running

    def execute(self, _context):
        RUNTIME.request_cancel()
        return {"FINISHED"}


_CLASSES = (
    RSP_OT_compile_preview,
    RSP_OT_apply,
    RSP_OT_restore,
    RSP_OT_render_selected,
    RSP_OT_render_all,
    RSP_OT_cancel_render,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    RUNTIME.cleanup()
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

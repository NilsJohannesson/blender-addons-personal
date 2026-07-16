"""Runtime transaction ownership and sequential render queue."""

import os

import bpy
from bpy.app.handlers import persistent

from ..core.model import Override
from .adapter import job_name, job_overrides, job_source_scene, output_status
from .path_expand import PathTemplateError, resolved_job_overrides
from .transaction import Transaction, TransactionError


def scene_state(scene):
    return getattr(scene, "rsp_state", None)


class _ContextProxy:
    def __init__(self, context, scene):
        self._context = context
        self.scene = scene

    def __getattr__(self, name):
        return getattr(self._context, name)


def _job_scene(job, fallback):
    name = job_source_scene(job)
    if not name:
        return fallback
    scene = bpy.data.scenes.get(name)
    if scene is None:
        raise TransactionError(f"Source scene not found: {name!r}")
    return scene


def _override_path(override):
    return getattr(override, "path", None) or (
        override.get("path") if isinstance(override, dict) else None
    )


def _override_value(override):
    if isinstance(override, dict):
        return override.get("value", override.get("new_value"))
    return getattr(override, "value", None)


def _job_int_override(job, path, fallback):
    for override in job_overrides(job):
        if _override_path(override) == path:
            value = _override_value(override)
            if value is not None:
                return int(value)
    return int(fallback)


def _needs_save_output(job, scene):
    """Animation and FFmpeg writes require Output panel save enabled."""
    for override in job_overrides(job):
        path = _override_path(override)
        value = _override_value(override)
        if path in (
            "render.image_settings.file_format",
            "render.file_format",
        ) and value == "FFMPEG":
            return True
        if path == "render.save_output" and value:
            return True
    start = _job_int_override(job, "frame_start", scene.frame_start)
    end = _job_int_override(job, "frame_end", scene.frame_end)
    return start != end


def _with_save_output(overrides, job, scene):
    if not _needs_save_output(job, scene):
        return overrides
    for override in overrides:
        if _override_path(override) == "render.save_output":
            return overrides
    return tuple(overrides) + (Override("render.save_output", True),)


def _ensure_output_directory(absolute_path):
    """Create parent folder for a resolved output file path."""
    if not absolute_path:
        return
    directory = os.path.dirname(absolute_path)
    if not directory:
        return

    # \\server\share\... is UNC. \\renders\file.png is almost always a mistake
    # for blend-relative //renders/file.png.
    normalized = directory.replace("/", "\\")
    if normalized.startswith("\\\\") and not normalized.startswith("\\\\?\\"):
        parts = [part for part in normalized.lstrip("\\").split("\\") if part]
        if len(parts) < 2:
            raise TransactionError(
                "Output path {!r} looks like an incomplete Windows network "
                "(UNC) path. For a folder next to the .blend file use "
                "//renders/{{view_layer}}_{{camera}}_{{resolution}}.png "
                "(two forward slashes)."
                .format(absolute_path)
            )

    if os.path.isdir(directory):
        return
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as exc:
        raise TransactionError(
            "Cannot create output directory {!r}: {}. "
            "If you meant a folder next to the .blend, use //renders/..."
            .format(directory, exc)
        ) from exc


class RSP_Runtime:
    def __init__(self):
        self.applied = None
        self.applied_scene = None
        self.applied_state_scene = None
        self.jobs = []
        self.indices = []
        self.position = 0
        self.current = None
        self.current_scene = None
        self.state_scene = None
        self.window = None
        self.old_window_scene = None
        self.old_lock_interface = None
        self.timer_owner = None
        self.timer = None
        self.event = None
        self.cancel_requested = False
        self.running = False

    def apply_job(self, job, context, label=None):
        self.restore_applied()
        target_scene = _job_scene(job, context.scene)
        target_context = _ContextProxy(context, target_scene)
        transaction = Transaction(label or job_name(job, 0))
        try:
            overrides = _with_save_output(
                resolved_job_overrides(job, target_scene),
                job,
                target_scene,
            )
        except PathTemplateError as exc:
            raise TransactionError(str(exc)) from exc
        transaction.apply(overrides, target_context, bpy)
        self.applied = transaction
        self.applied_scene = target_scene
        self.applied_state_scene = context.scene
        state = scene_state(context.scene)
        if state:
            state.transaction_active = True
            state.status_message = (
                f"Applied {transaction.change_count} override(s)"
            )
        return transaction

    def restore_applied(self):
        error = ""
        if self.applied is not None:
            error = self.applied.restore()
        scene = self.applied_state_scene or self.applied_scene
        self.applied = None
        self.applied_scene = None
        self.applied_state_scene = None
        state = scene_state(scene) if scene else None
        if state:
            state.transaction_active = False
            state.status_message = (
                f"Restore failed: {error}" if error else "Scene restored"
            )
        return error

    def configure_queue(self, jobs, indices, scene):
        if self.running:
            raise TransactionError("Render queue is already running")
        self.restore_applied()
        self.jobs = list(jobs)
        self.indices = list(indices)
        self.position = 0
        self.current = None
        self.current_scene = scene
        self.state_scene = scene
        self.window = None
        self.old_window_scene = None
        self.event = None
        self.cancel_requested = False
        self.running = True
        state = scene_state(scene)
        if state:
            state.rendering = True
            state.queue_total = len(self.indices)
            state.queue_position = 0
            state.status_message = "Starting render queue"

    def start_next(self, context):
        if not self.running or self.position >= len(self.indices):
            return False
        index = self.indices[self.position]
        job = self.jobs[index]
        state = scene_state(self.state_scene)
        scene = _job_scene(job, context.scene)
        if state:
            state.active_job_index = index
            state.queue_position = self.position + 1
            state.status_message = (
                f"Rendering {self.position + 1}/{len(self.indices)}: "
                f"{job_name(job, index)}"
            )

        try:
            absolute, exists, message = output_status(job, scene, bpy)
            overrides = _with_save_output(
                resolved_job_overrides(job, scene),
                job,
                scene,
            )
        except PathTemplateError as exc:
            raise TransactionError(str(exc)) from exc
        if state:
            state.output_path = absolute
            state.output_exists = exists
            state.output_status = message
        _ensure_output_directory(absolute)

        if context.window is not None and context.window.scene != scene:
            self.window = context.window
            self.old_window_scene = context.window.scene
            context.window.scene = scene
        target_context = _ContextProxy(context, scene)
        transaction = Transaction(job_name(job, index))
        self.old_lock_interface = scene.render.use_lock_interface
        try:
            transaction.apply(overrides, target_context, bpy)
        except Exception:
            self.old_lock_interface = None
            self._restore_window_scene()
            raise
        self.current = transaction
        self.current_scene = scene
        scene.render.use_lock_interface = True
        self.event = None
        try:
            is_animation = scene.frame_start != scene.frame_end
            result = bpy.ops.render.render(
                "INVOKE_DEFAULT",
                animation=is_animation,
                write_still=not is_animation,
            )
        except Exception:
            self._restore_current()
            raise
        if "CANCELLED" in result:
            self._restore_current()
            raise TransactionError("Blender rejected render request")
        return True

    def signal(self, event):
        if not self.running:
            return
        error = self._restore_current()
        self.event = f"ERROR:{error}" if error else event

    def consume_event(self):
        event = self.event
        self.event = None
        if event == "COMPLETE":
            self.position += 1
        return event

    def request_cancel(self):
        if not self.running:
            return False
        self.cancel_requested = True
        state = scene_state(self.state_scene) if self.state_scene else None
        if state:
            state.status_message = "Cancelling render"
        try:
            bpy.ops.render.cancel()
        except (AttributeError, RuntimeError):
            self.signal("CANCEL")
        return True

    def attach_timer(self, window_manager, timer):
        self.timer_owner = window_manager
        self.timer = timer

    def remove_timer(self):
        if self.timer_owner is not None and self.timer is not None:
            try:
                self.timer_owner.event_timer_remove(self.timer)
            except (ReferenceError, RuntimeError):
                pass
        self.timer_owner = None
        self.timer = None

    def _restore_current(self):
        errors = []
        if self.current is not None:
            error = self.current.restore()
            if error:
                errors.append(error)
            self.current = None
        if self.current_scene is not None and self.old_lock_interface is not None:
            try:
                self.current_scene.render.use_lock_interface = (
                    self.old_lock_interface
                )
            except Exception as exc:
                errors.append(str(exc))
        self.old_lock_interface = None
        error = self._restore_window_scene()
        if error:
            errors.append(error)
        return "; ".join(errors)

    def _restore_window_scene(self):
        error = ""
        if self.window is not None and self.old_window_scene is not None:
            try:
                self.window.scene = self.old_window_scene
            except Exception as exc:
                error = str(exc)
        self.window = None
        self.old_window_scene = None
        return error

    def finish_queue(self, message="Render queue complete", error=False):
        restore_error = self._restore_current()
        if restore_error:
            message = f"{message}; restore failed: {restore_error}"
            error = True
        scene = self.state_scene or self.current_scene
        self.running = False
        self.jobs = []
        self.indices = []
        self.position = 0
        self.current_scene = None
        self.state_scene = None
        self.event = None
        self.cancel_requested = False
        state = scene_state(scene) if scene else None
        if state:
            state.rendering = False
            state.transaction_active = False
            state.status_message = message
            state.has_error = error

    def cleanup(self):
        if self.running:
            try:
                bpy.ops.render.cancel()
            except Exception:
                pass
            self.finish_queue("Render queue stopped")
        self.remove_timer()
        self.restore_applied()


RUNTIME = RSP_Runtime()


@persistent
def _render_complete(_scene, *_args):
    RUNTIME.signal("COMPLETE")


@persistent
def _render_cancel(_scene, *_args):
    RUNTIME.signal("CANCEL")


def register():
    if _render_complete not in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.append(_render_complete)
    if _render_cancel not in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.append(_render_cancel)


def unregister():
    RUNTIME.cleanup()
    if _render_complete in bpy.app.handlers.render_complete:
        bpy.app.handlers.render_complete.remove(_render_complete)
    if _render_cancel in bpy.app.handlers.render_cancel:
        bpy.app.handlers.render_cancel.remove(_render_cancel)

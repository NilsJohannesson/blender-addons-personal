"""Runtime transaction ownership and sequential render queue."""

import os

import bpy
from bpy.app.handlers import persistent

from ..core.model import Override
from .adapter import task_name, task_overrides, task_source_scene, output_status
from .path_expand import PathTemplateError, resolved_task_overrides
from .transaction import Transaction, TransactionError


def scene_state(scene):
    return getattr(scene, "rsp_state", None)


class _ContextProxy:
    def __init__(self, context, scene):
        self._context = context
        self.scene = scene

    def __getattr__(self, name):
        return getattr(self._context, name)


def _task_scene(job, fallback):
    name = task_source_scene(job)
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


def _task_int_override(job, path, fallback):
    for override in task_overrides(job):
        if _override_path(override) == path:
            value = _override_value(override)
            if value is not None:
                return int(value)
    return int(fallback)


def _needs_save_output(job, scene):
    """Animation and FFmpeg writes require Output panel save enabled."""
    for override in task_overrides(job):
        path = _override_path(override)
        value = _override_value(override)
        if path in (
            "render.image_settings.file_format",
            "render.file_format",
        ) and value == "FFMPEG":
            return True
        if path == "render.save_output" and value:
            return True
    start = _task_int_override(job, "frame_start", scene.frame_start)
    end = _task_int_override(job, "frame_end", scene.frame_end)
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


def tag_node_editors():
    """Refresh Processor / Viewer node UI during queue updates."""
    window = getattr(bpy.context, "window", None)
    screens = []
    if window is not None and window.screen is not None:
        screens.append(window.screen)
    screen = getattr(bpy.context, "screen", None)
    if screen is not None and screen not in screens:
        screens.append(screen)
    for screen in screens:
        for area in screen.areas:
            if area.type == "NODE_EDITOR":
                area.tag_redraw()


def sync_processor_nodes():
    """Push queue progress onto Processor node RNA (upstream RenderNode pattern).

    Writing node properties + tagging the Node Editor is what makes the bar
    update live; reading RUNTIME alone only works if something redraws.
    """
    labels = RUNTIME.queue_labels
    task_list = ",".join(labels)
    cur_task = ""
    if labels:
        if RUNTIME.running:
            index = min(RUNTIME.queue_display_position, len(labels) - 1)
            cur_task = labels[index]
        elif RUNTIME.queue_finished:
            cur_task = labels[-1]
        else:
            index = min(RUNTIME.queue_display_position, len(labels) - 1)
            cur_task = labels[index]
    active = bool(RUNTIME.running or (labels and RUNTIME.queue_finished))
    for tree in bpy.data.node_groups:
        if getattr(tree, "bl_idname", "") != "RenderSpineNodeTree":
            continue
        for node in tree.nodes:
            if getattr(node, "bl_idname", "") != "RenderSpineNodeProcessor":
                continue
            if node.task_list != task_list:
                node.task_list = task_list
            if node.cur_task != cur_task:
                node.cur_task = cur_task
            if node.active != active:
                node.active = active
    tag_node_editors()


class RSP_Runtime:
    def __init__(self):
        self.applied = None
        self.applied_scene = None
        self.applied_state_scene = None
        self.applied_label = ""
        self.tasks = []
        self.indices = []
        self.position = 0
        self.current = None
        self.current_scene = None
        self.state_scene = None
        self.window = None
        self.old_window_scene = None

        self.timer_owner = None
        self.timer = None
        self.event = None
        self.cancel_requested = False
        self.running = False
        # Processor display (kept after queue finishes until next configure).
        self.queue_labels = ()
        self.queue_display_position = 0
        self.queue_finished = False

    def apply_task(self, job, context, label=None):
        self.restore_applied()
        target_scene = _task_scene(job, context.scene)
        target_context = _ContextProxy(context, target_scene)
        applied_label = label or task_name(job, 0)
        transaction = Transaction(applied_label)
        try:
            overrides = _with_save_output(
                resolved_task_overrides(job, target_scene),
                job,
                target_scene,
            )
        except PathTemplateError as exc:
            raise TransactionError(str(exc)) from exc
        transaction.apply(overrides, target_context, bpy)
        self.applied = transaction
        self.applied_scene = target_scene
        self.applied_state_scene = context.scene
        self.applied_label = applied_label
        state = scene_state(context.scene)
        if state:
            state.transaction_active = True
            state.status_message = (
                f"Applied {transaction.change_count} override(s)"
            )
        sync_processor_nodes()
        return transaction

    def restore_applied(self):
        error = ""
        if self.applied is not None:
            error = self.applied.restore()
        scene = self.applied_state_scene or self.applied_scene
        self.applied = None
        self.applied_scene = None
        self.applied_state_scene = None
        self.applied_label = ""
        state = scene_state(scene) if scene else None
        if state:
            state.transaction_active = False
            state.status_message = (
                f"Restore failed: {error}" if error else "Scene restored"
            )
        sync_processor_nodes()
        return error

    def configure_queue(self, tasks, indices, scene):
        if self.running:
            raise TransactionError("Render queue is already running")
        self.restore_applied()
        self.tasks = list(tasks)
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
        self.queue_finished = False
        self.queue_display_position = 0
        self.queue_labels = tuple(
            task_name(self.tasks[index], index) for index in self.indices
        )
        state = scene_state(scene)
        if state:
            state.rendering = True
            state.queue_total = len(self.indices)
            state.queue_position = 0
            state.status_message = "Starting render queue"
        sync_processor_nodes()

    def queue_items(self):
        """Processor UI rows: (label, status) with status done/current/waiting."""
        labels = self.queue_labels
        if not labels:
            return ()
        if self.running:
            current = self.position
        elif self.queue_finished:
            current = len(labels)
        else:
            current = self.queue_display_position
        items = []
        for index, label in enumerate(labels):
            if index < current:
                status = "done"
            elif index == current and self.running:
                status = "current"
            else:
                status = "waiting"
            items.append((label, status))
        return tuple(items)

    def start_next(self, context):
        if not self.running or self.position >= len(self.indices):
            return False
        index = self.indices[self.position]
        job = self.tasks[index]
        state = scene_state(self.state_scene)
        scene = _task_scene(job, context.scene)
        if state:
            state.active_task_index = index
            state.queue_position = self.position + 1
            state.status_message = (
                f"Rendering {self.position + 1}/{len(self.indices)}: "
                f"{task_name(job, index)}"
            )

        try:
            absolute, exists, message = output_status(job, scene, bpy)
            overrides = _with_save_output(
                resolved_task_overrides(job, scene),
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
        transaction = Transaction(task_name(job, index))
        try:
            transaction.apply(overrides, target_context, bpy)
        except Exception:
            self._restore_window_scene()
            raise
        self.current = transaction
        self.current_scene = scene
        self.queue_display_position = self.position
        self.event = None
        # Do not force use_lock_interface — it freezes the Node Editor so the
        # Processor cannot redraw live (upstream left this as a user choice).
        sync_processor_nodes()
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
        sync_processor_nodes()
        return True

    def signal(self, event):
        """Queue a render-thread event; restore runs on the modal timer (main thread)."""
        if not self.running:
            return
        if self.event is not None:
            return
        self.event = event

    def consume_event(self):
        event = self.event
        self.event = None
        if not event:
            return None
        if event.startswith("ERROR:"):
            return event
        if event in ("COMPLETE", "CANCEL"):
            error = self._restore_current()
            if error:
                return f"ERROR:{error}"
            sync_processor_nodes()
        if event == "COMPLETE":
            self.position += 1
            self.queue_display_position = self.position
            sync_processor_nodes()
        return event

    def refresh_processor_ui(self):
        """Called on modal TIMER so frame % and bars stay live."""
        if self.running or self.queue_labels:
            sync_processor_nodes()

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
        self.queue_finished = (not error) and (not self.cancel_requested)
        if self.queue_finished:
            self.queue_display_position = len(self.queue_labels)
        else:
            # Cancel / error: drop stale labels so Processor cannot look like
            # an old multi-task queue is still armed.
            self.queue_labels = ()
            self.queue_display_position = 0
        self.running = False
        self.tasks = []
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
        sync_processor_nodes()

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

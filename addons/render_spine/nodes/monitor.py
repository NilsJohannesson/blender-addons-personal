"""Queue Processor and Task Viewer nodes (RenderNode Processor / Viewer)."""

import bpy
from bpy.props import BoolProperty, FloatVectorProperty, StringProperty

from ..core.model import TaskList, TaskSpec
from ..core.node import RSP_NodeBase
from ..core.variants import expand_pending_axes
from ..execution.runtime import RUNTIME
from ..execution.transaction import TransactionError


class RSP_ProcessorNode(RSP_NodeBase, bpy.types.Node):
    """Live render-queue progress (upstream RenderNode Processor)."""

    bl_idname = "RenderSpineNodeProcessor"
    bl_label = "Processor"
    bl_icon = "SORTTIME"
    rsp_inputs = (("RenderSpineNodeSocketTaskList", "Tasks"),)
    rsp_outputs = ()

    # Written by runtime.sync_processor_nodes during the queue (upstream pattern).
    active: BoolProperty(default=False)
    task_list: StringProperty(default="")
    cur_task: StringProperty(default="")

    done_col: FloatVectorProperty(
        name="Done Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.2, 0.8, 0.2),
    )
    wait_col: FloatVectorProperty(
        name="Wait Color",
        subtype="COLOR",
        size=3,
        min=0.0,
        max=1.0,
        default=(0.15, 0.15, 0.15),
    )

    def init(self, context):
        super().init(context)
        self.width = 240

    def draw_buttons_ext(self, context, layout):
        layout.prop(self, "done_col")
        layout.prop(self, "wait_col")

    def draw_buttons(self, context, layout):
        # Prefer RNA props pushed by the queue (live updates). Fall back to RUNTIME.
        task_names = [name for name in self.task_list.split(",") if name]
        if not task_names and not self.active:
            items = RUNTIME.queue_items()
            if not items:
                layout.label(text="Waiting for render…", icon="TIME")
                layout.label(text="Start Render All / Selected")
                return
            task_names = [label for label, _status in items]

        if not task_names:
            layout.label(text="Waiting for render…", icon="TIME")
            return

        try:
            cur_id = task_names.index(self.cur_task) if self.cur_task else 0
        except ValueError:
            cur_id = 0

        running = RUNTIME.running
        finished = RUNTIME.queue_finished and not running
        if running:
            # Current task counts as in-progress toward the total.
            fraction = (cur_id + 0.5) / len(task_names)
        elif finished:
            fraction = 1.0
            cur_id = len(task_names) - 1
        else:
            fraction = (cur_id + 1) / len(task_names)

        fraction = min(1.0, max(0.0, fraction))
        process_index = min(cur_id + 1, len(task_names))

        col = layout.column(align=True)
        col.alignment = "CENTER"
        col.label(
            text="Total: {:.0f}% | Process: {} / {}".format(
                fraction * 100.0, process_index, len(task_names)
            )
        )
        split = col.split(factor=max(0.001, min(0.999, fraction)), align=True)
        split.scale_y = 0.35
        split.prop(self, "done_col", text="")
        split.prop(self, "wait_col", text="")

        scene = context.scene
        for index, task_name in enumerate(task_names):
            box = col.box()
            row = box.row(align=True)
            if index < cur_id or (finished and index <= cur_id):
                row.label(text=task_name, icon="CHECKBOX_HLT")
            elif index == cur_id and running:
                row.label(text=task_name, icon="RENDER_STILL")
                start = scene.frame_start
                end = scene.frame_end
                span = max(1, end - start + 1)
                current = max(0, min(span, scene.frame_current - start + 1))
                row.label(
                    text="{:.0f}%: {} / {}".format(
                        100.0 * current / span, current, span
                    )
                )
            elif index == cur_id and not running:
                row.label(text=task_name, icon="CHECKBOX_HLT")
            else:
                row.label(text=task_name, icon="CHECKBOX_DEHLT")

        if finished:
            col.label(text="Render finished", icon="CHECKMARK")

    def rsp_compile(self, context, socket):
        if self.inputs and self.inputs[0].is_linked:
            context.input(self, "Tasks")
        return None


class RSP_ViewerNode(RSP_NodeBase, bpy.types.Node):
    """Viewer-style Apply for a connected Job (upstream RenderNode Viewer)."""

    bl_idname = "RenderSpineNodeViewer"
    bl_label = "Viewer"
    bl_icon = "HIDE_OFF"
    rsp_inputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_outputs = ()

    summary: StringProperty(default="")

    def init(self, context):
        super().init(context)
        self.width = 200

    def draw_label(self):
        if RUNTIME.applied and RUNTIME.applied_label:
            return "Task: {}".format(RUNTIME.applied_label)
        return "Viewer"

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        op = col.operator("rsp.viewer_apply", text="View Task", icon="HIDE_OFF")
        op.tree_name = self.id_data.name if self.id_data else ""
        op.node_name = self.name
        restore = col.row(align=True)
        restore.enabled = bool(RUNTIME.applied)
        restore.operator("rsp.restore", text="Restore", icon="LOOP_BACK")
        if self.summary:
            box = col.box().column(align=True)
            for line in self.summary.split("\n")[:12]:
                if line:
                    box.label(text=line)

    def rsp_compile(self, context, socket):
        return None


class RSP_OT_viewer_apply(bpy.types.Operator):
    bl_idname = "rsp.viewer_apply"
    bl_label = "View Task"
    bl_description = (
        "Apply the Task connected to this Viewer into the scene "
        "(transactional; use Restore to undo)"
    )
    bl_options = {"REGISTER", "UNDO"}

    tree_name: StringProperty()
    node_name: StringProperty()

    @classmethod
    def poll(cls, context):
        state = getattr(context.scene, "rsp_state", None)
        return not (state and state.rendering) and not RUNTIME.running

    def execute(self, context):
        from ..core.compiler import CompileContext
        from ..execution.adapter import task_name, task_overrides, summarize_tasks

        tree = bpy.data.node_groups.get(self.tree_name)
        if tree is None:
            self.report({"ERROR"}, "Node tree not found")
            return {"CANCELLED"}
        node = tree.nodes.get(self.node_name)
        if node is None or node.bl_idname != "RenderSpineNodeViewer":
            self.report({"ERROR"}, "Viewer node not found")
            return {"CANCELLED"}
        socket = node.inputs.get("Task")
        if socket is None or not socket.is_linked:
            self.report({"ERROR"}, "Viewer Task input is not connected")
            return {"CANCELLED"}
        link = sorted(
            socket.links,
            key=lambda item: (item.from_node.name, item.from_socket.name),
        )[0]
        try:
            compile_context = CompileContext(tree)
            value = compile_context.output(link.from_node, link.from_socket)
            if isinstance(value, TaskSpec):
                jobs = expand_pending_axes(value).tasks
            elif isinstance(value, TaskList):
                expanded = []
                for task in value.tasks:
                    expanded.extend(expand_pending_axes(task).tasks)
                jobs = tuple(expanded)
            else:
                raise TransactionError("Viewer requires a Task connection")
            if not jobs:
                raise TransactionError("Connected graph produced no tasks")
            if len(jobs) > 1:
                self.report(
                    {"WARNING"},
                    "Connected graph has {} tasks; viewing the first".format(
                        len(jobs)
                    ),
                )
            job = jobs[0]
            RUNTIME.apply_task(job, context, task_name(job, 0))
            node.summary = summarize_tasks((job,))
            state = getattr(context.scene, "rsp_state", None)
            if state:
                state.compile_ok = True
                state.has_error = False
                state.dry_run_summary = node.summary
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report(
            {"INFO"},
            "Viewing {} ({} overrides)".format(
                RUNTIME.applied_label, len(task_overrides(job))
            ),
        )
        return {"FINISHED"}


OPERATORS = (RSP_OT_viewer_apply,)

CLASSES = (
    RSP_ProcessorNode,
    RSP_ViewerNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

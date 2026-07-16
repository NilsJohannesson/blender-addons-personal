"""Reusable render-setting graph groups."""

import bpy
from bpy.props import PointerProperty

from ..core.compiler import CompileError, compile_tree
from ..core.model import TaskSpec
from ..core.node import RSP_NodeBase


def _group_tree_poll(self, tree):
    return (
        tree.bl_idname == "RenderSpineNodeTree"
        and tree != getattr(self, "id_data", None)
    )


class RSP_JobGroupNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobGroup"
    bl_label = "Task Group"
    rsp_inputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)

    group_tree: PointerProperty(
        name="Group",
        type=bpy.types.NodeTree,
        poll=_group_tree_poll,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "group_tree", text="")

    def rsp_compile(self, context, socket):
        job = context.input(self, "Task", required=True)
        if not isinstance(job, TaskSpec):
            raise TypeError("Task input requires TaskSpec")
        if self.group_tree is None:
            raise ValueError("Select a render graph group")
        try:
            nested = compile_tree(self.group_tree, strict=True)
        except CompileError as exc:
            messages = "; ".join(item.message for item in exc.diagnostics)
            raise ValueError("Group compile failed: " + messages) from exc
        if len(nested.tasks) != 1:
            raise ValueError("Group graph must compile exactly one job")

        result = job
        for override in nested.tasks[0].overrides:
            result = result.with_override(
                override.path,
                override.value,
                override.target_type,
                override.target_name,
            )
        return result.with_metadata("group", self.group_tree.name)


CLASSES = (RSP_JobGroupNode,)
MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

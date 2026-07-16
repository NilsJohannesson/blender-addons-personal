"""Render graph tree and official add-menu integration."""

import bpy

from .core import compile_tree, validate_tree


class RSP_RenderNodeTree(bpy.types.NodeTree):
    bl_idname = "RenderSpineNodeTree"
    bl_label = "RenderSpine Graph"
    bl_icon = "RENDER_ANIMATION"

    @classmethod
    def poll(cls, context):
        return True

    def compile(self, strict=True):
        return compile_tree(self, strict=strict)

    def validate(self):
        return validate_tree(self)


class RSP_MT_add_root(bpy.types.Menu):
    bl_idname = "RSP_MT_add_root"
    bl_label = "RenderSpine"

    def draw(self, context):
        layout = self.layout
        from .nodes import NODE_CATEGORIES

        for menu_id, label in NODE_CATEGORIES:
            layout.menu(menu_id, text=label)


def _draw_add_menu(self, context):
    space = context.space_data
    if (
        space
        and space.type == "NODE_EDITOR"
        and space.tree_type == RSP_RenderNodeTree.bl_idname
    ):
        self.layout.separator()
        self.layout.menu(RSP_MT_add_root.bl_idname)


TREE_CLASSES = (
    RSP_RenderNodeTree,
    RSP_MT_add_root,
)


def register():
    for cls in TREE_CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(_draw_add_menu)


def unregister():
    bpy.types.NODE_MT_add.remove(_draw_add_menu)
    for cls in reversed(TREE_CLASSES):
        bpy.utils.unregister_class(cls)

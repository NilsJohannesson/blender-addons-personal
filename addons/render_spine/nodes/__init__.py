"""Explicit node registry and add menus."""

import bpy

from . import (
    groups,
    tasks,
    lists,
    monitor,
    objects,
    settings,
    utility,
    values,
    variants,
)
from ..core.node import register_classes, unregister_classes


NODE_CLASSES = (
    *values.CLASSES,
    *lists.CLASSES,
    *tasks.CLASSES,
    *variants.CLASSES,
    *monitor.CLASSES,
    *settings.CLASSES,
    *objects.CLASSES,
    *utility.CLASSES,
    *groups.CLASSES,
)


def _draw_items(layout, items):
    for node_type, label in items:
        operator = layout.operator("node.add_node", text=label)
        operator.type = node_type
        operator.use_transform = True


class RSP_MT_add_values(bpy.types.Menu):
    bl_idname = "RSP_MT_add_values"
    bl_label = "Values"

    def draw(self, context):
        _draw_items(self.layout, values.MENU_ITEMS + lists.MENU_ITEMS)


class RSP_MT_add_tasks(bpy.types.Menu):
    bl_idname = "RSP_MT_add_tasks"
    bl_label = "Tasks"

    def draw(self, context):
        _draw_items(
            self.layout,
            tasks.MENU_ITEMS + variants.MENU_ITEMS + monitor.MENU_ITEMS,
        )


class RSP_MT_add_settings(bpy.types.Menu):
    bl_idname = "RSP_MT_add_settings"
    bl_label = "Render Settings"

    def draw(self, context):
        _draw_items(self.layout, settings.MENU_ITEMS)


class RSP_MT_add_objects(bpy.types.Menu):
    bl_idname = "RSP_MT_add_objects"
    bl_label = "Objects and Collections"

    def draw(self, context):
        _draw_items(self.layout, objects.MENU_ITEMS)


class RSP_MT_add_utility(bpy.types.Menu):
    bl_idname = "RSP_MT_add_utility"
    bl_label = "Utility"

    def draw(self, context):
        _draw_items(self.layout, utility.MENU_ITEMS)


class RSP_MT_add_groups(bpy.types.Menu):
    bl_idname = "RSP_MT_add_groups"
    bl_label = "Groups"

    def draw(self, context):
        _draw_items(self.layout, groups.MENU_ITEMS)


MENU_CLASSES = (
    RSP_MT_add_values,
    RSP_MT_add_tasks,
    RSP_MT_add_settings,
    RSP_MT_add_objects,
    RSP_MT_add_utility,
    RSP_MT_add_groups,
)

NODE_CATEGORIES = (
    (RSP_MT_add_values.bl_idname, RSP_MT_add_values.bl_label),
    (RSP_MT_add_tasks.bl_idname, RSP_MT_add_tasks.bl_label),
    (RSP_MT_add_settings.bl_idname, RSP_MT_add_settings.bl_label),
    (RSP_MT_add_objects.bl_idname, RSP_MT_add_objects.bl_label),
    (RSP_MT_add_utility.bl_idname, RSP_MT_add_utility.bl_label),
    (RSP_MT_add_groups.bl_idname, RSP_MT_add_groups.bl_label),
)


def register():
    register_classes(lists.PROPERTY_GROUPS)
    register_classes(lists.OPERATORS)
    register_classes(monitor.OPERATORS)
    register_classes(settings.OPERATORS)
    register_classes(settings.MENU_CLASSES)
    register_classes(NODE_CLASSES)
    register_classes(MENU_CLASSES)


def unregister():
    unregister_classes(MENU_CLASSES)
    unregister_classes(NODE_CLASSES)
    unregister_classes(settings.MENU_CLASSES)
    unregister_classes(settings.OPERATORS)
    unregister_classes(monitor.OPERATORS)
    unregister_classes(lists.OPERATORS)
    unregister_classes(lists.PROPERTY_GROUPS)

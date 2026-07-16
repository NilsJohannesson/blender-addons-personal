"""Dynamic typed value-list nodes for variant axes."""

import bpy
from bpy.props import (
    CollectionProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..core.model import ValueList
from ..core.node import RSP_NodeBase


def _tree_node(context, tree_name, node_name):
    tree = bpy.data.node_groups.get(tree_name)
    if tree is None:
        return None, None
    node = tree.nodes.get(node_name)
    return tree, node


class RSP_OT_list_item_add(bpy.types.Operator):
    bl_idname = "rsp.list_item_add"
    bl_label = "Add List Item"
    bl_options = {"INTERNAL", "UNDO"}

    tree_name: StringProperty()
    node_name: StringProperty()

    def execute(self, context):
        _tree, node = _tree_node(context, self.tree_name, self.node_name)
        if node is None or not hasattr(node, "items"):
            return {"CANCELLED"}
        node.items.add()
        node.active_index = len(node.items) - 1
        return {"FINISHED"}


class RSP_OT_list_item_remove(bpy.types.Operator):
    bl_idname = "rsp.list_item_remove"
    bl_label = "Remove List Item"
    bl_options = {"INTERNAL", "UNDO"}

    tree_name: StringProperty()
    node_name: StringProperty()
    index: IntProperty(default=0, min=0)

    def execute(self, context):
        _tree, node = _tree_node(context, self.tree_name, self.node_name)
        if node is None or not hasattr(node, "items"):
            return {"CANCELLED"}
        if not node.items or self.index < 0 or self.index >= len(node.items):
            return {"CANCELLED"}
        node.items.remove(self.index)
        node.active_index = min(node.active_index, max(0, len(node.items) - 1))
        return {"FINISHED"}


class RSP_FloatListItem(bpy.types.PropertyGroup):
    value: FloatProperty(name="Value", default=0.0)


class RSP_IntListItem(bpy.types.PropertyGroup):
    value: IntProperty(name="Value", default=0)


class RSP_VectorListItem(bpy.types.PropertyGroup):
    value: FloatVectorProperty(name="Value", size=3, subtype="XYZ")


class RSP_ColorListItem(bpy.types.PropertyGroup):
    value: FloatVectorProperty(
        name="Value",
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),
    )


class RSP_StringListItem(bpy.types.PropertyGroup):
    value: StringProperty(name="Value", default="")


class RSP_ObjectListItem(bpy.types.PropertyGroup):
    value: PointerProperty(name="Value", type=bpy.types.Object)


class RSP_WorldListItem(bpy.types.PropertyGroup):
    value: PointerProperty(name="Value", type=bpy.types.World)


class RSP_CollectionListItem(bpy.types.PropertyGroup):
    value: PointerProperty(name="Value", type=bpy.types.Collection)


PROPERTY_GROUPS = (
    RSP_FloatListItem,
    RSP_IntListItem,
    RSP_VectorListItem,
    RSP_ColorListItem,
    RSP_StringListItem,
    RSP_ObjectListItem,
    RSP_WorldListItem,
    RSP_CollectionListItem,
)

OPERATORS = (
    RSP_OT_list_item_add,
    RSP_OT_list_item_remove,
)


class RSP_ListValueNode(RSP_NodeBase):
    rsp_inputs = ()
    active_index: IntProperty(name="Active", default=0, min=0)

    def _draw_items(self, layout, use_color=False):
        tree = self.id_data
        row = layout.row(align=True)
        add = row.operator("rsp.list_item_add", text="Add")
        add.tree_name = tree.name
        add.node_name = self.name
        for index, item in enumerate(self.items):
            item_row = layout.row(align=True)
            if use_color:
                item_row.prop(item, "value", text="")
            else:
                item_row.prop(item, "value", text=str(index))
            remove = item_row.operator(
                "rsp.list_item_remove", text="", icon="X"
            )
            remove.tree_name = tree.name
            remove.node_name = self.name
            remove.index = index

    def draw_buttons(self, context, layout):
        self._draw_items(layout)

    def rsp_compile(self, context, socket):
        return ValueList(tuple(self._item_value(item) for item in self.items))

    def _item_value(self, item):
        return item.value


class RSP_FloatListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeFloatList"
    bl_label = "Float List"
    rsp_outputs = (("RenderSpineNodeSocketFloatList", "Values"),)
    items: CollectionProperty(type=RSP_FloatListItem)


class RSP_IntListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeIntList"
    bl_label = "Int List"
    rsp_outputs = (("RenderSpineNodeSocketIntList", "Values"),)
    items: CollectionProperty(type=RSP_IntListItem)


class RSP_VectorListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeVectorList"
    bl_label = "Vector List"
    rsp_outputs = (("RenderSpineNodeSocketVectorList", "Values"),)
    items: CollectionProperty(type=RSP_VectorListItem)

    def _item_value(self, item):
        return tuple(item.value)


class RSP_ColorListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeColorList"
    bl_label = "Color List"
    rsp_outputs = (("RenderSpineNodeSocketVectorList", "Values"),)
    items: CollectionProperty(type=RSP_ColorListItem)

    def draw_buttons(self, context, layout):
        self._draw_items(layout, use_color=True)

    def _item_value(self, item):
        return tuple(item.value)


class RSP_StringListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeStringList"
    bl_label = "String List"
    rsp_outputs = (("RenderSpineNodeSocketStringList", "Values"),)
    items: CollectionProperty(type=RSP_StringListItem)


class RSP_ObjectListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectList"
    bl_label = "Object List"
    rsp_outputs = (("RenderSpineNodeSocketObjectList", "Values"),)
    items: CollectionProperty(type=RSP_ObjectListItem)


class RSP_WorldListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeWorldList"
    bl_label = "World List"
    rsp_outputs = (("RenderSpineNodeSocketWorldList", "Values"),)
    items: CollectionProperty(type=RSP_WorldListItem)


class RSP_CollectionListNode(RSP_ListValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeCollectionList"
    bl_label = "Collection List"
    rsp_outputs = (("RenderSpineNodeSocketCollectionList", "Values"),)
    items: CollectionProperty(type=RSP_CollectionListItem)


CLASSES = (
    RSP_FloatListNode,
    RSP_IntListNode,
    RSP_VectorListNode,
    RSP_ColorListNode,
    RSP_StringListNode,
    RSP_ObjectListNode,
    RSP_WorldListNode,
    RSP_CollectionListNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

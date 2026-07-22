"""Typed constant nodes."""

import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..core.node import RSP_ValueNodeBase


class RSP_TypedValueNode(RSP_ValueNodeBase):
    def draw_buttons(self, context, layout):
        layout.prop(self, "value", text="")


class RSP_BoolValueNode(RSP_TypedValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeBoolValue"
    bl_label = "Boolean"
    rsp_outputs = (("RenderSpineNodeSocketBool", "Value"),)
    value: BoolProperty(default=False)


class RSP_IntValueNode(RSP_TypedValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeIntValue"
    bl_label = "Integer"
    rsp_outputs = (("RenderSpineNodeSocketInt", "Value"),)
    value: IntProperty(default=0)


class RSP_FloatValueNode(RSP_TypedValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeFloatValue"
    bl_label = "Float"
    rsp_outputs = (("RenderSpineNodeSocketFloat", "Value"),)
    value: FloatProperty(default=0.0)


class RSP_StringValueNode(RSP_TypedValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeStringValue"
    bl_label = "String"
    rsp_outputs = (("RenderSpineNodeSocketString", "Value"),)
    value: StringProperty(default="")


class RSP_VectorValueNode(RSP_TypedValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeVectorValue"
    bl_label = "Vector"
    rsp_outputs = (("RenderSpineNodeSocketVector", "Value"),)
    value: FloatVectorProperty(size=3, subtype="XYZ")

    def rsp_compile(self, context, socket):
        return tuple(self.value)


class RSP_ColorValueNode(RSP_TypedValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeColorValue"
    bl_label = "Color"
    rsp_outputs = (("RenderSpineNodeSocketColor", "Value"),)
    value: FloatVectorProperty(
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),
    )

    def rsp_compile(self, context, socket):
        return tuple(self.value)


class RSP_DatablockValueNode(RSP_TypedValueNode):
    def rsp_compile(self, context, socket):
        return self.value


class RSP_ObjectValueNode(RSP_DatablockValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectValue"
    bl_label = "Object"
    rsp_outputs = (("RenderSpineNodeSocketObject", "Value"),)
    value: PointerProperty(type=bpy.types.Object)


class RSP_CameraResolutionNode(RSP_ValueNodeBase, bpy.types.Node):
    """Read the per-camera resolution provided by Nilor Blender Tools."""

    bl_idname = "RenderSpineNodeCameraResolution"
    bl_label = "Camera Resolution"
    rsp_inputs = (("RenderSpineNodeSocketObject", "Camera"),)
    rsp_outputs = (
        ("RenderSpineNodeSocketInt", "Width"),
        ("RenderSpineNodeSocketInt", "Height"),
    )

    def rsp_compile(self, context, socket):
        camera = context.input(self, "Camera", required=True)
        if not isinstance(camera, bpy.types.Object) or camera.type != "CAMERA":
            raise ValueError("Camera Resolution requires a camera object")
        settings = getattr(camera, "nilor_frustum", None)
        width = int(getattr(settings, "res_x", 0) or 0)
        height = int(getattr(settings, "res_y", 0) or 0)
        if width <= 0 or height <= 0:
            raise ValueError(
                "Camera has no Nilor resolution; enable Nilor Blender Tools"
            )
        if socket.name == "Width":
            return width
        if socket.name == "Height":
            return height
        raise ValueError("Unknown Camera Resolution output: {}".format(socket.name))


class RSP_MaterialValueNode(RSP_DatablockValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeMaterialValue"
    bl_label = "Material"
    rsp_outputs = (("RenderSpineNodeSocketMaterial", "Value"),)
    value: PointerProperty(type=bpy.types.Material)


class RSP_CollectionValueNode(RSP_DatablockValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeCollectionValue"
    bl_label = "Collection"
    rsp_outputs = (("RenderSpineNodeSocketCollection", "Value"),)
    value: PointerProperty(type=bpy.types.Collection)


class RSP_SceneValueNode(RSP_DatablockValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeSceneValue"
    bl_label = "Scene"
    rsp_outputs = (("RenderSpineNodeSocketScene", "Value"),)
    value: PointerProperty(type=bpy.types.Scene)


class RSP_WorldValueNode(RSP_DatablockValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeWorldValue"
    bl_label = "World"
    rsp_outputs = (("RenderSpineNodeSocketWorld", "Value"),)
    value: PointerProperty(type=bpy.types.World)


class RSP_ActionValueNode(RSP_DatablockValueNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeActionValue"
    bl_label = "Action"
    rsp_outputs = (("RenderSpineNodeSocketAction", "Value"),)
    value: PointerProperty(type=bpy.types.Action)


CLASSES = (
    RSP_BoolValueNode,
    RSP_IntValueNode,
    RSP_FloatValueNode,
    RSP_StringValueNode,
    RSP_VectorValueNode,
    RSP_ColorValueNode,
    RSP_ObjectValueNode,
    RSP_CameraResolutionNode,
    RSP_MaterialValueNode,
    RSP_CollectionValueNode,
    RSP_SceneValueNode,
    RSP_WorldValueNode,
    RSP_ActionValueNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

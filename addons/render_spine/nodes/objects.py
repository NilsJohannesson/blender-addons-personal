"""Object and collection override nodes."""

import math

import bpy

from ..core.model import Override, TaskSpec, ValueList
from ..core.node import RSP_NodeBase
from ..core.variants import (
    OVERRIDE_BUNDLE_PATH,
    VariantAxis,
    apply_override_or_axis,
)


def _spread_degrees_to_radians(value):
    """Light Settings UI uses degrees; RNA ``data.spread`` is radians."""
    if isinstance(value, ValueList):
        return ValueList(tuple(math.radians(float(item)) for item in value.items))
    return math.radians(float(value))


J = ("RenderSpineNodeSocketTask", "Task")
O = ("RenderSpineNodeSocketObject", "Object")
C = ("RenderSpineNodeSocketCollection", "Collection")
B = "RenderSpineNodeSocketBool"
F = "RenderSpineNodeSocketFloat"
V = "RenderSpineNodeSocketVector"
COL = "RenderSpineNodeSocketColor"
M = "RenderSpineNodeSocketMaterial"
A = "RenderSpineNodeSocketAction"


def _task_scene(job):
    source = job.source_scene
    scene = source if isinstance(source, bpy.types.Scene) else bpy.data.scenes.get(source)
    return scene or bpy.context.scene


def _job_view_layer(job, scene):
    metadata = dict(job.metadata)
    name = metadata.get("view_layer") or ""
    if name:
        layer = scene.view_layers.get(name)
        if layer is None:
            raise ValueError("View layer not found: {}".format(name))
        return layer
    active = getattr(scene.view_layers, "active", None)
    if active is not None:
        return active
    if scene.view_layers:
        return scene.view_layers[0]
    raise ValueError("No view layer available")


def _layer_collection_rna_path(view_layer, collection):
    """RNA path from Scene to the LayerCollection wrapping ``collection``."""
    if collection is None:
        return ""
    if '"' in view_layer.name or "\\" in view_layer.name:
        raise ValueError("View layer name cannot contain quotes or backslashes")
    if '"' in collection.name or "\\" in collection.name:
        raise ValueError("Collection name cannot contain quotes or backslashes")

    def walk(layer_collection, parts):
        if layer_collection.collection == collection:
            return parts
        for child in layer_collection.children:
            if '"' in child.name or "\\" in child.name:
                raise ValueError(
                    "Collection name cannot contain quotes or backslashes"
                )
            found = walk(child, parts + ['children["{}"]'.format(child.name)])
            if found is not None:
                return found
        return None

    parts = walk(view_layer.layer_collection, [])
    if parts is None:
        return ""
    base = 'view_layers["{}"].layer_collection'.format(view_layer.name)
    if not parts:
        return base
    return base + "." + ".".join(parts)

class RSP_TargetOverrideNode(RSP_NodeBase):
    rsp_target_input = "Object"
    rsp_target_root = "objects"
    rsp_values = ()

    def rsp_compile(self, context, socket):
        job = context.input(self, "Task", required=True)
        if not isinstance(job, TaskSpec):
            raise TypeError("Task input requires TaskSpec")
        target = context.input(self, self.rsp_target_input, required=True)
        if not target:
            raise ValueError("{} must not be empty".format(self.rsp_target_input))
        result = job
        for input_name, path in self.rsp_values:
            result = apply_override_or_axis(
                result,
                path,
                context.input(self, input_name),
                target_type=self.rsp_target_root,
                target_name=target.name_full,
            )
        return result


class RSP_ObjectVisibilityNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectVisibility"
    bl_label = "Object Visibility"
    rsp_inputs = (J, O, (B, "Viewport"), (B, "Render"))
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_values = (
        ("Viewport", "hide_viewport"),
        ("Render", "hide_render"),
    )

    def init(self, context):
        super().init(context)
        self.inputs["Viewport"].default_value = True
        self.inputs["Render"].default_value = True

    def rsp_compile(self, context, socket):
        job = super().rsp_compile(context, socket)
        target = context.input(self, "Object")
        return (
            job.with_override(
                "hide_viewport",
                not context.input(self, "Viewport"),
                target_type="objects",
                target_name=target.name_full,
            )
            .with_override(
                "hide_render",
                not context.input(self, "Render"),
                target_type="objects",
                target_name=target.name_full,
            )
        )


class RSP_ObjectTransformNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectTransform"
    bl_label = "Object Transform"
    rsp_inputs = (J, O, (V, "Location"), (V, "Rotation"), (V, "Scale"))
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_values = (
        ("Location", "location"),
        ("Rotation", "rotation_euler"),
        ("Scale", "scale"),
    )

    def init(self, context):
        super().init(context)
        self.inputs["Scale"].default_value = (1.0, 1.0, 1.0)


class RSP_ObjectMaterialNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectMaterial"
    bl_label = "Object Material"
    rsp_inputs = (J, O, (M, "Material"))
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_values = (("Material", "active_material"),)


class RSP_ObjectActionNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectAction"
    bl_label = "Object Action"
    rsp_inputs = (J, O, (A, "Action"))
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_values = (("Action", "animation_data.action"),)


class RSP_LightSettingsNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeLightSettings"
    bl_label = "Light Settings"
    rsp_inputs = (
        J,
        O,
        (F, "Intensity"),
        (COL, "Color"),
        (F, "Spread"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_values = (
        ("Intensity", "data.energy"),
        ("Color", "data.color"),
        ("Spread", "data.spread"),
    )

    def init(self, context):
        super().init(context)
        self.inputs["Intensity"].default_value = 10.0
        self.inputs["Color"].default_value = (1.0, 1.0, 1.0)
        # Degrees, matching the Area Light panel (RNA stores radians).
        self.inputs["Spread"].default_value = 180.0

    def rsp_compile(self, context, socket):
        job = context.input(self, "Task", required=True)
        if not isinstance(job, TaskSpec):
            raise TypeError("Task input requires TaskSpec")
        target = context.input(self, "Object", required=True)
        if not target:
            raise ValueError("Object must not be empty")
        if getattr(target, "type", None) != "LIGHT":
            raise ValueError("Light Settings requires a light object")
        light_data = getattr(target, "data", None)
        if light_data is not None and getattr(light_data, "type", None) != "AREA":
            context.warning(
                "LIGHT_SPREAD",
                "Spread applies to area lights; ignored by other light types",
                self,
            )
        result = job
        for input_name, path in self.rsp_values:
            value = context.input(self, input_name)
            if path == "data.color" and not isinstance(value, ValueList):
                value = tuple(value)
            elif path == "data.spread":
                value = _spread_degrees_to_radians(value)
            result = apply_override_or_axis(
                result,
                path,
                value,
                target_type=self.rsp_target_root,
                target_name=target.name_full,
            )
        return result


def _collection_visibility_overrides(
    job,
    collection,
    enabled,
    holdout,
    viewport_visible,
    render_visible,
):
    """Overrides for one collection only — no parent LayerCollection walks."""
    scene = _task_scene(job)
    view_layer = _job_view_layer(job, scene)
    layer_path = _layer_collection_rna_path(view_layer, collection)
    if not layer_path:
        raise ValueError(
            "Collection {!r} is not in view layer {!r}".format(
                collection.name, view_layer.name
            )
        )
    return (
        Override(layer_path + ".exclude", not enabled),
        Override(layer_path + ".holdout", holdout),
        Override(
            "hide_viewport",
            not viewport_visible,
            target_type="collections",
            target_name=collection.name_full,
        ),
        Override(
            "hide_render",
            not render_visible,
            target_type="collections",
            target_name=collection.name_full,
        ),
    )

class RSP_CollectionVisibilityNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeCollectionVisibility"
    bl_label = "Collection Visibility"
    rsp_target_input = "Collection"
    rsp_target_root = "collections"
    # Enabled/Holdout = view-layer LayerCollection; Viewport/Render = Collection.
    rsp_inputs = (
        J,
        C,
        (B, "Enabled"),
        (B, "Holdout"),
        (B, "Viewport"),
        (B, "Render"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)
    rsp_values = ()

    def init(self, context):
        super().init(context)
        self.inputs["Enabled"].default_value = True
        self.inputs["Holdout"].default_value = False
        self.inputs["Viewport"].default_value = True
        self.inputs["Render"].default_value = True

    def rsp_compile(self, context, socket):
        job = context.input(self, "Task", required=True)
        if not isinstance(job, TaskSpec):
            raise TypeError("Task input requires TaskSpec")
        collection = context.input(self, "Collection", required=True)
        if not collection:
            raise ValueError("Collection must not be empty")

        enabled = bool(context.input(self, "Enabled"))
        holdout = bool(context.input(self, "Holdout"))
        viewport_visible = bool(context.input(self, "Viewport"))
        render_visible = bool(context.input(self, "Render"))

        if isinstance(collection, ValueList):
            items = tuple(item for item in collection.items if item)
            if not items:
                raise ValueError("Collection must not be empty")
            bundles = tuple(
                _collection_visibility_overrides(
                    job,
                    item,
                    enabled,
                    holdout,
                    viewport_visible,
                    render_visible,
                )
                for item in items
            )
            return job.with_axis(
                VariantAxis(
                    label="collection",
                    path=OVERRIDE_BUNDLE_PATH,
                    values=bundles,
                )
            )

        result = job
        for override in _collection_visibility_overrides(
            job,
            collection,
            enabled,
            holdout,
            viewport_visible,
            render_visible,
        ):
            result = result.with_override(
                override.path,
                override.value,
                target_type=override.target_type,
                target_name=override.target_name,
            )
        return result


CLASSES = (
    RSP_ObjectVisibilityNode,
    RSP_ObjectTransformNode,
    RSP_ObjectMaterialNode,
    RSP_ObjectActionNode,
    RSP_LightSettingsNode,
    RSP_CollectionVisibilityNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

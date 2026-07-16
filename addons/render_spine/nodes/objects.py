"""Object and collection override nodes."""

import bpy

from ..core.model import JobSpec
from ..core.node import RSP_NodeBase


J = ("RenderSpineNodeSocketJob", "Job")
O = ("RenderSpineNodeSocketObject", "Object")
C = ("RenderSpineNodeSocketCollection", "Collection")
B = "RenderSpineNodeSocketBool"
V = "RenderSpineNodeSocketVector"
M = "RenderSpineNodeSocketMaterial"
A = "RenderSpineNodeSocketAction"


def _job_scene(job):
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
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        target = context.input(self, self.rsp_target_input, required=True)
        if not target:
            raise ValueError("{} must not be empty".format(self.rsp_target_input))
        result = job
        for input_name, path in self.rsp_values:
            result = result.with_override(
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
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
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
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
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
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_values = (("Material", "active_material"),)


class RSP_ObjectActionNode(RSP_TargetOverrideNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeObjectAction"
    bl_label = "Object Action"
    rsp_inputs = (J, O, (A, "Action"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_values = (("Action", "animation_data.action"),)


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
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_values = ()

    def init(self, context):
        super().init(context)
        self.inputs["Enabled"].default_value = True
        self.inputs["Holdout"].default_value = False
        self.inputs["Viewport"].default_value = True
        self.inputs["Render"].default_value = True

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        collection = context.input(self, "Collection", required=True)
        if not collection:
            raise ValueError("Collection must not be empty")

        scene = _job_scene(job)
        view_layer = _job_view_layer(job, scene)
        layer_path = _layer_collection_rna_path(view_layer, collection)
        if not layer_path:
            raise ValueError(
                "Collection {!r} is not in view layer {!r}".format(
                    collection.name, view_layer.name
                )
            )

        enabled = bool(context.input(self, "Enabled"))
        holdout = bool(context.input(self, "Holdout"))
        result = (
            job.with_override(layer_path + ".exclude", not enabled)
            .with_override(layer_path + ".holdout", holdout)
            .with_override(
                "hide_viewport",
                not context.input(self, "Viewport"),
                target_type="collections",
                target_name=collection.name_full,
            )
            .with_override(
                "hide_render",
                not context.input(self, "Render"),
                target_type="collections",
                target_name=collection.name_full,
            )
        )
        return result


CLASSES = (
    RSP_ObjectVisibilityNode,
    RSP_ObjectTransformNode,
    RSP_ObjectMaterialNode,
    RSP_ObjectActionNode,
    RSP_CollectionVisibilityNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

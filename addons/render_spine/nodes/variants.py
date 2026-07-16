"""Variant axis binding and Render Variants expansion nodes."""

import math

import bpy
from bpy.props import EnumProperty

from ..core.model import TaskSpec, ValueList
from ..core.node import RSP_NodeBase
from ..core.variants import VariantAxis, cartesian_tasks


# mode, property_id -> (label, path, target_kind, value_kind)
# target_kind: "" | "objects" | "collections"
# value_kind: float | int | vector | string | object | world | collection
_PROPERTY_TABLE = {
    ("SCENE", "SAMPLES"): ("samples", "cycles.samples", "", "int"),
    ("SCENE", "EEVEE_SAMPLES"): (
        "eevee_samples",
        "eevee.taa_render_samples",
        "",
        "int",
    ),
    ("SCENE", "CAMERA"): ("camera", "camera", "", "object"),
    ("SCENE", "WORLD"): ("world", "world", "", "world"),
    ("SCENE", "WIDTH"): ("width", "render.resolution_x", "", "int"),
    ("SCENE", "HEIGHT"): ("height", "render.resolution_y", "", "int"),
    ("SCENE", "FRAME_START"): ("frame_start", "frame_start", "", "int"),
    ("SCENE", "FRAME_END"): ("frame_end", "frame_end", "", "int"),
    ("SCENE", "FILEPATH"): ("path", "render.filepath", "", "string"),
    ("SCENE", "ENGINE"): ("engine", "render.engine", "", "string"),
    ("OBJECT", "ENERGY"): ("intensity", "data.energy", "objects", "float"),
    ("OBJECT", "COLOR"): ("color", "data.color", "objects", "vector"),
    ("OBJECT", "SPREAD"): ("spread", "data.spread", "objects", "float"),
    ("OBJECT", "SIZE"): ("size", "data.size", "objects", "float"),
    ("OBJECT", "LOCATION"): ("location", "location", "objects", "vector"),
    ("OBJECT", "HIDE_RENDER"): (
        "hide_render",
        "hide_render",
        "objects",
        "int",
    ),
    ("COLLECTION", "HIDE_RENDER"): (
        "hide_render",
        "hide_render",
        "collections",
        "int",
    ),
    ("COLLECTION", "HIDE_VIEWPORT"): (
        "hide_viewport",
        "hide_viewport",
        "collections",
        "int",
    ),
    ("WORLD", "WORLD"): ("world", "world", "", "world"),
}

_MODE_ITEMS = (
    ("SCENE", "Scene", "Scene-level RNA paths"),
    ("OBJECT", "Object", "Object or light datablock paths"),
    ("COLLECTION", "Collection", "Collection visibility paths"),
    ("WORLD", "World", "Assign scene world from a world list"),
)

_PROPERTY_ITEMS = {
    "SCENE": (
        ("SAMPLES", "Cycles Samples", ""),
        ("EEVEE_SAMPLES", "Eevee Samples", ""),
        ("CAMERA", "Camera", ""),
        ("WORLD", "World", ""),
        ("WIDTH", "Resolution X", ""),
        ("HEIGHT", "Resolution Y", ""),
        ("FRAME_START", "Frame Start", ""),
        ("FRAME_END", "Frame End", ""),
        ("FILEPATH", "Output Path", ""),
        ("ENGINE", "Render Engine", ""),
    ),
    "OBJECT": (
        ("ENERGY", "Light Intensity", "data.energy"),
        ("COLOR", "Light Color", "data.color"),
        ("SPREAD", "Light Spread (Degrees)", "data.spread"),
        ("SIZE", "Light Size", "data.size"),
        ("LOCATION", "Location", ""),
        ("HIDE_RENDER", "Hide Render", ""),
    ),
    "COLLECTION": (
        ("HIDE_RENDER", "Hide Render", ""),
        ("HIDE_VIEWPORT", "Hide Viewport", ""),
    ),
    "WORLD": (("WORLD", "World", "Scene world assignment"),),
}

def _property_items(self, context):
    return _PROPERTY_ITEMS.get(self.mode, _PROPERTY_ITEMS["SCENE"])


def _on_mode_update(self, context):
    items = _PROPERTY_ITEMS.get(self.mode, ())
    identifiers = {item[0] for item in items}
    if items and self.setting not in identifiers:
        self.setting = items[0][0]
    self._sync_sockets()


def _as_tuple(value):
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _normalize_values(values, kind):
    result = []
    for item in values:
        if kind == "vector":
            if item is None:
                raise ValueError("Vector list item must not be empty")
            result.append(tuple(item))
        elif kind in ("object", "world", "collection"):
            if item is None:
                raise ValueError("{} list item must not be empty".format(kind))
            result.append(item)
        elif kind == "int":
            result.append(int(item))
        elif kind == "float":
            result.append(float(item))
        else:
            result.append("" if item is None else str(item))
    return tuple(result)


class RSP_VariantAxisNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeVariantAxis"
    bl_label = "Variant Axis"
    rsp_inputs = (
        ("RenderSpineNodeSocketValueList", "Values"),
        ("RenderSpineNodeSocketObject", "Object"),
        ("RenderSpineNodeSocketCollection", "Collection"),
    )
    rsp_outputs = (("RenderSpineNodeSocketVariantAxis", "Axis"),)

    mode: EnumProperty(
        name="Mode",
        items=_MODE_ITEMS,
        default="OBJECT",
        update=_on_mode_update,
    )
    setting: EnumProperty(
        name="Property",
        items=_property_items,
        default=0,
        update=lambda self, context: self._sync_sockets(),
    )

    def init(self, context):
        super().init(context)
        self._sync_sockets()

    def draw_buttons(self, context, layout):
        layout.prop(self, "mode", text="")
        layout.prop(self, "setting", text="")

    def _lookup(self):
        key = (self.mode, self.setting)
        info = _PROPERTY_TABLE.get(key)
        if info is None:
            raise ValueError(
                "Unsupported variant property {} / {}".format(
                    self.mode, self.setting
                )
            )
        return info

    def _sync_sockets(self):
        try:
            _label, _path, target_kind, _value_kind = self._lookup()
        except ValueError:
            target_kind = "objects"
        obj = self.inputs.get("Object")
        coll = self.inputs.get("Collection")
        if obj is not None:
            obj.enabled = target_kind == "objects"
            obj.hide = target_kind != "objects"
        if coll is not None:
            coll.enabled = target_kind == "collections"
            coll.hide = target_kind != "collections"

    def rsp_compile(self, context, socket):
        label, path, target_kind, value_kind = self._lookup()
        raw = context.input(self, "Values", required=True)
        if isinstance(raw, ValueList):
            values = tuple(raw.items)
        else:
            values = _as_tuple(raw)
        values = _normalize_values(values, value_kind)
        # Match Area Light panel: UI degrees, RNA radians.
        if path == "data.spread":
            values = tuple(math.radians(float(item)) for item in values)

        target_type = target_kind
        target_name = ""
        if target_kind == "objects":
            target = context.input(self, "Object", required=True)
            if not target:
                raise ValueError("Object target must not be empty")
            target_name = target.name_full
        elif target_kind == "collections":
            target = context.input(self, "Collection", required=True)
            if not target:
                raise ValueError("Collection target must not be empty")
            target_name = target.name_full

        return VariantAxis(
            label=label,
            path=path,
            values=values,
            target_type=target_type,
            target_name=target_name,
        )


class RSP_RenderVariantsNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeRenderVariants"
    bl_label = "Render Variants"
    rsp_inputs = (
        ("RenderSpineNodeSocketTask", "Task"),
        ("RenderSpineNodeSocketVariantAxis", "Axis 1"),
        ("RenderSpineNodeSocketVariantAxis", "Axis 2"),
        ("RenderSpineNodeSocketVariantAxis", "Axis 3"),
        ("RenderSpineNodeSocketVariantAxis", "Axis 4"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTaskList", "Tasks"),)

    def rsp_compile(self, context, socket):
        job = context.input(self, "Task", required=True)
        if not isinstance(job, TaskSpec):
            raise TypeError("Task input requires TaskSpec")
        axes = []
        for name in ("Axis 1", "Axis 2", "Axis 3", "Axis 4"):
            socket_in = self.inputs.get(name)
            if socket_in is None or not socket_in.is_linked:
                continue
            axis = context.input(self, name)
            if not isinstance(axis, VariantAxis):
                raise TypeError("{} requires VariantAxis".format(name))
            axes.append(axis)
        return cartesian_tasks(job, axes)


CLASSES = (
    RSP_VariantAxisNode,
    RSP_RenderVariantsNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

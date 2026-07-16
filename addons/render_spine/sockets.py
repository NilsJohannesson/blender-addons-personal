"""Typed sockets for RenderSpine render graphs."""

import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)


# EnumProperty dynamic-items callbacks return Python strings that Blender's C
# layer holds by pointer. Cache the most recent result per socket pointer.
_view_layer_items_cache = {}
_engine_items_cache = {}
_format_items_cache = {}
_view_transform_items_cache = {}
_look_items_cache = {}
_denoiser_items_cache = {}

_FALLBACK_ENGINES = (
    ("CYCLES", "Cycles", "Path-tracing render engine"),
    ("BLENDER_EEVEE", "EEVEE", "Real-time render engine"),
    ("BLENDER_WORKBENCH", "Workbench", "Solid viewport-style engine"),
)

_FALLBACK_FORMATS = (
    ("PNG", "PNG", ""),
    ("JPEG", "JPEG", ""),
    ("OPEN_EXR", "OpenEXR", ""),
    ("OPEN_EXR_MULTILAYER", "OpenEXR MultiLayer", ""),
    ("TIFF", "TIFF", ""),
    ("WEBP", "WebP", ""),
    ("AVIF", "AVIF", ""),
    ("BMP", "Bitmap", ""),
    ("TARGA", "Targa", ""),
    ("FFMPEG", "FFmpeg Video", ""),
)

_FALLBACK_VIEW_TRANSFORMS = (
    ("AgX", "AgX", ""),
    ("Filmic", "Filmic", ""),
    ("Filmic Log", "Filmic Log", ""),
    ("False Color", "False Color", ""),
    ("Raw", "Raw", ""),
    ("Standard", "Standard", ""),
    ("Khronos PBR Neutral", "Khronos PBR Neutral", ""),
)

# Blender OCIO look identifiers are case-sensitive ("None", not "NONE") and
# AgX looks use the "AgX - …" prefix in current Blender releases.
_FALLBACK_LOOKS = (
    ("None", "None", ""),
    ("AgX - Punchy", "AgX - Punchy", ""),
    ("AgX - Greyscale", "AgX - Greyscale", ""),
    ("AgX - Very High Contrast", "AgX - Very High Contrast", ""),
    ("AgX - High Contrast", "AgX - High Contrast", ""),
    ("AgX - Medium High Contrast", "AgX - Medium High Contrast", ""),
    ("AgX - Base Contrast", "AgX - Base Contrast", ""),
    ("AgX - Medium Low Contrast", "AgX - Medium Low Contrast", ""),
    ("AgX - Low Contrast", "AgX - Low Contrast", ""),
    ("AgX - Very Low Contrast", "AgX - Very Low Contrast", ""),
)

# Device-dependent; RNA enum_items is often empty until Cycles probes GPUs.
_FALLBACK_DENOISERS = (
    ("OPENIMAGEDENOISE", "OpenImageDenoise", ""),
    ("OPTIX", "OptiX", ""),
)

_DENOISING_INPUT_PASSES = (
    ("RGB", "None", ""),
    ("RGB_ALBEDO", "Albedo", ""),
    ("RGB_ALBEDO_NORMAL", "Albedo and Normal", ""),
)

_DENOISING_PREFILTERS = (
    ("NONE", "None", ""),
    ("FAST", "Fast", ""),
    ("ACCURATE", "Accurate", ""),
)

_DENOISING_QUALITIES = (
    ("HIGH", "High", ""),
    ("BALANCED", "Balanced", ""),
    ("FAST", "Fast", ""),
)

_FFMPEG_CONTAINERS = (
    ("MPEG4", "MPEG-4", "MP4 container"),
    ("MKV", "Matroska", ""),
    ("QUICKTIME", "QuickTime", ""),
    ("AVI", "AVI", ""),
    ("WEBM", "WebM", ""),
)

_FFMPEG_CODECS = (
    ("H264", "H.264", ""),
    ("H265", "H.265 / HEVC", ""),
    ("WEBM", "WebM / VP9", ""),
    ("MPEG4", "MPEG-4 (divx)", ""),
    ("AV1", "AV1", ""),
    ("DNXHD", "DNxHD", ""),
    ("PRORES", "ProRes", ""),
)

_FFMPEG_CRF = (
    ("LOSSLESS", "Lossless", ""),
    ("PERC_LOSSLESS", "Perceptually Lossless", ""),
    ("HIGH", "High Quality", ""),
    ("MEDIUM", "Medium Quality", ""),
    ("LOW", "Low Quality", ""),
    ("VERYLOW", "Very Low Quality", ""),
    ("LOWEST", "Lowest Quality", ""),
)

_FFMPEG_PRESETS = (
    ("BEST", "Slowest", ""),
    ("GOOD", "Good", ""),
    ("REALTIME", "Realtime", ""),
)

_FFMPEG_AUDIO = (
    ("NONE", "No Audio", ""),
    ("AAC", "AAC", ""),
    ("MP3", "MP3", ""),
    ("AC3", "AC3", ""),
    ("OPUS", "Opus", ""),
    ("FLAC", "FLAC", ""),
)


def _cache_items(cache, owner, items):
    if not items:
        items = [("", "(none)", "")]
    cache[owner.as_pointer()] = items
    return cache[owner.as_pointer()]


def _rna_enum_items(owner, property_name):
    try:
        prop = owner.bl_rna.properties[property_name]
        items = [
            (item.identifier, item.name, item.description or "")
            for item in prop.enum_items
            if item.identifier
        ]
        # Headless / incomplete OCIO often only exposes a lone None entry.
        if len(items) <= 1 and items and items[0][0].lower() == "none":
            return []
        return items
    except (AttributeError, KeyError, TypeError):
        return []


def _scene_for_socket(socket, context):
    node = getattr(socket, "node", None)
    if node is not None:
        scene_socket = node.inputs.get("Scene")
        if scene_socket is not None and not scene_socket.is_linked:
            scene = getattr(scene_socket, "default_value", None)
            if isinstance(scene, bpy.types.Scene):
                return scene
    return context.scene if context is not None else bpy.context.scene


def _view_layer_items(self, context):
    scene = _scene_for_socket(self, context)
    items = [
        (
            "__NONE__",
            "—",
            "Use the active view layer only (disable other layers for this task)",
        )
    ]
    if scene is not None:
        items.extend((layer.name, layer.name, "") for layer in scene.view_layers)
    return _cache_items(_view_layer_items_cache, self, items)


def _engine_items(self, context):
    scene = _scene_for_socket(self, context)
    items = list(_rna_enum_items(scene.render, "engine")) if scene else []
    known = {item[0] for item in items}
    for item in _FALLBACK_ENGINES:
        if item[0] not in known:
            items.append(item)
    return _cache_items(_engine_items_cache, self, items)


def _format_items(self, context):
    scene = _scene_for_socket(self, context)
    items = []
    if scene is not None:
        items = list(_rna_enum_items(scene.render.image_settings, "file_format"))
    known = {item[0] for item in items}
    for item in _FALLBACK_FORMATS:
        if item[0] not in known:
            items.append(item)
    return _cache_items(_format_items_cache, self, items)


def _view_transform_items(self, context):
    scene = _scene_for_socket(self, context)
    items = list(_rna_enum_items(scene.view_settings, "view_transform")) if scene else []
    known = {item[0] for item in items}
    for item in _FALLBACK_VIEW_TRANSFORMS:
        if item[0] not in known:
            items.append(item)
    return _cache_items(_view_transform_items_cache, self, items)


def _look_items(self, context):
    scene = _scene_for_socket(self, context)
    items = []
    if scene is not None:
        view_settings = scene.view_settings
        old_transform = view_settings.view_transform
        desired = None
        node = getattr(self, "node", None)
        if node is not None:
            transform_socket = node.inputs.get("View Transform")
            if transform_socket is not None and not transform_socket.is_linked:
                desired = transform_socket.default_value
        try:
            if desired and desired != old_transform:
                view_settings.view_transform = desired
            items = list(_rna_enum_items(view_settings, "look"))
        except (TypeError, ValueError):
            items = []
        finally:
            if desired and view_settings.view_transform != old_transform:
                try:
                    view_settings.view_transform = old_transform
                except (TypeError, ValueError):
                    pass
    known = {item[0] for item in items}
    for item in _FALLBACK_LOOKS:
        if item[0] not in known:
            items.append(item)
    return _cache_items(_look_items_cache, self, items)


def _denoiser_items(self, context):
    scene = _scene_for_socket(self, context)
    items = []
    cycles = getattr(scene, "cycles", None) if scene is not None else None
    if cycles is not None:
        items = list(_rna_enum_items(cycles, "denoiser"))
    known = {item[0] for item in items}
    for item in _FALLBACK_DENOISERS:
        if item[0] not in known:
            items.append(item)
    return _cache_items(_denoiser_items_cache, self, items)


class RSP_SocketBase:
    rsp_family = "ANY"
    rsp_accepts = ("ANY",)
    color = (0.45, 0.45, 0.45, 1.0)

    def draw(self, context, layout, node, text):
        if self.is_output or self.is_linked or not hasattr(self, "default_value"):
            layout.label(text=text or self.name)
        else:
            layout.prop(self, "default_value", text=text or self.name)

    def draw_color(self, context, node):
        return self.color

    @classmethod
    def draw_color_simple(cls):
        return cls.color

    def rsp_value(self):
        return getattr(self, "default_value", None)


class RSP_ValueSocket(RSP_SocketBase):
    rsp_accepts = ("BOOL", "INT", "FLOAT", "STRING", "VECTOR", "DATABLOCK")


class RSP_AnySocket(RSP_SocketBase, bpy.types.NodeSocket):
    """Wildcard input. Validation treats rsp_accepts 'ANY' as accept-all."""

    bl_idname = "RenderSpineNodeSocketAny"
    bl_label = "Any"
    rsp_family = "ANY"
    rsp_accepts = ("ANY",)
    color = (0.45, 0.45, 0.45, 1.0)

    def draw(self, context, layout, node, text):
        layout.label(text=text or self.name)

    def rsp_value(self):
        return None


class RSP_BoolSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketBool"
    bl_label = "Boolean"
    rsp_family = "BOOL"
    rsp_accepts = ("BOOL",)
    color = (0.6, 0.2, 0.7, 1.0)
    default_value: BoolProperty(default=False)


class RSP_IntSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketInt"
    bl_label = "Integer"
    rsp_family = "INT"
    rsp_accepts = ("INT", "INT_LIST")
    color = (0.1, 0.55, 0.8, 1.0)
    default_value: IntProperty(default=0)


class RSP_FloatSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFloat"
    bl_label = "Float"
    rsp_family = "FLOAT"
    rsp_accepts = ("FLOAT", "INT", "FLOAT_LIST", "INT_LIST")
    color = (0.35, 0.65, 0.25, 1.0)
    default_value: FloatProperty(default=0.0)


# Plain string / path sockets coerce linked values (object name, ints, …).
# Enum string sockets stay STRING-only so Collection≠Engine, etc.
_STRING_COERCE_ACCEPTS = (
    "STRING",
    "STRING_LIST",
    "BOOL",
    "INT",
    "FLOAT",
    "VECTOR",
    "OBJECT",
    "MATERIAL",
    "COLLECTION",
    "SCENE",
    "WORLD",
    "ACTION",
    "DATABLOCK",
)


class RSP_StringSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketString"
    bl_label = "String"
    rsp_family = "STRING"
    rsp_accepts = _STRING_COERCE_ACCEPTS
    rsp_coerce_to_string = True
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: StringProperty(default="")


class RSP_FilePathSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFilePath"
    bl_label = "File Path"
    rsp_family = "STRING"
    rsp_accepts = _STRING_COERCE_ACCEPTS
    rsp_coerce_to_string = True
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: StringProperty(
        default="",
        subtype="FILE_PATH",
        options={"PATH_SUPPORTS_BLEND_RELATIVE", "OUTPUT_PATH"},
        description=(
            "Output path expression. Use // for blend-relative folders. "
            "Supports {tokens} and $tokens, e.g. "
            "//renders/$label/$V/$res_$camera_$F4 or "
            "//renders/{camera}_{resolution}_{variant_index}"
        ),
    )


class RSP_ViewLayerSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketViewLayer"
    bl_label = "View Layer"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="View Layer",
        items=_view_layer_items,
        default=0,
    )

    def rsp_value(self):
        value = self.default_value
        if value in ("", "__NONE__"):
            return ""
        return value


class RSP_EngineSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketEngine"
    bl_label = "Render Engine"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Engine",
        items=_engine_items,
        default=0,
    )


class RSP_ImageFormatSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketImageFormat"
    bl_label = "Image Format"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Format",
        items=_format_items,
        default=0,
    )


class RSP_ViewTransformSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketViewTransform"
    bl_label = "View Transform"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="View Transform",
        items=_view_transform_items,
        default=0,
    )


class RSP_LookSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketLook"
    bl_label = "Look"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Look",
        items=_look_items,
        default=0,
    )

    def rsp_value(self):
        value = self.default_value
        # Older socket defaults used uppercase NONE; Blender expects "None".
        if value == "NONE":
            return "None"
        return value


class RSP_DenoiserSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketDenoiser"
    bl_label = "Denoiser"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Denoiser",
        items=_denoiser_items,
        default=0,
    )


class RSP_DenoisingInputPassesSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketDenoisingInputPasses"
    bl_label = "Denoising Input Passes"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Passes",
        items=_DENOISING_INPUT_PASSES,
        default="RGB_ALBEDO_NORMAL",
    )


class RSP_DenoisingPrefilterSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketDenoisingPrefilter"
    bl_label = "Denoising Prefilter"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Prefilter",
        items=_DENOISING_PREFILTERS,
        default="ACCURATE",
    )


class RSP_DenoisingQualitySocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketDenoisingQuality"
    bl_label = "Denoising Quality"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Quality",
        items=_DENOISING_QUALITIES,
        default="HIGH",
    )


class RSP_FFmpegContainerSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFFmpegContainer"
    bl_label = "FFmpeg Container"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Container",
        items=_FFMPEG_CONTAINERS,
        default="MPEG4",
    )


class RSP_FFmpegCodecSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFFmpegCodec"
    bl_label = "FFmpeg Codec"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Codec",
        items=_FFMPEG_CODECS,
        default="H264",
    )


class RSP_FFmpegQualitySocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFFmpegQuality"
    bl_label = "FFmpeg Quality"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Quality",
        items=_FFMPEG_CRF,
        default="MEDIUM",
    )


class RSP_FFmpegPresetSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFFmpegPreset"
    bl_label = "FFmpeg Preset"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Encoding Speed",
        items=_FFMPEG_PRESETS,
        default="GOOD",
    )


class RSP_FFmpegAudioSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFFmpegAudio"
    bl_label = "FFmpeg Audio"
    rsp_family = "STRING"
    rsp_accepts = ("STRING",)
    color = (0.55, 0.55, 0.55, 1.0)
    default_value: EnumProperty(
        name="Audio",
        items=_FFMPEG_AUDIO,
        default="AAC",
    )


class RSP_VectorSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketVector"
    bl_label = "Vector"
    rsp_family = "VECTOR"
    rsp_accepts = ("VECTOR", "VECTOR_LIST")
    color = (0.35, 0.35, 0.8, 1.0)
    default_value: FloatVectorProperty(size=3, subtype="XYZ")

    def rsp_value(self):
        return tuple(self.default_value)


class RSP_ColorSocket(RSP_SocketBase, bpy.types.NodeSocket):
    """RGB color picker; same VECTOR family as Vector for graph linking."""

    bl_idname = "RenderSpineNodeSocketColor"
    bl_label = "Color"
    rsp_family = "VECTOR"
    rsp_accepts = ("VECTOR", "VECTOR_LIST")
    color = (0.8, 0.65, 0.2, 1.0)
    default_value: FloatVectorProperty(
        size=3,
        subtype="COLOR",
        min=0.0,
        max=1.0,
        default=(1.0, 1.0, 1.0),
    )

    def rsp_value(self):
        return tuple(self.default_value)


class RSP_DatablockSocket(RSP_SocketBase):
    rsp_family = "DATABLOCK"
    rsp_accepts = ("DATABLOCK",)
    color = (0.8, 0.55, 0.2, 1.0)

    def rsp_value(self):
        return self.default_value


class RSP_ObjectSocket(RSP_DatablockSocket, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketObject"
    bl_label = "Object"
    rsp_family = "OBJECT"
    rsp_accepts = ("OBJECT", "OBJECT_LIST")
    default_value: PointerProperty(type=bpy.types.Object)


class RSP_MaterialSocket(RSP_DatablockSocket, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketMaterial"
    bl_label = "Material"
    rsp_family = "MATERIAL"
    rsp_accepts = ("MATERIAL",)
    default_value: PointerProperty(type=bpy.types.Material)


class RSP_CollectionSocket(RSP_DatablockSocket, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketCollection"
    bl_label = "Collection"
    rsp_family = "COLLECTION"
    rsp_accepts = ("COLLECTION", "COLLECTION_LIST")
    default_value: PointerProperty(type=bpy.types.Collection)


class RSP_SceneSocket(RSP_DatablockSocket, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketScene"
    bl_label = "Scene"
    rsp_family = "SCENE"
    rsp_accepts = ("SCENE",)
    default_value: PointerProperty(type=bpy.types.Scene)


class RSP_WorldSocket(RSP_DatablockSocket, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketWorld"
    bl_label = "World"
    rsp_family = "WORLD"
    rsp_accepts = ("WORLD", "WORLD_LIST")
    default_value: PointerProperty(type=bpy.types.World)


class RSP_ActionSocket(RSP_DatablockSocket, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketAction"
    bl_label = "Action"
    rsp_family = "ACTION"
    rsp_accepts = ("ACTION",)
    default_value: PointerProperty(type=bpy.types.Action)


class RSP_TaskSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketTask"
    bl_label = "Task"
    rsp_family = "JOB"
    rsp_accepts = ("JOB",)
    color = (0.85, 0.25, 0.15, 1.0)


class RSP_TaskListSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketTaskList"
    bl_label = "Task List"
    rsp_family = "JOB_LIST"
    rsp_accepts = ("JOB_LIST",)
    color = (0.95, 0.5, 0.15, 1.0)


_LIST_FAMILIES = (
    "FLOAT_LIST",
    "INT_LIST",
    "VECTOR_LIST",
    "STRING_LIST",
    "OBJECT_LIST",
    "WORLD_LIST",
    "COLLECTION_LIST",
    "VALUE_LIST",
)


class RSP_ListSocketBase(RSP_SocketBase):
    """List sockets have no inline default; values come from list nodes."""

    color = (0.4, 0.7, 0.7, 1.0)

    def draw(self, context, layout, node, text):
        layout.label(text=text or self.name)

    def rsp_value(self):
        return ()


class RSP_FloatListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketFloatList"
    bl_label = "Float List"
    rsp_family = "FLOAT_LIST"
    rsp_accepts = ("FLOAT_LIST",)


class RSP_IntListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketIntList"
    bl_label = "Int List"
    rsp_family = "INT_LIST"
    rsp_accepts = ("INT_LIST",)


class RSP_VectorListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketVectorList"
    bl_label = "Vector List"
    rsp_family = "VECTOR_LIST"
    rsp_accepts = ("VECTOR_LIST",)


class RSP_StringListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketStringList"
    bl_label = "String List"
    rsp_family = "STRING_LIST"
    rsp_accepts = ("STRING_LIST",)


class RSP_ObjectListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketObjectList"
    bl_label = "Object List"
    rsp_family = "OBJECT_LIST"
    rsp_accepts = ("OBJECT_LIST",)
    color = (0.8, 0.55, 0.2, 1.0)


class RSP_WorldListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketWorldList"
    bl_label = "World List"
    rsp_family = "WORLD_LIST"
    rsp_accepts = ("WORLD_LIST",)
    color = (0.8, 0.55, 0.2, 1.0)


class RSP_CollectionListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketCollectionList"
    bl_label = "Collection List"
    rsp_family = "COLLECTION_LIST"
    rsp_accepts = ("COLLECTION_LIST",)
    color = (0.8, 0.55, 0.2, 1.0)


class RSP_ValueListSocket(RSP_ListSocketBase, bpy.types.NodeSocket):
    """Accepts any typed value list for Variant Axis binding."""

    bl_idname = "RenderSpineNodeSocketValueList"
    bl_label = "Value List"
    rsp_family = "VALUE_LIST"
    rsp_accepts = _LIST_FAMILIES
    color = (0.35, 0.75, 0.65, 1.0)


class RSP_VariantAxisSocket(RSP_SocketBase, bpy.types.NodeSocket):
    bl_idname = "RenderSpineNodeSocketVariantAxis"
    bl_label = "Variant Axis"
    rsp_family = "VARIANT_AXIS"
    rsp_accepts = ("VARIANT_AXIS",)
    color = (0.75, 0.35, 0.55, 1.0)

    def draw(self, context, layout, node, text):
        layout.label(text=text or self.name)

    def rsp_value(self):
        return None


SOCKET_CLASSES = (
    RSP_AnySocket,
    RSP_BoolSocket,
    RSP_IntSocket,
    RSP_FloatSocket,
    RSP_StringSocket,
    RSP_FilePathSocket,
    RSP_ViewLayerSocket,
    RSP_EngineSocket,
    RSP_ImageFormatSocket,
    RSP_ViewTransformSocket,
    RSP_LookSocket,
    RSP_DenoiserSocket,
    RSP_DenoisingInputPassesSocket,
    RSP_DenoisingPrefilterSocket,
    RSP_DenoisingQualitySocket,
    RSP_FFmpegContainerSocket,
    RSP_FFmpegCodecSocket,
    RSP_FFmpegQualitySocket,
    RSP_FFmpegPresetSocket,
    RSP_FFmpegAudioSocket,
    RSP_VectorSocket,
    RSP_ColorSocket,
    RSP_ObjectSocket,
    RSP_MaterialSocket,
    RSP_CollectionSocket,
    RSP_SceneSocket,
    RSP_WorldSocket,
    RSP_ActionSocket,
    RSP_TaskSocket,
    RSP_TaskListSocket,
    RSP_FloatListSocket,
    RSP_IntListSocket,
    RSP_VectorListSocket,
    RSP_StringListSocket,
    RSP_ObjectListSocket,
    RSP_WorldListSocket,
    RSP_CollectionListSocket,
    RSP_ValueListSocket,
    RSP_VariantAxisSocket,
)


def register():
    for cls in SOCKET_CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(SOCKET_CLASSES):
        bpy.utils.unregister_class(cls)

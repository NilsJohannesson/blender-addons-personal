"""Scene and render setting override nodes."""

import bpy
from bpy.props import PointerProperty

from ..core.model import JobSpec
from ..core.node import RSP_JobTransformNodeBase, apply_engine_samples, scene_snapshot


J = ("RenderSpineNodeSocketJob", "Job")
I = "RenderSpineNodeSocketInt"
F = "RenderSpineNodeSocketFloat"
B = "RenderSpineNodeSocketBool"
O = "RenderSpineNodeSocketObject"
W = "RenderSpineNodeSocketWorld"
VL = "RenderSpineNodeSocketViewLayer"
EN = "RenderSpineNodeSocketEngine"
FP = "RenderSpineNodeSocketFilePath"
FM = "RenderSpineNodeSocketImageFormat"
VT = "RenderSpineNodeSocketViewTransform"
LK = "RenderSpineNodeSocketLook"
DN = "RenderSpineNodeSocketDenoiser"
DIP = "RenderSpineNodeSocketDenoisingInputPasses"
DPF = "RenderSpineNodeSocketDenoisingPrefilter"
DQ = "RenderSpineNodeSocketDenoisingQuality"
FC = "RenderSpineNodeSocketFFmpegContainer"
FVC = "RenderSpineNodeSocketFFmpegCodec"
FQ = "RenderSpineNodeSocketFFmpegQuality"
FPST = "RenderSpineNodeSocketFFmpegPreset"
FA = "RenderSpineNodeSocketFFmpegAudio"

# (socket label, RNA path relative to view_layer, default)
_PASS_BOOL_SPECS = (
    ("Combined", "use_pass_combined", True),
    ("Depth", "use_pass_z", False),
    ("Mist", "use_pass_mist", False),
    ("Position", "use_pass_position", False),
    ("Normal", "use_pass_normal", False),
    ("Vector", "use_pass_vector", False),
    ("UV", "use_pass_uv", False),
    ("Grease Pencil", "use_pass_grease_pencil", False),
    ("Denoising Data", "cycles.denoising_store_passes", False),
    ("Object Index", "use_pass_object_index", False),
    ("Material Index", "use_pass_material_index", False),
    ("Sample Count", "cycles.pass_debug_sample_count", False),
    ("Render Time", "cycles.pass_render_time", False),
    ("Diffuse Direct", "use_pass_diffuse_direct", False),
    ("Diffuse Indirect", "use_pass_diffuse_indirect", False),
    ("Diffuse Color", "use_pass_diffuse_color", False),
    ("Glossy Direct", "use_pass_glossy_direct", False),
    ("Glossy Indirect", "use_pass_glossy_indirect", False),
    ("Glossy Color", "use_pass_glossy_color", False),
    ("Transmission Direct", "use_pass_transmission_direct", False),
    ("Transmission Indirect", "use_pass_transmission_indirect", False),
    ("Transmission Color", "use_pass_transmission_color", False),
    ("Volume Direct", "cycles.use_pass_volume_direct", False),
    ("Volume Indirect", "cycles.use_pass_volume_indirect", False),
    ("Emission", "use_pass_emit", False),
    ("Environment", "use_pass_environment", False),
    ("Ambient Occlusion", "use_pass_ambient_occlusion", False),
    ("Shadow Catcher", "cycles.use_pass_shadow_catcher", False),
    ("Cryptomatte Object", "use_pass_cryptomatte_object", False),
    ("Cryptomatte Material", "use_pass_cryptomatte_material", False),
    ("Cryptomatte Asset", "use_pass_cryptomatte_asset", False),
)


def _resolve_pass_view_layer(job, layer_name, scene):
    name = layer_name or ""
    if not name:
        metadata = dict(job.metadata)
        name = metadata.get("view_layer") or ""
    if not name:
        active = getattr(scene.view_layers, "active", None)
        if active is not None:
            name = active.name
        elif scene.view_layers:
            name = scene.view_layers[0].name
    if not name:
        raise ValueError("No view layer available for render passes")
    if '"' in name or "\\" in name:
        raise ValueError("View layer name cannot contain quotes or backslashes")
    if scene.view_layers.get(name) is None:
        raise ValueError("View layer not found: {}".format(name))
    return name


class RSP_SettingsNode(RSP_JobTransformNodeBase):
    rsp_defaults = {}

    def init(self, context):
        super().init(context)
        for name, value in self.rsp_defaults.items():
            socket = self.inputs.get(name)
            if socket is None:
                continue
            try:
                socket.default_value = value
            except (TypeError, ValueError):
                pass


class RSP_RenderSettingsNode(RSP_SettingsNode, bpy.types.Node):
    """Optional override pack. Chain after Render Job to retarget quality/film."""

    bl_idname = "RenderSpineNodeRenderSettings"
    bl_label = "Render Settings"
    bl_width_default = 220
    rsp_inputs = (
        J,
        (W, "World"),
        (EN, "Engine"),
        (I, "Samples"),
        (B, "Transparent"),
        (B, "Motion Blur"),
        (F, "Motion Blur Shutter"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_defaults = {
        "Engine": "CYCLES",
        "Samples": 128,
        "Motion Blur Shutter": 0.5,
    }
    rsp_simple_overrides = (
        ("Engine", "render.engine"),
        ("Transparent", "render.film_transparent"),
        ("Motion Blur", "render.use_motion_blur"),
        ("Motion Blur Shutter", "render.motion_blur_shutter"),
    )

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        values = {}
        world = context.input(self, "World")
        if world is not None:
            values["world"] = world
        for input_name, path in self.rsp_simple_overrides:
            values[path] = context.input(self, input_name)
        engine = context.input(self, "Engine")
        apply_engine_samples(values, engine, context.input(self, "Samples"))
        return job.with_overrides(values)


class RSP_CameraNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeSetCamera"
    bl_label = "Set Camera"
    rsp_inputs = (J, (O, "Camera"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (("Camera", "camera"),)


class RSP_WorldNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeSetWorld"
    bl_label = "Set World"
    rsp_inputs = (J, (W, "World"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (("World", "world"),)


class RSP_ViewLayerNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeSetViewLayer"
    bl_label = "Set View Layer"
    rsp_inputs = (J, (VL, "View Layer"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = ()

    def init(self, context):
        super().init(context)
        scene = context.scene if context is not None else bpy.context.scene
        if scene is not None and scene.view_layers:
            try:
                self.inputs["View Layer"].default_value = scene.view_layers[0].name
            except (TypeError, ValueError):
                pass

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        layer_name = context.input(self, "View Layer") or ""
        if not layer_name:
            raise ValueError("View layer is required")
        if '"' in layer_name or "\\" in layer_name:
            raise ValueError("View layer name cannot contain quotes or backslashes")
        source = job.source_scene
        scene = source if isinstance(source, bpy.types.Scene) else bpy.data.scenes.get(source)
        scene = scene or bpy.context.scene
        if scene.view_layers.get(layer_name) is None:
            raise ValueError("View layer not found: {}".format(layer_name))
        result = job.with_metadata("view_layer", layer_name)
        for layer in sorted(scene.view_layers, key=lambda item: item.name):
            result = result.with_override(
                'view_layers["{}"].use'.format(layer.name),
                layer.name == layer_name,
            )
        return result


class RSP_EngineNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeSetEngine"
    bl_label = "Set Render Engine"
    rsp_inputs = (J, (EN, "Engine"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (("Engine", "render.engine"),)
    rsp_defaults = {"Engine": "BLENDER_EEVEE"}


class RSP_CyclesSamplesNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeCyclesSamples"
    bl_label = "Cycles Samples"
    rsp_inputs = (J, (I, "Render"), (I, "Viewport"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Render", "cycles.samples"),
        ("Viewport", "cycles.preview_samples"),
    )
    rsp_defaults = {"Render": 4096, "Viewport": 1024}


class RSP_EeveeSamplesNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeEeveeSamples"
    bl_label = "Eevee Samples"
    rsp_inputs = (J, (I, "Render"), (I, "Viewport"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Render", "eevee.taa_render_samples"),
        ("Viewport", "eevee.taa_samples"),
    )
    rsp_defaults = {"Render": 64, "Viewport": 64}


class RSP_FrameRangeNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeFrameRange"
    bl_label = "Frame Range"
    rsp_inputs = (J, (I, "Start"), (I, "End"), (I, "Step"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Start", "frame_start"),
        ("End", "frame_end"),
        ("Step", "frame_step"),
    )
    rsp_defaults = {"Start": 1, "End": 250, "Step": 1}


class RSP_ResolutionNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeResolution"
    bl_label = "Resolution"
    rsp_inputs = (J, (I, "Width"), (I, "Height"), (I, "Percent"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Width", "render.resolution_x"),
        ("Height", "render.resolution_y"),
        ("Percent", "render.resolution_percentage"),
    )
    rsp_defaults = {"Width": 1920, "Height": 1080, "Percent": 100}


class RSP_OutputPathNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeOutputPath"
    bl_label = "Output Path"
    rsp_inputs = (J, (FP, "Path"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (("Path", "render.filepath"),)


class RSP_OutputFormatNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeOutputFormat"
    bl_label = "Output Format"
    rsp_inputs = (J, (FM, "Format"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (("Format", "render.image_settings.file_format"),)
    rsp_defaults = {"Format": "PNG"}


class RSP_FFmpegVideoNode(RSP_SettingsNode, bpy.types.Node):
    """FFmpeg video output. Defaults aimed at H.264 MP4 proxies."""

    bl_idname = "RenderSpineNodeFFmpegVideo"
    bl_label = "FFmpeg Video"
    bl_width_default = 200
    rsp_inputs = (
        J,
        (FC, "Container"),
        (FVC, "Codec"),
        (FQ, "Quality"),
        (FPST, "Encoding Speed"),
        (FA, "Audio"),
        (I, "Audio Bitrate"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = ()
    rsp_defaults = {
        "Container": "MPEG4",
        "Codec": "H264",
        "Quality": "MEDIUM",
        "Encoding Speed": "GOOD",
        "Audio": "AAC",
        "Audio Bitrate": 128,
    }

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        audio = context.input(self, "Audio") or "NONE"
        values = {
            # Animation/video writes require Output panel "save" enabled.
            "render.save_output": True,
            "render.image_settings.file_format": "FFMPEG",
            "render.ffmpeg.format": context.input(self, "Container"),
            "render.ffmpeg.codec": context.input(self, "Codec"),
            "render.ffmpeg.constant_rate_factor": context.input(self, "Quality"),
            "render.ffmpeg.ffmpeg_preset": context.input(self, "Encoding Speed"),
            "render.ffmpeg.audio_codec": audio,
            "render.ffmpeg.audio_bitrate": int(context.input(self, "Audio Bitrate")),
        }
        if audio != "NONE":
            values["render.ffmpeg.audio_channels"] = "STEREO"
        return job.with_overrides(values)


class RSP_FilmNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeFilm"
    bl_label = "Film"
    rsp_inputs = (
        J,
        (B, "Transparent"),
        (B, "Motion Blur"),
        (F, "Motion Blur Shutter"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Transparent", "render.film_transparent"),
        ("Motion Blur", "render.use_motion_blur"),
        ("Motion Blur Shutter", "render.motion_blur_shutter"),
    )
    rsp_defaults = {"Motion Blur Shutter": 0.5}


class RSP_ColorManagementNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeColorManagement"
    bl_label = "Color Management"
    rsp_inputs = (J, (VT, "View Transform"), (LK, "Look"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("View Transform", "view_settings.view_transform"),
        ("Look", "view_settings.look"),
    )
    rsp_defaults = {
        "View Transform": "AgX",
        "Look": "AgX - Medium High Contrast",
    }


class RSP_SimplifyNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeSimplify"
    bl_label = "Simplify"
    rsp_inputs = (J, (B, "Enabled"), (I, "Subdivision"))
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Enabled", "render.use_simplify"),
        ("Subdivision", "render.simplify_subdivision_render"),
    )


class RSP_DenoisingNode(RSP_SettingsNode, bpy.types.Node):
    """Cycles render denoising (Sampling › Denoise)."""

    bl_idname = "RenderSpineNodeDenoising"
    bl_label = "Denoising"
    bl_width_default = 200
    rsp_inputs = (
        J,
        (B, "Enabled"),
        (DN, "Denoiser"),
        (DIP, "Passes"),
        (DPF, "Prefilter"),
        (DQ, "Quality"),
        (B, "Use GPU"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = (
        ("Enabled", "cycles.use_denoising"),
        ("Denoiser", "cycles.denoiser"),
        ("Passes", "cycles.denoising_input_passes"),
        ("Prefilter", "cycles.denoising_prefilter"),
        ("Quality", "cycles.denoising_quality"),
        ("Use GPU", "cycles.denoising_use_gpu"),
    )
    rsp_defaults = {
        "Enabled": True,
        "Denoiser": "OPENIMAGEDENOISE",
        "Passes": "RGB_ALBEDO_NORMAL",
        "Prefilter": "ACCURATE",
        "Quality": "HIGH",
        "Use GPU": False,
    }


class RSP_RenderPassesNode(RSP_SettingsNode, bpy.types.Node):
    """Select view-layer AOV passes. Default is Combined only."""

    bl_idname = "RenderSpineNodeRenderPasses"
    bl_label = "Render Passes"
    bl_width_default = 220
    # Job first so it stays at the top (no draw_buttons — those bury inputs).
    rsp_inputs = (
        J,
        (VL, "View Layer"),
        *((B, label) for label, _rna_path, _default in _PASS_BOOL_SPECS),
        (F, "Alpha Threshold"),
        (I, "Cryptomatte Levels"),
    )
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    rsp_overrides = ()
    rsp_defaults = {
        **{label: default for label, _rna_path, default in _PASS_BOOL_SPECS},
        "Alpha Threshold": 0.5,
        "Cryptomatte Levels": 6,
    }

    def init(self, context):
        super().init(context)
        scene = context.scene if context is not None else bpy.context.scene
        if scene is not None and scene.view_layers:
            try:
                self.inputs["View Layer"].default_value = scene.view_layers[0].name
            except (TypeError, ValueError):
                pass

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        source = job.source_scene
        scene = source if isinstance(source, bpy.types.Scene) else bpy.data.scenes.get(source)
        scene = scene or bpy.context.scene
        layer_name = _resolve_pass_view_layer(
            job, context.input(self, "View Layer") or "", scene
        )
        prefix = 'view_layers["{}"].'.format(layer_name)
        values = {
            prefix + "pass_alpha_threshold": context.input(self, "Alpha Threshold"),
            prefix + "pass_cryptomatte_depth": context.input(
                self, "Cryptomatte Levels"
            ),
        }
        for label, rna_path, _default in _PASS_BOOL_SPECS:
            values[prefix + rna_path] = bool(context.input(self, label))
        return job.with_overrides(values)


class RSP_CurrentSettingsNode(RSP_SettingsNode, bpy.types.Node):
    bl_idname = "RenderSpineNodeCurrentSettings"
    bl_label = "Current Settings"
    rsp_inputs = (J,)
    rsp_outputs = (("RenderSpineNodeSocketJob", "Job"),)
    scene: PointerProperty(type=bpy.types.Scene)

    def draw_buttons(self, context, layout):
        layout.prop(self, "scene")

    def rsp_compile(self, context, socket):
        job = context.input(self, "Job", required=True)
        if not isinstance(job, JobSpec):
            raise TypeError("Job input requires JobSpec")
        scene = self.scene or bpy.context.scene
        return job.with_overrides(scene_snapshot(scene))


CLASSES = (
    RSP_RenderSettingsNode,
    RSP_CameraNode,
    RSP_WorldNode,
    RSP_ViewLayerNode,
    RSP_EngineNode,
    RSP_CyclesSamplesNode,
    RSP_EeveeSamplesNode,
    RSP_CurrentSettingsNode,
    RSP_FrameRangeNode,
    RSP_ResolutionNode,
    RSP_OutputPathNode,
    RSP_OutputFormatNode,
    RSP_FFmpegVideoNode,
    RSP_FilmNode,
    RSP_ColorManagementNode,
    RSP_SimplifyNode,
    RSP_DenoisingNode,
    RSP_RenderPassesNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

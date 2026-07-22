"""Compile deterministic render graphs and reject cycles."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

tree = bpy.data.node_groups.new("NRN Graph", "RenderSpineNodeTree")
seed = tree.nodes.new("RenderSpineNodeTaskSeed")
seed.inputs["Name"].default_value = "Beauty"
frame = tree.nodes.new("RenderSpineNodeFrameRange")
frame.inputs["Start"].default_value = 10
frame.inputs["End"].default_value = 20
frame.inputs["Step"].default_value = 2
resolution = tree.nodes.new("RenderSpineNodeResolution")
resolution.inputs["Width"].default_value = 320
resolution.inputs["Height"].default_value = 180
resolution.inputs["Percent"].default_value = 50
path = tree.nodes.new("RenderSpineNodeOutputPath")
path.inputs["Path"].default_value = "//renders/beauty_"
output = tree.nodes.new("RenderSpineNodeTaskOutput")

tree.links.new(seed.outputs["Task"], frame.inputs["Task"])
tree.links.new(frame.outputs["Task"], resolution.inputs["Task"])
tree.links.new(resolution.outputs["Task"], path.inputs["Task"])
tree.links.new(path.outputs["Task"], output.inputs["Task"])

first = tree.compile(strict=True)
second = tree.compile(strict=True)
assert_equal(first, second, "Compilation must be deterministic")
assert_equal(len(first.tasks), 1)
job = first.tasks[0]
assert_equal(job.name, "Beauty")
assert_equal(job.get_override("frame_start"), 10)
assert_equal(job.get_override("frame_end"), 20)
assert_equal(job.get_override("frame_step"), 2)
assert_equal(job.get_override("render.resolution_x"), 320)
assert_equal(job.get_override("render.resolution_y"), 180)
assert_equal(job.get_override("render.resolution_percentage"), 50)
assert_equal(job.get_override("render.filepath"), "//renders/beauty_")

bpy.data.node_groups.remove(tree)

# Unconnected Task chain is ignored (orphan warning, no overrides).
orphan_tree = bpy.data.node_groups.new("NRN Orphan Task", "RenderSpineNodeTree")
orphan_seed = orphan_tree.nodes.new("RenderSpineNodeTaskSeed")
orphan_seed.inputs["Name"].default_value = "Live"
orphan_cam = orphan_tree.nodes.new("RenderSpineNodeSetCamera")
orphan_vis = orphan_tree.nodes.new("RenderSpineNodeCollectionVisibility")
orphan_out = orphan_tree.nodes.new("RenderSpineNodeTaskOutput")
orphan_tree.links.new(orphan_seed.outputs["Task"], orphan_cam.inputs["Task"])
orphan_tree.links.new(orphan_cam.outputs["Task"], orphan_vis.inputs["Task"])
# Intentionally leave Collection Visibility unconnected from Task Output.
orphan_tree.links.new(orphan_seed.outputs["Task"], orphan_out.inputs["Task"])
orphan_result = orphan_tree.compile(strict=True)
assert_equal(len(orphan_result.tasks), 1)
assert_equal(orphan_result.tasks[0].name, "Live")
assert_equal(orphan_result.tasks[0].get_override("camera"), None)
orphan_codes = [item.code for item in orphan_result.diagnostics]
assert_equal("ORPHAN_TASK_CHAIN" in orphan_codes, True)
bpy.data.node_groups.remove(orphan_tree)

# Fat Render Task anchor works standalone.
render_job_tree = bpy.data.node_groups.new("NRN Render Task", "RenderSpineNodeTree")
extra_view_layer = bpy.context.scene.view_layers.new("RSP Not Rendered")
render_job = render_job_tree.nodes.new("RenderSpineNodeRenderTask")
render_job.inputs["Name"].default_value = "Combined"
render_job.inputs["Engine"].default_value = "CYCLES"
render_job.inputs["Samples"].default_value = 64
render_job.inputs["Frame Start"].default_value = 5
render_job.inputs["Frame End"].default_value = 15
render_job.inputs["Width"].default_value = 640
render_job.inputs["Height"].default_value = 360
render_job.inputs["Path"].default_value = "//renders/combined_"
render_job.inputs["Format"].default_value = "PNG"
render_job.inputs["Motion Blur"].default_value = True
render_job.inputs["Motion Blur Shutter"].default_value = 0.25
render_job_out = render_job_tree.nodes.new("RenderSpineNodeTaskOutput")
render_job_tree.links.new(render_job.outputs["Task"], render_job_out.inputs["Task"])
render_job_result = render_job_tree.compile(strict=True)
assert_equal(len(render_job_result.tasks), 1)
combined = render_job_result.tasks[0]
assert_equal(combined.name, "Combined")
assert_equal(combined.get_override("frame_start"), 5)
assert_equal(combined.get_override("render.filepath"), "//renders/combined_")
assert_equal(combined.get_override("render.engine"), "CYCLES")
assert_equal(combined.get_override("cycles.samples"), 64)
assert_equal(combined.get_override("eevee.taa_render_samples"), None)
assert_equal(combined.get_override("render.use_motion_blur"), True)
assert_equal(combined.get_override("render.motion_blur_shutter"), 0.25)
# Empty View Layer still pins active VL so Blender does not render every layer.
active_vl = bpy.context.view_layer.name
assert_equal(dict(combined.metadata).get("view_layer"), active_vl)
assert_equal(
    combined.get_override('view_layers["{}"].use'.format(active_vl)),
    True,
)
assert_equal(
    combined.get_override('view_layers["{}"].use'.format(extra_view_layer.name)),
    False,
)

# Optional Render Settings chain overrides samples/engine.
render_settings = render_job_tree.nodes.new("RenderSpineNodeRenderSettings")
render_settings.inputs["Engine"].default_value = "BLENDER_EEVEE"
render_settings.inputs["Samples"].default_value = 32
render_job_tree.links.clear()
render_job_tree.links.new(render_job.outputs["Task"], render_settings.inputs["Task"])
render_job_tree.links.new(render_settings.outputs["Task"], render_job_out.inputs["Task"])
override_result = render_job_tree.compile(strict=True)
overridden = override_result.tasks[0]
assert_equal(overridden.get_override("render.engine"), "BLENDER_EEVEE")
assert_equal(overridden.get_override("eevee.taa_render_samples"), 32)
assert_equal(overridden.get_override("cycles.samples"), 64)

# Output Path upstream of Render Task: blank Path on Render Task keeps template.
path_chain_tree = bpy.data.node_groups.new("NRN Path Chain", "RenderSpineNodeTree")
path_seed = path_chain_tree.nodes.new("RenderSpineNodeTaskSeed")
path_seed.inputs["Name"].default_value = "Cross_product_test"
path_node = path_chain_tree.nodes.new("RenderSpineNodeOutputPath")
path_node.save_blend_relative = False
path_node.inputs["Path"].default_value = (
    "renders/$label_color_{color}_$V.png"
)
path_render_job = path_chain_tree.nodes.new("RenderSpineNodeRenderTask")
path_out = path_chain_tree.nodes.new("RenderSpineNodeTaskOutput")
path_chain_tree.links.new(path_seed.outputs["Task"], path_node.inputs["Task"])
path_chain_tree.links.new(path_node.outputs["Task"], path_render_job.inputs["Task"])
path_chain_tree.links.new(path_render_job.outputs["Task"], path_out.inputs["Task"])
path_chain_result = path_chain_tree.compile(strict=True)
assert_equal(
    path_chain_result.tasks[0].get_override("render.filepath"),
    "renders/$label_color_{color}_$V.png",
)
bpy.data.node_groups.remove(path_chain_tree)

bpy.data.node_groups.remove(render_job_tree)
bpy.context.scene.view_layers.remove(extra_view_layer)

# Render Passes defaults to Combined only on the active view layer.
passes_tree = bpy.data.node_groups.new("NRN Passes", "RenderSpineNodeTree")
passes_seed = passes_tree.nodes.new("RenderSpineNodeTaskSeed")
passes_node = passes_tree.nodes.new("RenderSpineNodeRenderPasses")
passes_out = passes_tree.nodes.new("RenderSpineNodeTaskOutput")
passes_tree.links.new(passes_seed.outputs["Task"], passes_node.inputs["Task"])
passes_tree.links.new(passes_node.outputs["Task"], passes_out.inputs["Task"])
passes_result = passes_tree.compile(strict=True)
passes_job = passes_result.tasks[0]
layer_name = bpy.context.scene.view_layers[0].name
prefix = 'view_layers["{}"].'.format(layer_name)
assert_equal(passes_job.get_override(prefix + "use_pass_combined"), True)
assert_equal(passes_job.get_override(prefix + "use_pass_z"), False)
assert_equal(passes_job.get_override(prefix + "use_pass_normal"), False)
assert_equal(passes_job.get_override(prefix + "use_pass_diffuse_direct"), False)
assert_equal(
    passes_job.get_override(prefix + "use_pass_cryptomatte_object"), False
)
passes_node.inputs["Depth"].default_value = True
passes_node.inputs["Cryptomatte Object"].default_value = True
passes_enabled = passes_tree.compile(strict=True).tasks[0]
assert_equal(passes_enabled.get_override(prefix + "use_pass_z"), True)
assert_equal(
    passes_enabled.get_override(prefix + "use_pass_cryptomatte_object"), True
)
bpy.data.node_groups.remove(passes_tree)

# Denoising overrides Cycles sampling denoise settings.
denoise_tree = bpy.data.node_groups.new("NRN Denoise", "RenderSpineNodeTree")
denoise_seed = denoise_tree.nodes.new("RenderSpineNodeTaskSeed")
denoise_node = denoise_tree.nodes.new("RenderSpineNodeDenoising")
denoise_node.inputs["Enabled"].default_value = True
denoise_node.inputs["Denoiser"].default_value = "OPENIMAGEDENOISE"
denoise_node.inputs["Use GPU"].default_value = True
denoise_out = denoise_tree.nodes.new("RenderSpineNodeTaskOutput")
denoise_tree.links.new(denoise_seed.outputs["Task"], denoise_node.inputs["Task"])
denoise_tree.links.new(denoise_node.outputs["Task"], denoise_out.inputs["Task"])
denoise_job = denoise_tree.compile(strict=True).tasks[0]
assert_equal(denoise_job.get_override("cycles.use_denoising"), True)
assert_equal(denoise_job.get_override("cycles.denoiser"), "OPENIMAGEDENOISE")
assert_equal(
    denoise_job.get_override("cycles.denoising_input_passes"),
    "RGB_ALBEDO_NORMAL",
)
assert_equal(denoise_job.get_override("cycles.denoising_prefilter"), "ACCURATE")
assert_equal(denoise_job.get_override("cycles.denoising_quality"), "HIGH")
assert_equal(denoise_job.get_override("cycles.denoising_use_gpu"), True)
bpy.data.node_groups.remove(denoise_tree)

# String sockets auto-coerce datablocks (no To String required).
coerce_tree = bpy.data.node_groups.new("NRN Coerce String", "RenderSpineNodeTree")
collection = bpy.data.collections.new("RSP_Spot")
collection_node = coerce_tree.nodes.new("RenderSpineNodeCollectionValue")
collection_node.value = collection
prefix = coerce_tree.nodes.new("RenderSpineNodeStringValue")
prefix.value = "//render/"
suffix = coerce_tree.nodes.new("RenderSpineNodeStringValue")
suffix.value = ".png"
concat_a = coerce_tree.nodes.new("RenderSpineNodeStringOperation")
concat_a.operation = "CONCAT"
concat_b = coerce_tree.nodes.new("RenderSpineNodeStringOperation")
concat_b.operation = "CONCAT"
path_node = coerce_tree.nodes.new("RenderSpineNodeOutputPath")
seed = coerce_tree.nodes.new("RenderSpineNodeTaskSeed")
out = coerce_tree.nodes.new("RenderSpineNodeTaskOutput")
coerce_tree.links.new(prefix.outputs["Value"], concat_a.inputs["A"])
coerce_tree.links.new(collection_node.outputs["Value"], concat_a.inputs["B"])
coerce_tree.links.new(concat_a.outputs["Result"], concat_b.inputs["A"])
coerce_tree.links.new(suffix.outputs["Value"], concat_b.inputs["B"])
coerce_tree.links.new(seed.outputs["Task"], path_node.inputs["Task"])
coerce_tree.links.new(concat_b.outputs["Result"], path_node.inputs["Path"])
coerce_tree.links.new(path_node.outputs["Task"], out.inputs["Task"])
coerce_job = coerce_tree.compile(strict=True).tasks[0]
assert_equal(coerce_job.get_override("render.filepath"), "//render/RSP_Spot.png")
bpy.data.node_groups.remove(coerce_tree)
bpy.data.collections.remove(collection)

# Camera Resolution reads Nilor's per-camera values without importing Nilor.
class RSP_TestNilorFrustum(bpy.types.PropertyGroup):
    res_x: bpy.props.IntProperty(default=1920, min=1)
    res_y: bpy.props.IntProperty(default=1080, min=1)


bpy.utils.register_class(RSP_TestNilorFrustum)
bpy.types.Object.nilor_frustum = bpy.props.PointerProperty(
    type=RSP_TestNilorFrustum
)
camera_data = bpy.data.cameras.new("RSP Resolution Camera")
camera_object = bpy.data.objects.new("RSP Resolution Camera", camera_data)
bpy.context.scene.collection.objects.link(camera_object)
camera_object.nilor_frustum.res_x = 4096
camera_object.nilor_frustum.res_y = 1716

camera_res_tree = bpy.data.node_groups.new(
    "NRN Camera Resolution", "RenderSpineNodeTree"
)
camera_value = camera_res_tree.nodes.new("RenderSpineNodeObjectValue")
camera_value.value = camera_object
camera_resolution = camera_res_tree.nodes.new(
    "RenderSpineNodeCameraResolution"
)
camera_res_seed = camera_res_tree.nodes.new("RenderSpineNodeTaskSeed")
camera_res_settings = camera_res_tree.nodes.new("RenderSpineNodeResolution")
camera_res_out = camera_res_tree.nodes.new("RenderSpineNodeTaskOutput")
camera_res_tree.links.new(
    camera_value.outputs["Value"], camera_resolution.inputs["Camera"]
)
camera_res_tree.links.new(
    camera_resolution.outputs["Width"], camera_res_settings.inputs["Width"]
)
camera_res_tree.links.new(
    camera_resolution.outputs["Height"], camera_res_settings.inputs["Height"]
)
camera_res_tree.links.new(
    camera_res_seed.outputs["Task"], camera_res_settings.inputs["Task"]
)
camera_res_tree.links.new(
    camera_res_settings.outputs["Task"], camera_res_out.inputs["Task"]
)
camera_res_job = camera_res_tree.compile(strict=True).tasks[0]
assert_equal(camera_res_job.get_override("render.resolution_x"), 4096)
assert_equal(camera_res_job.get_override("render.resolution_y"), 1716)

bpy.data.node_groups.remove(camera_res_tree)
bpy.data.objects.remove(camera_object)
bpy.data.cameras.remove(camera_data)
del bpy.types.Object.nilor_frustum
bpy.utils.unregister_class(RSP_TestNilorFrustum)

# Collection Visibility: Enabled/Holdout on LayerCollection + Collection hides.
vis_collection = bpy.data.collections.new("RSP_VisCol")
bpy.context.scene.collection.children.link(vis_collection)
vis_tree = bpy.data.node_groups.new("NRN Collection Vis", "RenderSpineNodeTree")
vis_seed = vis_tree.nodes.new("RenderSpineNodeTaskSeed")
vis_col = vis_tree.nodes.new("RenderSpineNodeCollectionValue")
vis_col.value = vis_collection
vis_node = vis_tree.nodes.new("RenderSpineNodeCollectionVisibility")
vis_node.inputs["Enabled"].default_value = False
vis_node.inputs["Holdout"].default_value = True
vis_node.inputs["Viewport"].default_value = True
vis_node.inputs["Render"].default_value = False
vis_out = vis_tree.nodes.new("RenderSpineNodeTaskOutput")
vis_tree.links.new(vis_seed.outputs["Task"], vis_node.inputs["Task"])
vis_tree.links.new(vis_col.outputs["Value"], vis_node.inputs["Collection"])
vis_tree.links.new(vis_node.outputs["Task"], vis_out.inputs["Task"])
vis_job = vis_tree.compile(strict=True).tasks[0]
layer_name = bpy.context.scene.view_layers[0].name
layer_prefix = 'view_layers["{}"].layer_collection.children["{}"]'.format(
    layer_name, vis_collection.name
)
assert_equal(vis_job.get_override(layer_prefix + ".exclude"), True)
assert_equal(vis_job.get_override(layer_prefix + ".holdout"), True)
assert_equal(vis_job.get_override("hide_viewport"), False)
assert_equal(vis_job.get_override("hide_render"), True)
from render_spine.nodes.tasks import _apply_view_layer

retarget_layer = bpy.context.scene.view_layers.new("RSP_Retarget")
retargeted_job = _apply_view_layer(vis_job, retarget_layer.name)
retarget_prefix = 'view_layers["{}"].layer_collection.children["{}"]'.format(
    retarget_layer.name, vis_collection.name
)
assert_equal(retargeted_job.get_override(layer_prefix + ".exclude"), None)
assert_equal(retargeted_job.get_override(retarget_prefix + ".exclude"), True)
assert_equal(retargeted_job.get_override("scene.view_layer"), retarget_layer.name)
bpy.context.scene.view_layers.remove(retarget_layer)
bpy.data.node_groups.remove(vis_tree)
bpy.data.collections.remove(vis_collection)

# Collection List → Collection Visibility expands tasks + {collection} paths.
col_a = bpy.data.collections.new("RSP_Spot")
col_b = bpy.data.collections.new("RSP_Sun")
bpy.context.scene.collection.children.link(col_a)
bpy.context.scene.collection.children.link(col_b)
list_tree = bpy.data.node_groups.new("NRN Collection List Vis", "RenderSpineNodeTree")
list_seed = list_tree.nodes.new("RenderSpineNodeTaskSeed")
list_seed.inputs["Name"].default_value = "Cross_product_test"
col_list = list_tree.nodes.new("RenderSpineNodeCollectionList")
col_list.items.add()
col_list.items[0].value = col_a
col_list.items.add()
col_list.items[1].value = col_b
vis_node = list_tree.nodes.new("RenderSpineNodeCollectionVisibility")
path_node = list_tree.nodes.new("RenderSpineNodeOutputPath")
path_node.inputs["Path"].default_value = (
    "//renders/{name}_{collection}.png"
)
list_out = list_tree.nodes.new("RenderSpineNodeTaskOutput")
list_tree.links.new(list_seed.outputs["Task"], vis_node.inputs["Task"])
list_tree.links.new(col_list.outputs["Values"], vis_node.inputs["Collection"])
list_tree.links.new(vis_node.outputs["Task"], path_node.inputs["Task"])
list_tree.links.new(path_node.outputs["Task"], list_out.inputs["Task"])
list_result = list_tree.compile(strict=True)
assert_equal(len(list_result.tasks), 2)
assert_equal(
    list_result.tasks[0].get_override("render.filepath"),
    "//renders/{name}_{collection}.png",
)
meta0 = dict(list_result.tasks[0].metadata)
assert_equal(meta0.get("collection"), "RSP_Spot")
meta1 = dict(list_result.tasks[1].metadata)
assert_equal(meta1.get("collection"), "RSP_Sun")
from render_spine.execution.path_expand import expand_task_filepath

assert_equal(
    expand_task_filepath(
        list_result.tasks[0].get_override("render.filepath"),
        list_result.tasks[0],
        bpy.context.scene,
    ),
    "//renders/Cross_product_test_000_RSP_Spot.png",
)
from render_spine.execution.transaction import Transaction

layer_root = bpy.context.scene.view_layers[0].layer_collection
layer_a = layer_root.children[col_a.name]
layer_b = layer_root.children[col_b.name]
layer_a.exclude = True
layer_b.exclude = True
visibility_transaction = Transaction("Collection list visibility")
visibility_transaction.apply(list_result.tasks[0].overrides, bpy.context, bpy)
assert_equal(layer_a.exclude, False)
assert_equal(layer_b.exclude, True)
visibility_transaction.restore()

# Pending collection bundles must retarget when View Layer is chosen later.
retarget_layer = bpy.context.scene.view_layers.new("RSP_ColRetarget")
from render_spine.core.compiler import CompileContext
from render_spine.core.variants import expand_pending_axes

compile_ctx = CompileContext(list_tree)
vis_only = compile_ctx.output(vis_node)
assert_equal(len(vis_only.axes), 1)
retargeted = _apply_view_layer(vis_only, retarget_layer.name)
expanded = expand_pending_axes(retargeted)
sun_job = expanded.tasks[1]
sun_paths = [
    item.path
    for item in sun_job.overrides
    if item.path.endswith(".exclude")
]
assert_equal(
    sun_paths,
    [
        'view_layers["{}"].layer_collection.children["{}"].exclude'.format(
            retarget_layer.name, col_b.name
        )
    ],
)
bpy.context.scene.view_layers.remove(retarget_layer)
bpy.data.node_groups.remove(list_tree)
bpy.data.collections.remove(col_a)
bpy.data.collections.remove(col_b)

# FFmpeg Video defaults: H.264 MP4 medium CRF proxy profile.
ffmpeg_tree = bpy.data.node_groups.new("NRN FFmpeg", "RenderSpineNodeTree")
ffmpeg_seed = ffmpeg_tree.nodes.new("RenderSpineNodeTaskSeed")
ffmpeg_node = ffmpeg_tree.nodes.new("RenderSpineNodeFFmpegVideo")
ffmpeg_out = ffmpeg_tree.nodes.new("RenderSpineNodeTaskOutput")
ffmpeg_tree.links.new(ffmpeg_seed.outputs["Task"], ffmpeg_node.inputs["Task"])
ffmpeg_tree.links.new(ffmpeg_node.outputs["Task"], ffmpeg_out.inputs["Task"])
ffmpeg_job = ffmpeg_tree.compile(strict=True).tasks[0]
assert_equal(ffmpeg_job.get_override("render.save_output"), True)
assert_equal(ffmpeg_job.get_override("render.image_settings.file_format"), "FFMPEG")
assert_equal(ffmpeg_job.get_override("render.ffmpeg.format"), "MPEG4")
assert_equal(ffmpeg_job.get_override("render.ffmpeg.codec"), "H264")
assert_equal(ffmpeg_job.get_override("render.ffmpeg.constant_rate_factor"), "MEDIUM")
assert_equal(ffmpeg_job.get_override("render.ffmpeg.ffmpeg_preset"), "GOOD")
assert_equal(ffmpeg_job.get_override("render.ffmpeg.audio_codec"), "AAC")
assert_equal(ffmpeg_job.get_override("render.ffmpeg.audio_bitrate"), 128)
assert_equal(ffmpeg_job.get_override("render.ffmpeg.audio_channels"), "STEREO")
bpy.data.node_groups.remove(ffmpeg_tree)

group_tree = bpy.data.node_groups.new("NRN Group Definition", "RenderSpineNodeTree")
group_seed = group_tree.nodes.new("RenderSpineNodeTaskSeed")
group_frame = group_tree.nodes.new("RenderSpineNodeFrameRange")
group_frame.inputs["Start"].default_value = 3
group_frame.inputs["End"].default_value = 7
group_output = group_tree.nodes.new("RenderSpineNodeTaskOutput")
group_tree.links.new(group_seed.outputs["Task"], group_frame.inputs["Task"])
group_tree.links.new(group_frame.outputs["Task"], group_output.inputs["Task"])

outer_tree = bpy.data.node_groups.new("NRN Group Use", "RenderSpineNodeTree")
outer_seed = outer_tree.nodes.new("RenderSpineNodeTaskSeed")
outer_seed.inputs["Name"].default_value = "Grouped"
group_node = outer_tree.nodes.new("RenderSpineNodeJobGroup")
group_node.group_tree = group_tree
outer_output = outer_tree.nodes.new("RenderSpineNodeTaskOutput")
outer_tree.links.new(outer_seed.outputs["Task"], group_node.inputs["Task"])
outer_tree.links.new(group_node.outputs["Task"], outer_output.inputs["Task"])

group_result = outer_tree.compile(strict=True)
assert_equal(group_result.tasks[0].name, "Grouped")
assert_equal(group_result.tasks[0].get_override("frame_start"), 3)
assert_equal(group_result.tasks[0].get_override("frame_end"), 7)

bpy.data.node_groups.remove(outer_tree)
bpy.data.node_groups.remove(group_tree)

cycle_tree = bpy.data.node_groups.new("NRN Cycle", "RenderSpineNodeTree")
left = cycle_tree.nodes.new("RenderSpineNodeFrameRange")
right = cycle_tree.nodes.new("RenderSpineNodeResolution")
cycle_output = cycle_tree.nodes.new("RenderSpineNodeTaskOutput")
cycle_tree.links.new(left.outputs["Task"], right.inputs["Task"])
cycle_tree.links.new(right.outputs["Task"], left.inputs["Task"])
cycle_tree.links.new(right.outputs["Task"], cycle_output.inputs["Task"])

cycle_result = cycle_tree.compile(strict=False)
codes = {item.code for item in cycle_result.diagnostics}
if "CYCLE" not in codes:
    raise AssertionError("Cycle diagnostic missing: {}".format(codes))

bpy.data.node_groups.remove(cycle_tree)

# Render Variants: 2 intensities x 4 colors → 8 jobs on one light.
variant_tree = bpy.data.node_groups.new("NRN Variants", "RenderSpineNodeTree")
variant_seed = variant_tree.nodes.new("RenderSpineNodeTaskSeed")
variant_seed.inputs["Name"].default_value = "LightSweep"
variant_path = variant_tree.nodes.new("RenderSpineNodeOutputPath")
variant_path.inputs["Path"].default_value = (
    "//renders/{name}_{variant_index}_{intensity}.png"
)
intensity_list = variant_tree.nodes.new("RenderSpineNodeFloatList")
intensity_list.items.add()
intensity_list.items.add()
intensity_list.items[0].value = 1.0
intensity_list.items[1].value = 10.0
color_list = variant_tree.nodes.new("RenderSpineNodeColorList")
for rgb in (
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (1.0, 1.0, 0.0),
):
    item = color_list.items.add()
    item.value = rgb
light_data = bpy.data.lights.new("NRN Variant Light", "AREA")
light_obj = bpy.data.objects.new("NRN Variant Light", light_data)
bpy.context.scene.collection.objects.link(light_obj)
axis_intensity = variant_tree.nodes.new("RenderSpineNodeVariantAxis")
axis_intensity.mode = "OBJECT"
axis_intensity.setting = "ENERGY"
axis_intensity.inputs["Object"].default_value = light_obj
axis_color = variant_tree.nodes.new("RenderSpineNodeVariantAxis")
axis_color.mode = "OBJECT"
axis_color.setting = "COLOR"
axis_color.inputs["Object"].default_value = light_obj
cross = variant_tree.nodes.new("RenderSpineNodeRenderVariants")
list_out = variant_tree.nodes.new("RenderSpineNodeTaskListOutput")
variant_tree.links.new(variant_seed.outputs["Task"], variant_path.inputs["Task"])
variant_tree.links.new(variant_path.outputs["Task"], cross.inputs["Task"])
variant_tree.links.new(
    intensity_list.outputs["Values"], axis_intensity.inputs["Values"]
)
variant_tree.links.new(color_list.outputs["Values"], axis_color.inputs["Values"])
variant_tree.links.new(axis_intensity.outputs["Axis"], cross.inputs["Axis 1"])
variant_tree.links.new(axis_color.outputs["Axis"], cross.inputs["Axis 2"])
variant_tree.links.new(cross.outputs["Tasks"], list_out.inputs["Tasks"])
variant_result = variant_tree.compile(strict=True)
assert_equal(len(variant_result.tasks), 8)
assert_equal(variant_result.tasks[0].name, "LightSweep_000")
assert_equal(variant_result.tasks[0].get_override("data.energy"), 1.0)
assert_equal(
    variant_result.tasks[0].get_override("data.color"), (1.0, 0.0, 0.0)
)
assert_equal(variant_result.tasks[4].get_override("data.energy"), 10.0)
assert_equal(
    variant_result.tasks[7].get_override("data.color"), (1.0, 1.0, 0.0)
)
assert_equal(
    variant_result.tasks[0].get_override("render.filepath"),
    "//renders/{name}_{variant_index}_{intensity}.png",
)
meta = dict(variant_result.tasks[0].metadata)
assert_equal(meta["variant_index"], 0)
bpy.data.node_groups.remove(variant_tree)
bpy.data.objects.remove(light_obj)
bpy.data.lights.remove(light_data)

# Deferred list→axis: Color List into Light Settings Color (no Variant Axis node).
smart_tree = bpy.data.node_groups.new("NRN Smart List", "RenderSpineNodeTree")
smart_seed = smart_tree.nodes.new("RenderSpineNodeTaskSeed")
smart_seed.inputs["Name"].default_value = "AreaColors"
smart_light_data = bpy.data.lights.new("NRN Smart Light", "AREA")
smart_light = bpy.data.objects.new("NRN Smart Light", smart_light_data)
bpy.context.scene.collection.objects.link(smart_light)
smart_colors = smart_tree.nodes.new("RenderSpineNodeColorList")
for rgb in ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
    item = smart_colors.items.add()
    item.value = rgb
smart_light_node = smart_tree.nodes.new("RenderSpineNodeLightSettings")
smart_light_node.inputs["Object"].default_value = smart_light
smart_light_node.inputs["Intensity"].default_value = 1000.0
smart_out = smart_tree.nodes.new("RenderSpineNodeTaskOutput")
smart_tree.links.new(smart_seed.outputs["Task"], smart_light_node.inputs["Task"])
smart_tree.links.new(
    smart_colors.outputs["Values"], smart_light_node.inputs["Color"]
)
smart_tree.links.new(smart_light_node.outputs["Task"], smart_out.inputs["Task"])
smart_result = smart_tree.compile(strict=True)
assert_equal(len(smart_result.tasks), 3)
assert_equal(smart_result.tasks[0].name, "AreaColors_000")
assert_equal(
    smart_result.tasks[0].get_override("data.color"), (0.0, 0.0, 1.0)
)
assert_equal(smart_result.tasks[0].get_override("data.energy"), 1000.0)
assert_equal(
    smart_result.tasks[1].get_override("data.color"), (1.0, 0.0, 0.0)
)
assert_equal(
    smart_result.tasks[2].get_override("data.color"), (0.0, 1.0, 0.0)
)
bpy.data.node_groups.remove(smart_tree)
bpy.data.objects.remove(smart_light)
bpy.data.lights.remove(smart_light_data)

extension.unregister()
finish("graph")

"""Compile deterministic render graphs and reject cycles."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

tree = bpy.data.node_groups.new("NRN Graph", "RenderSpineNodeTree")
seed = tree.nodes.new("RenderSpineNodeJobSeed")
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
output = tree.nodes.new("RenderSpineNodeJobOutput")

tree.links.new(seed.outputs["Job"], frame.inputs["Job"])
tree.links.new(frame.outputs["Job"], resolution.inputs["Job"])
tree.links.new(resolution.outputs["Job"], path.inputs["Job"])
tree.links.new(path.outputs["Job"], output.inputs["Job"])

first = tree.compile(strict=True)
second = tree.compile(strict=True)
assert_equal(first, second, "Compilation must be deterministic")
assert_equal(len(first.jobs), 1)
job = first.jobs[0]
assert_equal(job.name, "Beauty")
assert_equal(job.get_override("frame_start"), 10)
assert_equal(job.get_override("frame_end"), 20)
assert_equal(job.get_override("frame_step"), 2)
assert_equal(job.get_override("render.resolution_x"), 320)
assert_equal(job.get_override("render.resolution_y"), 180)
assert_equal(job.get_override("render.resolution_percentage"), 50)
assert_equal(job.get_override("render.filepath"), "//renders/beauty_")

bpy.data.node_groups.remove(tree)

# Fat Render Job anchor works standalone.
render_job_tree = bpy.data.node_groups.new("NRN Render Job", "RenderSpineNodeTree")
render_job = render_job_tree.nodes.new("RenderSpineNodeRenderJob")
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
render_job_out = render_job_tree.nodes.new("RenderSpineNodeJobOutput")
render_job_tree.links.new(render_job.outputs["Job"], render_job_out.inputs["Job"])
render_job_result = render_job_tree.compile(strict=True)
assert_equal(len(render_job_result.jobs), 1)
combined = render_job_result.jobs[0]
assert_equal(combined.name, "Combined")
assert_equal(combined.get_override("frame_start"), 5)
assert_equal(combined.get_override("render.filepath"), "//renders/combined_")
assert_equal(combined.get_override("render.engine"), "CYCLES")
assert_equal(combined.get_override("cycles.samples"), 64)
assert_equal(combined.get_override("eevee.taa_render_samples"), None)
assert_equal(combined.get_override("render.use_motion_blur"), True)
assert_equal(combined.get_override("render.motion_blur_shutter"), 0.25)

# Optional Render Settings chain overrides samples/engine.
render_settings = render_job_tree.nodes.new("RenderSpineNodeRenderSettings")
render_settings.inputs["Engine"].default_value = "BLENDER_EEVEE"
render_settings.inputs["Samples"].default_value = 32
render_job_tree.links.clear()
render_job_tree.links.new(render_job.outputs["Job"], render_settings.inputs["Job"])
render_job_tree.links.new(render_settings.outputs["Job"], render_job_out.inputs["Job"])
override_result = render_job_tree.compile(strict=True)
overridden = override_result.jobs[0]
assert_equal(overridden.get_override("render.engine"), "BLENDER_EEVEE")
assert_equal(overridden.get_override("eevee.taa_render_samples"), 32)
assert_equal(overridden.get_override("cycles.samples"), 64)
bpy.data.node_groups.remove(render_job_tree)

# Render Passes defaults to Combined only on the active view layer.
passes_tree = bpy.data.node_groups.new("NRN Passes", "RenderSpineNodeTree")
passes_seed = passes_tree.nodes.new("RenderSpineNodeJobSeed")
passes_node = passes_tree.nodes.new("RenderSpineNodeRenderPasses")
passes_out = passes_tree.nodes.new("RenderSpineNodeJobOutput")
passes_tree.links.new(passes_seed.outputs["Job"], passes_node.inputs["Job"])
passes_tree.links.new(passes_node.outputs["Job"], passes_out.inputs["Job"])
passes_result = passes_tree.compile(strict=True)
passes_job = passes_result.jobs[0]
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
passes_enabled = passes_tree.compile(strict=True).jobs[0]
assert_equal(passes_enabled.get_override(prefix + "use_pass_z"), True)
assert_equal(
    passes_enabled.get_override(prefix + "use_pass_cryptomatte_object"), True
)
bpy.data.node_groups.remove(passes_tree)

# Denoising overrides Cycles sampling denoise settings.
denoise_tree = bpy.data.node_groups.new("NRN Denoise", "RenderSpineNodeTree")
denoise_seed = denoise_tree.nodes.new("RenderSpineNodeJobSeed")
denoise_node = denoise_tree.nodes.new("RenderSpineNodeDenoising")
denoise_node.inputs["Enabled"].default_value = True
denoise_node.inputs["Denoiser"].default_value = "OPENIMAGEDENOISE"
denoise_node.inputs["Use GPU"].default_value = True
denoise_out = denoise_tree.nodes.new("RenderSpineNodeJobOutput")
denoise_tree.links.new(denoise_seed.outputs["Job"], denoise_node.inputs["Job"])
denoise_tree.links.new(denoise_node.outputs["Job"], denoise_out.inputs["Job"])
denoise_job = denoise_tree.compile(strict=True).jobs[0]
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
seed = coerce_tree.nodes.new("RenderSpineNodeJobSeed")
out = coerce_tree.nodes.new("RenderSpineNodeJobOutput")
coerce_tree.links.new(prefix.outputs["Value"], concat_a.inputs["A"])
coerce_tree.links.new(collection_node.outputs["Value"], concat_a.inputs["B"])
coerce_tree.links.new(concat_a.outputs["Result"], concat_b.inputs["A"])
coerce_tree.links.new(suffix.outputs["Value"], concat_b.inputs["B"])
coerce_tree.links.new(seed.outputs["Job"], path_node.inputs["Job"])
coerce_tree.links.new(concat_b.outputs["Result"], path_node.inputs["Path"])
coerce_tree.links.new(path_node.outputs["Job"], out.inputs["Job"])
coerce_job = coerce_tree.compile(strict=True).jobs[0]
assert_equal(coerce_job.get_override("render.filepath"), "//render/RSP_Spot.png")
bpy.data.node_groups.remove(coerce_tree)
bpy.data.collections.remove(collection)

# Collection Visibility: Enabled/Holdout on LayerCollection + Collection hides.
vis_collection = bpy.data.collections.new("RSP_VisCol")
bpy.context.scene.collection.children.link(vis_collection)
vis_tree = bpy.data.node_groups.new("NRN Collection Vis", "RenderSpineNodeTree")
vis_seed = vis_tree.nodes.new("RenderSpineNodeJobSeed")
vis_col = vis_tree.nodes.new("RenderSpineNodeCollectionValue")
vis_col.value = vis_collection
vis_node = vis_tree.nodes.new("RenderSpineNodeCollectionVisibility")
vis_node.inputs["Enabled"].default_value = False
vis_node.inputs["Holdout"].default_value = True
vis_node.inputs["Viewport"].default_value = True
vis_node.inputs["Render"].default_value = False
vis_out = vis_tree.nodes.new("RenderSpineNodeJobOutput")
vis_tree.links.new(vis_seed.outputs["Job"], vis_node.inputs["Job"])
vis_tree.links.new(vis_col.outputs["Value"], vis_node.inputs["Collection"])
vis_tree.links.new(vis_node.outputs["Job"], vis_out.inputs["Job"])
vis_job = vis_tree.compile(strict=True).jobs[0]
layer_name = bpy.context.scene.view_layers[0].name
layer_prefix = 'view_layers["{}"].layer_collection.children["{}"]'.format(
    layer_name, vis_collection.name
)
assert_equal(vis_job.get_override(layer_prefix + ".exclude"), True)
assert_equal(vis_job.get_override(layer_prefix + ".holdout"), True)
assert_equal(vis_job.get_override("hide_viewport"), False)
assert_equal(vis_job.get_override("hide_render"), True)
bpy.data.node_groups.remove(vis_tree)
bpy.data.collections.remove(vis_collection)

# FFmpeg Video defaults: H.264 MP4 medium CRF proxy profile.
ffmpeg_tree = bpy.data.node_groups.new("NRN FFmpeg", "RenderSpineNodeTree")
ffmpeg_seed = ffmpeg_tree.nodes.new("RenderSpineNodeJobSeed")
ffmpeg_node = ffmpeg_tree.nodes.new("RenderSpineNodeFFmpegVideo")
ffmpeg_out = ffmpeg_tree.nodes.new("RenderSpineNodeJobOutput")
ffmpeg_tree.links.new(ffmpeg_seed.outputs["Job"], ffmpeg_node.inputs["Job"])
ffmpeg_tree.links.new(ffmpeg_node.outputs["Job"], ffmpeg_out.inputs["Job"])
ffmpeg_job = ffmpeg_tree.compile(strict=True).jobs[0]
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
group_seed = group_tree.nodes.new("RenderSpineNodeJobSeed")
group_frame = group_tree.nodes.new("RenderSpineNodeFrameRange")
group_frame.inputs["Start"].default_value = 3
group_frame.inputs["End"].default_value = 7
group_output = group_tree.nodes.new("RenderSpineNodeJobOutput")
group_tree.links.new(group_seed.outputs["Job"], group_frame.inputs["Job"])
group_tree.links.new(group_frame.outputs["Job"], group_output.inputs["Job"])

outer_tree = bpy.data.node_groups.new("NRN Group Use", "RenderSpineNodeTree")
outer_seed = outer_tree.nodes.new("RenderSpineNodeJobSeed")
outer_seed.inputs["Name"].default_value = "Grouped"
group_node = outer_tree.nodes.new("RenderSpineNodeJobGroup")
group_node.group_tree = group_tree
outer_output = outer_tree.nodes.new("RenderSpineNodeJobOutput")
outer_tree.links.new(outer_seed.outputs["Job"], group_node.inputs["Job"])
outer_tree.links.new(group_node.outputs["Job"], outer_output.inputs["Job"])

group_result = outer_tree.compile(strict=True)
assert_equal(group_result.jobs[0].name, "Grouped")
assert_equal(group_result.jobs[0].get_override("frame_start"), 3)
assert_equal(group_result.jobs[0].get_override("frame_end"), 7)

bpy.data.node_groups.remove(outer_tree)
bpy.data.node_groups.remove(group_tree)

cycle_tree = bpy.data.node_groups.new("NRN Cycle", "RenderSpineNodeTree")
left = cycle_tree.nodes.new("RenderSpineNodeFrameRange")
right = cycle_tree.nodes.new("RenderSpineNodeResolution")
cycle_output = cycle_tree.nodes.new("RenderSpineNodeJobOutput")
cycle_tree.links.new(left.outputs["Job"], right.inputs["Job"])
cycle_tree.links.new(right.outputs["Job"], left.inputs["Job"])
cycle_tree.links.new(right.outputs["Job"], cycle_output.inputs["Job"])

cycle_result = cycle_tree.compile(strict=False)
codes = {item.code for item in cycle_result.diagnostics}
if "CYCLE" not in codes:
    raise AssertionError("Cycle diagnostic missing: {}".format(codes))

bpy.data.node_groups.remove(cycle_tree)
extension.unregister()
finish("graph")

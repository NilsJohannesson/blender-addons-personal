"""Render a tiny still from a compiled-style job and restore scene state."""

import os
import shutil
import sys
import tempfile

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import JobSpec
from render_spine.execution.transaction import Transaction


scene = bpy.context.scene
camera_data = bpy.data.cameras.new("NRN Smoke Camera")
camera = bpy.data.objects.new("NRN Smoke Camera", camera_data)
scene.collection.objects.link(camera)

old_camera = scene.camera
old_x = scene.render.resolution_x
old_y = scene.render.resolution_y
old_percent = scene.render.resolution_percentage
old_path = scene.render.filepath
old_format = scene.render.image_settings.file_format
old_media = getattr(scene.render.image_settings, "media_type", None)

# Blender 5.2 gates file_format by media_type; multilayer must round-trip to PNG.
if hasattr(scene.render.image_settings, "media_type"):
    scene.render.image_settings.media_type = "MULTI_LAYER_IMAGE"
    scene.render.image_settings.file_format = "OPEN_EXR_MULTILAYER"

baseline_format = scene.render.image_settings.file_format
baseline_media = getattr(scene.render.image_settings, "media_type", None)

temp_dir = tempfile.mkdtemp(prefix="render_spine_")
output_path = os.path.join(temp_dir, "smoke.png")
job = (
    JobSpec(name="Smoke")
    .with_override("camera", camera)
    .with_override("render.resolution_x", 8)
    .with_override("render.resolution_y", 8)
    .with_override("render.resolution_percentage", 100)
    .with_override("render.filepath", output_path)
    .with_override("render.image_settings.file_format", "PNG")
)

transaction = Transaction("Smoke")
try:
    transaction.apply(job.overrides, bpy.context, bpy)
    assert_equal(scene.render.image_settings.file_format, "PNG")
    if baseline_media is not None:
        assert_equal(scene.render.image_settings.media_type, "IMAGE")
    result = bpy.ops.render.render(write_still=True)
    if "FINISHED" not in result:
        raise AssertionError("Render failed: {}".format(result))
    if not os.path.exists(output_path):
        raise AssertionError("Render output missing: {}".format(output_path))
finally:
    error = transaction.restore()
    if error:
        raise AssertionError("Restore failed: {}".format(error))

assert_equal(scene.camera, old_camera)
assert_equal(scene.render.resolution_x, old_x)
assert_equal(scene.render.resolution_y, old_y)
assert_equal(scene.render.resolution_percentage, old_percent)
assert_equal(scene.render.filepath, old_path)
assert_equal(scene.render.image_settings.file_format, baseline_format)
if baseline_media is not None:
    assert_equal(scene.render.image_settings.media_type, baseline_media)

# Leave factory defaults for later cleanup consistency.
if old_media is not None:
    scene.render.image_settings.media_type = old_media
scene.render.image_settings.file_format = old_format

bpy.data.objects.remove(camera)
bpy.data.cameras.remove(camera_data)
shutil.rmtree(temp_dir)
extension.unregister()
finish("render_smoke")

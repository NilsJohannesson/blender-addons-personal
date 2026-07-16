"""Round-trip scene and datablock changes through one transaction."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()
extension.register()

from render_spine.core.model import TaskSpec
from render_spine.execution.transaction import Transaction, TransactionError


scene = bpy.context.scene
mesh = bpy.data.meshes.new("NRN Mesh")
obj = bpy.data.objects.new("NRN Object", mesh)
scene.collection.objects.link(obj)
material = bpy.data.materials.new("NRN Material")
collection = bpy.data.collections.new("NRN Collection")
scene.collection.children.link(collection)
action = bpy.data.actions.new("NRN Action")

original_frame = scene.frame_start
original_resolution = scene.render.resolution_x
original_location = tuple(obj.location)
original_material = obj.active_material
original_collection_render = collection.hide_render
view_layer = scene.view_layers[0]
layer_collection = view_layer.layer_collection.children[collection.name]
original_exclude = layer_collection.exclude
original_holdout = layer_collection.holdout
assert_equal(obj.animation_data, None)

layer_prefix = 'view_layers["{}"].layer_collection.children["{}"]'.format(
    view_layer.name, collection.name
)
job = (
    TaskSpec(name="Transaction")
    .with_override("frame_start", 17)
    .with_override("render.resolution_x", 321)
    .with_override(
        "location",
        (1.0, 2.0, 3.0),
        target_type="objects",
        target_name=obj.name,
    )
    .with_override(
        "active_material",
        material,
        target_type="objects",
        target_name=obj.name,
    )
    .with_override(
        "animation_data.action",
        action,
        target_type="objects",
        target_name=obj.name,
    )
    .with_override(
        "hide_render",
        True,
        target_type="collections",
        target_name=collection.name,
    )
    .with_override(layer_prefix + ".exclude", True)
    .with_override(layer_prefix + ".holdout", True)
)

transaction = Transaction("Round trip")
transaction.apply(job.overrides, bpy.context, bpy)
assert_equal(scene.frame_start, 17)
assert_equal(scene.render.resolution_x, 321)
assert_equal(tuple(obj.location), (1.0, 2.0, 3.0))
assert_equal(obj.active_material, material)
assert_equal(obj.animation_data.action, action)
assert_equal(collection.hide_render, True)
assert_equal(layer_collection.exclude, True)
assert_equal(layer_collection.holdout, True)

error = transaction.restore()
assert_equal(error, "")
assert_equal(scene.frame_start, original_frame)
assert_equal(scene.render.resolution_x, original_resolution)
assert_equal(tuple(obj.location), original_location)
assert_equal(obj.active_material, original_material)
assert_equal(obj.animation_data, None)
assert_equal(collection.hide_render, original_collection_render)
assert_equal(layer_collection.exclude, original_exclude)
assert_equal(layer_collection.holdout, original_holdout)

invalid = TaskSpec().with_override("_unsafe", True)
failed = False
try:
    Transaction("Invalid").apply(invalid.overrides, bpy.context, bpy)
except TransactionError:
    failed = True
if not failed:
    raise AssertionError("Unsafe path was accepted")
assert_equal(scene.frame_start, original_frame)

light_data = bpy.data.lights.new("NRN Light", "AREA")
light_obj = bpy.data.objects.new("NRN Light", light_data)
scene.collection.objects.link(light_obj)
original_energy = light_data.energy
original_color = tuple(light_data.color)
original_spread = float(light_data.spread)
light_job = (
    TaskSpec(name="Light")
    .with_override(
        "data.energy",
        42.5,
        target_type="objects",
        target_name=light_obj.name,
    )
    .with_override(
        "data.color",
        (0.25, 0.5, 0.75),
        target_type="objects",
        target_name=light_obj.name,
    )
    .with_override(
        "data.spread",
        1.25,
        target_type="objects",
        target_name=light_obj.name,
    )
)
light_tx = Transaction("Light settings")
light_tx.apply(light_job.overrides, bpy.context, bpy)
assert_equal(light_data.energy, 42.5)
assert_equal(tuple(round(c, 5) for c in light_data.color), (0.25, 0.5, 0.75))
assert_equal(round(light_data.spread, 5), 1.25)
assert_equal(light_tx.restore(), "")
assert_equal(light_data.energy, original_energy)
assert_equal(tuple(light_data.color), original_color)
assert_equal(float(light_data.spread), original_spread)

bpy.data.objects.remove(light_obj)
bpy.data.lights.remove(light_data)
bpy.data.actions.remove(action)
bpy.data.collections.remove(collection)
bpy.data.objects.remove(obj)
bpy.data.meshes.remove(mesh)
bpy.data.materials.remove(material)
extension.unregister()
finish("transaction")

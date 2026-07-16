"""Register extension and instantiate every production node."""

import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(__file__))
from common import assert_equal, finish, load_extension


extension = load_extension()

for cycle in range(2):
    extension.register()

    from render_spine import nodes, sockets

    tree = bpy.data.node_groups.new(
        "NRN Registration {}".format(cycle),
        "RenderSpineNodeTree",
    )
    for cls in nodes.NODE_CLASSES:
        node = tree.nodes.new(cls.bl_idname)
        assert_equal(node.bl_idname, cls.bl_idname)

    socket_ids = {cls.bl_idname for cls in sockets.SOCKET_CLASSES}
    instantiated_socket_ids = {
        socket.bl_idname
        for node in tree.nodes
        for socket in tuple(node.inputs) + tuple(node.outputs)
    }
    missing = socket_ids - instantiated_socket_ids
    if missing:
        raise AssertionError("Sockets not exercised by production nodes: {}".format(missing))

    bpy.data.node_groups.remove(tree)
    extension.unregister()

finish("registration")

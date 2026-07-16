"""RenderSpine Blender extension."""

from . import sockets
from . import tree
from . import nodes
from . import state
from . import execution
from . import operators
from . import ui


_submodules = (
    sockets,
    tree,
    nodes,
    state,
    execution,
    operators,
    ui,
)


def register():
    """Register extension modules in dependency order."""
    for module in _submodules:
        module.register()


def unregister():
    """Unregister extension modules in reverse dependency order."""
    for module in reversed(_submodules):
        module.unregister()

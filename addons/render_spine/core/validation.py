"""Structural graph validation independent of evaluation order."""

from .model import Diagnostic


_TASK_FAMILIES = frozenset(("JOB", "JOB_LIST"))


def socket_family(socket):
    return getattr(socket, "rsp_family", getattr(socket, "bl_idname", ""))


def _is_task_family(socket):
    return socket_family(socket) in _TASK_FAMILIES


def _orphan_task_chain_diagnostics(tree):
    """Warn when a Task chain has no path to Task Output (ignored at compile)."""
    diagnostics = []
    for node in sorted(tree.nodes, key=lambda item: item.name):
        if getattr(node, "mute", False):
            continue
        if getattr(node, "rsp_is_task_output", False):
            continue
        task_outputs = [socket for socket in node.outputs if _is_task_family(socket)]
        if not task_outputs:
            continue
        if any(socket.is_linked for socket in task_outputs):
            continue
        task_inputs = [socket for socket in node.inputs if _is_task_family(socket)]
        if not any(socket.is_linked for socket in task_inputs):
            continue
        diagnostics.append(
            Diagnostic(
                "WARNING",
                "ORPHAN_TASK_CHAIN",
                "Task output is unconnected; this chain is ignored until "
                "linked into a Task Output",
                node.name,
            )
        )
    return diagnostics


def validate_tree(tree):
    diagnostics = []

    for link in sorted(
        tree.links,
        key=lambda item: (
            item.to_node.name,
            item.to_socket.name,
            item.from_node.name,
            item.from_socket.name,
        ),
    ):
        source = socket_family(link.from_socket)
        target = socket_family(link.to_socket)
        accepts = tuple(getattr(link.to_socket, "rsp_accepts", (target,)))
        if source not in accepts and "ANY" not in accepts:
            diagnostics.append(
                Diagnostic(
                    "ERROR",
                    "SOCKET_TYPE",
                    "{} cannot connect to {}".format(source, target),
                    link.to_node.name,
                    link.to_socket.name,
                )
            )

    diagnostics.extend(_orphan_task_chain_diagnostics(tree))

    for node in sorted(tree.nodes, key=lambda item: item.name):
        validate = getattr(node, "rsp_validate", None)
        if validate is not None:
            for diagnostic in validate():
                diagnostics.append(diagnostic)

    return tuple(sorted(diagnostics, key=lambda item: item.sort_key()))

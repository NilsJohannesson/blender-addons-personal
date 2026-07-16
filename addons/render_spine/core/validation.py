"""Structural graph validation independent of evaluation order."""

from .model import Diagnostic


def socket_family(socket):
    return getattr(socket, "rsp_family", getattr(socket, "bl_idname", ""))


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

    for node in sorted(tree.nodes, key=lambda item: item.name):
        validate = getattr(node, "rsp_validate", None)
        if validate is not None:
            for diagnostic in validate():
                diagnostics.append(diagnostic)

    return tuple(sorted(diagnostics, key=lambda item: item.sort_key()))

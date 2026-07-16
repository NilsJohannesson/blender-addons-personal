"""Deterministic, side-effect-free graph compiler."""

from .model import CompileResult, Diagnostic, JobList, JobSpec
from .path_template import coerce_to_string
from .validation import validate_tree


class CompileError(Exception):
    def __init__(self, diagnostics):
        self.diagnostics = tuple(diagnostics)
        super().__init__("Render graph compilation failed")


class CompileContext:
    """Memoized evaluator exposed to node compile methods."""

    def __init__(self, tree):
        self.tree = tree
        self.cache = {}
        self.visiting = []
        self.order = []
        self.diagnostics = []

    def error(self, code, message, node=None, socket=None):
        self.diagnostics.append(
            Diagnostic(
                "ERROR",
                code,
                message,
                getattr(node, "name", ""),
                getattr(socket, "name", ""),
            )
        )

    def warning(self, code, message, node=None, socket=None):
        self.diagnostics.append(
            Diagnostic(
                "WARNING",
                code,
                message,
                getattr(node, "name", ""),
                getattr(socket, "name", ""),
            )
        )

    def _coerce_input(self, socket, value, node):
        if not getattr(socket, "rsp_coerce_to_string", False):
            return value
        if isinstance(value, (JobSpec, JobList)):
            self.error(
                "STRING_COERCE",
                "Cannot convert Job / Job List to string",
                node,
                socket,
            )
            return ""
        return coerce_to_string(value, sanitize=True)

    def input(self, node, name, default=None, required=False):
        socket = node.inputs.get(name)
        if socket is None:
            self.error("MISSING_SOCKET", "Input socket is not defined", node)
            return default
        if socket.is_linked:
            links = sorted(
                socket.links,
                key=lambda link: (
                    link.from_node.name,
                    link.from_socket.name,
                ),
            )
            if len(links) > 1 and not socket.is_multi_input:
                self.error("MULTIPLE_LINKS", "Input accepts only one link", node, socket)
            value = self.output(links[0].from_node, links[0].from_socket)
            return self._coerce_input(socket, value, node)
        if required and getattr(socket, "hide_value", False):
            self.error("REQUIRED_INPUT", "Required input is not connected", node, socket)
            return default
        try:
            value = socket.rsp_value()
        except (AttributeError, TypeError, ValueError) as exc:
            self.error("INVALID_VALUE", str(exc), node, socket)
            return default
        return self._coerce_input(socket, value, node)

    def output(self, node, socket=None):
        socket_name = socket.name if socket is not None else ""
        key = (node.as_pointer(), socket_name)
        if key in self.cache:
            return self.cache[key]
        node_key = node.as_pointer()
        if node_key in self.visiting:
            cycle = " -> ".join(
                item.name
                for item in self.tree.nodes
                if item.as_pointer() in self.visiting + [node_key]
            )
            self.error("CYCLE", "Dependency cycle: " + cycle, node, socket)
            return None
        self.visiting.append(node_key)
        try:
            value = node.rsp_compile(self, socket)
            self.cache[key] = value
            if node.name not in self.order:
                self.order.append(node.name)
            return value
        except (TypeError, ValueError, IndexError, KeyError) as exc:
            self.error("COMPILE_NODE", str(exc), node, socket)
            return None
        finally:
            self.visiting.pop()


def _job_outputs(tree):
    nodes = [
        node
        for node in tree.nodes
        if getattr(node, "rsp_is_job_output", False) and not node.mute
    ]
    return sorted(nodes, key=lambda node: (node.name, node.as_pointer()))


def compile_tree(tree, strict=True):
    """Compile tree to immutable JobSpec values without changing Blender data."""
    context = CompileContext(tree)
    context.diagnostics.extend(validate_tree(tree))
    outputs = _job_outputs(tree)
    if not outputs:
        context.error("NO_OUTPUT", "Graph has no enabled Job Output node")

    jobs = []
    for node in outputs:
        value = context.output(node)
        if isinstance(value, JobSpec):
            jobs.append(value)
        elif isinstance(value, JobList):
            jobs.extend(value.jobs)
        elif value is not None:
            context.error(
                "OUTPUT_TYPE",
                "Job Output must compile to JobSpec or JobList",
                node,
            )

    diagnostics = tuple(sorted(context.diagnostics, key=lambda item: item.sort_key()))
    result = CompileResult(tuple(jobs), diagnostics, tuple(context.order))
    if strict and not result.ok:
        raise CompileError(diagnostics)
    return result

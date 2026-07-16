"""Duck-typed boundary between execution code and the compiler."""

from importlib import import_module
import inspect
from pathlib import Path


class CompileFailure(Exception):
    """Compiler failure normalized for operators and UI."""


def _read(value, *names, default=None):
    if isinstance(value, dict):
        for name in names:
            if name in value:
                return value[name]
        return default
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _compiler_module():
    package = __package__.rsplit(".", 1)[0]
    candidates = (
        f"{package}.core",
        f"{package}.core.compiler",
        f"{package}.core.compile",
    )
    errors = []
    for module_name in candidates:
        try:
            module = import_module(module_name)
        except (ImportError, ModuleNotFoundError) as exc:
            errors.append(str(exc))
            continue
        if callable(getattr(module, "compile_tree", None)):
            return module
    raise CompileFailure("compile_tree() unavailable: " + "; ".join(errors))


def compile_jobs(tree, context):
    if tree is None:
        raise CompileFailure("No render-node tree is active")
    try:
        compiler = _compiler_module().compile_tree
        parameters = tuple(inspect.signature(compiler).parameters.values())
        if len(parameters) > 1 and parameters[1].name == "context":
            result = compiler(tree, context)
        else:
            result = compiler(tree, strict=True)
    except Exception as exc:
        errors = validation_messages(exc)
        raise CompileFailure("; ".join(errors) if errors else str(exc)) from exc
    diagnostics = _read(result, "diagnostics", default=())
    failures = [
        item
        for item in diagnostics
        if str(_read(item, "severity", default="")).upper() == "ERROR"
    ]
    if failures:
        raise CompileFailure("; ".join(validation_messages(failures)))
    jobs = _read(result, "jobs", default=result)
    if jobs is None:
        return []
    if not isinstance(jobs, (list, tuple)):
        try:
            jobs = list(jobs)
        except TypeError as exc:
            raise CompileFailure("Compiler result is not an iterable of jobs") from exc
    return jobs


def validation_messages(value):
    if isinstance(value, (list, tuple)):
        result = []
        for item in value:
            result.extend(validation_messages(item))
        return result
    messages = _read(
        value,
        "errors",
        "validation_errors",
        "issues",
        "diagnostics",
        default=None,
    )
    if messages is None:
        message = _read(value, "message", default=None)
        if not message:
            return []
        node = _read(value, "node_name", default="")
        return [f"{node}: {message}" if node else str(message)]
    if isinstance(messages, str):
        return [messages]
    result = []
    for item in messages:
        message = _read(item, "message", "text", "description", default=item)
        result.append(str(message))
    return result


def job_name(job, index):
    value = _read(job, "name", "label", "title", "id", default=None)
    return str(value) if value not in (None, "") else f"Job {index + 1}"


def job_overrides(job):
    value = _read(
        job,
        "overrides",
        "operations",
        "ordered_overrides",
        "mutations",
        default=(),
    )
    return tuple(value or ())


def job_source_scene(job):
    value = _read(job, "source_scene", "scene", "scene_name", default="")
    if not isinstance(value, (str, type(None))):
        value = getattr(value, "name", value)
    return str(value or "")


def job_output(job, scene=None, expand=True):
    value = _read(
        job,
        "output_path",
        "filepath",
        "output",
        "render_path",
        default=None,
    )
    if value is None and scene is not None:
        for override in job_overrides(job):
            path = _read(override, "path", "rna_path", "data_path", default="")
            if path in ("render.filepath", "scene.render.filepath"):
                value = _read(override, "value", "new_value", default=None)
                break
        if value is None:
            value = scene.render.filepath
    if isinstance(value, dict):
        value = _read(value, "path", "filepath", default="")
    text = str(value or "")
    if expand and scene is not None and "{" in text:
        from .path_expand import expand_job_filepath

        text = expand_job_filepath(text, job, scene)
    return text


def operation_value(operation, *names, default=None):
    return _read(operation, *names, default=default)


def operation_kind(operation):
    value = _read(operation, "kind", "type", "op", "operation", default="SET")
    return str(value).strip().upper().replace("-", "_")


def operation_summary(operation):
    kind = operation_kind(operation)
    path = _read(operation, "path", "rna_path", "data_path", "attribute", "key")
    target = _read(
        operation,
        "target_name",
        "target_id",
        "datablock",
        "target",
        default="scene",
    )
    if not isinstance(target, (str, int, float)):
        target = getattr(target, "name", type(target).__name__)
    value = _read(operation, "value", "new_value", default=None)
    return f"{kind} {target}.{path} = {value!r}"


def summarize_jobs(jobs):
    lines = []
    for index, job in enumerate(jobs):
        operations = job_overrides(job)
        lines.append(f"{index + 1}. {job_name(job, index)} ({len(operations)} overrides)")
        lines.extend(f"   {operation_summary(item)}" for item in operations)
        output = job_output(job)
        if output:
            lines.append(f"   output: {output}")
    return "\n".join(lines) if lines else "No jobs compiled"


def output_status(job, scene, bpy_module):
    raw_path = job_output(job, scene)
    if not raw_path:
        return "", False, "Output path is empty"
    absolute = bpy_module.path.abspath(raw_path)
    path = Path(absolute)
    exists = path.exists()
    if exists:
        message = "Output exists"
    elif path.parent.exists():
        message = "Output does not exist"
    else:
        message = "Output directory does not exist"
    return absolute, exists, message

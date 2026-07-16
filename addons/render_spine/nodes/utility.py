"""Allowlisted utility operations. No expression evaluation."""

import math

import bpy
from bpy.props import BoolProperty, EnumProperty

from ..core.model import TaskList, TaskSpec
from ..core.node import RSP_NodeBase
from ..core.path_template import sanitize_token_value, token_value


class RSP_JobSwitchNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeJobSwitch"
    bl_label = "Task Switch"
    rsp_inputs = (
        ("RenderSpineNodeSocketBool", "Condition"),
        ("RenderSpineNodeSocketTask", "False"),
        ("RenderSpineNodeSocketTask", "True"),
    )
    rsp_outputs = (("RenderSpineNodeSocketTask", "Task"),)

    def rsp_compile(self, context, socket):
        name = "True" if context.input(self, "Condition") else "False"
        value = context.input(self, name, required=True)
        if not isinstance(value, TaskSpec):
            raise TypeError("{} input requires TaskSpec".format(name))
        return value


class RSP_BooleanMathNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeBooleanMath"
    bl_label = "Boolean Math"
    operation: EnumProperty(
        items=(
            ("AND", "And", ""),
            ("OR", "Or", ""),
            ("XOR", "Exclusive Or", ""),
            ("NOT", "Not A", ""),
        ),
        default="AND",
    )
    rsp_inputs = (
        ("RenderSpineNodeSocketBool", "A"),
        ("RenderSpineNodeSocketBool", "B"),
    )
    rsp_outputs = (("RenderSpineNodeSocketBool", "Result"),)

    def draw_buttons(self, context, layout):
        layout.prop(self, "operation", text="")

    def rsp_compile(self, context, socket):
        a = bool(context.input(self, "A"))
        b = bool(context.input(self, "B"))
        operations = {
            "AND": lambda: a and b,
            "OR": lambda: a or b,
            "XOR": lambda: a != b,
            "NOT": lambda: not a,
        }
        return operations[self.operation]()


class RSP_MathNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeMath"
    bl_label = "Math"
    operation: EnumProperty(
        items=(
            ("ADD", "Add", ""),
            ("SUBTRACT", "Subtract", ""),
            ("MULTIPLY", "Multiply", ""),
            ("DIVIDE", "Divide", ""),
            ("MINIMUM", "Minimum", ""),
            ("MAXIMUM", "Maximum", ""),
            ("POWER", "Power", ""),
            ("MODULO", "Modulo", ""),
        ),
        default="ADD",
    )
    rsp_inputs = (
        ("RenderSpineNodeSocketFloat", "A"),
        ("RenderSpineNodeSocketFloat", "B"),
    )
    rsp_outputs = (("RenderSpineNodeSocketFloat", "Result"),)

    def draw_buttons(self, context, layout):
        layout.prop(self, "operation", text="")

    def rsp_compile(self, context, socket):
        a = float(context.input(self, "A"))
        b = float(context.input(self, "B"))
        if self.operation in {"DIVIDE", "MODULO"} and b == 0:
            raise ValueError("Division by zero")
        operations = {
            "ADD": lambda: a + b,
            "SUBTRACT": lambda: a - b,
            "MULTIPLY": lambda: a * b,
            "DIVIDE": lambda: a / b,
            "MINIMUM": lambda: min(a, b),
            "MAXIMUM": lambda: max(a, b),
            "POWER": lambda: math.pow(a, b),
            "MODULO": lambda: a % b,
        }
        value = operations[self.operation]()
        if not math.isfinite(value):
            raise ValueError("Math result is not finite")
        return value


class RSP_StringOperationNode(RSP_NodeBase, bpy.types.Node):
    bl_idname = "RenderSpineNodeStringOperation"
    bl_label = "String Operation"
    operation: EnumProperty(
        items=(
            ("CONCAT", "Concatenate", ""),
            ("REPLACE", "Replace", ""),
            ("UPPER", "Uppercase", ""),
            ("LOWER", "Lowercase", ""),
        ),
        default="CONCAT",
    )
    rsp_inputs = (
        ("RenderSpineNodeSocketString", "A"),
        ("RenderSpineNodeSocketString", "B"),
        ("RenderSpineNodeSocketString", "Search"),
        ("RenderSpineNodeSocketString", "Replacement"),
    )
    rsp_outputs = (("RenderSpineNodeSocketString", "Result"),)

    def draw_buttons(self, context, layout):
        layout.prop(self, "operation", text="")

    def rsp_compile(self, context, socket):
        a = str(context.input(self, "A"))
        operations = {
            "CONCAT": lambda: a + str(context.input(self, "B")),
            "REPLACE": lambda: a.replace(
                str(context.input(self, "Search")),
                str(context.input(self, "Replacement")),
            ),
            "UPPER": a.upper,
            "LOWER": a.lower,
        }
        return operations[self.operation]()


class RSP_ToStringNode(RSP_NodeBase, bpy.types.Node):
    """Coerce any non-job value to a string for path / string building."""

    bl_idname = "RenderSpineNodeToString"
    bl_label = "To String"
    rsp_inputs = (("RenderSpineNodeSocketAny", "Value"),)
    rsp_outputs = (("RenderSpineNodeSocketString", "String"),)
    sanitize: BoolProperty(
        name="Sanitize",
        description="Replace path-unsafe characters (for filename segments)",
        default=True,
    )

    def draw_buttons(self, context, layout):
        layout.prop(self, "sanitize")

    def rsp_compile(self, context, socket):
        value = context.input(self, "Value")
        if isinstance(value, (TaskSpec, TaskList)):
            raise TypeError("Cannot convert Task / Task List to string")
        if self.sanitize:
            return sanitize_token_value(value)
        return token_value(value)


CLASSES = (
    RSP_JobSwitchNode,
    RSP_BooleanMathNode,
    RSP_MathNode,
    RSP_StringOperationNode,
    RSP_ToStringNode,
)

MENU_ITEMS = tuple((cls.bl_idname, cls.bl_label) for cls in CLASSES)

"""Future tools are explicitly registered, typed and executed by trusted code only."""

from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, ValidationError


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    input_schema: type[BaseModel]
    execute: Callable[[BaseModel], BaseModel]


class ToolRegistry:
    def __init__(self, tools=()):
        self._tools = {}
        for tool in tools:
            if tool.name in self._tools or tool.input_schema.model_config.get("extra") != "forbid":
                raise ValueError("invalid_tool_registration")
            self._tools[tool.name] = tool

    def execute(self, name, arguments):
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError("tool_not_allowed")
        try:
            data = tool.input_schema.model_validate(arguments)
        except ValidationError:
            raise ToolError("tool_invalid_arguments") from None
        try:
            result = tool.execute(data)
            if not isinstance(result, BaseModel):
                raise TypeError
            return result
        except Exception:
            raise ToolError("tool_failure") from None

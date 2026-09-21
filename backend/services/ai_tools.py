"""Typed allowlist for AI tools. Authorization never comes from model arguments."""

from dataclasses import dataclass
from enum import Enum
import hashlib
import logging
from time import monotonic
from typing import Callable, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from schemas.ai import (
    ConversationMode,
    ProviderToolDefinition,
    ProviderToolResult,
    ToolCall,
)


logger = logging.getLogger(__name__)


class ToolError(Exception):
    """Stable tool error codes only; handler exceptions never cross this boundary."""


class ToolCategory(str, Enum):
    PUBLIC_READ = "public_read"
    PRIVATE_READ = "private_read"
    CONTROLLED_WRITE = "controlled_write"
    HUMAN_ONLY = "human_only"


class ToolExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: UUID
    cliente_id: int | None = Field(default=None, gt=0)
    identity_verified: bool = False
    mode: ConversationMode
    actor: Literal["client", "operator", "system"] = "client"
    source: Literal["site", "email", "internal"]
    request_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9._-]{8,64}$")


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    category: ToolCategory
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    execute: Callable[[ToolExecutionContext, BaseModel], BaseModel]


def _log_reference(value):
    if value is None:
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return "sha256:" + hashlib.sha256(value.encode()).hexdigest()


class ToolRegistry:
    def __init__(self, tools=()):
        self._tools = {}
        for tool in tools:
            strict_input = tool.input_schema.model_config.get("extra") == "forbid"
            strict_output = tool.output_schema.model_config.get("extra") == "forbid"
            if (
                tool.name in self._tools
                or not tool.name.isidentifier()
                or not strict_input
                or not strict_output
                or tool.category == ToolCategory.HUMAN_ONLY
            ):
                raise ValueError("invalid_tool_registration")
            self._tools[tool.name] = tool

    @staticmethod
    def _authorized(tool, context):
        if tool.category == ToolCategory.PUBLIC_READ:
            return True
        if tool.category in (ToolCategory.PRIVATE_READ, ToolCategory.CONTROLLED_WRITE):
            return context.identity_verified and context.cliente_id is not None
        return False

    def definitions(self, context: ToolExecutionContext):
        return tuple(
            ProviderToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema.model_json_schema(),
            )
            for tool in self._tools.values()
            if self._authorized(tool, context)
        )

    def execute(self, name, arguments, context: ToolExecutionContext):
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError("tool_not_allowed")
        if not self._authorized(tool, context):
            raise ToolError("tool_not_authorized")
        try:
            data = tool.input_schema.model_validate(arguments)
        except ValidationError:
            raise ToolError("tool_invalid_arguments") from None
        try:
            result = tool.execute(context, data)
        except ToolError:
            raise
        except Exception:
            raise ToolError("tool_temporarily_unavailable") from None
        try:
            return tool.output_schema.model_validate(result)
        except (ValidationError, TypeError, ValueError):
            raise ToolError("tool_invalid_result") from None

    def run(self, call: ToolCall, context: ToolExecutionContext):
        started = monotonic()
        error_code = None
        try:
            output = self.execute(call.name, call.arguments, context)
            return ProviderToolResult(
                call_id=call.id,
                name=call.name,
                success=True,
                data=output.model_dump(mode="json"),
            )
        except ToolError as error:
            stable = {
                "tool_not_allowed": "not_allowed",
                "tool_not_authorized": "not_authorized",
                "tool_invalid_arguments": "invalid_input",
                "tool_temporarily_unavailable": "temporarily_unavailable",
                "tool_invalid_result": "invalid_result",
                "not_found": "not_found",
                "conflict": "conflict",
            }
            error_code = stable.get(str(error), "temporarily_unavailable")
            return ProviderToolResult(
                call_id=call.id,
                name=call.name,
                success=False,
                error_code=error_code,
            )
        finally:
            duration_ms = round((monotonic() - started) * 1000)
            logger.info(
                "ai_tool_called tool=%s success=%s error_code=%s duration_ms=%s "
                "conversation_id=%s request_id=%s",
                call.name,
                error_code is None,
                error_code,
                duration_ms,
                context.conversation_id,
                _log_reference(context.request_id),
            )

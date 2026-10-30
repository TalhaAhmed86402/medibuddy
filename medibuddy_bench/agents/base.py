"""The interface an agent under test implements, and the wire format that lets any external
agent (A2A / HTTP / subprocess) be plugged in without writing Python."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Message:
    """What the benchmark sends to the agent."""
    text: str
    sender: str = "patient"          # patient | doctor | system
    lang: str = "en"
    expect: str = "chat"             # chat | recommendations | triage | translation | summary | follow_up
    extra: dict = field(default_factory=dict)   # e.g. {"translate_to": "ko"}


@dataclass
class Reply:
    text: str = ""
    data: dict | None = None         # structured answer, if the task asks for one


class Agent(ABC):
    """Subclass this.  One instance = one conversation context."""
    name = "agent"

    @abstractmethod
    def start_session(self, card: str, tools) -> None:
        """Called once, before the first message.  `card` = task instructions (also the system prompt
        you would give an LLM).  `tools` = ToolClient with .specs() and .call(name, args)."""

    @abstractmethod
    def respond(self, message: Message) -> Reply:
        """Handle one message and return the reply (text + optional structured data)."""

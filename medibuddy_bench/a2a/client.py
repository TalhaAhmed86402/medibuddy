"""Tiny A2A client: send one text message to an agent and get its text reply.

Needs the optional dependency  pip install "a2a-sdk[http-server]==0.3.26" uvicorn  (the rest of the
benchmark is standard-library only)."""
from __future__ import annotations

import uuid

import httpx
from a2a.client import ClientConfig, ClientFactory, create_text_message_object
from a2a.types import Message, Part, Role, Task, TextPart


def _text_of_parts(parts) -> str:
    out = []
    for p in parts or []:
        root = getattr(p, "root", p)
        if getattr(root, "text", None) is not None:
            out.append(root.text)
    return "\n".join(out)


def _text_of_event(ev) -> str:
    """Pull the agent's reply text out of whatever the SDK yields (Message, or (Task, update))."""
    if isinstance(ev, tuple):
        ev = ev[0]
    if isinstance(ev, Message):
        return _text_of_parts(ev.parts)
    if isinstance(ev, Task):
        texts = [_text_of_parts(a.parts) for a in (ev.artifacts or [])]
        if ev.status and ev.status.message:
            texts.append(_text_of_parts(ev.status.message.parts))
        return "\n".join(t for t in texts if t)
    return ""


class TextTalker:
    """Keeps one A2A context per conversation so a purple agent can hold its own history."""

    def __init__(self, timeout: float = 600.0):
        self._http = httpx.AsyncClient(timeout=timeout)
        self._clients: dict[str, object] = {}
        self._ctx: dict[str, str | None] = {}

    async def _client(self, url: str):
        if url not in self._clients:
            cfg = ClientConfig(streaming=False, httpx_client=self._http)
            self._clients[url] = await ClientFactory.connect(url, client_config=cfg)
        return self._clients[url]

    async def send(self, url: str, text: str, new_conversation: bool = False) -> str:
        if new_conversation:
            self._ctx[url] = uuid.uuid4().hex
        client = await self._client(url)
        msg = create_text_message_object(content=text)
        msg.context_id = self._ctx.get(url) or uuid.uuid4().hex
        self._ctx[url] = msg.context_id
        reply = ""
        async for ev in client.send_message(msg):
            t = _text_of_event(ev)
            if t:
                reply = t
        return reply

    async def close(self):
        await self._http.aclose()

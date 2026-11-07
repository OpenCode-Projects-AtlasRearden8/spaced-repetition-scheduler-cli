"""Tests for the optional LLM polish client against a local stub endpoint."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from srs_scheduler.polish import build_payload, polish_card

HOST = "127.0.0.1"


class _StubHandler(BaseHTTPRequestHandler):
    server_version = "Stub"

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(body)
        self.server.headers_seen.append(dict(self.headers))
        if not self.path.endswith("/chat/completions") or body["model"] == "explode":
            self.send_error(401 if body["model"] == "explode" else 404)
            return
        content = json.dumps({"front": "Rewritten front?", "back": "Rewritten back."})
        if body["model"] == "reasoner":
            encoded = json.dumps({"choices": [{"message": {"content": "",
                                                           "reasoning": "think think\n" + content}}]}).encode("utf-8")
        else:
            response = {"choices": [{"message": {"content": content}}]}
            encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *args):  # silence the test output
        pass


@pytest.fixture()
def stub_url():
    server = HTTPServer((HOST, 0), _StubHandler)
    server.requests = []
    server.headers_seen = []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://{HOST}:{server.server_port}/v1", server
    server.shutdown()
    server.server_close()


def test_build_payload_has_system_prompt_and_card() -> None:
    payload = build_payload("gemma", "front text", "back text")
    assert payload["model"] == "gemma"
    roles = [message["role"] for message in payload["messages"]]
    assert roles == ["system", "user"]
    assert json.loads(payload["messages"][1]["content"]) == {"front": "front text", "back": "back text"}
    assert payload["messages"][0]["role"] == "system"


def test_polish_card_succeeds_against_openai_compatible_url(stub_url) -> None:
    url, server = stub_url
    result = polish_card("old front", "old back", base_url=url, model="gemma")
    assert result == {"front": "Rewritten front?", "back": "Rewritten back."}
    request = server.requests[0]
    assert request["model"] == "gemma"
    assert server.headers_seen[0].get("Authorization") is None


def test_polish_card_sends_bearer_only_when_key_given(stub_url) -> None:
    url, server = stub_url
    polish_card("f", "b", base_url=url, model="gemma", api_key="sekrit")
    assert server.headers_seen[0]["Authorization"] == "Bearer sekrit"


def test_polish_card_falls_back_to_reasoning_field(stub_url) -> None:
    url, server = stub_url
    result = polish_card("f", "b", base_url=url, model="reasoner")
    assert result == {"front": "Rewritten front?", "back": "Rewritten back."}


def test_polish_card_reports_http_errors(stub_url) -> None:
    url, _ = stub_url
    with pytest.raises(RuntimeError, match="HTTP 401"):
        polish_card("f", "b", base_url=url, model="explode")


def test_polish_card_reports_down_endpoint() -> None:
    with pytest.raises(RuntimeError, match="could not reach"):
        polish_card("f", "b", base_url=f"http://{HOST}:1/v1", model="gemma", timeout=1)


def test_parse_accepts_fenced_json() -> None:
    from srs_scheduler.polish import _parse_text_response

    fenced = "```json\n{\"front\": \"f\", \"back\": \"b\"}\n```"
    assert _parse_text_response(fenced) == {"front": "f", "back": "b"}


def test_parse_rejects_non_json() -> None:
    from srs_scheduler.polish import _parse_text_response

    with pytest.raises(ValueError):
        _parse_text_response("here is a thought, not json")

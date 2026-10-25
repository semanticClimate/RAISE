"""
Sub-suite conftest for API routing and network contract tests.
"""
import json
import pytest

@pytest.fixture
def github_pages_origin():
    return "https://semanticclimate.github.io"

@pytest.fixture
def cloudflare_tunnel_origin():
    return "https://raise-preview-tunnel.trycloudflare.com"

@pytest.fixture
def parse_sse_events():
    def _parse(response):
        lines = [line if isinstance(line, str) else line.decode("utf-8") for line in response.iter_lines() if line]
        tokens = []
        final_meta = None
        done = False
        for line in lines:
            if line.startswith("data: "):
                payload_str = line[6:].strip()
                if payload_str == "[DONE]":
                    done = True
                    continue
                try:
                    ev_data = json.loads(payload_str)
                    if "token" in ev_data:
                        tokens.append(ev_data["token"])
                    if "sources" in ev_data:
                        final_meta = ev_data
                except Exception:
                    pass
        return {"tokens": tokens, "full_text": "".join(tokens), "meta": final_meta, "done": done}
    return _parse
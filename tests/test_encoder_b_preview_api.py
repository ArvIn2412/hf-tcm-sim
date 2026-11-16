from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from hf_tcm.studio.server import make_server


def test_encoder_b_preview_post_does_not_call_receiver_or_trace_builder() -> None:
    def unexpected(_request):
        pytest.fail("encoder preview must not call the simulation/receiver trace builder")

    server = make_server("127.0.0.1", 0, trace_builder=unexpected)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(f"{base}/api/health") as response:
            assert json.load(response)["receiver_invoked"] is False
        request = urllib.request.Request(
            f"{base}/api/encoder-b-preview",
            data=json.dumps({"bits": "001011", "initial_state_id": 0}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request) as response:
            result = json.load(response)
        assert result["receiver_invoked"] is False
        assert result["encoder_id"] == "chapter4_code2"
        assert result["initial_state_id"] == 0
        assert result["encoded_bits"] == [[0, 0, 0], [0, 1, 0], [0, 1, 0]]
        assert result["manipulation_parameters"] == [0, 2, 2]
        assert result["branch_ids"] == [0, 1, 35]
        assert len(result["trellis"]) == 64
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"bits": "010"}, "even"),
        ({"bits": "01x0"}, "only 0 and 1"),
        ({"bits": "0" * 258}, "2..256"),
        ({"bits": "01", "initial_state_id": 16}, "0..15"),
    ],
)
def test_encoder_b_preview_rejects_invalid_request_without_receiver(payload, message) -> None:
    server = make_server("127.0.0.1", 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/encoder-b-preview",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        assert error.value.code == 400
        response = json.load(error.value)
        assert message in response["error"]
        assert response["receiver_invoked"] is False
    finally:
        server.shutdown()
        worker.join(timeout=2)
        server.server_close()

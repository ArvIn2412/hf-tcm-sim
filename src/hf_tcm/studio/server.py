"""Dependency-free localhost HTTP server for the M11b interactive studio."""

from __future__ import annotations

import json
import logging
import mimetypes
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from hf_tcm.coding.encoder_b import (
    MAX_INFORMATION_BITS_B,
    build_trellis_b,
    encode_b,
    state_b_from_id,
    state_id_b,
)
from hf_tcm.evaluation.m11a_demo_studio import (
    DemoRequest,
    _json_value,
    build_demo_trace,
    build_studio_metadata,
)
from hf_tcm.repro.metric_experiment import (
    MetricStudyConfig,
    list_metric_studies,
    load_metric_study,
)
from hf_tcm.repro.paired_experiment import ExperimentConfig, verify_experiment
from hf_tcm.studio.archive_views import build_archive_views
from hf_tcm.studio.energy import (
    EnergyStudyConfig,
    list_energy_studies,
    load_energy_study,
)
from hf_tcm.studio.energy_view import load_energy_view
from hf_tcm.studio.historical_energy import (
    load_historical_energy_study,
    load_historical_exp01b_energy_study,
)
from hf_tcm.studio.lab_window import load_lab_window
from hf_tcm.studio.metric_trace import load_metric_trace
from hf_tcm.studio.scientific import (
    JOBS,
    ScientificRunConfig,
    load_long_frame_archive,
    load_run_summary,
    long_frame_viterbi_window,
    trace_sample_window,
    trace_window,
    viterbi_window,
)
from hf_tcm.studio.scientific_exp03b_results import load_exp03b_analysis
from hf_tcm.studio.study_catalog import list_study_catalog
from hf_tcm.studio.system_signal import system_signal

STATIC_ROOT = Path(__file__).with_name("static")


def make_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    default_view: str = "demo",
    trace_builder: Callable[[DemoRequest], dict[str, Any]] = build_demo_trace,
) -> ThreadingHTTPServer:
    """Create a local-only studio server; no receiver runs during startup/GET."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the demo studio may bind only to the local machine")
    if default_view not in {"demo", "scientific"}:
        raise ValueError("default_view must be 'demo' or 'scientific'")

    class StudioHandler(BaseHTTPRequestHandler):
        server_version = "HF-TCM-SIM-M11b"

        def log_message(self, fmt: str, *args: object) -> None:
            logging.getLogger(__name__).debug(fmt, *args)

        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(payload)
            except ConnectionError:
                # AbortController may close a superseded read-only window request.
                return

        def _json(self, status: int, payload: object) -> None:
            encoded = json.dumps(
                _json_value(payload), ensure_ascii=False, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
            self._send(status, encoded, "application/json; charset=utf-8")

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/" and default_view == "scientific":
                path = "/scientific"
            if path == "/api/metadata":
                self._json(200, build_studio_metadata())
                return
            if path == "/api/health":
                self._json(200, {"status": "ready", "receiver_invoked": False})
                return
            if path == "/api/archive-views":
                self._json(200, build_archive_views())
                return
            if path == "/api/scientific/runs":
                self._get_scientific_runs()
                return
            if path == "/api/scientific/long-frame":
                try:
                    self._json(200, load_long_frame_archive())
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self._json(409, {"error": str(exc)})
                return
            if path == "/api/scientific/long-frame/viterbi":
                query = parse_qs(parsed.query)
                try:
                    self._json(
                        200,
                        long_frame_viterbi_window(
                            symbol_index=int(query.get("symbol", ["0"])[0]),
                            traceback_depth=int(query.get("depth", ["20"])[0]),
                            survivor_state=(
                                int(query["survivor_state"][0])
                                if query.get("survivor_state", [""])[0]
                                else None
                            ),
                        ),
                    )
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self._json(409, {"error": str(exc)})
                return
            if path == "/api/scientific/experiments":
                self._get_scientific_experiments()
                return
            if path == "/api/scientific/energy-studies":
                rows = list_energy_studies(Path("outputs/repro09/energy-studies"))
                self._json(
                    200,
                    {
                        "studies": [
                            {key: value for key, value in row.items() if key != "records"}
                            for row in rows
                        ]
                    },
                )
                return
            if path == "/api/scientific/exp03b-results":
                try:
                    result = load_exp03b_analysis(
                        Path("outputs/scientific_exp03b/analysis/independent_analysis.json"),
                        Path("configs/SCIENTIFIC_EXP_03B_PROTOCOL.json"),
                        Path("outputs/scientific_exp03b"),
                    )
                    self._json(200, result)
                except FileNotFoundError as exc:
                    self._json(404, {"error": str(exc)})
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    self._json(409, {"error": str(exc)})
                return
            if path == "/api/scientific/lab-window":
                query = parse_qs(parsed.query)
                try:
                    arguments = {
                        key: int(query.get(key, [str(default)])[0])
                        for key, default in (
                            ("start", 0),
                            ("count", 160),
                            ("selected", 0),
                            ("bins", 800),
                            ("point", 0),
                            ("trial", 0),
                            ("index", 0),
                            ("direction", 0),
                        )
                    }
                    result = load_lab_window(
                        Path("outputs/scientific-exp03a/metric-studies"),
                        query.get("study_id", [""])[0],
                        domain=query.get("domain", ["sample"])[0],
                        **arguments,
                    )
                    self._json(200, result)
                except (OSError, ValueError, KeyError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if path in {"/api/scientific/study-catalog", "/api/scientific/energy-view"}:
                query = parse_qs(parsed.query)
                try:
                    if path.endswith("energy-view"):
                        result = load_energy_view(
                            Path("outputs/scientific-exp03a/metric-studies"),
                            query.get("study_id", [""])[0],
                        )
                    else:
                        options = {key: values[0] for key, values in query.items()}
                        for key in ("page", "size"):
                            if key in options:
                                options[key] = int(options[key])
                        result = list_study_catalog(Path("outputs"), **options)
                    self._json(200, result)
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if path == "/api/scientific/metric-trace":
                query = parse_qs(parsed.query)
                try:
                    self._json(
                        200,
                        load_metric_trace(
                            Path("outputs/scientific-exp03a/metric-studies"),
                            query.get("study_id", [""])[0],
                            compact=query.get("compact", ["0"])[0] == "1",
                            **{
                                key: int(query.get(key, [str(default)])[0])
                                for key, default in (
                                    ("point", 0),
                                    ("trial", 0),
                                    ("start", 0),
                                    ("count", 20),
                                    ("limit", 1000),
                                )
                            },
                        ),
                    )
                except (OSError, ValueError, KeyError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if path == "/api/scientific/metric-studies":
                self._json(
                    200,
                    {
                        "studies": list_metric_studies(
                            Path("outputs/scientific-exp03a/metric-studies")
                        )
                    },
                )
                return
            if path.startswith("/api/scientific/metric-studies/"):
                self._get_metric_study(path.rsplit("/", 1)[-1])
                return
            if path == "/api/scientific/energy-studies/historical/static-amplitude-005":
                try:
                    self._json(200, load_historical_energy_study())
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self._json(409, {"error": str(exc)})
                return
            if path == "/api/scientific/energy-studies/historical/exp01b-static-amplitude-005":
                began = time.perf_counter()
                status = 200
                try:
                    self._json(200, load_historical_exp01b_energy_study())
                except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    status = 409
                    self._json(409, {"error": str(exc)})
                finally:
                    logging.getLogger(__name__).info(
                        "exp01b_http status=%d seconds=%.6f", status, time.perf_counter() - began
                    )
                return
            if path.startswith("/api/scientific/energy-studies/"):
                self._get_scientific_energy_study(path.rsplit("/", 1)[-1])
                return
            if path.startswith("/api/scientific/jobs/"):
                job = JOBS.get(path.rsplit("/", 1)[-1])
                self._json(200 if job else 404, job or {"error": "job not found"})
                return
            if path.startswith("/api/scientific/runs/"):
                self._get_scientific_run(path.rsplit("/", 1)[-1])
                return
            if path.startswith("/api/scientific/experiments/"):
                self._get_scientific_experiment(path.rsplit("/", 1)[-1])
                return
            if path == "/api/scientific/traces":
                query = parse_qs(parsed.query)
                try:
                    run_id = query.get("run_id", [""])[0]
                    if not run_id or any(
                        char
                        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                        for char in run_id
                    ):
                        raise ValueError("invalid run ID")
                    start = int(query.get("start", ["0"])[0])
                    count = int(query.get("count", ["20"])[0])
                    if query.get("overview") == ["1"]:
                        self._json(
                            200,
                            system_signal(
                                Path("outputs/repro09") / run_id,
                                start,
                                count,
                                int(query.get("symbol", ["0"])[0]),
                            ),
                        )
                        return
                    self._json(
                        200,
                        trace_window(
                            Path("outputs/repro09") / run_id, start_symbol=start, symbol_count=count
                        ),
                    )
                except (ValueError, OSError, KeyError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if path == "/api/scientific/samples":
                query = parse_qs(parsed.query)
                try:
                    run_id = query.get("run_id", [""])[0]
                    if not run_id or any(
                        char
                        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                        for char in run_id
                    ):
                        raise ValueError("invalid run ID")
                    sample_start = int(query.get("start", ["0"])[0])
                    sample_count = int(query.get("count", ["20"])[0])
                    self._json(
                        200,
                        trace_sample_window(
                            Path("outputs/repro09") / run_id,
                            sample_start=sample_start,
                            sample_count=sample_count,
                        ),
                    )
                except (ValueError, OSError, KeyError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if path == "/api/scientific/viterbi":
                query = parse_qs(parsed.query)
                try:
                    run_id = query.get("run_id", [""])[0]
                    if not run_id or any(
                        char
                        not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                        for char in run_id
                    ):
                        raise ValueError("invalid run ID")
                    self._json(
                        200,
                        viterbi_window(
                            Path("outputs/repro09") / run_id,
                            receiver=query.get("receiver", ["joint"])[0],
                            symbol_index=int(query.get("symbol", ["0"])[0]),
                            traceback_depth=int(query.get("depth", ["20"])[0]),
                            survivor_state=(
                                int(query["survivor_state"][0])
                                if query.get("survivor_state", [""])[0]
                                else None
                            ),
                        ),
                    )
                except (ValueError, OSError, KeyError) as exc:
                    self._json(400, {"error": str(exc)})
                return
            if path == "/" or path == "/scientific" or path.startswith("/static/"):
                relative = "index.html" if path == "/" else path.removeprefix("/static/")
                if path == "/scientific":
                    relative = "scientific.html"
                candidate = (STATIC_ROOT / relative).resolve()
                if (
                    STATIC_ROOT.resolve() not in candidate.parents
                    and candidate != STATIC_ROOT.resolve()
                ):
                    self._json(404, {"error": "not found"})
                    return
                if not candidate.is_file():
                    self._json(404, {"error": "not found"})
                    return
                content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type in {
                    "application/javascript",
                    "application/json",
                }:
                    content_type += "; charset=utf-8"
                self._send(200, candidate.read_bytes(), content_type)
                return
            self._json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = urlsplit(self.path).path
            if path == "/api/scientific/run":
                self._post_scientific_run()
                return
            if path == "/api/scientific/experiments":
                self._post_scientific_experiment()
                return
            if path == "/api/scientific/energy-studies":
                self._post_scientific_energy_study()
                return
            if path == "/api/scientific/metric-studies":
                self._post_scientific_metric_study()
                return
            if path.startswith("/api/scientific/jobs/") and path.endswith("/stop"):
                job_id = path.removeprefix("/api/scientific/jobs/").removesuffix("/stop").strip("/")
                stopped = JOBS.stop(job_id)
                self._json(200 if stopped else 409, {"stop_requested": stopped})
                return
            if path == "/api/encoder-b-preview":
                self._post_encoder_b_preview()
                return
            if path == "/api/demo":
                self._post_demo()
                return
            self._json(404, {"error": "not found"})

        def _post_scientific_run(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32768:
                    raise ValueError("request body must be between 1 and 32768 bytes")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("request body must be a JSON object")
                data["output_root"] = "outputs/repro09"
                config = ScientificRunConfig.from_dict(data)
                job_id = JOBS.submit(config)
                self._json(202, {"job_id": job_id, "status": "queued"})
            except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                self._json(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._json(409, {"error": str(exc)})

        def _get_scientific_runs(self) -> None:
            root = Path("outputs/repro09")
            runs = []
            if root.is_dir():
                for candidate in sorted(
                    root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True
                ):
                    if candidate.is_dir() and (candidate / "manifest.json").is_file():
                        try:
                            runs.append(load_run_summary(candidate))
                        except (OSError, ValueError, KeyError):
                            continue
            self._json(200, {"runs": runs[:100]})

        def _get_scientific_run(self, run_id: str) -> None:
            if not run_id or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                for char in run_id
            ):
                self._json(400, {"error": "invalid run ID"})
                return
            try:
                summary = load_run_summary(Path("outputs/repro09") / run_id)
                self._json(200, summary)
            except FileNotFoundError:
                self._json(404, {"error": "saved run not found"})
            except (OSError, ValueError, KeyError) as exc:
                self._json(409, {"error": str(exc)})

        def _post_scientific_experiment(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32768:
                    raise ValueError("request body must be between 1 and 32768 bytes")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("experiment configuration must be a JSON object")
                data["output_dir"] = "outputs/repro09/monte-carlo"
                config = ExperimentConfig.from_dict(data)
                job_id = JOBS.submit_experiment(config)
                self._json(202, {"job_id": job_id, "status": "queued"})
            except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                self._json(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._json(409, {"error": str(exc)})

        def _post_scientific_energy_study(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32768:
                    raise ValueError("request body must be between 1 and 32768 bytes")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                config = EnergyStudyConfig.from_dict(data)
                job_id = JOBS.submit_energy_study(config, Path("outputs/repro09/energy-studies"))
                self._json(202, {"job_id": job_id, "status": "queued"})
            except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                self._json(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._json(409, {"error": str(exc)})

        def _post_scientific_metric_study(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 32768:
                    raise ValueError("request body must be between 1 and 32768 bytes")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                if isinstance(data, dict) and data.get("phase") == "confirmatory":
                    raise ValueError(
                        "the GUI cannot execute confirmatory studies; "
                        "use scripts/run_scientific_exp04.py with an approved protocol"
                    )
                config = MetricStudyConfig.from_dict(data)
                job_id = JOBS.submit_metric_study(
                    config, Path("outputs/scientific-exp03a/metric-studies")
                )
                self._json(202, {"job_id": job_id, "status": "queued"})
            except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                self._json(400, {"error": str(exc)})
            except RuntimeError as exc:
                self._json(409, {"error": str(exc)})

        def _get_scientific_energy_study(self, study_id: str) -> None:
            if not study_id or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                for char in study_id
            ):
                self._json(400, {"error": "invalid energy-study ID"})
                return
            try:
                result = load_energy_study(Path("outputs/repro09/energy-studies") / study_id)
                self._json(200, result)
            except FileNotFoundError:
                self._json(404, {"error": "saved energy study not found"})
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self._json(409, {"error": str(exc)})

        def _get_metric_study(self, study_id: str) -> None:
            if not study_id or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                for char in study_id
            ):
                self._json(400, {"error": "invalid metric-study ID"})
                return
            try:
                result = load_metric_study(
                    Path("outputs/scientific-exp03a/metric-studies") / study_id
                )
                self._json(200, result)
            except FileNotFoundError:
                self._json(404, {"error": "saved metric study not found"})
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self._json(409, {"error": str(exc)})

        def _get_scientific_experiments(self) -> None:
            root = Path("outputs/repro09/monte-carlo")
            rows = []
            if root.is_dir():
                for candidate in sorted(
                    root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True
                ):
                    if candidate.is_dir() and (candidate / "summary.json").is_file():
                        try:
                            verify_experiment(candidate)
                            rows.append(
                                json.loads((candidate / "summary.json").read_text(encoding="utf-8"))
                            )
                        except (OSError, ValueError, KeyError, json.JSONDecodeError):
                            continue
            self._json(200, {"experiments": rows[:100]})

        def _get_scientific_experiment(self, experiment_id: str) -> None:
            if not experiment_id or any(
                char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
                for char in experiment_id
            ):
                self._json(400, {"error": "invalid experiment ID"})
                return
            candidate = Path("outputs/repro09/monte-carlo") / experiment_id
            try:
                verify_experiment(candidate)
                summary = json.loads((candidate / "summary.json").read_text(encoding="utf-8"))
                self._json(200, summary)
            except FileNotFoundError:
                self._json(404, {"error": "saved experiment not found"})
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                self._json(409, {"error": str(exc)})
                return

        def _post_demo(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 8192:
                    raise ValueError("request body must be between 1 and 8192 bytes")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("request body must be a JSON object")
                raw_bits = data.get("bits", "01011010")
                if isinstance(raw_bits, str):
                    if not raw_bits or any(bit not in "01" for bit in raw_bits):
                        raise ValueError("bits string must contain only 0 and 1")
                    bits = tuple(int(bit) for bit in raw_bits)
                elif isinstance(raw_bits, list):
                    bits = tuple(raw_bits)
                else:
                    raise ValueError("bits must be a bit string or integer list")
                defaults = DemoRequest()
                raw_k = data.get("k_tilde", list(defaults.k_tilde))
                if not isinstance(raw_k, list) or len(raw_k) != 2:
                    raise ValueError("k_tilde must contain two numbers")
                request = DemoRequest(
                    bits=bits,
                    receiver_mode=data.get("receiver_mode", "compare"),
                    alpha_prime=float(data.get("alpha_prime", defaults.alpha_prime)),
                    k_tilde=(float(raw_k[0]), float(raw_k[1])),
                    beta=float(data.get("beta", defaults.beta)),
                    noise_fixture=data.get("noise_fixture", defaults.noise_fixture),
                )
                self._json(200, trace_builder(request))
            except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                self._json(400, {"error": str(exc), "receiver_invoked": False})
            except Exception as exc:  # surface a diagnostic without returning a traceback
                self._json(500, {"error": f"demo failed: {type(exc).__name__}: {exc}"})

        def _post_encoder_b_preview(self) -> None:
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 8192:
                    raise ValueError("request body must be between 1 and 8192 bytes")
                data = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("request body must be a JSON object")
                raw_bits = data.get("bits", "")
                if isinstance(raw_bits, str):
                    if not raw_bits or any(bit not in "01" for bit in raw_bits):
                        raise ValueError("bits string must contain only 0 and 1")
                    bits = tuple(int(bit) for bit in raw_bits)
                elif isinstance(raw_bits, list):
                    bits = tuple(raw_bits)
                else:
                    raise ValueError("bits must be a bit string or integer list")
                if len(bits) % 2:
                    raise ValueError(
                        "bits must have an even number of bits in complete 2-bit groups"
                    )
                if not 2 <= len(bits) <= MAX_INFORMATION_BITS_B:
                    raise ValueError("bits must contain 2..256 bits in complete 2-bit groups")
                state_id = data.get("initial_state_id", 0)
                initial_state = state_b_from_id(state_id)
                result = encode_b(bits, initial_state=initial_state)
                trellis = build_trellis_b()
                self._json(
                    200,
                    {
                        "encoder_id": "chapter4_code2",
                        "source": "references/Раздел_4.pdf, printed pp. 126-129, Fig. 4.6 and Table 4.2",
                        "source_status": "SOURCE_TABLE_AND_GENERATOR_VERIFIED; receiver/phase integration unresolved",
                        "receiver_invoked": False,
                        "receiver_enabled": False,
                        "decoder_enabled": False,
                        "information_bits": bits,
                        "encoded_bits": result.encoded_bits,
                        "states": result.states,
                        "state_ids": tuple(state_id_b(state) for state in result.states),
                        "branch_ids": result.branch_ids,
                        "manipulation_parameters": result.manipulation_parameters,
                        "symbol_count": len(result.encoded_bits),
                        "sample_count": None,
                        "phase_sequence": None,
                        "initial_state_id": state_id,
                        "trellis_state_count": 16,
                        "trellis_transition_count": len(trellis),
                        "trellis": tuple(
                            {
                                "branch_id": branch.branch_id,
                                "state_id": branch.state_id,
                                "state": branch.state,
                                "input_bits": branch.input_pair,
                                "output_bits": branch.encoded_bits,
                                "target_state": branch.next_state,
                                "target_state_id": state_id_b(branch.next_state),
                                "manipulation_parameter_B": branch.manipulation_parameter,
                            }
                            for branch in trellis
                        ),
                        "warning": (
                            "Code 2 encoder/trellis preview only. No compatible receiver or "
                            "author-confirmed mapping from B to absolute 8PSK phase is enabled."
                        ),
                    },
                )
            except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as exc:
                self._json(400, {"error": str(exc), "receiver_invoked": False})

    class StudioHTTPServer(ThreadingHTTPServer):
        # A browser opens concurrent connections for scripts, windows and catalog
        # requests. The socketserver default backlog of five can drop this burst.
        request_queue_size = 64

    return StudioHTTPServer((host, port), StudioHandler)

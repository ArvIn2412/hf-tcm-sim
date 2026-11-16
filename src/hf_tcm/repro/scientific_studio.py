"""Launch the REPRO scientific workspace on a local HTTP server."""

from __future__ import annotations

import argparse
import webbrowser

from hf_tcm.studio.server import make_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch the HF-TCM-SIM Scientific Workspace")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    arguments = parser.parse_args()
    server = make_server(arguments.host, arguments.port, default_view="scientific")
    address = f"http://{arguments.host}:{server.server_port}/scientific"
    print(f"HF-TCM-SIM Scientific Workspace: {address}")
    print("Offline research simulation · paper_exact:false")
    if not arguments.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Scientific Workspace.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

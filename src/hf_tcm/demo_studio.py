"""Launch the local M11b interactive demo studio."""

from __future__ import annotations

import argparse
import webbrowser

from hf_tcm.studio.server import make_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch HF-TCM-SIM M11b Demo Studio")
    parser.add_argument("--host", default="127.0.0.1", choices=("127.0.0.1", "localhost"))
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--no-browser", action="store_true", help="do not open a browser window")
    arguments = parser.parse_args()
    server = make_server(arguments.host, arguments.port)
    address = f"http://{arguments.host}:{server.server_port}/"
    print(f"HF-TCM-SIM M11b Demo Studio: {address}")
    print("RECONSTRUCTED MODEL — paper_exact:false — receiver_enabled:false")
    print("Press Ctrl+C to stop. Receiver runs only after ‘Виконати демонстрацію’.")
    if not arguments.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping M11b Demo Studio.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

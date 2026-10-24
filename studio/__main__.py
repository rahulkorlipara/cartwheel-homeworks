"""Start Cartwheel Studio on localhost: uv run python -m studio [--port 8765]."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Cartwheel Studio locally.")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    print(f"Cartwheel Studio: http://127.0.0.1:{args.port}")
    uvicorn.run("studio.app:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

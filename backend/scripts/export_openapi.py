#!/usr/bin/env python3
"""
Export OpenAPI spec to openapi.json

Usage:
  python scripts/export_openapi.py              # writes ./openapi.json (backend root)
  python scripts/export_openapi.py --out ../frontend/openapi.json  # custom path
  make openapi                                  # via Makefile

Spec is available at runtime as GET /openapi.json and /docs.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

# Ensure app/ is importable when run as `python scripts/export_openapi.py` from backend/
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export FastAPI OpenAPI spec")
    parser.add_argument("--out", default=str(ROOT / "openapi.json"), help="Output path for openapi.json")
    parser.add_argument("--frontend", action="store_true", help="Also copy to frontend/openapi.json")
    args = parser.parse_args()

    spec = app.openapi()

    out_path = pathlib.Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(spec, f, indent=2)
    print(f"[export_openapi] wrote {out_path} ({len(json.dumps(spec))} bytes, {len(spec.get('paths', {}))} paths)")

    if args.frontend:
        fe_path = ROOT.parent / "frontend" / "openapi.json"
        fe_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fe_path, "w") as f:
            json.dump(spec, f, indent=2)
        print(f"[export_openapi] also wrote {fe_path}")

    # quick validation
    assert "openapi" in spec, "spec missing openapi version"
    assert "paths" in spec, "spec missing paths"
    assert spec["info"]["title"] == "NSE Finance API", f"unexpected title {spec['info']['title']}"
    # ensure key routers present
    paths = spec["paths"]
    expected_prefixes = ["/stocks", "/stock-exchange", "/portfolios", "/positions", "/trades", "/quant"]
    for p in expected_prefixes:
        if not any(k.startswith(p) for k in paths):
            print(f"[warn] expected prefix {p} not found in spec paths: {list(paths.keys())[:10]}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check which Google models from the app catalog can actually generate output.

Usage:
    python3 scripts/check_google_models.py
    python3 scripts/check_google_models.py --api-version v1
    python3 scripts/check_google_models.py --model gemini-2.5-flash

Reads GOOGLE_API_KEY from the environment by default.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def load_get_known_models():
    """Load model_catalog.py without importing the full llm_clients package."""
    module_path = PROJECT_ROOT / "tradingagents" / "llm_clients" / "model_catalog.py"
    spec = importlib.util.spec_from_file_location("tradingagents_model_catalog", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load model catalog from {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_known_models


get_known_models = load_get_known_models()


DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate Google models from the TradingAgents catalog against the Gemini API.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("GOOGLE_API_KEY", ""),
        help="Google API key. Defaults to GOOGLE_API_KEY.",
    )
    parser.add_argument(
        "--api-version",
        default="v1beta",
        choices=["v1", "v1beta"],
        help="Gemini API version to query. Defaults to v1beta.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL. Defaults to {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Specific model(s) to check. Repeat to check more than one.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable SSL certificate verification for debugging only.",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: OK",
        help="Short prompt used for the generation probe.",
    )
    return parser.parse_args()


def fetch_json(
    url: str,
    *,
    insecure: bool = False,
    method: str = "GET",
    payload: dict | None = None,
) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, headers=headers, method=method, data=data)
    context = None
    if insecure:
        context = ssl._create_unverified_context()

    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.load(response)


def list_models(
    base_url: str,
    api_version: str,
    api_key: str,
    insecure: bool = False,
) -> list[dict]:
    models: list[dict] = []
    page_token = None

    while True:
        params = {"key": api_key}
        if page_token:
            params["pageToken"] = page_token

        url = (
            f"{base_url.rstrip('/')}/{api_version}/models"
            f"?{urllib.parse.urlencode(params)}"
        )
        payload = fetch_json(url, insecure=insecure)
        models.extend(payload.get("models", []))
        page_token = payload.get("nextPageToken")
        if not page_token:
            return models


def catalog_google_models(selected_models: list[str] | None) -> list[str]:
    models = sorted(get_known_models()["google"])
    if not selected_models:
        return models

    selected_set = {name.strip() for name in selected_models if name.strip()}
    return [model for model in models if model in selected_set]


def normalize_model_name(name: str) -> str:
    return name.removeprefix("models/")


def supported_generation_methods(model_payload: dict) -> str:
    methods = model_payload.get("supportedGenerationMethods") or []
    return ", ".join(methods) if methods else "-"


def probe_model(
    base_url: str,
    api_version: str,
    api_key: str,
    model_name: str,
    prompt: str,
    *,
    insecure: bool = False,
) -> tuple[bool, str]:
    url = (
        f"{base_url.rstrip('/')}/{api_version}/models/{model_name}:generateContent"
        f"?{urllib.parse.urlencode({'key': api_key})}"
    )
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ]
    }

    try:
        response = fetch_json(
            url,
            insecure=insecure,
            method="POST",
            payload=payload,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {body}"
    except urllib.error.URLError as exc:
        return False, f"Network error: {exc}"

    candidates = response.get("candidates") or []
    if not candidates:
        return False, f"No candidates in response: {json.dumps(response)[:300]}"

    parts = (
        candidates[0]
        .get("content", {})
        .get("parts", [])
    )
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    text = "\n".join(t for t in texts if t).strip()
    return True, text or "[empty text response]"


def print_report(
    catalog_models: Iterable[str],
    live_models: list[dict],
    base_url: str,
    api_version: str,
    api_key: str,
    prompt: str,
    *,
    insecure: bool = False,
) -> int:
    catalog_models = list(catalog_models)
    live_index = {
        normalize_model_name(model.get("name", "")): model
        for model in live_models
        if model.get("name")
    }

    print(f"Endpoint: {base_url.rstrip('/')}/{api_version}")
    print(f"Catalog Google models checked: {len(catalog_models)}")
    print()

    missing = []
    failed = []
    for model_name in catalog_models:
        live_payload = live_index.get(model_name)
        if live_payload:
            methods = supported_generation_methods(live_payload)
            print(f"[LISTED]  {model_name}")
            print(f"         API name: {live_payload.get('name')}")
            print(f"         Methods:  {methods}")
            ok, detail = probe_model(
                base_url,
                api_version,
                api_key,
                model_name,
                prompt,
                insecure=insecure,
            )
            if ok:
                print("         Probe:    OK")
                print(f"         Output:   {detail[:200]}")
            else:
                failed.append(model_name)
                print("         Probe:    FAILED")
                print(f"         Error:    {detail[:300]}")
        else:
            missing.append(model_name)
            print(f"[MISSING] {model_name}")

        print()

    print()
    print(f"Live models returned by API: {len(live_models)}")

    if missing:
        print()
        print("Models missing from this endpoint/account:")
        for model_name in missing:
            print(f"- {model_name}")

    if failed:
        print()
        print("Models listed by API but failing generation:")
        for model_name in failed:
            print(f"- {model_name}")

    if missing or failed:
        return 1

    return 0


def main() -> int:
    args = parse_args()

    if not args.api_key:
        print("GOOGLE_API_KEY is not set. Pass --api-key or export GOOGLE_API_KEY.", file=sys.stderr)
        return 2

    models_to_check = catalog_google_models(args.models)
    if not models_to_check:
        print("No matching Google models found in the app catalog for the requested --model values.", file=sys.stderr)
        return 2

    try:
        live_models = list_models(
            args.base_url,
            args.api_version,
            args.api_key,
            insecure=args.insecure,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code} when listing models from the Gemini API.", file=sys.stderr)
        print(body, file=sys.stderr)
        return 3
    except urllib.error.URLError as exc:
        print(f"Network error while contacting the Gemini API: {exc}", file=sys.stderr)
        return 3

    return print_report(
        models_to_check,
        live_models,
        args.base_url,
        args.api_version,
        args.api_key,
        args.prompt,
        insecure=args.insecure,
    )


if __name__ == "__main__":
    raise SystemExit(main())

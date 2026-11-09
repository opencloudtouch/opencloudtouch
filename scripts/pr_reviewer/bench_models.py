"""Throwaway benchmark: run the PR review prompt through several OpenAI models and compare the findings."""

from __future__ import annotations

import asyncio
import json
import os
import time

import httpx
from openai import AsyncOpenAI

import main as reviewer

# USD per 1M tokens (Flex tier, https://developers.openai.com/api/docs/pricing)
PRICES = {
    "gpt-6-luna": (0.05, 0.25),
    "gpt-6.1-terra": (0.50, 2.50),
    "gpt-6.1-sol": (1.00, 5.00),
    "gpt-6-astra": (5.00, 25.00),
    "gpt-5.4-nano": (0.10, 0.625),
    "gpt-4o": (2.50, 10.00),
}

SEEDED = '''@@ -0,0 +1,38 @@
+"""Keep the volume of grouped devices in sync."""
+
+import asyncio
+import xml.etree.ElementTree as ET
+
+import httpx
+
+
+async def fetch_volume(client: httpx.AsyncClient, ip: str) -> int:
+    resp = await client.get(f"http://{ip}:8090/volume")
+    root = ET.fromstring(resp.text)
+    return int(root.findtext("actualvolume", "0"))
+
+
+async def set_volume(client: httpx.AsyncClient, ip: str, level: int) -> None:
+    body = f"<volume>{level}</volume>"
+    await client.post(f"http://{ip}:8090/volume", content=body)
+
+
+def collect_ips(devices: list[dict], seen: list[str] = []) -> list[str]:
+    for d in devices:
+        if d["ip"] not in seen:
+            seen.append(d["ip"])
+    return seen
+
+
+async def sync_group(client: httpx.AsyncClient, devices: list[dict]) -> None:
+    ips = collect_ips(devices)
+    master = await fetch_volume(client, ips[0])
+    for ip in ips[1:]:
+        asyncio.create_task(_safe_set(client, ip, master))
+
+
+async def _safe_set(client: httpx.AsyncClient, ip: str, level: int) -> None:
+    try:
+        await set_volume(client, ip, level)
+    except Exception:
+        pass
'''


async def cases(client: httpx.AsyncClient, repo: str) -> dict[str, str]:
    out = {}
    seeded_details = {"title": "feat(devices): keep grouped device volumes in sync", "body": "Adds volume sync for stereo pairs.",
                      "base": {"ref": "main"}, "head": {"ref": "feat/volume-sync"}}
    out["seeded"] = reviewer.build_review_prompt(
        seeded_details, [{"filename": "apps/backend/src/opencloudtouch/devices/volume_sync.py", "status": "added", "patch": SEEDED}]
    )
    for n in (620, 627):
        details = await reviewer.get_pr_details(client, repo, n)
        files = await reviewer.get_pr_files(client, repo, n)
        out[f"pr{n}"] = reviewer.build_review_prompt(details, files)
    return out


async def ask(ai: AsyncOpenAI, model: str, prompt: str) -> tuple[dict, int, int, float]:
    messages = [
        {"role": "system", "content": "You are a senior staff engineer performing code reviews. You never comment on style or "
         "formatting, only real issues that could cause bugs or security problems. Respond only with valid JSON."},
        {"role": "user", "content": prompt},
    ]
    last: Exception | None = None
    for tier in ("flex", None):
        kwargs = {"model": model, "messages": messages, "response_format": {"type": "json_object"}, "max_completion_tokens": 16000}
        if tier:
            kwargs["service_tier"] = tier
        t0 = time.time()
        try:
            r = await ai.chat.completions.create(**kwargs)
            return json.loads(r.choices[0].message.content or "{}"), r.usage.prompt_tokens, r.usage.completion_tokens, time.time() - t0
        except Exception as e:  # noqa: BLE001 - benchmark: report and try the next tier
            last = e
    raise RuntimeError(str(last))


async def main() -> None:
    repo = os.environ["REPO_FULL_NAME"]
    ai = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    available = {m.id for m in (await ai.models.list()).data}
    print("available gpt models:", sorted(m for m in available if m.startswith(("gpt-6", "gpt-5", "gpt-4o", "o"))))
    wanted = os.environ.get("MODELS", ",".join(PRICES)).split(",")
    async with httpx.AsyncClient(headers={**reviewer.HEADERS, "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}, timeout=60) as gh:
        prompts = await cases(gh, repo)
    lines = []
    for model in wanted:
        if model not in available:
            lines.append(f"## {model}: NOT AVAILABLE for this key")
            continue
        for name, prompt in prompts.items():
            try:
                data, tin, tout, secs = await ask(ai, model, prompt)
            except Exception as e:  # noqa: BLE001
                lines.append(f"## {model} / {name}: ERROR {str(e)[:200]}")
                continue
            pin, pout = PRICES[model]
            cost = tin * pin / 1e6 + tout * pout / 1e6
            comments = data.get("comments") or []
            lines.append(f"## {model} / {name}: verdict={data.get('verdict')} comments={len(comments)} in={tin} out={tout} "
                         f"cost=${cost:.4f} {secs:.0f}s")
            for c in comments:
                lines.append(f"- {c.get('path')}:{c.get('line')} [{c.get('severity', '')}] {str(c.get('body', ''))[:230]!r}")
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text + "\n")


asyncio.run(main())

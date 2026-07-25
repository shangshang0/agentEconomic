"""Independent probe for correlated outputs under nearly identical contexts.

Run inside the model-gateway container so credentials remain confined there:

    docker compose exec -T gateway python - < independent_probes/context_similarity_probe.py

The script does not call or mutate the experiment backend. Gateway requests are
made concurrently within each condition, with unique request identifiers.
"""

from __future__ import annotations

import concurrent.futures
import itertools
import json
import os
import re
import time
import urllib.request
import uuid
from difflib import SequenceMatcher
from typing import Any


GATEWAY_URL = "http://127.0.0.1:8001/v1/generate"
REPLICATES = 6
RUN_TAG = "context-similarity-" + uuid.uuid4().hex[:12]

SYSTEM = (
    "你是一个四人共同决策实验中的参与者。所有参与者拥有相同权限，"
    "每轮必须独立选择 A 或 B；至少三人选择相同方案，公共任务才完成。"
    "你只能通过语言影响别人，不能替别人行动。"
)


def user_context(agent_id: str, preference: str, switch_cost: int) -> str:
    return (
        f"你的编号是 {agent_id}。这是第一轮，公共记录中还没有任何参与者消息。"
        f"你本轮的低成本方案是 {preference}；如果改选另一方案，你损失 {switch_cost} 点。"
        "其他人的私人信息未知。现在是公开讨论阶段。请直接发出一条不超过 80 个汉字的消息，"
        "尝试推动本轮决策。不要解释任务，不要使用标题、列表或固定格式。"
    )


def conditions() -> dict[str, list[dict[str, Any]]]:
    exact = [
        {"agent_id": "P1", "preference": "A", "switch_cost": 2}
        for _ in range(REPLICATES)
    ]
    identity_only = [
        {"agent_id": f"P{i + 1}", "preference": "A", "switch_cost": 2}
        for i in range(REPLICATES)
    ]
    private_state = [
        {"agent_id": "P1", "preference": "A", "switch_cost": 1},
        {"agent_id": "P2", "preference": "A", "switch_cost": 4},
        {"agent_id": "P3", "preference": "B", "switch_cost": 1},
        {"agent_id": "P4", "preference": "B", "switch_cost": 4},
        {"agent_id": "P5", "preference": "A", "switch_cost": 2},
        {"agent_id": "P6", "preference": "B", "switch_cost": 2},
    ]
    return {
        "exact_same_context": exact,
        "agent_id_only": identity_only,
        "private_state_varies": private_state,
    }


def generate(condition: str, index: int, item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "request_id": f"{RUN_TAG}:{condition}:{index}",
        "run_id": RUN_TAG,
        "agent_id": item["agent_id"],
        "model_profile": "default",
        "metadata": {"purpose": "independent_context_similarity_probe", "condition": condition},
        "input": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": user_context(item["agent_id"], item["preference"], item["switch_cost"]),
            },
        ],
        "tools": [],
    }
    request = urllib.request.Request(
        GATEWAY_URL,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers={
            "Authorization": "Bearer " + os.environ["GATEWAY_TOKEN"],
            "Content-Type": "application/json",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=240) as response:
        result = json.load(response)
    return {
        **item,
        "index": index,
        "text": str(result.get("text", "")).strip(),
        "model": result.get("model"),
        "usage": result.get("usage"),
        "latency_seconds": round(time.monotonic() - started, 3),
    }


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)


def ngrams(text: str, size: int = 3) -> set[str]:
    value = normalize(text)
    if len(value) < size:
        return {value} if value else set()
    return {value[i : i + size] for i in range(len(value) - size + 1)}


def jaccard(left: str, right: str) -> float:
    a, b = ngrams(left), ngrams(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def option_mentions(text: str) -> str:
    a = bool(re.search(r"(?<![A-Za-z])A(?![A-Za-z])|方案\s*A|选择\s*A|支持\s*A", text, re.I))
    b = bool(re.search(r"(?<![A-Za-z])B(?![A-Za-z])|方案\s*B|选择\s*B|支持\s*B", text, re.I))
    if a and not b:
        return "A"
    if b and not a:
        return "B"
    if a and b:
        return "both"
    return "none"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [row["text"] for row in rows]
    pairs = list(itertools.combinations(texts, 2))
    normalized = [normalize(text) for text in texts]
    seq = [SequenceMatcher(None, left, right).ratio() for left, right in pairs]
    jac = [jaccard(left, right) for left, right in pairs]
    options = [option_mentions(text) for text in texts]
    counts = {value: options.count(value) for value in sorted(set(options))}
    return {
        "n": len(rows),
        "unique_exact": len(set(texts)),
        "unique_normalized": len(set(normalized)),
        "exact_duplicate_pair_rate": round(
            sum(left == right for left, right in pairs) / len(pairs), 4
        ),
        "mean_pairwise_sequence_similarity": round(sum(seq) / len(seq), 4),
        "max_pairwise_sequence_similarity": round(max(seq), 4),
        "mean_pairwise_char3_jaccard": round(sum(jac) / len(jac), 4),
        "max_pairwise_char3_jaccard": round(max(jac), 4),
        "option_mentions": counts,
    }


def main() -> None:
    all_results: dict[str, Any] = {
        "run_tag": RUN_TAG,
        "model_profile": "default",
        "requests_within_condition_concurrent": True,
        "conditions": {},
    }
    for name, items in conditions().items():
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(items)) as executor:
            futures = [executor.submit(generate, name, index, item) for index, item in enumerate(items)]
            rows = [future.result() for future in futures]
        rows.sort(key=lambda row: row["index"])
        all_results["conditions"][name] = {"summary": summarize(rows), "outputs": rows}
    print(json.dumps(all_results, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

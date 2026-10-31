"""A local teacher on this Mac (2C.3), at no cost: the largest model that runs at a usable speed,
read through the local Ollama server with the teacher's full prompt (round 3's instructions
and POLICY.md).

  throughput MODEL     the credit check's seeded 50 at 1 and 2 requests at once, into
                       eval/results/phase2c/local_teacher.json
  dev MODEL ROUND [think]   all 150 dev articles, one at a time so the server can reuse the
                       policy prefix, saved as data/teacher/dev_ROUND.jsonl in the dev round's
                       own format, then scored by teacher.dev_round from that file, so no Tinker
                       call is made
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx
from credit_check import RESULT as CREDIT
from credit_check import rows_of
from label_gold import ROOT
from teacher import article_text, final, prompt_sha256, system_prompt

URL = "http://127.0.0.1:11434/api/chat"
RESULT = ROOT / "eval" / "results" / "phase2c" / "local_teacher.json"
CANDIDATES = 1_236_122


def one(row: dict, model: str, system: str, think: bool = False) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": article_text(row)},
        ],
        "stream": False,
        "think": think,
        "options": {"temperature": 0, "num_predict": 4096, "num_ctx": 16384},
    }
    answer = httpx.post(URL, json=body, timeout=1800).json()
    return {
        "article_id": row["article_id"],
        "answer": final(answer.get("message", {}).get("content", "")),
        "prompt_tokens": answer.get("prompt_eval_count", 0),
        "output_tokens": answer.get("eval_count", 0),
        "hit_limit": int(answer.get("eval_count", 0) >= 4096),
        "model": model,
        "thinking": think,
        "thinking_chars": len(answer.get("message", {}).get("thinking") or ""),
        "seconds": answer.get("total_duration", 0) / 1e9,
        "prompt_seconds": answer.get("prompt_eval_duration", 0) / 1e9,
        "prompt_sha256": prompt_sha256(system),
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def timed(
    rows: list, model: str, system: str, workers: int, think: bool = False
) -> tuple[dict, list]:
    started = time.time()
    with ThreadPoolExecutor(workers) as pool:
        out = list(pool.map(lambda r: one(r, model, system, think), rows))
    wall = time.time() - started
    per_hour = len(rows) / wall * 3600
    return {
        "concurrent": workers,
        "wall_seconds": round(wall, 1),
        "articles_per_hour": round(per_hour),
        "prompt_tokens": sum(o["prompt_tokens"] for o in out),
        "output_tokens": sum(o["output_tokens"] for o in out),
        "draw_of_3000_hours": round(3000 / per_hour, 1),
        "prompt_seconds_per_article": round(
            sum(o["prompt_seconds"] for o in out) / len(out), 2
        ),
    }, out


def main() -> None:
    run, model, *rest = sys.argv[1:]
    system = system_prompt()
    if run == "throughput":
        picked = json.loads(CREDIT.read_text())["sample"]
        rows = rows_of(set(picked))
        rows = [rows[aid] for aid in picked]
        one(rows[0], model, system)  # load the model before timing
        found = json.loads(RESULT.read_text()) if RESULT.exists() else {}
        found[model] = [timed(rows, model, system, workers)[0] for workers in (1, 2)]
        RESULT.write_text(json.dumps(found, indent=1) + "\n")
        print(json.dumps(found[model], indent=1))
    elif run == "dev":
        from label_gold import articles
        from teacher import dev_round

        round_name, think = rest[0], "think" in rest[1:]
        rows = {aid: r for aid, r in articles().items() if r["split"] == "dev"}
        timing, out = timed([rows[a] for a in sorted(rows)], model, system, 1, think)
        found = json.loads(RESULT.read_text()) if RESULT.exists() else {}
        found[round_name] = timing | {
            "model": model,
            "thinking": think,
            "articles": len(out),
        }
        RESULT.write_text(json.dumps(found, indent=1) + "\n")
        raw = ROOT / "data" / "teacher" / f"dev_{round_name}.jsonl"
        raw.write_text("".join(json.dumps(o) + "\n" for o in out))
        found = dev_round(
            round_name, model=model
        )  # scored from the saved file: no Tinker call
        print(
            json.dumps(
                {
                    k: found[k]
                    for k in ("model", "report_recall", "unparsed", "hit_limit")
                },
                indent=1,
                default=str,
            )
        )


if __name__ == "__main__":
    main()

"""Base Qwen3.5-4B's local throughput on this Mac (2C.3): the free path for the full pass.

The credit check's seeded 50 candidates, with the student's instructions and the same hand-rendered
ChatML, go to the local Ollama server one at a time and then several at once. Ollama runs this
model on its MLX runner with nvfp4 weights, can load a LoRA adapter, and is already on this Mac
(phase 1). The quantized weights may read differently from Tinker's, which the plan's step 9
measures on dev, not here. Writes eval/results/phase2c/local_throughput.json.
"""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from credit_check import RESULT as CREDIT
from credit_check import rows_of
from label_gold import ROOT
from teacher import INSTRUCTIONS, article_text, rendered

MODEL = "qwen3.5:4b"
URL = "http://127.0.0.1:11434/api/generate"
RESULT = ROOT / "eval" / "results" / "phase2c" / "local_throughput.json"
CANDIDATES = 1_236_122


def one(row: dict) -> dict:
    body = {
        "model": MODEL,
        "prompt": rendered(INSTRUCTIONS, article_text(row)),
        "raw": True,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 700,
            "num_ctx": 8192,
            "stop": ["<|im_end|>"],
        },
    }
    answer = httpx.post(URL, json=body, timeout=600).json()
    return {
        "article_id": row["article_id"],
        "prompt_tokens": answer.get("prompt_eval_count", 0),
        "output_tokens": answer.get("eval_count", 0),
        "seconds": answer.get("total_duration", 0) / 1e9,
    }


def main() -> None:
    picked = json.loads(CREDIT.read_text())["sample"]
    rows = rows_of(set(picked))
    rows = [rows[aid] for aid in picked]
    one(rows[0])  # load the model before timing
    found = {"model": MODEL, "articles": len(rows), "runs": []}
    for workers in (1, 4, 8):
        started = time.time()
        with ThreadPoolExecutor(workers) as pool:
            out = list(pool.map(one, rows))
        wall = time.time() - started
        per_hour = len(rows) / wall * 3600
        found["runs"].append(
            {
                "concurrent": workers,
                "wall_seconds": round(wall, 1),
                "articles_per_hour": round(per_hour),
                "prompt_tokens": sum(o["prompt_tokens"] for o in out),
                "output_tokens": sum(o["output_tokens"] for o in out),
                "full_pass_days": round(CANDIDATES / per_hour / 24, 1),
            }
        )
        print(found["runs"][-1], flush=True)
    RESULT.write_text(json.dumps(found, indent=1) + "\n")


if __name__ == "__main__":
    main()

"""Why local prefill is slow, and which runtime the full pass should use (2C.3).

On the credit check's seeded 50 with the student's short prompt:
  ollama    one request at a time at num_ctx 2048 and 8192, with Ollama's own load_duration and
            prompt_eval_duration, so reloads and context allocation show apart from compute
  mlx       mlx-lm directly on the downloaded Qwen3.5-4B weights: prefill and generation tokens
            a second one article at a time, batched generation, and a prompt cache reused for
            the instruction prefix the articles share
  agree     the kind and the JSON the two runtimes give each article, greedy, compared
Writes eval/results/phase2c/runtime_check.json, one key per mode, each with its settings.
"""

import json
import sys
import time

import httpx
from credit_check import RESULT as CREDIT
from credit_check import rows_of
from label_gold import ROOT
from local_throughput import SHORT
from teacher import article_text, parsed, rendered

RESULT = ROOT / "eval" / "results" / "phase2c" / "runtime_check.json"
OLLAMA = "http://127.0.0.1:11434/api/generate"
MODEL = "Qwen/Qwen3.5-4B"
MAX_TOKENS = 700


def sample_rows() -> list:
    picked = json.loads(CREDIT.read_text())["sample"]
    rows = rows_of(set(picked))
    return [rows[aid] for aid in picked]


def ollama(rows: list) -> dict:
    found = {}
    for ctx in (2048, 8192):
        out = []
        for row in rows:
            body = {
                "model": "qwen3.5:4b",
                "prompt": rendered(SHORT, article_text(row)),
                "raw": True,
                "stream": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0,
                    "num_predict": MAX_TOKENS,
                    "num_ctx": ctx,
                    "stop": ["<|im_end|>"],
                },
            }
            a = httpx.post(OLLAMA, json=body, timeout=600).json()
            out.append(a)
        n = len(out)
        found[f"num_ctx {ctx}"] = {
            "settings": {
                "num_ctx": ctx,
                "concurrent": 1,
                "keep_alive": "30m",
                "prompt": "short",
            },
            "load_seconds": sum(a.get("load_duration", 0) for a in out) / n / 1e9,
            "prompt_seconds": sum(a.get("prompt_eval_duration", 0) for a in out)
            / n
            / 1e9,
            "prompt_tokens": sum(a.get("prompt_eval_count", 0) for a in out) / n,
            "generation_seconds": sum(a.get("eval_duration", 0) for a in out) / n / 1e9,
            "output_tokens": sum(a.get("eval_count", 0) for a in out) / n,
            "total_seconds": sum(a.get("total_duration", 0) for a in out) / n / 1e9,
            "answers": [a.get("response", "") for a in out],
        }
        f = found[f"num_ctx {ctx}"]
        f["prefill_tokens_per_second"] = f["prompt_tokens"] / max(
            f["prompt_seconds"], 1e-9
        )
    return found


def mlx(rows: list) -> dict:
    from mlx_lm import batch_generate, load, stream_generate
    from mlx_lm.models.cache import make_prompt_cache
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(MODEL)
    greedy = make_sampler(temp=0.0)
    prompts = [
        tokenizer.encode(rendered(SHORT, article_text(r)), add_special_tokens=False)
        for r in rows
    ]
    found = {}

    started, answers, stats = time.time(), [], []
    for ids in prompts:
        text, last = "", None
        for last in stream_generate(
            model, tokenizer, ids, max_tokens=MAX_TOKENS, sampler=greedy
        ):
            text += last.text
            if "<|im_end|>" in text:
                break
        answers.append(text.split("<|im_end|>")[0])
        stats.append(last)
    wall = time.time() - started
    found["one at a time"] = {
        "settings": {
            "concurrent": 1,
            "prompt": "short",
            "sampler": "greedy",
            "weights": "bf16",
        },
        "articles_per_hour": round(len(rows) / wall * 3600),
        "prefill_tokens_per_second": sum(s.prompt_tps for s in stats) / len(stats),
        "generation_tokens_per_second": sum(s.generation_tps for s in stats)
        / len(stats),
        "peak_memory_gb": max(s.peak_memory for s in stats),
        "answers": answers,
    }

    for size in (4, 8):
        started = time.time()
        done = []
        for i in range(0, len(prompts), size):
            done += batch_generate(
                model,
                tokenizer,
                prompts[i : i + size],
                max_tokens=MAX_TOKENS,
                sampler=greedy,
            ).texts
        wall = time.time() - started
        found[f"batched {size}"] = {
            "settings": {
                "batch": size,
                "prompt": "short",
                "sampler": "greedy",
                "weights": "bf16",
            },
            "articles_per_hour": round(len(rows) / wall * 3600),
        }

    # the long prompt's shared prefix, its 779 instruction tokens, read once and reused: what a
    # prompt cache buys, on ten articles, against reading the whole prompt each time
    import copy

    from teacher import INSTRUCTIONS

    head = rendered(INSTRUCTIONS, "")
    prefix = tokenizer.encode(
        head[: head.index("<|im_start|>user")], add_special_tokens=False
    )
    longs = [
        tokenizer.encode(
            rendered(INSTRUCTIONS, article_text(r)), add_special_tokens=False
        )
        for r in rows[:10]
    ]
    timings = {}
    for cached in (False, True):
        base = None
        if cached:
            base = make_prompt_cache(model)
            for _ in stream_generate(
                model,
                tokenizer,
                prefix,
                max_tokens=1,
                sampler=greedy,
                prompt_cache=base,
            ):
                pass
        started = time.time()
        for ids in longs:
            cache = copy.deepcopy(base) if cached else None
            rest = ids[len(prefix) :] if cached else ids
            for _ in stream_generate(
                model, tokenizer, rest, max_tokens=1, sampler=greedy, prompt_cache=cache
            ):
                pass
        timings["cached" if cached else "uncached"] = (time.time() - started) / len(
            longs
        )
    found["long prompt prefix"] = {
        "settings": {
            "prefix_tokens": len(prefix),
            "articles": len(longs),
            "max_tokens": 1,
        },
        "prefill_seconds_per_article": timings,
    }
    return found


def agree(found: dict) -> dict:
    ollama_answers = found["ollama"]["num_ctx 8192"]["answers"]
    mlx_answers = found["mlx"]["one at a time"]["answers"]
    kinds = [
        ((parsed(a) or {}).get("kind"), (parsed(b) or {}).get("kind"))
        for a, b in zip(ollama_answers, mlx_answers, strict=True)
    ]
    return {
        "articles": len(kinds),
        "same_kind": sum(a == b for a, b in kinds),
        "both_parse": sum(a is not None and b is not None for a, b in kinds),
        "same_json": sum(
            (parsed(a) or {}) == (parsed(b) or {})
            for a, b in zip(ollama_answers, mlx_answers, strict=True)
        ),
    }


def main(runs: list) -> None:
    rows = sample_rows()
    found = json.loads(RESULT.read_text()) if RESULT.exists() else {}
    if "ollama" in runs:
        found["ollama"] = ollama(rows)
    if "mlx" in runs:
        found["mlx"] = mlx(rows)
    if "agree" in runs:
        found["agree"] = agree(found)
    RESULT.write_text(json.dumps(found, indent=1) + "\n")
    print(
        json.dumps(
            {
                k: {
                    m: {x: y for x, y in v.items() if x != "answers"}
                    for m, v in part.items()
                }
                if k != "agree"
                else part
                for k, part in found.items()
            },
            indent=1,
            default=str,
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:] or ["ollama", "mlx", "agree"])

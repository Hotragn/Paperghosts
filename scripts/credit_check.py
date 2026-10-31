"""The Tinker credit check (2C.3, before any bulk spend): real tokens and cost per article for
the teacher and for 4B reading, on a seeded 50 of the candidates the reader's full pass reads.
Tinker's billing gives cost and rates, but not the balance left, which only the console shows.

  pool       the training pool, every candidate and near-miss article outside split.json's
             out_of_pool, with its group in the inclusive grouping, into data/gold/pool.json.zst
  measure    the 50 through the teacher and through 4B, into eval/results/phase2c/credit_check.json
"""

import json
import random
import sys
import time
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

import zstandard
from check_leakage import SPLIT, frame, paths_of
from label_gold import ROOT, rows_in
from teacher import INSTRUCTIONS, STUDENT, TEACHER, read, system_prompt

POOL = ROOT / "data" / "gold" / "pool.json.zst"
RESULT = ROOT / "eval" / "results" / "phase2c" / "credit_check.json"
SAMPLE = 50


def pool(root: Path = ROOT) -> dict:
    """The pool's articles in frame order, each with its group and whether it is a candidate."""
    found, out = frame(root), set(json.loads(SPLIT.read_text())["out_of_pool"])
    kept = [i for i, aid in enumerate(found["ids"]) if aid not in out]
    return {
        "ids": [found["ids"][i] for i in kept],
        "group": [found["group"][i] for i in kept],
        "candidate": [i < found["candidates"] for i in kept],
    }


def loaded() -> dict:
    with zstandard.open(POOL, "rt") as f:
        return json.load(f)


def rows_of(wanted: set, root: Path = ROOT) -> dict:
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=8) as workers:
        parts = workers.map(partial(rows_in, wanted=wanted), paths_of(root))
        return {row["article_id"]: row for part in parts for row in part}


def billed(model: str, since: datetime) -> dict:
    """What Tinker's billing records for the model since a UTC hour: cost and tokens by event."""
    import warnings

    import tinker

    from paperghosts.config import setting

    warnings.simplefilter("ignore", FutureWarning)
    rest = tinker.ServiceClient(
        api_key=setting("TINKER_API_KEY").get()
    ).create_rest_client()
    end = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    found = {}
    for bucket in rest.get_billing_usage(since, end).result().data:
        if bucket.base_model != model:
            continue
        info = bucket.event_info.model_dump()
        row = found.setdefault(info["type"], {"usd": 0.0, "tokens": 0, "rates": set()})
        row["usd"] += bucket.estimated_cost_usd or 0
        row["tokens"] += info.get("token_count") or 0
        if bucket.effective_rate_usd_per_million_tokens:
            row["rates"].add(round(bucket.effective_rate_usd_per_million_tokens, 3))
    return {k: v | {"rates": sorted(v["rates"])} for k, v in found.items()}


def main() -> None:
    run = sys.argv[1]
    if run == "pool":
        made = pool()
        POOL.parent.mkdir(parents=True, exist_ok=True)
        with zstandard.open(POOL, "wt") as f:
            json.dump(made, f)
        print(len(made["ids"]), "pool articles,", sum(made["candidate"]), "candidates")
    elif run == "measure":
        made = loaded()
        candidates = [
            aid for aid, c in zip(made["ids"], made["candidate"], strict=True) if c
        ]
        picked = sorted(
            random.Random("2C.3 credit check sample").sample(sorted(candidates), SAMPLE)
        )
        rows = rows_of(set(picked))
        rows = [rows[aid] for aid in picked]
        since = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        found = {"sample": picked, "measured_at": since.isoformat()}
        for name, model, system in (
            ("teacher", TEACHER, system_prompt()),
            ("student", STUDENT, INSTRUCTIONS),
        ):
            started = time.time()
            out = read(rows, model, system)
            ok = [o for o in out if o and "error" not in o]
            found[name] = {
                "model": model,
                "articles": len(ok),
                "errors": len(out) - len(ok),
                "seconds": round(time.time() - started, 1),
                "prompt_tokens": sum(o["prompt_tokens"] for o in ok),
                "output_tokens": sum(o["output_tokens"] for o in ok),
                "answers": out,
            }
        time.sleep(90)  # billing lags the requests a little
        for name in ("teacher", "student"):
            found[name]["billed"] = billed(found[name]["model"], since)
        RESULT.write_text(json.dumps(found, indent=1) + "\n")
        print(
            json.dumps(
                {
                    k: {x: y for x, y in v.items() if x != "answers"}
                    if isinstance(v, dict)
                    else v
                    for k, v in found.items()
                    if k != "sample"
                },
                indent=1,
            )
        )


if __name__ == "__main__":
    main()

"""The live reading demo: one dev article read by the local teacher, gemma4:26b through Ollama, with
the teacher's prompt (round 3's instructions with the value-and-quote rule, then POLICY.md), and
each field printed with its quote and the verifier's ruling: VERIFIED, NOT VERIFIED (the quote isn't
in the text, so a training label would drop it), or NOT STATED. Dev articles only; gold stays
untouched until eval B.

  uv run python scripts/read_one.py ARTICLE_ID [NUM_CTX]
"""

import sys

from label_gold import articles, squeezed
from local_teacher import one
from teacher import FIELDS, parsed, system_prompt, verified

MODEL = "gemma4:26b-a4b-it-qat"
THRESHOLD = 0.70  # the verifier's threshold, calibrated on dev (RDR-9)


def ruled(name: str, stated, kept) -> str:
    if not stated:
        return f"{name:15} NOT STATED"
    mark = "VERIFIED" if kept else "NOT VERIFIED"
    return f"{name:15} {mark:12} {stated['value']}\n{'':28}quote: “{stated['quote']}”"


def main(aid: str, num_ctx: int | None = None) -> None:
    row = articles().get(aid)
    if row is None or row["split"] != "dev":
        sys.exit(f"{aid} is not a dev article; the demo reads dev only")
    answer = one(row, MODEL, system_prompt(), num_ctx=num_ctx)
    label = parsed(answer["answer"])
    print(f"{row.get('paper')} · {row.get('date')}\n{row.get('headline') or ''}\n")
    print(
        f"model {MODEL}, {answer['prompt_tokens']} prompt tokens, {answer['seconds']:.1f} s\n"
    )
    if label is None:
        print("The answer had no label to read:\n" + answer["answer"])
        return
    text = squeezed(f"{row.get('headline') or ''}\n{row.get('text') or ''}")
    kept = verified({**label, "article_id": aid}, text, THRESHOLD)[0]
    print(f"{'kind':15} {label['kind']}\n")
    for name in FIELDS:
        print(ruled(name, label.get(name), kept.get(name)))
    people = label.get("people") or []
    for person in people:
        print(ruled("person", person, person in kept["people"]))
    if not people:
        print(ruled("people", None, None))


if __name__ == "__main__":
    main(sys.argv[1], *map(int, sys.argv[2:]))

"""The teacher (2C.3): Qwen3.5-397B on Tinker labels an article under POLICY.md, and the quote
verifier keeps only the values whose quotes are in the article (SRS RDR-9).

The prompt is the instructions below and POLICY.md in full; its sha256 goes on every label. The
model answers in the label record's shape. A value is kept only if its quote scores at least
the threshold against the article and its choice is the schema's; otherwise it's dropped, never
kept. The threshold is calibrated on dev, and gold stays untouched until eval B.

  dev [ROUND]         the teacher on all 150 dev articles, scored against the frozen dev labels
                      with Wilson intervals, and the verifier's threshold calibrated on them
"""

import hashlib
import json
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from difflib import SequenceMatcher

from label_gold import CHOICES, FIELDS, KINDS, POLICY, ROOT

TEACHER = "Qwen/Qwen3.5-397B-A17B"
STUDENT = "Qwen/Qwen3.5-4B"
RESULTS = ROOT / "eval" / "results" / "phase2c"
INSTRUCTIONS = """You label one newspaper article for a historical archive of ghost reports, under the labelling policy below. Read the article, decide its one kind under the policy's rules, and for a report fill the fields the text states.

Answer with one JSON object and nothing else:
{"kind": "report|fiction|idiom|religious|advert|other", "kind_quote": "<the span that shows the kind>",
 "place": F, "place_state": F, "seen": F, "outcome": F, "specific_place": F, "place_type": F, "precision": F,
 "people": [F, ...]}
where each F is an object {"value": "...", "quote": "..."} or null, never a bare string: the value says it in your words, and the quote is the text's own span. For example:
{"kind": "report", "kind_quote": "the family have been disturbed every night",
 "place": {"value": "the old Hale farmhouse, Milford", "quote": "the old farmhouse"},
 "place_state": {"value": "Connecticut", "quote": "MILFORD, Conn."},
 "seen": {"value": "knockings upon the walls", "quote": "knockings upon the walls"},
 "outcome": {"value": "unexplained", "quote": "which no search has been able to explain"},
 "specific_place": {"value": "the old farmhouse", "quote": "the old farmhouse"},
 "place_type": {"value": "house", "quote": "the old farmhouse"},
 "precision": {"value": "building", "quote": "the old farmhouse"},
 "people": [{"value": "the family of Mr. John Hale", "quote": "The family of Mr. John Hale"}]}

- Fields are for reports only; for any other kind every field is null and people is [].
- Every quote is an exact span of the headline or OCR text, copied as printed, OCR errors and all. Use the shortest span that states the value.
- A value the text doesn't state is null. Never infer one.
- outcome is one of explained, hoax, unexplained, unknown. place_type is one of house, church, cemetery, inn_or_hotel, road_or_bridge, public_building, ship, other. precision is one of town, street, building.

How to apply the policy, in its own terms:
- The kind follows how the article uses its ghost word. If the only ghost, spirit, haunt or spectre in it is a figure of speech, the kind is idiom, whatever the article is about: politics, sport, a profile. other is for names and titles, social events, OCR accidents, ordinary senses of spirit or medium, and essays about ghosts in general.
- A joke, quip, squib, poem, story, serial or comic sketch is fiction, whatever its subject, even a short one in a column of paragraphs.
- One particular claim makes a report: a named person, a place or an occasion with a ghost, spirit or manifestation told as having happened. It counts inside an essay, a round-up, a column or an article cut off in the archive. Take the fields from the first claim told in particulars.
- seen is what was seen, heard or felt: the apparition, the noises or the message, not the house or the occasion.
- people are those who saw, heard, felt or claimed it, and at a seance the medium and the sitters the text names. Leave out anyone who only reports it, investigates it, is told of it afterwards, or plays the ghost.

THE POLICY
"""
# Round 3's lines above restate POLICY.md; each was prompted by dev's round 2 confusions, never
# by one article. The kind line: 14 dev idioms called other, among them a political "Ghost of
# Major Andre" and "CHOLERA SPECTRE". The fiction line: 7 fictions called other, quips and
# sketches. The report line: 7 reports called other, claims inside essays and round-ups (rules 6,
# 16, 17). The seen and people lines: seen right on 7 of 24 reports, people on 6.


def system_prompt(policy: str | None = None) -> str:
    return INSTRUCTIONS + (policy if policy is not None else POLICY.read_text())


def prompt_sha256(system: str) -> str:
    return hashlib.sha256(system.encode()).hexdigest()


def rendered(system: str, article: str) -> str:
    """Qwen's ChatML, rendered by hand, with an empty think block so the model answers at once."""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{article}<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def article_text(row: dict) -> str:
    return f"{row.get('paper') or ''} · {row.get('date') or ''}\nheadline: {row.get('headline') or ''}\n---\n{row.get('text') or ''}"


def parsed(answer: str) -> dict | None:
    """The answer's JSON object, or None where there is none or its kind isn't POLICY.md's."""
    start, end = answer.find("{"), answer.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        found = json.loads(answer[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(found, dict) or found.get("kind") not in KINDS:
        return None

    def shaped(stated):  # a malformed value is dropped, never kept
        ok = (
            isinstance(stated, dict)
            and isinstance(stated.get("value"), str)
            and isinstance(stated.get("quote"), str)
        )
        return {"value": stated["value"], "quote": stated["quote"]} if ok else None

    people = found.get("people") if isinstance(found.get("people"), list) else []
    return {
        "kind": found["kind"],
        "kind_quote": found.get("kind_quote")
        if isinstance(found.get("kind_quote"), str)
        else "",
        **{name: shaped(found.get(name)) for name in FIELDS},
        "people": [p for p in map(shaped, people) if p],
    }


def normal(text: str) -> str:
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text.lower()).split())


def score(quote: str, text: str) -> float:
    """How well a quote matches its best place in the text, from 0 to 1. A match ignoring case,
    spacing and punctuation is 1; otherwise the best window of the quote's length, found by its
    words, is compared character by character."""
    q, t = normal(quote), normal(text)
    if not q:
        return 0.0
    if q in t:
        return 1.0
    words, tw = q.split(), t.split()
    n = len(words)
    wanted = set(words)
    hits = sorted(
        range(max(1, len(tw) - n + 1)),
        key=lambda i: -sum(w in wanted for w in tw[i : i + n]),
    )[:5]
    return max(
        SequenceMatcher(None, q, " ".join(tw[i : i + n]), autojunk=False).ratio()
        for i in hits
    )


def verified(label: dict, text: str, threshold: float) -> tuple[dict, list]:
    """The label with each value kept only if its quote scores at least the threshold and its
    choice is the schema's; and the names of the fields it dropped something from."""

    def keep(name, stated):
        if (
            not isinstance(stated, dict)
            or not stated.get("value")
            or not stated.get("quote")
        ):
            return None
        if name in CHOICES and stated["value"] not in CHOICES[name]:
            return None
        return stated if score(stated["quote"], text) >= threshold else None

    kept, dropped = dict(label), []
    report = label.get("kind") == "report"
    for name in FIELDS:
        given = label.get(name)
        kept[name] = keep(name, given) if report else None
        if given and kept[name] is None:
            dropped.append(name)
    people = [p for p in (label.get("people") or []) if report and keep("people", p)]
    if len(people) < len(label.get("people") or []):
        dropped.append("people")
    kept["people"] = people
    return kept, dropped


def final(answer: str) -> str:
    """The answer after the model's reasoning: what follows Qwen's </think> or gpt-oss's final
    channel. Thinking traces are never training targets."""
    for mark in ("<|channel|>final<|message|>", "</think>"):
        if mark in answer:
            answer = answer.rsplit(mark, 1)[1]
    for end in ("<|im_end|>", "<|return|>", "<|end|>"):
        answer = answer.replace(end, "")
    return answer


def read(
    rows: list,
    model: str,
    system: str,
    max_tokens: int = 700,
    workers: int = 16,
    thinking: bool = False,
    samples: int = 1,
    temperature: float = 0.0,
) -> list:
    """Each article through the model on Tinker: its answers, its token counts and the time.
    With thinking, the model's own chat template asks it to reason first; without, the prompt
    is the hand-rendered ChatML with an empty think block. Several samples read the prompt once."""
    import tinker

    from paperghosts.config import setting

    service = tinker.ServiceClient(api_key=setting("TINKER_API_KEY").get())
    client = service.create_sampling_client(base_model=model)
    tokenizer = client.get_tokenizer()
    stops = ["<|return|>"] if model.startswith("openai/") else ["<|im_end|>"]
    params = tinker.SamplingParams(
        max_tokens=max_tokens, temperature=temperature, stop=stops
    )

    def prompt(row):
        if not thinking:
            return rendered(system, article_text(row))
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": article_text(row)},
        ]
        extra = (
            {"reasoning_effort": "medium"}
            if model.startswith("openai/")
            else {"enable_thinking": True}
        )
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, **extra
        )

    def one(row):
        ids = tokenizer.encode(prompt(row), add_special_tokens=False)
        for attempt in range(4):
            try:
                out = client.sample(
                    tinker.ModelInput.from_ints(ids), samples, params
                ).result()
                answers = [tokenizer.decode(s.tokens) for s in out.sequences]
                return {
                    "article_id": row["article_id"],
                    "answer": final(answers[0]),
                    "answers": [final(a) for a in answers],
                    "prompt_tokens": len(ids),
                    "output_tokens": sum(len(s.tokens) for s in out.sequences),
                    "hit_limit": sum(
                        len(s.tokens) >= max_tokens for s in out.sequences
                    ),
                    "model": model,
                    "thinking": thinking,
                    "samples": samples,
                    "temperature": temperature,
                    "prompt_sha256": prompt_sha256(system),
                    "at": datetime.now(UTC).isoformat(timespec="seconds"),
                }
            except (
                tinker.TinkerError,
                TimeoutError,
                ConnectionError,
            ) as error:  # wait, then retry
                if attempt == 3:
                    return {
                        "article_id": row["article_id"],
                        "error": type(error).__name__,
                    }
                time.sleep(5 * (attempt + 1))
        return None

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, rows))


def voted(answers: list) -> dict | None:
    """The majority kind of several parsed answers, and the first answer that has it: fields come
    from a sample that agrees with the majority. With no majority, the first parsed answer."""
    found = [a for a in map(parsed, answers) if a]
    if not found:
        return None
    kinds = [a["kind"] for a in found]
    top = max(set(kinds), key=kinds.count)
    return (
        next(a for a in found if a["kind"] == top) if kinds.count(top) > 1 else found[0]
    )


def quotes(label: dict) -> list:
    """Each stated value's quote in a label, field by field."""
    found = [(n, label[n]["quote"]) for n in FIELDS if label.get(n)]
    return found + [("people", p["quote"]) for p in label.get("people") or []]


def calibrated(answers: dict, labels: dict, texts: dict, step: float = 0.05) -> dict:
    """The verifier's curve on dev: at each threshold, the share of the teacher's values it
    rejects, of those that agree with the dev label and of those that don't, and the share of
    dev's true quotes that pass against another article's text. The threshold is the lowest
    whose cross-article pass rate is at most 1%."""
    from second_pass import same

    rng = random.Random("2C.3 verifier negatives")
    ids = sorted(labels)
    negatives = [
        score(q, texts[rng.choice([j for j in ids if j != aid])])
        for aid in ids
        for _, q in quotes(labels[aid])
    ]
    values = []  # (score, agrees with the dev label)
    for aid, label in answers.items():
        if label.get("kind") != "report" or labels[aid]["kind"] != "report":
            continue
        for name, quote in quotes(label):
            agrees = same(name, labels[aid], label, texts[aid])
            values.append((score(quote, texts[aid]), agrees))
    curve = []
    for k in range(round(1 / step) + 1):
        t = round(k * step, 2)
        good, bad = [s for s, a in values if a], [s for s, a in values if not a]
        curve.append(
            {
                "threshold": t,
                "rejected": sum(s < t for s, _ in values) / max(1, len(values)),
                "rejected_agreeing": sum(s < t for s in good) / max(1, len(good)),
                "rejected_disagreeing": sum(s < t for s in bad) / max(1, len(bad)),
                "negatives_passing": sum(s >= t for s in negatives)
                / max(1, len(negatives)),
            }
        )
    chosen = next(c for c in curve if c["negatives_passing"] <= 0.01)
    return {
        "values": len(values),
        "negatives": len(negatives),
        "threshold": chosen["threshold"],
        "at_threshold": chosen,
        "curve": curve,
    }


def recall(labels: dict, kept: dict) -> dict:
    """Of dev's reports, how many the teacher calls reports, with a Wilson interval."""
    from paperghosts.stats import wilson

    reports = [aid for aid, label in labels.items() if label["kind"] == "report"]
    hits = sum(kept[aid]["kind"] == "report" for aid in reports)
    return {
        "found": hits,
        "reports": len(reports),
        "interval": wilson(hits, len(reports)),
    }


def dev_round(
    round_name: str,
    model: str = TEACHER,
    thinking: bool = False,
    samples: int = 1,
    temperature: float = 0.0,
    max_tokens: int = 700,
) -> dict:
    from label_gold import OUT, articles, saved, squeezed
    from second_pass import agreed

    rows = {aid: r for aid, r in articles().items() if r["split"] == "dev"}
    labels = {r["article_id"]: r for r in saved(OUT["dev"])}
    texts = {
        aid: squeezed(f"{r.get('headline') or ''}\n{r.get('text') or ''}")
        for aid, r in rows.items()
    }
    system = system_prompt()
    raw = ROOT / "data" / "teacher" / f"dev_{round_name}.jsonl"
    if (
        raw.exists()
    ):  # score a round's saved answers again, without asking the model twice
        out = [json.loads(line) for line in raw.read_text().splitlines()]
    else:
        out = read(
            [rows[a] for a in sorted(rows)],
            model,
            system,
            max_tokens,
            thinking=thinking,
            samples=samples,
            temperature=temperature,
        )
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text("".join(json.dumps(o) + "\n" for o in out))
    answers, unparsed = {}, []
    for o in out:
        label = (
            (voted(o["answers"]) if samples > 1 else parsed(o.get("answer") or ""))
            if o and "error" not in o
            else None
        )
        if label is None:
            unparsed.append(o["article_id"] if o else None)
            label = {
                "kind": "other",
                "kind_quote": "",
            }  # no answer: scored as a miss, never kept
        answers[o["article_id"]] = {
            "article_id": o["article_id"],
            "people": [],
            **label,
        }
    calibration = calibrated(answers, labels, texts)
    kept = {
        aid: {**verified(a, texts[aid], calibration["threshold"])[0], "article_id": aid}
        for aid, a in answers.items()
    }
    pairs = [(labels[aid], kept[aid]) for aid in sorted(kept)]
    raw_pairs = [(labels[aid], answers[aid]) for aid in sorted(answers)]
    found = {
        "round": round_name,
        "model": model,
        "thinking": thinking,
        "samples": samples,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "hit_limit": sum(o.get("hit_limit", 0) for o in out if o),
        "errors": sum(1 for o in out if not o or "error" in o),
        "report_recall": recall(labels, kept),
        "prompt_sha256": prompt_sha256(system),
        "articles": len(out),
        "unparsed": unparsed,
        "prompt_tokens": sum(o.get("prompt_tokens", 0) for o in out if o),
        "output_tokens": sum(o.get("output_tokens", 0) for o in out if o),
        "accuracy_verified": agreed(pairs, texts),
        "accuracy_unverified": agreed(raw_pairs, texts),
        "verifier": calibration,
    }
    (RESULTS / f"teacher_dev_{round_name}.json").write_text(
        json.dumps(found, indent=1) + "\n"
    )
    return found


def confusion(round_name: str) -> dict:
    """The dev label's kind against the teacher's, from a round's saved answers."""
    from label_gold import OUT, saved

    labels = {r["article_id"]: r["kind"] for r in saved(OUT["dev"])}
    found = {}
    for line in (
        (ROOT / "data" / "teacher" / f"dev_{round_name}.jsonl").read_text().splitlines()
    ):
        answer = json.loads(line)
        label = parsed(answer.get("answer") or "")
        row = found.setdefault(labels[answer["article_id"]], {})
        kind = label["kind"] if label else "unparsed"
        row[kind] = row.get(kind, 0) + 1
    return found


if __name__ == "__main__":
    run, *rest = sys.argv[1:]
    if run == "confusion":
        found = {r: confusion(r) for r in rest}
        (RESULTS / "teacher_confusion.json").write_text(
            json.dumps(found, indent=1) + "\n"
        )
        for r, m in found.items():
            print(r, "rows: dev label; columns: teacher")
            for label, row in sorted(m.items()):
                print(f"  {label:10}", dict(sorted(row.items(), key=lambda kv: -kv[1])))
    if run == "dev":
        import argparse

        given = argparse.ArgumentParser()
        given.add_argument("round")
        given.add_argument("--model", default=TEACHER)
        given.add_argument("--thinking", action="store_true")
        given.add_argument("--samples", type=int, default=1)
        given.add_argument("--temperature", type=float, default=0.0)
        given.add_argument("--max-tokens", type=int, default=700)
        a = given.parse_args(rest)
        found = dev_round(
            a.round, a.model, a.thinking, a.samples, a.temperature, a.max_tokens
        )
        brief = {
            k: v
            for k, v in found.items()
            if k not in ("verifier", "accuracy_unverified")
        }
        brief["verifier"] = {k: v for k, v in found["verifier"].items() if k != "curve"}
        print(json.dumps(brief, indent=1, default=str))

# Entire: the build's paper trail

Entire records each commit's agent session as a checkpoint. A commit names its checkpoint in an
`Entire-Checkpoint:` trailer, and the checkpoint is a ref, `refs/entire/checkpoints/<last two
characters>/<id>`, pushed to origin. `scripts/article_numbers.py` counts them: 122 commits carry
the trailer, across 123 refs.

## Two sessions that show the problem solving

| What it shows | Commit | Checkpoint |
|---|---|---|
| **Reprint chaining, and its fix:** chained clusters grew through near matches, so a printing now joins a story only by matching its first printing directly | `1a2f8b7` | `01M67W8SMF2WGS6DNG76TSEAXP` |
| **A judge ruling its own case, caught:** the first rulings were the first labeller's, so fresh judges re-ruled all 69 disputes blind, and the blind ruling was taken in 28 of the 30 that differed | `537e605`, `35e8a53` | `01M69P1PXCDRMN4FCBZRDQAGV2`, `01M69PCNVRXPX8DD1EWAHB57JF` |

## What they cost
From `entire checkpoint tokens <id> --json`:
- **The reprint chaining fix** (`01M67W8SMF2WGS6DNG76TSEAXP`): 59,983,120 tokens over 73 API calls. 48,106,921 were cache reads and 151,830 were output, plus 11,438,698 in subagents.
- **The blind re-ruling** (`01M69PCNVRXPX8DD1EWAHB57JF`): 26,688,512 tokens over 34 calls. 24,916,651 were cache reads and 20,603 were output, plus 1,703,781 in subagents.

`entire recap` shows no activity here, because its figures come from Entire's server analysis, which this repo doesn't use. `entire dispatch` was not run: its cloud mode needs a published repository, and its local mode starts another agent on this laptop.

## Entire's own redaction
Entire redacts secrets by itself, on by default, when it writes a checkpoint (docs.entire.com, "Privacy and redaction" and "Security"). Its layers:
- an entropy check
- Betterleaks' known secret formats
- provider key prefixes
- credentialed URLs and database connection strings
- credential assignments
- rules the user adds

It doesn't rewrite the raw agent session files, and the docs call it a safety net rather than a guarantee. This repo now has a personal rule pack in `.entire/redactors/local/` (gitignored, so it's never committed) that redacts the other local account's name from every new checkpoint.

## Before either is published
- **The secret scan has passed:** all history, all 123 checkpoint refs. No secret, and the hostname nowhere. The 4 MongoDB URIs are test fixtures. Two `.env` values appear, but they're plain names the docs print: the Sentry project and a model name.
- **Redacted locally, not yet pushed:** each checkpoint holds the whole accumulated transcript, and its `0/full.jsonl` held step 1.7's process listing, which named another local account.
  - 121 of the 127 refs had it, in 19 versions of the file. Each listing is now one `[redacted: another local account's process list]` line, with nothing else changed, and each `content_hash.txt` is recomputed.
  - Tested on a clone: `entire checkpoint list`, `explain` on two rewritten and two untouched checkpoints (with their raw transcripts), and `doctor` all pass, and the name appears in no ref.
  - The originals are kept in a verified git bundle.
  - Force-pushing the 121 refs needs the owner's permission in this session.
- **Publishing** a session as "My Agent Session" on DEV is the owner's step.

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

## Before either is published
- **The secret scan has passed:** all history, all 123 checkpoint refs. No secret, and the hostname nowhere. The 4 MongoDB URIs are test fixtures. Two `.env` values appear, but they're plain names the docs print: the Sentry project and a model name.
- **Not yet redacted:** each checkpoint holds the whole accumulated transcript (about 120 MB). Its `0/full.jsonl` includes step 1.7's process listing, which names another local account and its browsers' paths. It has to be redacted before a session is embedded or the repo goes public. That means rewriting the checkpoint refs and force-pushing them, so it's the owner's call.
- **Publishing** a session as "My Agent Session" on DEV is the owner's step.

# Paper Ghosts

Type a US town and read the ghost reports its newspapers printed between 1774 and 1963. The reports come from the AmericanStories dataset and the Library of Congress page scans. The site never writes a ghost story: every claim links to the clipping it came from.

This is a work in progress. The plan is in [`Docs/BUILD-PLAN.md`](Docs/BUILD-PLAN.md), and where the build stands is in [`Docs/RESUME.md`](Docs/RESUME.md).

## Run it

You need `uv`, Node and `pnpm`. Keys go in `.env`, which git ignores.

```bash
make setup   # the Python 3.12 environment and the web shell's packages
make lint    # ruff, oxlint and the TypeScript check
make test    # pytest
make keys    # checks every key by shape and one cheap call; never prints a value
make web     # the web shell at http://localhost:5173
```

Temporal runs locally. Start the dev server and a worker in two terminals, then run the smoke workflow in a third:

```bash
make temporal   # dev server; state in data/temporal/, UI at http://localhost:8233
make worker
make smoke      # one workflow: heartbeats, an injected failure, a retry
```

The other targets print the phase that builds them.

## What it can't do

Filled in as limits are found.

## Failure log

Filled in as failures are found.

## Credits

- Article text: AmericanStories, from Harvard's Dell Research (CC-BY-4.0)
- Page scans: Library of Congress, Chronicling America (public domain)

The code is MIT licensed; see [LICENSE](LICENSE).

# Paper Ghosts: brand

**Name:** Paper Ghosts. The site is **The Morgue**: the room where a newspaper keeps its clippings. The look comes from `Docs/UI-IDEAS.md`: a newspaper morgue after hours.

## The mark
- **What it is:** a newspaper page that is itself the ghost.
  - The bottom edge is torn into a ghost's hem.
  - Two hollow, drooping eyes and an open mouth sit in its columns.
  - It has a nameplate bar, column rules and a dog-eared corner in oxblood.
- **Files,** in `web/public/brand/`, all drawn by hand as SVG:
  - `logo.svg`, the full-colour mark
  - `logo-mono.svg`, one colour (`currentColor`), with the fold, eyes, mouth and rules cut out of the page
  - `logo-16.png` to `logo-512.png`, rendered from `logo.svg`
  - `social-card.svg` and `social-card.jpg`, 1200×630
- **At 16 px** the eyes and mouth still read; the hem blurs into an edge.
- **Never** add a glow, a gradient or a drop shadow to the mark.

## Colour
The tokens are in `web/src/index.css`, for two lights: lights on, the archive by day, and lights off, the reading room.

| Token | Lights on | Lights off | Where |
|---|---|---|---|
| `--bg` | newsprint `#E9E2D0` | reading-room dark `#111214` | the page |
| `--text` | ink `#1B1916` | newsprint `#E9E2D0` | reading text |
| `--card` | `#F4EEDF` | `#1A1B1E` | an open case |
| `--envelope` | manila `#D9C79F` | `#1D1C1A` | a closed report |
| `--muted` | `#4A4339` | `#B9B09C` | labels and notes |
| `--stamp-ink` | oxblood `#8A2920` | `#E0796D` | outcome stamps only |
| `--link` | blue pencil `#2F5C9E` | `#8DAEE3` | links and the archive's notes |
| `--lamp` | ghost light `#F0C987` | the same | the lamp, quote marks and focus rings |
| `--rule` | foxing `#8C6A43` | `#6E5537` | thin rules |

`uv run python scripts/check_contrast.py` checks every text pairing against WCAG AA (4.5:1). All 20 pass, from 5.17 to 15.15, and `tests/test_check_contrast.py` keeps them passing.

## Type
All four are Google Fonts, self-hosted through Fontsource, so the page never calls Google:
- **UnifrakturMaguntia,** blackletter, for the nameplate only
- **Bodoni Moda** for headline decks
- **Newsreader** for reading text and transcriptions
- **Courier Prime** for labels, dates, filing numbers and stamps

## Voice
The archive's librarian: plain, dry and exact.
- Say what the paper printed and what it didn't: "Story place not stated", "Outcome unknown".
- Never sensational: no "spooky", no puns, no "chilling".
- Never say the site holds "every ghost". It holds the reports it has filed, and says how many.
- A report of hearing voices or of insanity (`POLICY.md` rule 2) gets no ghostly framing, only what the text says.

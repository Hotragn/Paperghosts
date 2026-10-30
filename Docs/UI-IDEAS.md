# Paper Ghosts: how it should look and feel

## The idea
A newspaper morgue after hours. You stayed late in the reading room. The overhead lights are off, one lamp is on, and the drawers are full of clippings nobody has asked for in a hundred years.

Everything on the site should feel like it came out of that room: paper, ink, typewritten labels, rubber stamps, a microfilm reel. Nothing should feel like it came from a Halloween store or a website template.

The scans do the scaring. A real 1850 column about knocking in the walls is creepier than any effect we could add. The design's job is to light it well and then get out of the way.

## What we kept from the first round of ideas
- **Cinematic horror:** the restraint, the dark space, the slow fades. Kept.
- **Dark academia:** the historical type and real materials. Kept, but they come from a newsroom, not an occult library. No tarot cards, no alchemy symbols.
- **Obsidian monolith:** the cursor flashlight. Kept, as the reading lamp.
- **Dark glassmorphism:** dropped. Frosted glass and glowing orbs are what every generated site looks like right now. The one part worth keeping, the feeling of looking through glass, comes back as the microfilm reader's screen.

## Materials and color
Every color is something you could find in that room.

| Name | Hex | Where it goes |
|---|---|---|
| Reading-room dark | `#111214` | Background with the lights off. A blue-black, not pure black. |
| Newsprint | `#E9E2D0` | Paper in daylight mode, and text with the lights off |
| Ink | `#1B1916` | Text in daylight mode |
| Lamp | `#F0C987` | The warm pool of light, and focus rings |
| Stamp red | `#A3352B` | Outcome stamps and the one main button. Nothing else. |
| Blue pencil | `#2F5C9E` (daylight), `#8DAEE3` (lights off) | The archive's own notes, because editors marked up copy in blue pencil |
| Foxing | `#8C6A43` | Aged paper edges and thin rules |

Treat these as starting points. Tune them against the real scans, and check every text pairing for contrast.

There are two modes, switched by a lamp pull-chain at the top right:
- **Lights off:** the reading room. The scans glow under the lamp. This is the default at night or when the device is in dark mode.
- **Lights on:** the archive by day, with a newsprint background and ink text.

## Type
- **Nameplate:** "Paper Ghosts" in blackletter (UnifrakturMaguntia), the way newspapers have always set their names. It appears once, in the masthead, and nowhere else.
- **Headlines:** Bodoni Moda, stacked in "decks" the way 19th-century papers did it: a large top line, then smaller lines beneath. Made-up example of the format only; the site shows nothing but real headlines:
  > A HAUNTED HOUSE.
  > Strange Knockings Heard Nightly.
  > The Family Have Left the Premises.
- **Reading text:** Newsreader, built for long reading on screens, with optical sizes. Use it for transcriptions and all body copy.
- **Labels:** Courier Prime, like a typed envelope label. Use it for dates, paper names and filing numbers.
- **Loading:** self-host every font (Fontsource), so opening the page never calls Google.
- **Never:** Cinzel, Playfair Display, Montserrat, or Inter as a display face. They are the stock "premium" fonts of generated sites.

## The rooms (pages)
- **Front page:**
  - A masthead with the nameplate, plus a newspaper "ear" in the corner: "Every ghost the papers printed, 1774–1963".
  - One search field styled like a library request slip ("Town and state"), with one stamp-red button: **Pull the file**.
  - Below it, **Printed on this night**: a real clipping printed on today's date in some past year, picked from the archive.
  - A slow ticker of real headlines.
- **A town's drawer:**
  - Each report is a manila envelope with a typed label (date, paper, one-line summary) and its outcome stamp.
  - A small atlas-style map sits beside the envelopes.
  - A plain count line: "3 reports, 1850–1852".
- **A case:**
  - The clipping, large, under the lamp, with slightly uneven scissor-cut edges. Its transcription sits beside it, with a toggle to show the raw scanned text.
  - The facts, on a typed index card.
  - What happened next: a column of follow-up clippings, each with its dateline.
  - The person behind the ghost, when one is found: the death notice clipped beside the report, with how sure the link is, written in blue pencil.
  - Then and now, followed by the source link to the Library of Congress page.
  - It ends with **-30-**, the mark reporters typed at the end of a story.
- **The reel (the whole archive):**
  - The decades scroll past like microfilm, with frame numbers down the side.
  - The chart of ghost reports per million articles is drawn like a page from an 1870s statistical atlas: fine lines, flat hand-tinted colors, no gradients.
- **Walks:**
  - A printable "assignment sheet": numbered stops, each one a dateline plus its clipping, with the map.
  - It prints cleanly on paper.
- **Not found:** "This page was never filed."

There is no leaderboard, no login and no "join" button.

## Signature moments (each one means something)
1. **The lamp.**
   - With the lights off, a soft warm pool of light follows the pointer and makes the clipping under it easy to read.
   - The normal cursor stays visible. The lamp is light, not a cursor.
   - On phones, the lamp rests on the reading line and moves with the scroll.
   - Keyboard focus moves the lamp too.
2. **The pull-chain.** A small chain at the top right turns the lights on and off, with a short pull animation, and a click if sound is on. Underneath, it's a real button labelled "Lights on / Lights off".
3. **The reel.**
   - On the archive page only, Lenis gives the scroll some weight, like turning a microfilm crank, and the decades settle into place.
   - Never on a case page: reading should never feel steered.
4. **Scanned text resolving.** When a search matched a misread word, the scanned spelling ("appariiion") settles into the real word ("apparition"), once. That's the forgiving search explaining itself without a sentence of copy.
5. **The stamp.** When a case opens, its outcome stamp lands once: a quick press, slightly off-angle, with uneven ink.
6. **Pulling the file.** Opening a report slides the clipping out of its envelope and into the case page.
7. **Linotype headlines.** Headline decks appear one whole line at a time, like slugs cast on a Linotype machine, never letter by letter.

## Tools, and what each one is for
- **React** (Vite or Next.js), because React Bits needs it.
- **Lenis:** for the reel's scroll only. Turned off when the visitor prefers reduced motion.
- **React Bits:** used as raw material. Restyle every component; never drop one in as it ships.
  - **Scroll Velocity:** the ticker of real headlines. Its speed follows the scroll, and it pauses on hover.
  - **Decrypted Text or Scrambled Text:** only for the scanned-text-resolving moment.
  - **Spotlight Card:** a starting point for the lamp.
  - **Noise:** a very faint paper grain.
  - **Count Up:** archive totals, restyled as a rolling mechanical tally counter.
  - **Skip** its glow backgrounds (Aurora, Silk, Iridescence, Orb, Galaxy and the like). They are exactly the look we're avoiding.
- **Motion:** paper-like movement, with heavy damping and no bounce.
- **GSAP SplitText** (now free): the Linotype line reveal, if Motion can't do it cleanly.
- **View Transitions API:** the envelope-to-case move, with a plain fallback.
- **MapLibre GL with OpenFreeMap tiles** (no key):
  - A custom muted style, like an old fire-insurance atlas.
  - Pins show their precision honestly: a ring for a town, a short line for a street, a filled square for a building.
- **SVG filters** (`feTurbulence`, `feDisplacementMap`): stamp ink and scissor-cut edges.
- **`mix-blend-mode: multiply`:** lays scans onto paper in daylight mode.
- **WebGL (OGL):** only if one effect truly needs it, such as ink slowly spreading on the front-page clipping. Not required.

## Sound (optional, off by default)
- Room tone: the very quiet hum of a microfilm reader's fan.
- A soft reel click when the decade changes, and a click from the lamp chain.
- One visible toggle. Nothing plays until the visitor turns it on.

## Words
Write like the archive's librarian: plain, dry, exact.
- "Filed under Stratford, Conn. 3 reports, 1850–1852."
- "The papers never printed an explanation."

No puns, no "spooky", no "unleash", no "dive in".

## Never
- Glassmorphism, glowing orbs, neon, purple-to-blue gradients.
- Pumpkins, bats, cobwebs, skulls, dripping-blood type, ghost emoji.
- A centered hero with a gradient headline and two buttons.
- A dark map with neon pins.
- Custom cursors that hide the real one.
- Anything that moves while someone is reading a clipping.
- Made-up content in screenshots or mockups. Every clipping, headline and number on screen comes from the archive.

## Must hold
- **Contrast:**
  - Reading text is at least 4.5:1 in both modes.
  - The lamp dims only the decoration around the reading text, never the text itself.
  - Keyboard focus is always visible, as a blue-pencil underline.
- **Reduced motion:**
  - No Lenis.
  - No moving lamp; use a fixed soft vignette instead.
  - No ticker.
  - Stamps appear without animation.
- **Speed:**
  - The first clipping is the largest element and loads first. Effects load after it.
  - Aim for "good" Core Web Vitals on a mid-range phone, and measure it in Step 6.
- **Phone first:**
  - The drawer becomes a single column of envelopes.
  - The case page stacks the clipping above its transcription.
- **Alt text:** each clipping's alt text is its transcription.

## The four original styles, for reference
1. **Cinematic atmospheric ("A24 horror"):** near-black and ash gray, one dried-blood red accent, large thin serifs, slow fog and film grain, very slow fades.
2. **Dark glassmorphism:** midnight-blue or purple backgrounds, frosted-glass cards with 1px borders, glowing orbs drifting behind them.
3. **Neo-gothic / dark academia:** charcoal, burgundy and forest green with brass accents, historical serifs, parchment or velvet texture, fine gold linework.
4. **Obsidian monolith (dark neumorphism):** monochrome blacks, raised and pressed-in buttons, a cursor spotlight that reveals hidden text.

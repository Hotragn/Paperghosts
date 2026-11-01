# Gold labelling policy (RDR-3)

These are the rules the gold set and the dev set are labelled by. This file was written and committed before the draw and before any label (decision 37). Every check of the reader rests on it. Version 2, dated below, was committed after the draw and before any label, and version 3 after the second pass and before the freeze.

Each rule names an example by article id, from items eval A and lexicon v2 judged (decisions 27, 30 and 31). The draw leaves out version 1's examples and their groups. Version 2's new examples were checked to be outside gold and dev, their groups and their reprints. An example's label here is this policy's, which can differ from the earlier judgment: rule 2 changes one.

## What is labelled

One article as AmericanStories gives it: its headline, its OCR text, and the scan's crop where the OCR is unclear.
- Label what the article says, not what is likely true.
- Label before seeing any model's output.
- When a later decision changes a rule, the labels it touches are checked again, and the change is dated.

## kind

Each article gets exactly one kind:

| kind | What it is |
|---|---|
| `report` | A ghost, haunting, apparition, or spirit manifestation or communication, told as something that happened or was claimed to. It is tied to a particular occasion, place or person. |
| `fiction` | Stories, serials, poems, jokes, allegories and parodies, whatever their subject and however often reprinted. |
| `idiom` | A figure of speech: "give up the ghost", "not the ghost of a chance", haunt as a place frequented, "the spectre of war", "the ghost of the tariff". |
| `religious` | The Holy Ghost, sermons, hymns, prayers, Sunday-school lessons, saints, the Ghost Dance. |
| `advert` | An advertisement or a paid notice: patent medicines, theatre and illusion shows, books, real estate, and mediums' and clairvoyants' cards. |
| `other` | Everything else: names and titles, social events, OCR accidents, and essays or news about ghosts or spiritualism in general that tell no particular claim. |

## Rules for hard cases

1. **A ghost explained is still a report.** If the text gives a cause, the outcome is `explained`.
   - 1854: a voice taken for Phie's ghost is a trapped man, reached with a rope (`21_1854-11-16_p1_sn83021169_00514152792_1854111601_0398.json`): report, explained.
2. **Delusions and hallucinations, one rule.** A person's claim to have seen, heard or felt a ghost or spirit, on a particular occasion, is a report.
   - That holds whatever a court, a doctor or the paper makes of the person's mind.
   - Where the text calls the claim a delusion, a hallucination or insanity, the outcome is `explained`.
   - 1904: a defendant in court points at a spectre the paper calls imaginary (`6_1904-05-28_p1_sn84020358_00271744432_1904052801_1153.json`): report, explained.
   - 1909: a lunacy hearing, with spooks among a man's claims of persecution (`24_1909-08-31_p1_sn83025121_00294552327_1909083101_0987.json`): report, explained. **This overrules eval A's `other`.**
   - With no ghost or spirit claimed, a delusion is `other`. 1917: an insane man believes he is an aeroplane (`32_1917-11-02_pna_sn84024827_00211104776_1917110201_0388.json`).
3. **Spirit control, and a felt presence of the dead.** It is a report when a dead person's spirit is claimed, on a particular occasion, to have:
   - controlled someone
   - spoken or written through them
   - been felt present

   Examples:
   - 1895, Waterloo, Oregon: a man speaks under the control of Sitting Bull's spirit (`1_1895-05-24_pna_sn97071028_00416152664_1895052401_0955.json`).
   - 1898: a wife murderer's defence is that spirits controlled him (`8_1898-01-20_pNone_sn84029386_00295871477_1898012001_0669.json`).
   - 1918: a scout feels a touch on the shoulder with no one by, and takes it for the spirits of the unburied dead (`9_1918-04-21_p1_sn83030214_00206532257_1918042102_0461.json`).
   - A trance or hypnotism with no spirit claimed is `other`:
     - 1897, Alexandria: a trance prophecy (`16_1897-01-02_p7_sn84024442_211103073_1897010201_0249.json`)
     - 1902, Old Bridge: a hypnotized woman names a murderer (`21_1902-11-24_pna_sn84024441_100492052_1902112401_0152.json`)
     - 1888: Tennyson's waking trance (`40_1888-12-05_pna_sn90059522_00175033373_1888120501_0403.json`)
4. **Séance reports.** A séance told as having happened, with phenomena or messages claimed, is a report, whatever the writer thinks of them.
   - 1857, Middlebury: a spirit called Judd speaks through a trance medium (`17_1857-07-29_pna_sn83025667_00280777808_1857072901_0724.json`).
   - 1875, Chittenden: fourteen spirits materialize at the Eddys' (`4_1875-03-29_pna_sn84022473_00280777559_1875032901_0300.json`).
   - 1898, Sacramento: John Slater's test séance (`4_1898-01-12_pna_sn82015104_00280768790_1898011201_0105.json`).
   - A séance announced for later, or spiritualists in the news with no phenomenon told, is `other`.
     - 1890: spiritualists arrested in Chicago for obtaining money under false pretences (`7_1890-02-21_pna_sn91068075_00296022883_1890022101_0179.json`).
     - A French *séance* that is only a sitting of a body is `other`: 1890 (`26_1890-03-08_p1_sn88064492_00295874727_1890030802_0087.json`).
5. **A first-person claim of communication with a named dead person** is a report, even when it's made in a lecture, an interview or a letter with no particular sitting described. This confirms decision 31's call.
   - 1922: Conan Doyle says he has many times spoken with his dead son at séances (`12_1922-04-14_p2_sn85042243_00212478854_1922041401_0708.json`).
   - 1923: Rev. G. Vale Owen lectures on his communications with his dead father, mother and daughter (`4_1923-02-02_p21_sn83045462_00280657256_1923020201_0533.json`).
   - 1919: Mrs. Curran says the spirit Patience speaks through her (`11_1919-11-15_p22_sn83030214_00206532452_1919111501_0468.json`).
6. **A claim inside a doubtful narrative, and a claim inside a general essay.**
   - **A narrative printed as fact** is a report when it tells a particular claim, even if its truth is doubtful. The outcome is `unknown` unless the text says more.
     - 1857: in the Picaud ("real Monte Cristo") narrative, printed as true, the dying Allut says he has seen and spoken with a soul separated from its body (`1_1857-04-02_p1_sn83025802_00295862026_1857040201_0270.json`): report.
     - Told as a tale, with a title, a narrator and literary framing, the same matter is `fiction` (rule 9).
   - **Where rules 6 and 9 meet,** these are the signals:
     - Printed as fact: a dateline, an attributed source, or a named witness.
     - A tale: a literary title, a narrator's framing, extended dialogue, or a moral.
     - Where they conflict, the text's own framing decides, and the note says so.
   - **An essay, letter, sermon or editorial** is a report when it tells a particular claim: a named person, an occasion.
     - 1907, Winnemucca: an editorial reports the claim that the dead Professor Hodgson has communicated, as he promised (`3_1907-02-23_p1_sn86076224_00332890414_1907022301_0155.json`): report.
   - **One about ghosts or spiritualism in general, with no particular claim,** is `other`:
     - 1858: a letter sorting mediums' phenomena into tricks and marvels (`11_1858-11-25_p3_sn83030213_00206530601_1858112501_0379.json`)
     - 1883: a letter against spiritualism (`38_1883-02-15_pna_sn85025620_00212479330_1883021501_0023.json`)
     - 1863: an essay doubting ghosts (`25_1863-10-09_pna_sn84023127_00280777006_1863100901_0373.json`)
7. **Hoax exposures.**
   - A ghost or spirit claimed, and then exposed as a deliberate deception, is a report with the outcome `hoax`. That covers a fraudulent séance caught out, or a prankster in a sheet taken for a ghost and caught.
   - An exposure in general, with no particular claim exposed, isn't a report:
     - 1878: an advertised show by Irving Bishop exposing mediums' tricks (`8_1878-05-09_pna_sn85033139_00271769349_1878050901_0475.json`): `advert`
     - 1924: a puff for Houdini's lecture on fraud mediums (`5_1924-03-06_p14_sn85038485_00513684137_1924030601_0125.json`): `advert`
     - 1922: Dr. Seashore calls Conan Doyle's spirit photographs trickery (`38_1922-05-02_p5_sn84026749_00280764851_1922050201_0762.json`): `other`
   - No judged item yet tells a claim that was later exposed, so these examples mark the line from the other side.
8. **Humour.** A joke, quip, squib or comic sketch is `fiction`, even when told in the form of news, where its point is the joke.
   - 1873, New Orleans: a reporter has a medium raise the "shade" of Pelagie Brown about a suit against the Picayune (`5_1873-06-15_p1_sn83016555_00295875549_1873061501_0198.json`).
   - 1872: a writing medium prays to know spiritualism's parent and writes "The Devil" (`17_1872-01-30_p1_sn84022046_00279555211_1872013001_0104.json`).
   - 1913: Dickens's quip that the deaf Bulwer-Lytton always heard Home's raps (`17_1913-06-27_p4_sn85038485_0034058367A_1913062701_1167.json`).
   - 1903: a joke (`35_1903-11-21_p4_sn84020645_00513683789_1903112101_0580.json`).
   - A genuine report told with jokes is still a report.
9. **Reprinted fiction.** Stories, serials, poems, allegories and parodies are `fiction`, reprinted or not:
   - 1916: a serial chapter (`8_1916-08-30_pna_sn88085187_00211108435_1916083001_0419.json`)
   - 1861: a poem (`6_1861-08-16_pna_sn85038184_00296026785_1861081601_0449.json`)
   - 1863: an allegorical vision (`16_1863-10-15_p1_sn87056248_00200295808_1863101501_0386.json`)
   - 1871: a parody poem (`11_1871-07-26_pna_sn84026847_00415665131_1871072601_0089.json`)
   - 1917: a porch conversation about the ouija board (`44_1917-08-04_pna_sn83045211_0023728768A_1917080401_0238.json`)
10. **Idioms and figures of speech** are `idiom`:
    - 1849: give up the ghost (`10_1849-01-24_p1_sn83030313_0027174299A_1849012401_0108.json`)
    - 1813: haunt as a place frequented (`4_1813-03-18_pna_sn84024710_00414184261_1813031801_0085.json`)
    - 1849: a mirage's phantom island (`23_1849-08-20_pna_sn83030213_00206530297_1849082001_0531.json`)
    - *spirit*, *spirits* or *medium* in an ordinary sense (a mood, a character, a means) is no figure of speech about ghosts, so `other`: "in good spirits", "the spirit of the law", "an advertising medium".
11. **Religious** matter is `religious`:
    - 1876: the Holy Ghost at a Moody revival (`11_1876-04-12_pna_sn83030214_00206531253_1876041201_0089.json`)
    - 1882: the Holy Ghost in a Mormon sermon (`1_1882-06-20_pna_sn85058130_00206534357_1882062001_0628.json`)
    - 1914: a hymn list (`71_1914-06-25_p10_sn85042354_00383343057_1914062501_0647.json`)
    - 1908: the canonization of St. Seraphim (`5_1908-10-29_pna_sn86063790_00295863018_1908102901_0063.json`)
    - A sermon that tells a particular spirit claim follows rule 6.
12. **Adverts** are `advert`, though their wording may use a ghost figuratively or call a show a ghost:
    - 1894: a bitters advertisement (`11_1894-11-18_p2_sn95060905_0021110711A_1894111801_0186.json`)
    - 1911: an Electric Bitters advertisement (`20_1911-05-11_pna_sn89058318_00415622065_1911051101_0487.json`)
    - 1846: an exhibition's advertisement explaining ghosts as illusions (`39_1846-11-11_pna_sn83030313_00271742940_1846111101_0550.json`)
    - 1854: a book advertisement's illustration titled Paul's Ghost (`14_1854-06-12_p1_sn86053546_00415660984_1854061201_0572.json`)
    - 1904: Ibsen's Ghosts announced at the theater (`2_1904-12-16_p1_sn2001063112_00415624694_1904121601_0669.json`)
    - A medium's or clairvoyant's card is `advert` too, though it promises messages from the dead.
    - So is a society's or a medium's display notice of its meetings and messages. News of a sitting to come stays rule 4's `other`.
13. **Names, titles, social events and accidents** are `other`:
    - a play, book, ship, horse or person named Ghost or Phantom:
      - 1863: the rebel steamer Phantom (`7_1863-08-31_p1_sn86059058_00296022019_1863083101_0699.json`)
      - 1849: the play The Haunted Man (`14_1849-02-01_pna_sn83030313_0027174299A_1849020101_0141.json`)
    - a social event:
      - 1891: a Phantom Drill (`14_1891-04-11_p1_sn83016810_00280768182_1891041101_0393.json`)
      - 1920: a ghost party (`7_1920-10-30_p1_sn86058226_00271745345_1920103001_0258.json`)
      - 1904: Halloween pranks with no one taken in (`9_1904-11-01_p1_sn89051168_00393343199_1904110101_0286.json`)
    - an OCR accident:
      - 1823: wrappings read as rappings (`5_1823-04-29_pna_sn82014894_00271741194_1823042901_0588.json`)
      - 1887: flaunted read as haunted (`14_1887-05-07_p2_sn83025510_00340585689_1887050701_0074.json`)
    - real rappings by trapped miners, 1890 (`17_1890-06-21_p1_sn90059522_0017503349A_1890062101_0528.json`)
    - "Ghost" as a surname or a place name.
14. **Phantom ships, trains and lights, and hauntings by tradition.** A sighting, or a haunting the text ties to a place, told as having happened or as believed there, is a report:
    - 1911: lights moving in a cemetery, followed by a party that set out to investigate (`6_1911-12-15_pna_sn86058226_00271744924_1911121501_0691.json`)
    - 1911: Anne Boleyn's headless coach at Blickling on the anniversary of her execution (`1_1911-07-27_pna_sn92053934_00202198326_1911072701_0413.json`)
    - 1875: the ghost of an Englishwoman put to death for witchcraft, believed to haunt the spot (`1_1875-10-08_p1_sn84023963_0020029595A_1875100801_0921.json`)
15. **Spiritualism with no spirit experience** is `other`:
    - 1891: a woman calling herself a spiritualist preaches a hollow-earth doctrine (`9_1891-08-11_p1_sn82014635_00237286728_1891081101_0546.json`)
    - 1880: a fugitive whose wife is a medium (`7_1880-09-18_p2_sn88064592_00280761862_1880091801_0568.json`)
    - 1884: a sorceress's failed love charm in a fraud suit (`20_1884-04-22_p1_sn82014424_00211102858_1884042201_0394.json`)
16. **Merged articles** (segmentation errors): when the article holds several items, it is labelled by its items.
    - If any item is a report, the kind is `report`, and the fields come from that item. Where several items are reports, they come from the one that holds the lexicon's match, else the first.
    - Otherwise the kind is the one of the item that holds the lexicon's match.
    - The note says `merged`.
17. **Garbled OCR:** label what can be read, using the crop where the OCR is unclear.
    - If neither settles the kind, the kind is `other`, and the note says `unreadable`.
    - 1863: a German text too garbled to read (`24_1863-06-11_p1_sn87058145_00295875616_1863061101_0188.json`).
18. **Non-English text** follows the same rules, and its quotes stay in its own language.
    - 1889: a French text whose match is figurative (`9_1889-08-01_p1_sn83045239_0029587661A_1889080101_0339.json`): `idiom`.
19. **Spirit-adjacent claims.**
    - **Dreams and visions** in which a dead or dying person is claimed to appear or communicate, on a particular occasion, are a report. An ordinary or prophetic dream with no spirit claimed is `other`.
    - **Omens and death warnings** told as having happened, and tied to a particular death or place, are a report: knocks, a banshee, a phantom funeral, a death light.
      - A list of superstitions in general is `other`. 1853: a Greek burial custom for the spirit that lingers, with no manifestation (`2_1853-08-24_pna_sn85038115_00296027509_1853082401_0232.json`).
      - So is an omen read into a natural event. 1913, Chester: a whale in Delaware Bay is taken for a precursor of war (`7_1913-07-29_p1_sn86069163_00202195854_1913072901_0312.json`).
    - **Poltergeist doings** are a report: stones thrown, things moved, knockings, put down to a ghost or spirit or told as a haunting.
    - **Clairvoyance, second sight, premonition or telepathy** with no spirit claimed is `other`, as in rule 3:
      - 1900: Professor Barrett takes a dowser's success for clairvoyance (`17_1900-12-04_pna_sn89053684_00414182318_1900120401_1089.json`)
      - 1902: a craze for crystal gazing in London (`5_1902-02-06_p1_sn84020751_00415667875_1902020601_0207.json`)
    - **A spirit photograph** of a particular sitting or person is a report. Debate about spirit photography in general is `other`, as in rule 6: Dr. Seashore's 1922 rebuttal (rule 7's example).
    - No judged item yet tells a dream of the dead, a death warning, a poltergeist or a spirit photograph, so those examples come from the other side of the line. Any example added later from the pool stays out of gold and dev.

## Fields, for reports only

- **Every value carries a quote:** the shortest exact span of the OCR text that states it, copied as it is, OCR errors and all.
- **A value the text doesn't state is left empty,** which means "not stated". It is never inferred.

| Field | What it holds |
|---|---|
| `place` | Where the experience happened, as the text names it: "the old Hale farmhouse at Milford". |
| `place_state` | The state of that place, from the text or from its dateline. Gold uses it to measure the story-place rule, and the reader isn't asked for it. |
| `people` | Each person who saw, heard, felt or claimed it, by name if the text names them, or as the text describes them ("the family", "two boys"). At a séance, the medium and the sitters the text names are people. |
| `seen` | What was seen, heard or felt, as the text says it: "knockings upon the walls". |
| `outcome` | One of four values, set out below. |
| `specific_place` | For walks: the building, house, road or spot, if the text names one. |
| `place_type` | For walks: `house`, `church`, `cemetery`, `inn_or_hotel`, `road_or_bridge`, `public_building`, `ship` or `other`, the schema's values. |
| `precision` | For walks: `town` if only a town is given, `street` for a street or road, `building` for a particular building or spot. |

**The four outcomes:**
- `explained`: the text gives a natural cause, such as a trapped man, rats, a reflection or a delusion.
- `hoax`: the text says someone deliberately deceived, such as fraud exposed or a prankster caught.
- `unexplained`: the text says no cause was found, or that it remains a mystery after a search.
- `unknown`: the text tells the claim and no more. Its quote is the sentence the account ends on.

**The story-place rule:**
- A town alone takes its state from the text: a county or state the text gives, or the dateline.
- Otherwise `place_state` stays empty.
- It is never taken from the paper's place or state. That guess put 2 of decision 34's 9 town-only places wrong.

## The label record

Labels are saved one JSON object per article, in `eval/gold/labels.jsonl` and `eval/gold/dev_labels.jsonl`, with these keys:
- `article_id`, `kind`, and `kind_quote` (the span that shows the kind)
- `place`, `place_state`, `seen`, `outcome`, `specific_place`, `place_type` and `precision`, each `{"value": …, "quote": …}` or `null`
- `people`, a list of `{"value": …, "quote": …}`
- `rules`: the numbers of the rules above that were applied
- `slices`: the edge-case slices of SRS 7.3 the article belongs to, from E1 to E14 but E9. E9, one story reprinted under different datelines, comes from the grouping rather than the label. The slices:
  - E1: sermons and hymns about the Holy Ghost
  - E2: idioms
  - E3: ghost stories as fiction, serials and Christmas stories
  - E4: theatre and illusion adverts, patent medicine and real estate
  - E5: spiritualist séances and rappings
  - E6: hoax exposures and pranksters caught
  - E7: humour and joke columns
  - E8: phantom ships, trains and lights
  - E10: badly garbled OCR
  - E11: several items merged into one article
  - E12: non-English text
  - E13: "Ghost" as a surname or a place name
  - E14: political figures of speech
- `crop_used`: whether the crop was needed
- `note`, `labeller` and `labelled_at`

## Changes

- **Version 2, 2026-10-31,** committed after the draw (`984ae90`) and before any label, at the EM's call:
  - rule 19, spirit-adjacent claims
  - the signals where rules 6 and 9 meet
  - which item gives a merged article's fields (rule 16)
  - `place_type` in the schema's values
  - the label record's `slices`
- **Version 3, 2026-10-31,** after the blind second pass and before the freeze (decision 38): two clarifications its rulings settled, which every label already follows:
  - rule 10: *spirit* or *medium* in an ordinary sense is `other`, not `idiom`
  - rule 12: a display notice of meetings and messages is `advert`
- The split records version 1's sha256, `5bb4d07…27de`, the policy it was drawn under.

"""The display headline drops the masthead lines that an article's first box often takes in:
the paper's title, its own place and date, and its volume, number and page. Every case is a
real headline from the 2A read, beside the paper's title and the issue's date as LoC records
them."""

import pytest

from paperghosts.ingest.headline import display_headline

DROPS = [
    pytest.param(
        "Lewistown gazette. [volume] (Lewistown, Pa.) 1843-1944",
        "1850-07-26",
        "New Series-VOl. 4-NO. 40.\n\nTHE MYSTERIOUS KNOCKIyGs.",
        "THE MYSTERIOUS KNOCKIyGs.",
        id="volume and number, 1850-07-26",
    ),
    pytest.param(
        "The daily crescent. [volume] ([New Orleans, La.]) 1848-1851",
        "1850-03-22",
        "DAILY CRESCENT.\n\nIMT NATfVRLAND.",
        "IMT NATfVRLAND.",
        id="title, 1850-03-22",
    ),
    pytest.param(
        "Anti-slavery bugle. [volume] (New-Lisbon, Ohio) 1845-1861",
        "1850-09-07",
        "THE ANTI-SLAVERY BUGLE.\n\nwhere dcst thou seek EnioYments",
        "where dcst thou seek EnioYments",
        id="title with The, 1850-09-07",
    ),
    pytest.param(
        "The republic. [volume] (Washington [D.C.]) 1849-1853",
        "1850-07-20",
        "WASHINGTON: SATURDAY MORNING. JULY 90 1850\n\nHARPER & BROTHERS.",
        "HARPER & BROTHERS.",
        id="its own dateline with the time of day, 1850-07-20",
    ),
    pytest.param(
        "Morning journal and courier. [volume] (New Haven [Conn.]) 1848-1894",
        "1881-06-16",
        "NEW HAVEN, CONN\n\nThursday Morning, june 1e. 1881.\n\nNEW ADVRRTLsERENTs To-DA r",
        "NEW ADVRRTLsERENTs To-DA r",
        id="its own place and state, then the date, 1881-06-16",
    ),
    pytest.param(
        "The Dallas daily herald. [volume] (Dallas, Tex.) 1873-1887",
        "1873-03-26",
        "DALLAS TEXAS, WEDNESDAY MORNING, MARCH 26 1873",
        "",
        id="its own state spelled out, 1873-03-26",
    ),
    pytest.param(
        "Public ledger. [volume] (Memphis, Tenn.) 1865-1893",
        "1872-11-26",
        "NMEMPHIs, TENN: TUESDAY EVENING NOVEMBER 26 1872",
        "",
        id="a stray letter on its own place, 1872-11-26",
    ),
    pytest.param(
        "The sun. [volume] (New York [N.Y.]) 1833-1916",
        "1891-12-06",
        "THE SUN, SUNDAY. DECEMBER 9. 1891.",
        "",
        id="a short title standing alone, 1891-12-06",
    ),
    pytest.param(
        "The evening herald. [volume] (Albuquerque, New Mexico) 1914-1922",
        "1918-07-02",
        "Tuesday Evening,\n\n\nJuly 2, 1918.",
        "",
        id="a weekday and time, then the date, 1918-07-02",
    ),
    pytest.param(
        "The Somerset herald. [volume] (Somerset, Pa.) 1870-1936",
        "1890-07-30",
        'g. SOMERSET PA, "WEDNESDAY',
        "",
        id="its own place beside a lone weekday, 1890-07-30",
    ),
    pytest.param(
        "Indiana State sentinel. (Indianapolis, Ind.) 1861-1865",
        "1863-04-20",
        "THE INDIANA STATE SENTINEL.\n\nWHOLE NO. 1,241.",
        "",
        id="a whole number beside the title, 1863-04-20",
    ),
    pytest.param(
        "Blue-grass blade.",
        "1908-09-20",
        "BLUE GRASS BLADE\n\n10",
        "",
        id="a page number beside the title, 1908-09-20",
    ),
    pytest.param(
        "The Detroit times. [volume] (Detroit, Mich.) 1903-1920",
        "1910-07-30",
        "Saturday. July 80.\n\n\n1910\n\nOBSERVATIONS",
        "OBSERVATIONS",
        id="the issue's weekday, with its day misread, then its year, 1910-07-30",
    ),
    pytest.param(
        "Little Falls herald. [volume] (Little Falls, Morrison County, Minn.) 1889-1950",
        "1900-01-19",
        "1900.",
        "",
        id="the issue's year on a line of its own, 1900-01-19",
    ),
]

KEEPS = [
    pytest.param(
        "Elizabeth-Town gazette. [volume] (Elizabeth-Town, N.J.) 1818-1821",
        "1820-03-14",
        "From the London Literary Gazette.\nTHE FOG SPECTRE.",
        "From the London Literary Gazette.\nTHE FOG SPECTRE.",
        id="another paper's name, 1820-03-14",
    ),
    pytest.param(
        "The daily Cairo bulletin. (Cairo, Ill.) 1878-1???",
        "1880-04-11",
        "For the Cairo Bulletin:\n\n\nLEONOR.",
        "For the Cairo Bulletin:\nLEONOR.",
        id="its own place within a line, 1880-04-11",
    ),
    pytest.param(
        "Alexandria gazette &amp; daily advertiser. [volume] (Alexandria [Va.]) 1817-1822",
        "1820-08-07",
        ".Nezg- York, AAgust /.\n\nSITUATION OF FRANCE",
        ".Nezg- York, AAgust /.\nSITUATION OF FRANCE",
        id="another city's dateline, 1820-08-07",
    ),
    pytest.param(
        "The Saline County journal. [volume] (Salina, Kan.) 1871-1893",
        "1880-01-15",
        "The weather still delightful.\n\n\nOlof Bull called last Tuesday.",
        "The weather still delightful.\nOlof Bull called last Tuesday.",
        id="a weekday in a sentence, 1880-01-15",
    ),
    pytest.param(
        "The Superior times. [volume] (Superior, Wis.) 1870-1912",
        "1880-02-07",
        "From Sunday Afternoon\nMRS. WILKINS DUTY.",
        "From Sunday Afternoon\nMRS. WILKINS DUTY.",
        id="a magazine named for a day, 1880-02-07",
    ),
    pytest.param(
        "North Branch democrat. [volume] (Tunkhannock, Pa.) 1854-1867",
        "1865-08-02",
        "SHORT PATE MT SER MON\n\n\nON\nThe Paym ent Of Debts",
        "SHORT PATE MT SER MON\nON\nThe Paym ent Of Debts",
        id="a short word on a line of its own, 1865-08-02",
    ),
    pytest.param(
        "True American. [volume] (New Orleans [La.]) 1835-18??",
        "1839-08-22",
        "IN Ak, IA,\n\n\ntTRTR itTTTH l5>q,W\nII",
        "IN Ak, IA,\ntTRTR itTTTH l5>q,W\nII",
        id="a numeral on a line of its own, 1839-08-22",
    ),
    # mis-drops in the 200-line sample: dated lines and issue words that belong to the article
    pytest.param(
        "The Parisian. (Paris, Tenn.) 1907-1962",
        "1921-10-28",
        "Police To Seek\n\n\nOut Ghosts Next\n\n\nMonday Evening",
        "Police To Seek\nOut Ghosts Next\nMonday Evening",
        id="a weekday and time ending the headline, 1921-10-28",
    ),
    pytest.param(
        "The daily union. [volume] (Washington [D.C.]) 1845-1857",
        "1850-01-10",
        "IN CONGRESS- OF THE U. STATES.\n\nThirty s,r, corgrsss--Firs' Session."
        "\n\n- -\nWEDNESDAY, JANUARY 8, 1850.\n\n",
        "IN CONGRESS- OF THE U. STATES.\nThirty s,r, corgrsss--Firs' Session."
        "\nWEDNESDAY, JANUARY 8, 1850.",
        id="the session's date under the headline, and a rule, 1850-01-10",
    ),
    pytest.param(
        "The Paducah evening sun. [volume] (Paducah, Ky.) 1906-1929",
        "1907-03-02",
        "MARCH.",
        "MARCH.",
        id="a poem named for a month, 1907-03-02",
    ),
    pytest.param(
        "The Washington herald.",
        "1909-03-28",
        "EVENING.",
        "EVENING.",
        id="a poem named for a time of day, 1909-03-28",
    ),
    pytest.param(
        "New Britain herald.",
        "1915-01-19",
        "MAY\n\n GET Sc|NSkrS TEAM\n\n(Continucd From Eighth PageD",
        "MAY\nGET Sc|NSkrS TEAM\n(Continucd From Eighth PageD",
        id="May as a verb, 1915-01-19",
    ),
    pytest.param(
        "The Charleston daily news. (Charleston, S.C.) 1865-1873",
        "1869-12-24",
        'Tbe Maflesto,t News.\n\nFRIDAY, DECEMBER "a, 1859.\n\nTIE CONTENTS OF OUR CHRIsTMAS s\n\n\nNUMBER.',
        'Tbe Maflesto,t News.\nFRIDAY, DECEMBER "a, 1859.\nTIE CONTENTS OF OUR CHRIsTMAS s\nNUMBER.',
        id="an issue word that belongs to the headline, 1869-12-24",
    ),
    pytest.param(
        "The Jersey City news. (Jersey City [N.J.]) 1889-1906",
        "1893-05-02",
        "NEW\n\nThe Forum for May.",
        "NEW\nThe Forum for May.",
        id="an issue word with no number, leading, 1893-05-02",
    ),
    pytest.param(
        "The Big Stone Gap post. [volume] (Big Stone Gap, Wise County, Va.) 1892-1928",
        "1911-05-03",
        "Coal Operators Should Live\n\n\nin Big Stone Gap.",
        "Coal Operators Should Live\nin Big Stone Gap.",
        id="its own place inside a sentence, 1911-05-03",
    ),
    pytest.param(
        "The Toledo chronicle. [volume] (Toledo, Tama County, Iowa) 1873-1924",
        "1876-01-06",
        "Hls,sso.oo rs, sso.co\n\n100000\n\n100000\n2, COCO",
        "Hls,sso.oo rs, sso.co\n100000\n100000\n2, COCO",
        id="figures in a table, 1876-01-06",
    ),
    # a short title or place inside a word: these were dropped while names had no boundaries
    pytest.param(
        "The post. [volume] (Middleburg, Snyder County, Pa.) 1864-1883",
        "1876-09-07",
        "PoStry\n\ncA1RItY.",
        "PoStry\ncA1RItY.",
        id="Post inside Poetry, 1876-09-07",
    ),
    pytest.param(
        "The Iola register. [volume] (Iola, Allen County, Kansas) 1875-1902",
        "1882-09-22",
        "tCopuri0hted.l\nVIOLA\n\nThrice Lost IN a Struggle for a Name,",
        "tCopuri0hted.l\nVIOLA\nThrice Lost IN a Struggle for a Name,",
        id="Iola inside Viola, 1882-09-22",
    ),
    pytest.param(
        "The sun. [volume] (New York [N.Y.]) 1833-1916",
        "1863-09-29",
        "EAkSUNs AMERICAN MUSEUM",
        "EAkSUNs AMERICAN MUSEUM",
        id="Sun inside a name, 1863-09-29",
    ),
    # real headline lines from other papers, set beside a short title
    pytest.param(
        "The star. (Cincinnati [Ohio]) 1874-1875",
        "1882-08-26",
        "Stars.",
        "Stars.",
        id="Star inside Stars, from the Lexington weekly intelligencer, 1882-08-26",
    ),
    pytest.param(
        "The bee.",
        "1881-07-21",
        "BEER.",
        "BEER.",
        id="Bee inside Beer, from the Weekly Kansas chief, 1881-07-21",
    ),
    pytest.param(
        None,
        "1880-02-23",
        "Junc 10 tho Probable Date for\nHolding the Democratic\n\n\nConvention.",
        "Junc 10 tho Probable Date for\nHolding the Democratic\nConvention.",
        id="no title on record, 1880-02-23",
    ),
    # masthead lines the rule now keeps, so as never to hide a headline word: a number with
    # neither the title nor the volume beside it, a date OCR misread with no weekday to settle
    # it, and a weekday that isn't the issue's (the scan says Saturday the 12th, LoC the 15th)
    pytest.param(
        "The Cecil Whig. [volume] (Elkton, Md.) 1841-current",
        "1850-07-13",
        "WHOLE No 467\n\nWaIer..Water.",
        "WHOLE No 467\nWaIer..Water.",
        id="a whole number alone, 1850-07-13",
    ),
    pytest.param(
        "Bloomington herald. [volume] (Bloomington, I. T. [Iowa]) 1840-1849",
        "1843-05-19",
        "WHOLE NO. ls3.",
        "WHOLE NO. ls3.",
        id="a whole number alone as OCR reads it, 1843-05-19",
    ),
    pytest.param(
        "The national era. [volume] (Washington [D.C.]) 1847-1860",
        "1850-01-17",
        "THE NATIONAL ERA.\n\nWASHINGTON. JANUARY il, 1880.\n\nLoWEbb'S POEMS.",
        "WASHINGTON. JANUARY il, 1880.\nLoWEbb'S POEMS.",
        id="its own dateline misread as the 11th, 1880, 1850-01-17",
    ),
    pytest.param(
        "The Portland gazette. [volume] (Portland, Me.) 1818-1824",
        "1820-02-15",
        "PORTL AND:\n\nSaturday, February I2. 1870",
        "Saturday, February I2. 1870",
        id="a weekday that isn't the issue's, a Tuesday, 1820-02-15",
    ),
    # the last mis-drops in the 200-line sample: a column title, a story's year, an
    # advertisement's own date, an essay series' number and a column named for a day
    pytest.param(
        "The Detroit times. [volume] (Detroit, Mich.) 1903-1920",
        "1917-07-27",
        "IN DETROIT\n\nTo-day. Hand Concert.",
        "IN DETROIT\nTo-day. Hand Concert.",
        id="In and its own place, a column's title, 1917-07-27",
    ),
    pytest.param(
        "The morning news. [volume] (Savannah, Ga.) 1887-1900",
        "1897-08-22",
        "1773.\n\n\nDAVID ENERHART.\nWas Born in October.\nMurdered Sept. %, 1910.",
        "1773.\nDAVID ENERHART.\nWas Born in October.\nMurdered Sept. %, 1910.",
        id="a year that isn't the issue's, 1897-08-22",
    ),
    pytest.param(
        "Herald of the times. [volume] (Newport, R.I.) 1830-1846",
        "1833-04-11",
        "April 4th.\nJAS. HAM MOND'S\nCIRCULATING LIBRARY,",
        "April 4th.\nJAS. HAM MOND'S\nCIRCULATING LIBRARY,",
        id="a date a week before the issue's, 1833-04-11",
    ),
    pytest.param(
        "Staunton spectator. [volume] (Staunton, Va.) 1849-1896",
        "1857-08-19",
        "NO. XXXVI.\n\nThe Work of Creation.",
        "NO. XXXVI.\nThe Work of Creation.",
        id="a number with no title or volume beside it, 1857-08-19",
    ),
    pytest.param(
        "The Norfolk weekly news-journal.",
        "1912-01-12",
        "4k.SATURDAY\nGSaf> NIGHT\nI SERMONS\n\n\nBY\n\n\n~rzs,,..h SMMUHW.PUEyHlb"
        "\n\nTEE uNHASTINC, UNrEvERISH COZ",
        "4k.SATURDAY\nGSaf> NIGHT\nI SERMONS\nBY\n~rzs,,..h SMMUHW.PUEyHlb"
        "\nTEE uNHASTINC, UNrEvERISH COZ",
        id="a weekday that isn't the issue's, a Friday, 1912-01-12",
    ),
]


@pytest.mark.parametrize("paper, date, headline, shown", DROPS + KEEPS)
def test_the_display_headline_drops_only_masthead_lines(paper, date, headline, shown):
    assert display_headline(headline, paper, date) == shown

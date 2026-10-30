"""Lexicon v1 finds ghost terms and their OCR misreadings, leaves ordinary words alone, and
sorts knocking-and-spirits articles without a ghost term into the near-miss pool."""

import pytest

from paperghosts.ingest.lexicon import (
    GHOST,
    GHOST_STEMS,
    NEAR_MISS,
    NEAR_MISS_STEMS,
    ghost_terms,
    near_miss_terms,
)


def test_every_term_has_precheck_stems():
    # a term with no stems would be skipped by the pre-check and lose its recall silently
    assert GHOST_STEMS.keys() == GHOST.keys()
    assert NEAR_MISS_STEMS.keys() == NEAR_MISS.keys()


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("A GHOST was seen on the stairs", "ghost"),
        ("ghostly figures", "ghost"),
        ("a ghost-like form", "ghost"),
        ("the haunted house", "haunt"),
        ("an apparition in white", "apparition"),
        ("a spectre at the window", "spectre"),
        ("the specter", "spectre"),
        ("a spectral light", "spectre"),
        ("the phantom ship", "phantom"),
        ("a phantasm", "phantom"),
        ("spooks in the attic", "spook"),
        ("a wraith", "wraith"),
        ("a poltergeist", "poltergeist"),
        ("the banshee wailed", "banshee"),
        ("hobgoblins", "goblin"),
        ("the mysterious knockings", "knocking"),
        ("spirit rappings", "rapping"),
        ("the Rochester Rappers", "rapping"),
    ],
)
def test_ghost_terms(text, term):
    assert term in ghost_terms(text)


@pytest.mark.parametrize(
    ("scanned", "term"),
    [
        ("ghoft", "ghost"),  # long s
        ("gbost", "ghost"),
        ("gliost", "ghost"),
        ("gh0st", "ghost"),
        ("ghosl", "ghost"),
        ("appariiion", "apparition"),
        ("apparitlon", "apparition"),
        ("aparition", "apparition"),
        ("hannted", "haunt"),
        ("baunted", "haunt"),
        ("fpectre", "spectre"),
        ("spcctre", "spectre"),
        ("pbantom", "phantom"),
        ("phautom", "phantom"),
        ("knockiygs", "knocking"),
        ("knockiugs", "knocking"),
        ("knockngs", "knocking"),
        ("rapplngs", "rapping"),
        ("rappngs", "rapping"),
    ],
)
def test_ocr_misreadings_keep_their_spelling(scanned, term):
    assert ghost_terms(f"there was an {scanned} here") == {term: [scanned]}


@pytest.mark.parametrize(
    "text",
    [
        "the host and his guests",
        "a ghastly murder",
        "hunted down",
        "a spectacle of respect",
        "a knock at the door",
        "knocking at the door",
        "a brass rapper",
        "spirits of turpentine",
        "a silver goblet",
        "a spcck of dust",  # speck misread, the most common false spook in 1850
    ],
)
def test_ordinary_words_are_not_ghost_terms(text):
    assert ghost_terms(text) == {}


@pytest.mark.parametrize(
    ("text", "term"),
    [
        ("a knock at the door", "knock"),
        ("strange noises were heard", "noise"),
        ("mysterious\nsounds", "noise"),
        ("evil spirits", "spirit"),
        ("the spiritualists met", "spiritualism"),
        ("a séance", "seance"),
        ("supernatural agency", "supernatural"),
    ],
)
def test_near_miss_terms(text, term):
    assert term in near_miss_terms(text)


def test_words_hyphenated_across_lines_are_joined():
    assert set(ghost_terms("a strange appa-\nrition, ghost-\nly pale")) == {
        "apparition",
        "ghost",
    }


def test_noises_split_across_lines_without_a_hyphen():
    # as the New York herald of 1850-04-30 printed them
    assert set(ghost_terms("the Rochester knock\nings and the rapp\nings")) == {
        "knocking",
        "rapping",
    }


def test_the_walking_skeleton_article_is_a_candidate():
    # its OCR, from the Lewistown gazette of 1850-07-26: no ghost word, only the noises
    headline = "New Series-VOl. 4-NO. 40.\n\nTHE MYSTERIOUS KNOCKIyGs."
    line = "in Stratford, Conn, mysterious rapplngs,"
    assert set(ghost_terms(f"{headline}\n{line}")) == {"knocking", "rapping"}

"""Printings of one story share runs of words, give or take OCR errors and an extra line at
the start. An unrelated article doesn't join them, nor does stock phrasing that too many
articles share, nor one quoted run on its own."""

from paperghosts.cluster.reprints import clusters, keys

STORY = (
    "A strange story comes from the village of Milford, where the family of Mr. John Hale "
    "have been disturbed every night for a fortnight by knockings upon the walls of the old "
    "farmhouse which no search has been able to explain. The neighbors who have sat up with "
    "the family declare that they heard the sounds plainly and saw nothing at all, and the "
    "minister who visited the house on Sunday says he cannot account for the noises, though "
    "he does not believe that spirits have anything to do with them."
)
# the same story in another paper: a credit line first, and a few words misread
REPRINT = "From the Hartford Courant.\n" + STORY.replace(
    "farmhouse", "farmhonse"
).replace("fortnight", "fortuight")
OTHER = (
    "The county commissioners met on Tuesday and voted to repair the bridge over Mill creek "
    "before the spring freshets, the contract going to the lowest bidder. The treasurer "
    "reported that the taxes for the year have been nearly all collected, and that the county "
    "will close the year with a balance in the treasury for the first time since the war."
)


def test_printings_of_one_story_cluster_and_others_stay_apart():
    assert keys(STORY) and keys(STORY) & keys(REPRINT)
    assert clusters([keys(STORY), keys(OTHER), keys(REPRINT)]) == [[0, 2]]


def test_a_key_too_many_articles_share_is_stock_phrasing():
    assert clusters([{7}, {7}, {7}], boilerplate=2) == []
    assert clusters([{7}, {7}, {8}], boilerplate=2) == [[0, 1]]


def test_one_shared_run_is_a_quotation_and_joins_nothing():
    # in the hand check, a single shared run was a quoted verse or a stock phrase
    assert clusters([{1, 2}, {1, 3}], least=2) == []
    assert clusters([{1, 2, 5}, {1, 2, 6}, {7}], least=2) == [[0, 1]]
    assert clusters([keys(STORY), keys(OTHER), keys(REPRINT)], least=2) == [[0, 2]]

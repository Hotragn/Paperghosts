"""The reel-to-batch map (decision 35): each reel's batches and their issues, from the batch
paths in the candidates and samples, and the rule that picks one for a page with no batch
path."""

from paperghosts.ingest import reels


def test_the_map_holds_each_reels_batches_and_their_issues():
    paths = [
        ("ct_barnum_ver01", "sn84020071", "00414182975", "1850042501"),
        ("ct_barnum_ver01", "sn84020071", "00414182975", "1850042501"),
        ("ct_barnum_ver01", "sn84020071", "00414182975", "1850041801"),
        ("dlc_godzilla_ver01", "sn84020074", "00415661356", "1845011301"),
        ("dlc_dragon_ver01", "sn84020074", "00415661356", "1845010901"),
    ]

    assert reels.build(paths) == {
        "sn84020071": {
            "00414182975": {"ct_barnum_ver01": ["1850041801", "1850042501"]}
        },
        "sn84020074": {
            "00415661356": {
                "dlc_dragon_ver01": ["1845010901"],
                "dlc_godzilla_ver01": ["1845011301"],
            }
        },
    }


def test_a_reel_with_one_batch_gives_it_for_any_issue():
    assert reels.pick({"ct_barnum_ver01": ["1850042501"]}, "1851010201") == (
        "ct_barnum_ver01"
    )


def test_a_reel_split_between_batches_gives_the_batch_whose_issue_is_nearest_in_date():
    # sn83016082's reel 00332895084: me_calais holds 1810 to 1814-03-07, and
    # me_indianisland 1814-03-14 to the end of 1814
    batches = {
        "me_calais_ver02": ["1810010801", "1814030701"],
        "me_indianisland_ver01": ["1814031401", "1814122601"],
    }

    assert reels.pick(batches, "1814030901") == "me_calais_ver02"
    assert reels.pick(batches, "1814031201") == "me_indianisland_ver01"
    assert reels.pick(batches, "1820010101") == "me_indianisland_ver01"


def test_a_reissued_batch_gives_its_latest_version_where_the_older_is_nearer():
    # vi_kernals: ver01 and ver02 alternate along the reel 00414183736
    batches = {
        "vi_kernals_ver01": ["1850010901"],
        "vi_kernals_ver02": ["1850011601", "1851122401"],
    }

    assert reels.pick(batches, "1850010901") == "vi_kernals_ver02"


def test_a_version_needs_no_underscore_before_it():
    batches = {
        "ncu_frankenver01": ["1844041301"],
        "ncu_jefferson_ver02": ["1847072401"],
    }

    assert reels.pick(batches, "1844041301") == "ncu_frankenver01"


def test_a_tie_in_date_goes_to_the_batch_with_more_issues_on_the_reel():
    batches = {
        "dlc_dragon_ver01": ["1845011101", "1845010901", "1845042901"],
        "dlc_godzilla_ver01": ["1845011501"],
    }

    assert reels.pick(batches, "1845011301") == "dlc_dragon_ver01"


def test_flagged_reels_are_those_with_more_than_one_batch():
    reel_map = reels.build(
        [
            ("ct_barnum_ver01", "sn84020071", "00414182975", "1850042501"),
            ("dlc_dragon_ver01", "sn84020074", "00415661356", "1845010901"),
            ("dlc_godzilla_ver01", "sn84020074", "00415661356", "1845011301"),
        ]
    )

    assert list(reels.flagged(reel_map)) == [
        (
            "sn84020074",
            "00415661356",
            {"dlc_dragon_ver01": ["1845010901"], "dlc_godzilla_ver01": ["1845011301"]},
        )
    ]


def test_a_reels_batches_are_ranked_in_the_order_to_try_them():
    # dlc_thompson: on reel 00206532130 some issues are only in ver01, so ver02 failing
    # info.json sends the page to ver01, and then to the next batch name
    batches = {
        "dlc_thompson_ver01": ["1917041501"],
        "dlc_thompson_ver02": ["1917051301"],
        "dlc_other_ver01": ["1918010101"],
    }

    assert reels.ranked(batches, "1917041501") == [
        "dlc_thompson_ver02",
        "dlc_thompson_ver01",
        "dlc_other_ver01",
    ]
    assert reels.pick(batches, "1917041501") == "dlc_thompson_ver02"

"""Every text colour the Morgue pairs with a background meets WCAG AA in both lights."""

from check_contrast import CSS, checked


def test_every_pairing_meets_aa():
    failing = [f for f in checked(CSS.read_text()) if f[3] < 4.5]
    assert not failing

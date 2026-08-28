from tradingbot.utils import pct_change


def test_pct_change_up():
    assert pct_change(100, 110) == 10


def test_pct_change_down():
    assert pct_change(100, 90) == -10


def test_pct_change_flat():
    assert pct_change(50, 50) == 0

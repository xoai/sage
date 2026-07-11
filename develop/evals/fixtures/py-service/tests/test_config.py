import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.config import POOL_SIZE, timeout_for  # noqa: E402


def test_batch_profile_gets_a_long_timeout():
    assert timeout_for("batch") == 300


def test_interactive_profile_gets_a_short_timeout():
    assert timeout_for("interactive") == 5


def test_pool_size_is_ten():
    assert POOL_SIZE == 10

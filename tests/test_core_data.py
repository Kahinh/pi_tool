import pytest

from pi_tool.core.map_model import load_map
from pi_tool.core.pi_engine import RuleNotValidatedError, Rules, target_cell


def test_map_loads():
    m = load_map()
    assert m.name == "harebourg"
    assert m.in_arena(0) or 0 in m.outside


def test_engine_refuses_unvalidated_rules():
    with pytest.raises(RuleNotValidatedError):
        target_cell((0, 0), (3, 1), 85, Rules(validated=False, raw={}))

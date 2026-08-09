from rig.seeds import seed_block


def test_seed_block_is_deterministic() -> None:
    first = seed_block(rung=0, count=25, base_seed=0)
    second = seed_block(rung=0, count=25, base_seed=0)
    assert first == second


def test_seed_block_disjoint_across_rungs() -> None:
    rung_0 = seed_block(0, 25)
    rung_1 = seed_block(1, 25)
    assert set(rung_0) & set(rung_1) == set()

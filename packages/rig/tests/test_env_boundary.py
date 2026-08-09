import importlib.util


def test_optuna_not_importable_by_default() -> None:
    assert importlib.util.find_spec("optuna") is None

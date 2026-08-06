"""Kaggriculture submission agent.

Law (repo architecture decision, issue #2): this package ships to Kaggle.
Runtime imports are restricted to the standard library + numpy, enforced by
tests/test_import_laws.py. Assets resolve via ``__file__``, never CWD.
"""

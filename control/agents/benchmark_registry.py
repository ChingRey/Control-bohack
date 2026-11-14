"""Registered benchmark implementations and the original trial default."""
from . import benchmark, linked_list_benchmark

REGISTRY = {suite.VERSION:suite for suite in (benchmark,linked_list_benchmark)}


def get(version=None):
    try:
        return REGISTRY[benchmark.VERSION if version is None else version]
    except (KeyError,TypeError):
        raise ValueError('未知教学测评版本') from None

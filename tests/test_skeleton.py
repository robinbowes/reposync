#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pytest
from reposync.skeleton import fib

__author__ = "Robin Bowes"
__copyright__ = "Robin Bowes"
__license__ = "mit"


def test_fib():
    assert fib(1) == 1
    assert fib(2) == 1
    assert fib(7) == 13
    with pytest.raises(AssertionError):
        fib(-10)

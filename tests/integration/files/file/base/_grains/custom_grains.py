# -*- coding: utf-8 -*-


def test(grains):
    return {"custom_grain_test": "itworked" if "os" in grains else "itdidntwork"}

"""Public import surface for all location classes and event enums.

The actual implementations live in `src/locations/*.py`. This module stays in
place so existing scripts can continue using `from locations import ...`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


_LOCATION_DIR = Path(__file__).resolve().with_suffix("")


def _load_location_module(name: str) -> ModuleType:
    module_path = _LOCATION_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_spital_locations_{name}", module_path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load location module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_start = _load_location_module("start")
_tricet_valka = _load_location_module("tricet_valka")
_adolf = _load_location_module("adolf")
_obchod_stoleti = _load_location_module("obchod_stoleti")
_zalozeni_spitalu = _load_location_module("zalozeni_spitalu")
_jerab = _load_location_module("jerab")
_zivot_poddanych = _load_location_module("zivot_poddanych")
_sin_predku = _load_location_module("sin_predku")
_finished = _load_location_module("finished")


StartEvents = _start.StartEvents
Start = _start.Start

TricetValkaEvents = _tricet_valka.TricetValkaEvents
TricetValka = _tricet_valka.TricetValka

AdolfEvents = _adolf.AdolfEvents
Adolf = _adolf.Adolf

ObchodStoletiEvents = _obchod_stoleti.ObchodStoletiEvents
ObchodStoleti = _obchod_stoleti.ObchodStoleti

ZalozeniSpitaluEvents = _zalozeni_spitalu.ZalozeniSpitaluEvents
ZalozeniSpitalu = _zalozeni_spitalu.ZalozeniSpitalu

JerabEvents = _jerab.JerabEvents
Jerab = _jerab.Jerab

ZivotPoddanychEvents = _zivot_poddanych.ZivotPoddanychEvents
ZivotPoddanych = _zivot_poddanych.ZivotPoddanych

SinPredkuEvents = _sin_predku.SinPredkuEvents
SinPredku = _sin_predku.SinPredku

Finished = _finished.Finished


__all__ = [
    "StartEvents",
    "Start",
    "TricetValkaEvents",
    "TricetValka",
    "AdolfEvents",
    "Adolf",
    "ObchodStoletiEvents",
    "ObchodStoleti",
    "ZalozeniSpitaluEvents",
    "ZalozeniSpitalu",
    "JerabEvents",
    "Jerab",
    "ZivotPoddanychEvents",
    "ZivotPoddanych",
    "SinPredkuEvents",
    "SinPredku",
    "Finished",
]

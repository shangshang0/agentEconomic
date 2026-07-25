#!/usr/bin/env python3
"""Fetch a small reproducible CC0 Poly Haven pack from its public API.

The API tells us the exact dependent .bin and texture URLs for each glTF asset;
using it prevents version-specific or resolution-specific broken imports.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen, urlretrieve

ROOT = Path(sys.argv[1])
MODELS = [
    "WoodenTable_01", "SchoolChair_01", "concrete_road_barrier",
    "fire_hydrant", "exterior_aircon_unit", "fir_tree_01", "barrel_03",
    "cardboard_box_01", "covered_car", "portable_generator", "power_box_01",
    "medical_box", "industrial_storage_cart", "street_lamp_01", "modular_chainlink_fence",
]
TEXTURES = ["aerial_asphalt_01", "wooden_planks", "concrete_floor_worn_001", "brick_wall_001"]


def api(asset: str) -> dict:
    request = Request(
        f"https://api.polyhaven.com/files/{asset}",
        headers={"User-Agent": "AuthorityLab3D/0.1 research asset fetcher"},
    )
    with urlopen(request) as response:
        return json.load(response)


def get(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    print(f"download {path.relative_to(ROOT)}")
    urlretrieve(url, path)


def fetch_model(name: str) -> None:
    entry = api(name)["gltf"]["1k"]["gltf"]
    target = ROOT / "models" / name
    get(entry["url"], target / f"{name}.gltf")
    for relative_name, dependency in entry["include"].items():
        get(dependency["url"], target / relative_name)


def fetch_texture(name: str) -> None:
    entry = api(name)
    target = ROOT / "textures" / name
    wanted = [("Diffuse", "diff.jpg"), ("nor_gl", "normal.jpg"), ("Rough", "rough.jpg")]
    for category, filename in wanted:
        if category not in entry:
            continue
        source = entry[category]["1k"]["jpg"]
        get(source["url"], target / filename)


def fetch_hdri() -> None:
    source = api("abandoned_parking")["hdri"]["2k"]["hdr"]
    get(source["url"], ROOT / "hdr" / "abandoned_parking_2k.hdr")


for model in MODELS:
    fetch_model(model)
for texture in TEXTURES:
    fetch_texture(texture)
fetch_hdri()
print(f"CC0 asset pack ready at {ROOT}")

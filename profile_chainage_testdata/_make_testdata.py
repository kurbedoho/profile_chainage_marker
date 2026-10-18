# -*- coding: utf-8 -*-
import json
import os
from pathlib import Path

import shapefile

out = Path(__file__).resolve().parent
out.mkdir(parents=True, exist_ok=True)

# CRS: EPSG:32637 (UTM 37N), metres — flat projected coordinates
profiles = [
    # ID 1: 1187 m horizontal — scale labels to 1200
    (1, [(500000.0, 4500000.0), (501187.0, 4500000.0)]),
    # ID 2: exactly 1000 m
    (2, [(500000.0, 4500100.0), (501000.0, 4500100.0)]),
    # ID 3: short 35 m — start+end only when step=10
    (3, [(500000.0, 4500200.0), (500035.0, 4500200.0)]),
    # ID 4: 500 m right-to-left — reverse checkbox test
    (4, [(500500.0, 4500300.0), (500000.0, 4500300.0)]),
    # ID 5: polyline 700 m (300+200+200)
    (
        5,
        [
            (500000.0, 4500400.0),
            (500300.0, 4500400.0),
            (500300.0, 4500600.0),
            (500500.0, 4500600.0),
        ],
    ),
]


def line_length(pts):
    total = 0.0
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        total += (dx * dx + dy * dy) ** 0.5
    return total


shp_path = out / "profiles_test"
w = shapefile.Writer(str(shp_path), shapeType=shapefile.POLYLINE)
w.field("ID", "N", 10, 0)
for pid, pts in profiles:
    w.line([pts])
    w.record(pid)
w.close()

prj = (
    'PROJCS["WGS_1984_UTM_Zone_37N",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],'
    'PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],'
    'PARAMETER["Central_Meridian",39.0],PARAMETER["Scale_Factor",0.9996],'
    'PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]'
)
(shp_path.with_suffix(".prj")).write_text(prj, encoding="utf-8")

features = []
for pid, pts in profiles:
    length = line_length(pts)
    features.append(
        {
            "type": "Feature",
            "properties": {"ID": pid, "len_m": round(length, 3)},
            "geometry": {
                "type": "LineString",
                "coordinates": [[x, y] for x, y in pts],
            },
        }
    )

geo = {
    "type": "FeatureCollection",
    "name": "profiles_test",
    "crs": {
        "type": "name",
        "properties": {"name": "urn:ogc:def:crs:EPSG::32637"},
    },
    "features": features,
}
(out / "profiles_test.geojson").write_text(
    json.dumps(geo, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

readme = """# Тестовые профили для Profile Chainage Marker

CRS: EPSG:32637 (WGS 84 / UTM zone 37N), единицы — метры (плоская система).

Файл: profiles_test.shp  (+ profiles_test.geojson)

ID | Описание              | Реальная длина | Подсказка
---|-----------------------|----------------|----------
1  | Горизонталь вправо    | 1187 м         | Длина разметки 1200, шаг 100 → масштаб подписей
2  | Горизонталь вправо    | 1000 м         | Длина 1000, шаг 100
3  | Короткая              | 35 м           | Шаг 10 → только начало и конец
4  | Горизонталь влево     | 500 м          | Галочка «Развернуть» меняет ноль
5  | Ломаная               | 800 м          | Шаг 50 / длина 800

Defaults в плагине для быстрого теста: шаг=100, длина разметки=1200, старт=0.
Потом для ID 2–5 подправьте «Длину разметки» в таблице под реальную.
"""
(out / "README.txt").write_text(readme, encoding="utf-8")

print("Written to:", out)
for name in sorted(os.listdir(out)):
    p = out / name
    if p.is_file():
        print(f"  {name} ({p.stat().st_size} bytes)")
for pid, pts in profiles:
    print(f"ID {pid}: {line_length(pts):.3f} m")

# -*- coding: utf-8 -*-
"""Расчёт точек разметки профиля."""

import math

from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsPointXY,
    QgsWkbTypes,
)

# Соответствует Qgis.LabelQuadrantPosition / QgsPalLayerSettings.QuadrantPosition
LAB_Q_ABOVE_LEFT = 0
LAB_Q_ABOVE = 1
LAB_Q_ABOVE_RIGHT = 2
LAB_Q_LEFT = 3
LAB_Q_OVER = 4
LAB_Q_RIGHT = 5
LAB_Q_BELOW_LEFT = 6
LAB_Q_BELOW = 7
LAB_Q_BELOW_RIGHT = 8


def _tangent_at(geom: QgsGeometry, distance: float):
    """Касательный вектор линии в точке на расстоянии distance."""
    length = geom.length()
    if length <= 0:
        return 0.0, 0.0
    eps = max(length * 1e-4, 1e-6)
    d0 = max(0.0, min(length, distance - eps))
    d1 = max(0.0, min(length, distance + eps))
    if d1 <= d0:
        d0 = max(0.0, distance - eps)
        d1 = min(length, d0 + eps)
    p0 = geom.interpolate(d0)
    p1 = geom.interpolate(d1)
    if p0 is None or p1 is None or p0.isEmpty() or p1.isEmpty():
        return 0.0, 0.0
    a = p0.asPoint()
    b = p1.asPoint()
    return b.x() - a.x(), b.y() - a.y()


def label_quadrant_for_tangent(dx: float, dy: float) -> int:
    """
    Квадрант подписи перпендикулярно линии, чтобы не ложилась на линию.
    При равных вариантах предпочитаем вверх, затем влево.
    """
    length = math.hypot(dx, dy)
    if length < 1e-12:
        return LAB_Q_ABOVE
    dx /= length
    dy /= length
    # два перпендикуляра
    candidates = ((-dy, dx), (dy, -dx))

    def score(nx, ny):
        return ny * 2.0 - nx

    nx, ny = max(candidates, key=lambda v: score(v[0], v[1]))

    ax, ay = abs(nx), abs(ny)
    if ay >= ax * 1.2:
        return LAB_Q_ABOVE if ny > 0 else LAB_Q_BELOW
    if ax >= ay * 1.2:
        return LAB_Q_LEFT if nx < 0 else LAB_Q_RIGHT
    if ny > 0 and nx < 0:
        return LAB_Q_ABOVE_LEFT
    if ny > 0 and nx >= 0:
        return LAB_Q_ABOVE_RIGHT
    if ny <= 0 and nx < 0:
        return LAB_Q_BELOW_LEFT
    return LAB_Q_BELOW_RIGHT


def as_single_line(geometry):
    """Вернуть одну линию (для multipart — самая длинная часть)."""
    if geometry is None or geometry.isEmpty():
        return None

    geom = QgsGeometry(geometry)
    if QgsWkbTypes.isMultiType(geom.wkbType()):
        parts = geom.asGeometryCollection()
        best = None
        best_len = -1.0
        for part in parts:
            if part.type() != QgsWkbTypes.GeometryType.LineGeometry:
                continue
            length = part.length()
            if length > best_len:
                best_len = length
                best = part
        return QgsGeometry(best) if best is not None else None

    if geom.type() != QgsWkbTypes.GeometryType.LineGeometry:
        return None
    return geom


def reversed_line(geometry):
    """Развернуть линию без изменения исходного объекта."""
    geom = as_single_line(geometry)
    if geom is None:
        return QgsGeometry()

    engine = geom.constGet().clone()
    if isinstance(engine, QgsLineString):
        return QgsGeometry(engine.reversed())
    if isinstance(engine, QgsMultiLineString) and engine.numGeometries() > 0:
        line = engine.geometryN(0)
        if isinstance(line, QgsLineString):
            return QgsGeometry(line.reversed())

    pts = geom.asPolyline()
    if not pts:
        multi = geom.asMultiPolyline()
        if not multi:
            return QgsGeometry(geom)
        pts = multi[0]
    pts = list(reversed(pts))
    return QgsGeometry.fromPolylineXY(pts)


def direction_endpoints(geometry, reverse: bool):
    """Точки начала/конца с учётом разворота."""
    geom = as_single_line(geometry)
    if geom is None:
        return None, None
    if reverse:
        geom = reversed_line(geom)
    polyline = geom.asPolyline()
    if len(polyline) < 2:
        multi = geom.asMultiPolyline()
        if not multi or len(multi[0]) < 2:
            return None, None
        polyline = multi[0]
    return QgsPointXY(polyline[0]), QgsPointXY(polyline[-1])


def _polyline_vertices(geom: QgsGeometry):
    pts = geom.asPolyline()
    if pts:
        return list(pts)
    multi = geom.asMultiPolyline()
    if multi:
        return list(multi[0])
    return []


def mark_values(start_mark: float, step: float, length_mark: float):
    """Список значений подписей от start до start+length, конец всегда включён."""
    end_mark = start_mark + length_mark
    if length_mark <= 0:
        return [start_mark, end_mark]

    if step <= 0 or length_mark <= step:
        return [start_mark, end_mark]

    values = []
    current = start_mark
    max_points = int(length_mark / step) + 3
    for _ in range(max_points):
        if current >= end_mark - 1e-9:
            break
        values.append(round(current, 10))
        current += step

    if not values:
        values = [start_mark]
    if abs(values[-1] - end_mark) > 1e-9:
        values.append(round(end_mark, 10))
    else:
        values[-1] = round(end_mark, 10)
    return values


def _mark_from_fraction(start_mark: float, length_mark: float, fraction: float) -> float:
    fraction = max(0.0, min(1.0, fraction))
    if length_mark > 0:
        return round(start_mark + fraction * length_mark, 10)
    return start_mark if fraction < 0.5 else start_mark + length_mark


def _merge_mark_stations(stations, tol_fraction: float):
    """Слить близкие станции: [(fraction, mark), ...], сортировка по fraction."""
    if not stations:
        return []
    stations = sorted(stations, key=lambda x: x[0])
    merged = [stations[0]]
    for frac, mark in stations[1:]:
        prev_frac, prev_mark = merged[-1]
        if abs(frac - prev_frac) <= tol_fraction:
            # оставляем уже имеющуюся (шаговую), если совпало с изгибом
            continue
        merged.append((frac, mark))
    return merged


def bend_stations(geom: QgsGeometry, real_length: float, start_mark: float, length_mark: float):
    """
    Промежуточные вершины (изгибы) с отметками, масштабированными
    в диапазон [start_mark, start_mark + length_mark] по доле длины.
    Пример: линия целиком размечена от 100 до 200, изгиб посередине → 150.
    """
    verts = _polyline_vertices(geom)
    if len(verts) < 3 or real_length <= 0:
        return []

    stations = []
    # без первой и последней вершины — они уже есть как начало/конец
    for pt in verts[1:-1]:
        dist = geom.lineLocatePoint(QgsGeometry.fromPointXY(QgsPointXY(pt)))
        if dist < 0:
            continue
        fraction = dist / real_length
        # пропускаем почти концы
        if fraction <= 1e-9 or fraction >= 1.0 - 1e-9:
            continue
        mark = _mark_from_fraction(start_mark, length_mark, fraction)
        stations.append((fraction, mark))
    return stations


def build_point_features(
    geometry,
    reverse: bool,
    step: float,
    length_mark: float,
    start_mark: float,
    profile_id,
    fields,
    include_bends: bool = False,
):
    """
    Создать точечные фичи на линии.
    Подписи масштабируются под length_mark; координаты — по реальной длине.
    При include_bends добавляются точки на промежуточных вершинах
    с отметкой по той же шкале разметки.
    """
    geom = as_single_line(geometry)
    if geom is None:
        return []

    if reverse:
        geom = reversed_line(geom)

    real_length = geom.length()
    if real_length <= 0:
        return []

    stations = []
    marks = mark_values(start_mark, step, length_mark)
    for mark in marks:
        if length_mark > 0:
            fraction = (mark - start_mark) / length_mark
        else:
            fraction = 0.0 if mark == start_mark else 1.0
        fraction = max(0.0, min(1.0, fraction))
        stations.append((fraction, mark))

    if include_bends:
        stations.extend(bend_stations(geom, real_length, start_mark, length_mark))

    stations = _merge_mark_stations(stations, tol_fraction=1e-9)

    features = []
    has_lab_q = fields.indexFromName("lab_q") >= 0
    for seq, (fraction, mark) in enumerate(stations):
        distance = fraction * real_length
        point_geom = geom.interpolate(distance)
        if point_geom is None or point_geom.isEmpty():
            continue

        feat = QgsFeature(fields)
        feat.setGeometry(point_geom)
        feat.setAttribute("profile_id", profile_id)
        feat.setAttribute("mark", mark)
        feat.setAttribute("seq", seq)
        if has_lab_q:
            dx, dy = _tangent_at(geom, distance)
            feat.setAttribute("lab_q", label_quadrant_for_tangent(dx, dy))
        features.append(feat)
    return features

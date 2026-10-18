# -*- coding: utf-8 -*-
"""Qt5 / Qt6 enum compatibility helpers for QGIS plugins."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import QAbstractItemView, QHeaderView
from qgis.core import QgsMapLayerProxyModel, QgsPalLayerSettings, QgsWkbTypes
from qgis.gui import QgsVertexMarker


def enum_member(container, *parts):
    """
    Resolve nested Qt6-style enums with Qt5 flat fallback.

    enum_member(Qt, 'ItemDataRole', 'UserRole')
      -> Qt.ItemDataRole.UserRole (Qt6) or Qt.UserRole (Qt5)
    """
    if len(parts) == 1:
        return getattr(container, parts[0])
    group = getattr(container, parts[0], None)
    member = parts[1]
    if group is not None and hasattr(group, member):
        return getattr(group, member)
    return getattr(container, member)


# Qt.Core
UserRole = enum_member(Qt, "ItemDataRole", "UserRole")
ItemIsEditable = enum_member(Qt, "ItemFlag", "ItemIsEditable")
ItemIsUserCheckable = enum_member(Qt, "ItemFlag", "ItemIsUserCheckable")
ItemIsEnabled = enum_member(Qt, "ItemFlag", "ItemIsEnabled")
ItemIsSelectable = enum_member(Qt, "ItemFlag", "ItemIsSelectable")
Checked = enum_member(Qt, "CheckState", "Checked")
Unchecked = enum_member(Qt, "CheckState", "Unchecked")

# Qt Widgets
HeaderStretch = enum_member(QHeaderView, "ResizeMode", "Stretch")
HeaderResizeToContents = enum_member(QHeaderView, "ResizeMode", "ResizeToContents")
SelectRows = enum_member(QAbstractItemView, "SelectionBehavior", "SelectRows")
SingleSelection = enum_member(QAbstractItemView, "SelectionMode", "SingleSelection")

# Qt Gui
FontBold = enum_member(QFont, "Weight", "Bold")

# QGIS
LineLayerFilter = enum_member(QgsMapLayerProxyModel, "Filter", "LineLayer")
LineGeometry = enum_member(QgsWkbTypes, "GeometryType", "LineGeometry")
VertexIconCircle = enum_member(QgsVertexMarker, "IconType", "ICON_CIRCLE")


def pal_over_point():
    """Label placement OverPoint for Qt5/Qt6 QGIS builds."""
    if hasattr(QgsPalLayerSettings, "PredefinedPointPosition"):
        return QgsPalLayerSettings.PredefinedPointPosition.OverPoint
    if hasattr(QgsPalLayerSettings, "Placement"):
        return QgsPalLayerSettings.Placement.OverPoint
    return QgsPalLayerSettings.OverPoint

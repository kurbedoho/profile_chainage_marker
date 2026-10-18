# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .profile_dialog import ProfileChainageDialog


def _read_metadata(plugin_dir):
    meta = {}
    path = os.path.join(plugin_dir, "metadata.txt")
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("[") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            meta[key.strip()] = value.strip()
    return meta


def _format_release_date(value):
    """YYYY-MM-DD -> DD.MM.YYYY"""
    parts = value.split("-")
    if len(parts) == 3 and all(parts):
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return value


def plugin_display_name(plugin_dir, russian=False):
    meta = _read_metadata(plugin_dir)
    version = meta.get("version", "").strip()
    date_raw = meta.get("releasedate", "").strip()
    date_disp = _format_release_date(date_raw) if date_raw else ""

    if version and date_disp:
        suffix = f" {version} ({date_disp})"
    elif version:
        suffix = f" {version}"
    elif date_disp:
        suffix = f" ({date_disp})"
    else:
        suffix = ""

    if russian:
        return f"Разметка профилей{suffix}"
    base = meta.get("name", "Profile Chainage Marker")
    # если в name уже есть версия — не дублировать
    if version and version in base:
        return base
    return f"Profile Chainage Marker{suffix}"


class ProfileChainageMarkerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.plugin_dir = os.path.dirname(__file__)
        self.menu_title = plugin_display_name(self.plugin_dir, russian=True)

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.svg")
        title = self.menu_title
        self.action = QAction(
            QIcon(icon_path),
            title,
            self.iface.mainWindow(),
        )
        self.action.setToolTip(
            f"{title} — разметка линий-профилей точками по длине"
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(title, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.dialog is not None:
            self.dialog.cleanup()
            self.dialog.close()
            self.dialog = None
        if self.action is not None:
            self.iface.removePluginVectorMenu(self.menu_title, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = ProfileChainageDialog(self.iface, self.iface.mainWindow())
        self.dialog.setWindowTitle(self.menu_title)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

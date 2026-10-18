# -*- coding: utf-8 -*-
import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .profile_dialog import ProfileChainageDialog


class ProfileChainageMarkerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, "icon.svg")
        self.action = QAction(
            QIcon(icon_path),
            "Разметка профилей",
            self.iface.mainWindow(),
        )
        self.action.setToolTip("Разметка линий-профилей точками по длине")
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu("Разметка профилей", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        if self.dialog is not None:
            self.dialog.cleanup()
            self.dialog.close()
            self.dialog = None
        if self.action is not None:
            self.iface.removePluginVectorMenu("Разметка профилей", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None

    def run(self):
        if self.dialog is None:
            self.dialog = ProfileChainageDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

# -*- coding: utf-8 -*-
import math

from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from qgis.core import (
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsMapLayerComboBox, QgsRubberBand, QgsVertexMarker

from .chainage import as_single_line, build_point_features, reversed_line


COL_ID = 0
COL_REAL = 1
COL_STEP = 2
COL_LMARK = 3
COL_START = 4
COL_REVERSE = 5

ARROW_COUNT = 10


class ProfileChainageDialog(QDialog):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.source_layer = None
        self.feature_by_row = {}
        self.id_field_name = None

        self.rubber_lines = []
        self.rubber_arrows = None
        self.markers_start = []
        self.markers_end = []

        self._build_ui()
        self.clear_map_preview()

    def _build_ui(self):
        self.setWindowTitle("Разметка профилей")
        self.resize(900, 560)

        root = QVBoxLayout(self)

        source_box = QGroupBox("Исходные линии")
        source_layout = QHBoxLayout(source_box)
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.LineLayer)
        try:
            self.layer_combo.setAllowEmptyLayer(True)
        except Exception:
            pass
        source_layout.addWidget(QLabel("Слой:"))
        source_layout.addWidget(self.layer_combo, 1)
        root.addWidget(source_box)

        defaults_box = QGroupBox("Параметры по умолчанию")
        form = QFormLayout(defaults_box)
        self.spin_step = QDoubleSpinBox()
        self.spin_step.setDecimals(3)
        self.spin_step.setRange(0.001, 1_000_000)
        self.spin_step.setValue(10.0)
        self.spin_start = QDoubleSpinBox()
        self.spin_start.setDecimals(3)
        self.spin_start.setRange(-1_000_000_000, 1_000_000_000)
        self.spin_start.setValue(0.0)
        form.addRow("Шаг разметки:", self.spin_step)
        form.addRow("Старт подписи (0-отметка):", self.spin_start)

        self.chk_bends = QCheckBox("Ставить точки на изгибах")
        self.chk_bends.setToolTip(
            "Дополнительные точки на промежуточных вершинах линии. "
            "Отметка считается по доле длины и масштабируется "
            "в диапазон «Старт … Старт + Длина разметки» "
            "(например линия от 100 до 200, изгиб посередине → 150)."
        )
        form.addRow(self.chk_bends)

        btn_apply_defaults = QPushButton("Применить шаг и старт ко всем строкам")
        form.addRow(btn_apply_defaults)
        root.addWidget(defaults_box)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Реальная длина",
                "Шаг",
                "Длина разметки",
                "Старт",
                "Развернуть",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(COL_REVERSE, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        root.addWidget(self.table, 1)

        hint = QLabel(
            "На карте у каждого профиля: зелёная точка — начало (0), красная — конец, "
            "10 стрелок вдоль геометрии. Исходный слой не меняется. "
            "Подписи mark масштабируются под «Длину разметки»."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        buttons = QHBoxLayout()
        btn_generate = QPushButton("Создать точки")
        btn_generate.setDefault(True)
        btn_close = QPushButton("Закрыть")
        buttons.addStretch(1)
        buttons.addWidget(btn_generate)
        buttons.addWidget(btn_close)
        root.addLayout(buttons)

        btn_apply_defaults.clicked.connect(self.apply_defaults_to_table)
        btn_generate.clicked.connect(self.generate_points)
        btn_close.clicked.connect(self.close)
        self.layer_combo.layerChanged.connect(self.on_layer_changed)
        self.table.cellChanged.connect(self.on_cell_changed)

        # если слой уже выбран в комбо при открытии — сразу заполнить
        current = self.layer_combo.currentLayer()
        if current is not None:
            self.populate_table(current)

    def cleanup(self):
        self.clear_map_preview()

    def closeEvent(self, event):
        self.clear_map_preview()
        super().closeEvent(event)

    def _remove_canvas_item(self, item):
        if item is None:
            return
        try:
            self.canvas.scene().removeItem(item)
        except Exception:
            pass

    def clear_map_preview(self):
        for rb in self.rubber_lines:
            rb.reset(QgsWkbTypes.LineGeometry)
            self._remove_canvas_item(rb)
        self.rubber_lines = []

        if self.rubber_arrows is not None:
            self.rubber_arrows.reset(QgsWkbTypes.LineGeometry)
            self._remove_canvas_item(self.rubber_arrows)
            self.rubber_arrows = None

        for m in self.markers_start + self.markers_end:
            m.hide()
            self._remove_canvas_item(m)
        self.markers_start = []
        self.markers_end = []
        self.canvas.refresh()

    def on_layer_changed(self, layer):
        if layer is None:
            self.table.blockSignals(True)
            self.table.setRowCount(0)
            self.feature_by_row.clear()
            self.source_layer = None
            self.table.blockSignals(False)
            self.clear_map_preview()
            return
        self.populate_table(layer)

    def _id_field_name(self, layer: QgsVectorLayer):
        fields = layer.fields()
        for candidate in ("ID", "Id", "id"):
            if fields.indexFromName(candidate) >= 0:
                return candidate
        for field in fields:
            if field.name().lower() == "id":
                return field.name()
        if fields.count():
            return fields[0].name()
        return None

    def populate_table(self, layer: QgsVectorLayer):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.feature_by_row.clear()
        self.source_layer = layer
        self.clear_map_preview()

        if layer is None or not layer.isValid():
            self.table.blockSignals(False)
            return

        self.id_field_name = self._id_field_name(layer)
        if self.id_field_name is None:
            QMessageBox.warning(self, "Поля", "У слоя нет атрибутов.")
            self.table.blockSignals(False)
            return

        step = self.spin_step.value()
        start = self.spin_start.value()

        row = 0
        for feat in layer.getFeatures():
            geom = as_single_line(feat.geometry())
            if geom is None:
                continue
            real_len = geom.length()
            profile_id = feat[self.id_field_name]

            self.table.insertRow(row)
            self.feature_by_row[row] = feat.id()

            item_id = QTableWidgetItem(str(profile_id))
            item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, COL_ID, item_id)

            item_real = QTableWidgetItem(f"{real_len:.3f}")
            item_real.setFlags(item_real.flags() & ~Qt.ItemIsEditable)
            item_real.setData(Qt.UserRole, real_len)
            self.table.setItem(row, COL_REAL, item_real)

            # длина разметки по умолчанию — реальная длина, округлённая до целых
            default_lmark = float(round(real_len))
            self.table.setItem(row, COL_STEP, self._number_item(step))
            self.table.setItem(row, COL_LMARK, self._number_item(default_lmark))
            self.table.setItem(row, COL_START, self._number_item(start))

            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk.setCheckState(Qt.Unchecked)
            self.table.setItem(row, COL_REVERSE, chk)
            row += 1

        self.table.blockSignals(False)
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "Данные", "В слое нет линейных объектов.")
        else:
            self.refresh_map_preview()

    @staticmethod
    def _number_item(value: float) -> QTableWidgetItem:
        item = QTableWidgetItem(f"{value:g}")
        item.setData(Qt.UserRole, float(value))
        return item

    def apply_defaults_to_table(self):
        if self.table.rowCount() == 0:
            return
        self.table.blockSignals(True)
        step = self.spin_step.value()
        start = self.spin_start.value()
        for row in range(self.table.rowCount()):
            self.table.setItem(row, COL_STEP, self._number_item(step))
            self.table.setItem(row, COL_START, self._number_item(start))
        self.table.blockSignals(False)

    def on_cell_changed(self, row, column):
        if column == COL_REVERSE:
            self.refresh_map_preview()
        elif column in (COL_STEP, COL_LMARK, COL_START):
            item = self.table.item(row, column)
            if item is None:
                return
            try:
                value = float(item.text().replace(",", "."))
            except ValueError:
                value = float(item.data(Qt.UserRole) or 0)
                self.table.blockSignals(True)
                item.setText(f"{value:g}")
                self.table.blockSignals(False)
            item.setData(Qt.UserRole, value)

    def _row_reverse(self, row: int) -> bool:
        item = self.table.item(row, COL_REVERSE)
        return item is not None and item.checkState() == Qt.Checked

    def refresh_map_preview(self):
        self.clear_map_preview()
        if self.source_layer is None or self.table.rowCount() == 0:
            return

        self.rubber_arrows = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rubber_arrows.setColor(QColor(231, 76, 60, 230))
        self.rubber_arrows.setWidth(2)

        for row in range(self.table.rowCount()):
            feat_id = self.feature_by_row.get(row)
            if feat_id is None:
                continue
            feat = self.source_layer.getFeature(feat_id)
            if not feat.isValid():
                continue

            geom = as_single_line(feat.geometry())
            if geom is None:
                continue

            reverse = self._row_reverse(row)
            draw_geom = reversed_line(geom) if reverse else QgsGeometry(geom)
            length = draw_geom.length()
            if length <= 0:
                continue

            line_rb = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
            line_rb.setColor(QColor(31, 78, 121, 160))
            line_rb.setWidth(2)
            line_rb.setToGeometry(draw_geom, self.source_layer)
            self.rubber_lines.append(line_rb)

            start_pt = draw_geom.interpolate(0.0)
            end_pt = draw_geom.interpolate(length)
            if not start_pt.isEmpty():
                self.markers_start.append(
                    self._make_marker(start_pt.asPoint(), QColor(39, 174, 96))
                )
            if not end_pt.isEmpty():
                self.markers_end.append(
                    self._make_marker(end_pt.asPoint(), QColor(231, 76, 60))
                )

            for arrow_geom in self._arrows_along_line(draw_geom, ARROW_COUNT):
                self.rubber_arrows.addGeometry(arrow_geom, self.source_layer)

        self.canvas.refresh()

    def _make_marker(self, point, color: QColor) -> QgsVertexMarker:
        marker = QgsVertexMarker(self.canvas)
        marker.setColor(color)
        marker.setFillColor(color)
        marker.setIconSize(10)
        marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
        marker.setPenWidth(2)
        marker.setCenter(QgsPointXY(point))
        marker.show()
        return marker

    def _arrows_along_line(self, geom: QgsGeometry, count: int):
        """10 стрелок равномерно вдоль линии, касательная следует геометрии."""
        length = geom.length()
        if length <= 0 or count <= 0:
            return []

        # размер стрелки от длины профиля и масштаба карты
        map_units_per_px = self.canvas.mapUnitsPerPixel()
        size_by_line = length / (count * 5.0)
        size_by_screen = map_units_per_px * 14.0
        arrow_len = max(min(size_by_line, length * 0.08), size_by_screen * 0.35)
        # шаг вдоль линии для оценки касательной
        sample = max(arrow_len * 0.35, length * 1e-4)

        arrows = []
        for i in range(count):
            # равномерно внутри линии, не на самых концах
            t = (i + 0.5) / count
            dist = t * length
            d0 = max(0.0, dist - sample * 0.5)
            d1 = min(length, dist + sample * 0.5)
            if d1 <= d0:
                continue
            g0 = geom.interpolate(d0)
            g1 = geom.interpolate(d1)
            if g0.isEmpty() or g1.isEmpty():
                continue
            p0 = g0.asPoint()
            p1 = g1.asPoint()
            tip_g = geom.interpolate(dist)
            if tip_g.isEmpty():
                continue
            tip = tip_g.asPoint()
            arrow = self._arrow_head_geometry(
                QgsPointXY(p0.x(), p0.y()),
                QgsPointXY(p1.x(), p1.y()),
                QgsPointXY(tip.x(), tip.y()),
                arrow_len,
            )
            if arrow is not None:
                arrows.append(arrow)
        return arrows

    @staticmethod
    def _arrow_head_geometry(p_back, p_fwd, tip, arrow_len):
        dx = p_fwd.x() - p_back.x()
        dy = p_fwd.y() - p_back.y()
        hyp = math.hypot(dx, dy)
        if hyp < 1e-12:
            return None
        ux, uy = dx / hyp, dy / hyp
        # хвостик и наконечник относительно tip, вдоль локальной касательной
        tail = QgsPointXY(tip.x() - ux * arrow_len, tip.y() - uy * arrow_len)
        head = tip
        px, py = -uy, ux
        wing = arrow_len * 0.45
        left = QgsPointXY(
            head.x() - ux * wing + px * wing * 0.7,
            head.y() - uy * wing + py * wing * 0.7,
        )
        right = QgsPointXY(
            head.x() - ux * wing - px * wing * 0.7,
            head.y() - uy * wing - py * wing * 0.7,
        )
        return QgsGeometry.fromPolylineXY([tail, head, left, head, right])

    def _row_number(self, row: int, column: int) -> float:
        item = self.table.item(row, column)
        if item is None:
            return 0.0
        data = item.data(Qt.UserRole)
        if data is not None:
            try:
                return float(data)
            except (TypeError, ValueError):
                pass
        try:
            return float(item.text().replace(",", "."))
        except ValueError:
            return 0.0

    def generate_points(self):
        if self.source_layer is None or self.table.rowCount() == 0:
            QMessageBox.information(self, "Данные", "Сначала загрузите линии в таблицу.")
            return

        crs = self.source_layer.crs()
        fields = QgsFields()
        fields.append(QgsField("profile_id", QVariant.String))
        fields.append(QgsField("mark", QVariant.Double))
        fields.append(QgsField("seq", QVariant.Int))

        uri = f"Point?crs={crs.authid()}"
        out_layer = QgsVectorLayer(uri, "profile_marks", "memory")
        provider = out_layer.dataProvider()
        provider.addAttributes(fields)
        out_layer.updateFields()

        all_features = []
        for row in range(self.table.rowCount()):
            feat = self.source_layer.getFeature(self.feature_by_row[row])
            if not feat.isValid():
                continue

            reverse = self._row_reverse(row)
            step = self._row_number(row, COL_STEP)
            length_mark = self._row_number(row, COL_LMARK)
            start_mark = self._row_number(row, COL_START)
            profile_id = self.table.item(row, COL_ID).text()

            if step <= 0:
                QMessageBox.warning(
                    self,
                    "Шаг",
                    f"У профиля {profile_id} шаг должен быть > 0.",
                )
                return

            built = build_point_features(
                feat.geometry(),
                reverse,
                step,
                length_mark,
                start_mark,
                profile_id,
                out_layer.fields(),
                include_bends=self.chk_bends.isChecked(),
            )
            all_features.extend(built)

        if not all_features:
            QMessageBox.warning(self, "Результат", "Не удалось создать точки.")
            return

        provider.addFeatures(all_features)
        out_layer.updateExtents()

        from qgis.core import QgsPalLayerSettings, QgsVectorLayerSimpleLabeling

        settings = QgsPalLayerSettings()
        settings.fieldName = "mark"
        settings.enabled = True
        try:
            settings.placement = QgsPalLayerSettings.Placement.OverPoint
        except AttributeError:
            settings.placement = QgsPalLayerSettings.OverPoint
        out_layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
        out_layer.setLabelsEnabled(True)

        QgsProject.instance().addMapLayer(out_layer)
        self.iface.setActiveLayer(out_layer)
        QMessageBox.information(
            self,
            "Готово",
            f"Создан временный слой «profile_marks»: {len(all_features)} точек.",
        )

# -*- coding: utf-8 -*-
"""UI language from QGIS locale: Russian if QGIS is Russian, else English."""

from qgis.PyQt.QtCore import QSettings

try:
    from qgis.core import QgsSettings, QgsApplication
except ImportError:  # pragma: no cover
    QgsSettings = None
    QgsApplication = None

# English source -> Russian
_RU = {
    "Profile Chainage Marker": "Разметка профилей",
    "Mark chainage points along profile lines": (
        "Разметка линий-профилей точками по длине"
    ),
    "Source lines": "Исходные линии",
    "Layer:": "Слой:",
    "Default parameters": "Параметры по умолчанию",
    "Mark step:": "Шаг разметки:",
    "Apply step to all rows": "Применить шаг ко всем строкам",
    "Marking options": "Опции разметки",
    "Place points at bends": "Ставить точки на изгибах",
    "Extra points at intermediate line vertices. "
    "The mark is scaled to Mark length "
    "(e.g. marks 0…200, bend in the middle → 100).": (
        "Дополнительные точки на промежуточных вершинах линии. "
        "Отметка масштабируется под «Длину разметки» "
        "(например разметка 0…200, изгиб посередине → 100)."
    ),
    "ID": "ID",
    "Real length": "Реальная длина",
    "Step": "Шаг",
    "Mark length": "Длина разметки",
    "Reverse": "Развернуть",
    "On the map: ID at the profile start, direction arrows, "
    "preview of mark points with labels (start is always 0). "
    "The source layer is not modified.": (
        "На карте: ID у начала профиля, стрелки направления, "
        "превью точек с подписями mark (старт всегда 0). "
        "Исходный слой не меняется."
    ),
    "Create points": "Создать точки",
    "Close": "Закрыть",
    "Fields": "Поля",
    "The layer has no attributes.": "У слоя нет атрибутов.",
    "Data": "Данные",
    "The layer has no line features.": "В слое нет линейных объектов.",
    "Load lines into the table first.": "Сначала загрузите линии в таблицу.",
    "Profile {id}: step must be greater than 0.": (
        "У профиля {id} шаг должен быть > 0."
    ),
    "Result": "Результат",
    "Could not create points.": "Не удалось создать точки.",
    "Done": "Готово",
    "Temporary layer “profile_marks” created: {count} points.": (
        "Создан временный слой «profile_marks»: {count} точек."
    ),
    "profile ID preview": "превью ID профилей",
    "mark preview": "превью разметки",
}


def _settings():
    if QgsSettings is not None:
        return QgsSettings()
    return QSettings()


def qgis_locale_code():
    """Return QGIS UI locale like 'ru' or 'en'."""
    locale = ""
    if QgsApplication is not None:
        try:
            app = QgsApplication.instance()
            if app is not None and hasattr(app, "locale"):
                locale = app.locale() or ""
        except (AttributeError, RuntimeError, TypeError):
            locale = ""
    if not locale:
        s = _settings()
        locale = s.value("locale/userLocale", "", type=str) or ""
        if not locale:
            locale = s.value("locale/globalLocale", "", type=str) or ""
    locale = str(locale).replace("-", "_")
    if "_" in locale:
        locale = locale.split("_", 1)[0]
    return locale.lower() or "en"


def resolve_language():
    """Russian only when QGIS UI is Russian; otherwise English."""
    if qgis_locale_code().startswith("ru"):
        return "ru"
    return "en"


def tr(text: str, **kwargs) -> str:
    """Translate English source string; optional format kwargs."""
    out = text
    if resolve_language() == "ru":
        out = _RU.get(text, text)
    if kwargs:
        return out.format(**kwargs)
    return out


def plugin_title(version_suffix: str = "") -> str:
    return f"{tr('Profile Chainage Marker')}{version_suffix}"

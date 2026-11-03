import os
import json
import datetime
import hashlib
import math
import requests
import logging
import traceback
import sys
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit, QComboBox, QScrollArea,
                             QGridLayout, QFrame, QFileDialog, QMessageBox, QProgressBar,
                             QTextEdit, QSplashScreen, QDialog, QCheckBox, QStyleFactory,
                             QButtonGroup, QStackedWidget, QSizePolicy, QGraphicsDropShadowEffect)
from PyQt6.QtCore import (Qt, QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QSize,
                          QTimer, QUrl, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPointF, QEvent,
                          pyqtProperty)
from PyQt6.QtGui import (QPixmap, QFont, QIcon, QColor, QDesktopServices, QPainter, QPen,
                         QCursor, QLinearGradient, QPainterPath, QFontMetrics, QAction, QPalette)
import vrchatapi
from vrchatapi.api import authentication_api
from vrchatapi.exceptions import UnauthorizedException, ApiException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode
import api_patch

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('vrchat_avatar_manager')

# Constants
APP_NAME = "VRChat Avatar Manager"
APP_VERSION = "0.2.0"
USER_AGENT = "SaveMyProjects/1.0.0 (none@gmial.com)"
DATA_FOLDER = "data"
CONFIG_FILE = os.path.join(DATA_FOLDER, "config.json")
IMAGES_FOLDER = os.path.join(DATA_FOLDER, "images")
CACHE_FOLDER = os.path.join(DATA_FOLDER, "cache")

CARD_WIDTH = 264
CARD_HEIGHT = 330
THUMB_HEIGHT = 198
GRID_SPACING = 18

# Theme Colors
THEME = {
    "dark": {
        "background": "#0E1016",     # Window background
        "surface": "#151821",        # Top bar, panels
        "card": "#1A1E29",           # Cards
        "card_hover": "#202533",     # Card hover
        "input": "#11141B",          # Text inputs
        "border": "#262B38",         # Borders and dividers
        "border_strong": "#343A4B",  # Hovered borders
        "text": "#E9EBF1",           # Primary text
        "text_secondary": "#9BA2B4", # Secondary text
        "text_muted": "#666D80",     # Hints, placeholders
        "primary": "#7C6CF2",        # Violet accent
        "primary_hover": "#8E80F6",
        "primary_pressed": "#6957E8",
        "primary_soft": "#252140",   # Tinted background for accent chips
        "accent": "#22D3EE",         # Cyan
        "success": "#34D399",
        "warning": "#FBBF24",
        "error": "#F87171",
    },
    "light": {
        "background": "#F4F5F9",
        "surface": "#FFFFFF",
        "card": "#FFFFFF",
        "card_hover": "#FBFBFE",
        "input": "#F1F3F8",
        "border": "#E2E5EE",
        "border_strong": "#CBD0DD",
        "text": "#171A23",
        "text_secondary": "#566074",
        "text_muted": "#8D93A5",
        "primary": "#6352E6",
        "primary_hover": "#7365EC",
        "primary_pressed": "#5341D6",
        "primary_soft": "#ECEAFD",
        "accent": "#0891B2",
        "success": "#059669",
        "warning": "#D97706",
        "error": "#DC2626",
    }
}

PLATFORM_LABELS = {
    "standalonewindows": "PC",
    "android": "Quest",
    "ios": "iOS",
}

SORT_OPTIONS = ["Recently updated", "Name (A–Z)", "Name (Z–A)"]

# Global theme state
app_theme = THEME
is_dark_mode = True

# Ensure directories exist
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)


def current_theme():
    return app_theme["dark" if is_dark_mode else "light"]


def cookies_from_client(api_client):
    """Copy the session cookies out of the vrchatapi client for direct requests."""
    cookies = {}
    if api_client:
        for cookie in api_client.rest_client.cookie_jar:
            cookies[cookie.name] = cookie.value
    return cookies


def format_date(value):
    """Turn an ISO timestamp from the API into e.g. 'Mar 3, 2025'."""
    if not value:
        return ""
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%b %d, %Y").replace(" 0", " ")
    except ValueError:
        return ""


def avatar_platforms(avatar_data):
    """Return the friendly platform names an avatar has packages for, PC first."""
    platforms = []
    for package in avatar_data.get('unityPackages') or []:
        label = PLATFORM_LABELS.get(package.get('platform'))
        if label and label not in platforms:
            platforms.append(label)
    order = list(PLATFORM_LABELS.values())
    return sorted(platforms, key=order.index)


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

def ensure_style_assets(theme_name):
    """Draw the small icons the stylesheet references (check mark, combo chevron)."""
    theme = app_theme[theme_name]
    paths = {
        "check": os.path.join(CACHE_FOLDER, "check.png"),
        "chevron": os.path.join(CACHE_FOLDER, f"chevron_{theme_name}.png"),
    }

    if not os.path.exists(paths["check"]):
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("white"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        path = QPainterPath(QPointF(8, 17))
        path.lineTo(14, 23)
        path.lineTo(25, 10)
        painter.drawPath(path)
        painter.end()
        pixmap.save(paths["check"])

    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(theme["text_secondary"]), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    path = QPainterPath(QPointF(6, 9))
    path.lineTo(12, 15)
    path.lineTo(18, 9)
    painter.drawPath(path)
    painter.end()
    pixmap.save(paths["chevron"])

    return {key: value.replace("\\", "/") for key, value in paths.items()}


def build_stylesheet(theme_name):
    """One application-wide stylesheet so every window and dialog matches."""
    t = app_theme[theme_name]
    assets = ensure_style_assets(theme_name)

    return f"""
        * {{
            font-family: "Segoe UI", "Inter", sans-serif;
            font-size: 10pt;
            color: {t["text"]};
        }}
        QMainWindow, QDialog, QWidget#page, QWidget#central {{
            background-color: {t["background"]};
        }}
        QWidget#qt_scrollarea_viewport {{
            background: transparent;
        }}
        QToolTip {{
            background-color: {t["card"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
            border-radius: 6px;
            padding: 6px 8px;
        }}

        /* ---- Top bar & navigation ---- */
        QFrame#topBar {{
            background-color: {t["surface"]};
            border: none;
            border-bottom: 1px solid {t["border"]};
        }}
        QLabel#appTitle {{
            font-size: 13pt;
            font-weight: 700;
        }}
        QLabel#appSubtitle {{
            font-size: 8.5pt;
            color: {t["text_muted"]};
        }}
        QPushButton#navButton {{
            background: transparent;
            border: none;
            border-radius: 8px;
            padding: 8px 14px;
            color: {t["text_secondary"]};
            font-weight: 600;
        }}
        QPushButton#navButton:hover {{
            background-color: {t["card_hover"]};
            color: {t["text"]};
        }}
        QPushButton#navButton:checked {{
            background-color: {t["primary_soft"]};
            color: {t["primary"]};
        }}
        QFrame#userChip {{
            background-color: {t["input"]};
            border: 1px solid {t["border"]};
            border-radius: 16px;
        }}
        QLabel#userName {{
            font-weight: 600;
        }}

        /* ---- Buttons ---- */
        QPushButton {{
            border-radius: 8px;
            padding: 8px 16px;
            font-weight: 600;
            border: 1px solid transparent;
        }}
        QPushButton[variant="primary"] {{
            background-color: {t["primary"]};
            color: white;
        }}
        QPushButton[variant="primary"]:hover {{
            background-color: {t["primary_hover"]};
        }}
        QPushButton[variant="primary"]:pressed {{
            background-color: {t["primary_pressed"]};
        }}
        QPushButton[variant="secondary"] {{
            background-color: {t["card"]};
            color: {t["text"]};
            border: 1px solid {t["border"]};
        }}
        QPushButton[variant="secondary"]:hover {{
            background-color: {t["card_hover"]};
            border-color: {t["border_strong"]};
        }}
        QPushButton[variant="secondary"]:pressed {{
            background-color: {t["input"]};
        }}
        QPushButton[variant="ghost"] {{
            background: transparent;
            color: {t["text_secondary"]};
        }}
        QPushButton[variant="ghost"]:hover {{
            background-color: {t["card_hover"]};
            color: {t["text"]};
        }}
        QPushButton:disabled {{
            background-color: {t["input"]};
            color: {t["text_muted"]};
            border-color: {t["border"]};
        }}

        /* ---- Inputs ---- */
        QLineEdit {{
            background-color: {t["input"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 8px 12px;
            selection-background-color: {t["primary"]};
            selection-color: white;
        }}
        QLineEdit:hover {{
            border-color: {t["border_strong"]};
        }}
        QLineEdit:focus {{
            border: 1px solid {t["primary"]};
        }}
        QLineEdit#codeInput {{
            font-size: 22pt;
            font-weight: 600;
            letter-spacing: 8px;
            padding: 8px;
        }}
        QComboBox {{
            background-color: {t["input"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 7px 12px;
            min-width: 120px;
        }}
        QComboBox:hover {{
            border-color: {t["border_strong"]};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: padding;
            subcontrol-position: center right;
            width: 28px;
            border: none;
        }}
        QComboBox::down-arrow {{
            image: url("{assets["chevron"]}");
            width: 12px;
            height: 12px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {t["card"]};
            border: 1px solid {t["border"]};
            border-radius: 8px;
            padding: 4px;
            outline: none;
            selection-background-color: {t["primary_soft"]};
            selection-color: {t["text"]};
        }}
        QCheckBox {{
            spacing: 8px;
            color: {t["text_secondary"]};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
            border-radius: 4px;
            border: 1px solid {t["border_strong"]};
            background-color: {t["input"]};
        }}
        QCheckBox::indicator:hover {{
            border-color: {t["primary"]};
        }}
        QCheckBox::indicator:checked {{
            background-color: {t["primary"]};
            border-color: {t["primary"]};
            image: url("{assets["check"]}");
        }}

        /* ---- Panels & cards ---- */
        QFrame#panel {{
            background-color: {t["surface"]};
            border: 1px solid {t["border"]};
            border-radius: 14px;
        }}
        QLabel#pageTitle {{
            font-size: 17pt;
            font-weight: 700;
        }}
        QLabel#pageSubtitle, QLabel#secondary {{
            color: {t["text_secondary"]};
        }}
        QLabel#fieldLabel {{
            color: {t["text_secondary"]};
            font-size: 9pt;
            font-weight: 600;
        }}
        QLabel#muted {{
            color: {t["text_muted"]};
        }}
        QLabel#emptyTitle {{
            font-size: 14pt;
            font-weight: 700;
        }}
        QFrame#avatarCard {{
            background-color: {t["card"]};
            border: 1px solid {t["border"]};
            border-radius: 14px;
        }}
        QFrame#avatarCard:hover {{
            background-color: {t["card_hover"]};
            border-color: {t["primary"]};
        }}
        QLabel#cardName {{
            font-size: 11pt;
            font-weight: 700;
        }}
        QLabel#cardAuthor {{
            color: {t["text_secondary"]};
            font-size: 9pt;
        }}
        QLabel#cardMeta {{
            color: {t["text_muted"]};
            font-size: 8.5pt;
        }}

        /* ---- Progress, scrollbars, text areas ---- */
        QProgressBar {{
            background-color: {t["input"]};
            border: none;
            border-radius: 3px;
        }}
        QProgressBar::chunk {{
            background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                              stop:0 {t["primary"]}, stop:1 {t["accent"]});
            border-radius: 3px;
        }}
        QScrollArea {{
            border: none;
            background: transparent;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {t["border_strong"]};
            border-radius: 3px;
            min-height: 32px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {t["text_muted"]};
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:horizontal {{
            background: {t["border_strong"]};
            border-radius: 3px;
            min-width: 32px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0px;
            height: 0px;
        }}
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}
        QTextEdit#logView {{
            background-color: {t["input"]};
            border: 1px solid {t["border"]};
            border-radius: 10px;
            padding: 10px;
            font-family: "Cascadia Mono", "Consolas", monospace;
            font-size: 9pt;
        }}
        QMessageBox {{
            background-color: {t["surface"]};
        }}
        QMessageBox QPushButton {{
            background-color: {t["card"]};
            border: 1px solid {t["border"]};
            min-width: 72px;
        }}
        QMessageBox QPushButton:hover {{
            border-color: {t["primary"]};
        }}
    """


def build_palette(theme_name):
    """Palette for the parts the stylesheet doesn't reach (popups, message boxes)."""
    t = app_theme[theme_name]
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(t["surface"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(t["input"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(t["card"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(t["card"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(t["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(t["primary"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(t["text_muted"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(t["card"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(t["text"]))
    return palette


def make_button(text, variant="primary", parent=None):
    button = QPushButton(text, parent)
    button.setProperty("variant", variant)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return button


def make_label(text="", object_name=None, parent=None):
    label = QLabel(text, parent)
    if object_name:
        label.setObjectName(object_name)
    return label


def make_search_icon(color):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawEllipse(QRectF(6, 6, 15, 15))
    painter.drawLine(QPointF(19, 19), QPointF(26, 26))
    painter.end()
    return QIcon(pixmap)


def add_shadow(widget, blur=28, alpha=60, offset=6):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setColor(QColor(0, 0, 0, alpha))
    shadow.setOffset(0, offset)
    widget.setGraphicsEffect(shadow)


# The Worker class for background tasks
class Worker(QRunnable):
    class Signals(QObject):
        finished = pyqtSignal()
        error = pyqtSignal(str)
        result = pyqtSignal(object)
        progress = pyqtSignal(int, str)

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = Worker.Signals()

    @pyqtSlot()
    def run(self):
        """
        Execute the worker function and emit signals
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            traceback.print_exc()
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


# Thumbnail cache shared by every card (memory + data/images on disk)
class ImageCache:
    _memory = {}

    @classmethod
    def _path(cls, url):
        return os.path.join(IMAGES_FOLDER, hashlib.sha1(url.encode("utf-8")).hexdigest() + ".img")

    @classmethod
    def get(cls, url):
        if url in cls._memory:
            return cls._memory[url]
        path = cls._path(url)
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            cls._memory[url] = data
            return data
        return None

    @classmethod
    def put(cls, url, data):
        cls._memory[url] = data
        try:
            with open(cls._path(url), "wb") as f:
                f.write(data)
        except OSError as e:
            logger.warning(f"Could not cache image: {e}")


def paint_logo(painter, rect, theme=None):
    """Draw the app logo (gradient tile with a "V") into rect."""
    theme = theme or current_theme()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    size = rect.width()

    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0, QColor(theme["primary"]))
    gradient.setColorAt(1, QColor(theme["accent"]))
    path = QPainterPath()
    path.addRoundedRect(rect, size * 0.28, size * 0.28)
    painter.fillPath(path, gradient)

    # Stylised "V"
    pen = QPen(QColor("white"), size * 0.11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    v_path = QPainterPath(QPointF(rect.left() + size * 0.28, rect.top() + size * 0.30))
    v_path.lineTo(rect.left() + size * 0.50, rect.top() + size * 0.72)
    v_path.lineTo(rect.left() + size * 0.72, rect.top() + size * 0.30)
    painter.drawPath(v_path)


def make_app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        paint_logo(painter, QRectF(0, 0, size, size), THEME["dark"])
        painter.end()
        icon.addPixmap(pixmap)
    return icon


# App logo, painted so there are no image files to ship
class LogoMark(QWidget):
    def __init__(self, size=36, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        paint_logo(painter, QRectF(0, 0, self.width(), self.height()))


# Small coloured dot used for the login status
class StatusDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.state = "offline"

    def set_state(self, state):
        self.state = state
        self.update()

    def paintEvent(self, event):
        theme = current_theme()
        color = {
            "online": theme["success"],
            "busy": theme["warning"],
        }.get(self.state, theme["error"])
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawEllipse(QRectF(1, 1, 8, 8))


# Avatar thumbnail with rounded top corners, centre-crop and overlay badges
class AvatarThumbnail(QWidget):
    def __init__(self, avatar_data, parent=None):
        super().__init__(parent)
        self.setFixedSize(CARD_WIDTH, THUMB_HEIGHT)
        self.pixmap = None
        self.failed = False
        self.name = avatar_data.get('name') or "?"
        self.platforms = avatar_platforms(avatar_data)
        self.release_status = (avatar_data.get('releaseStatus') or "").lower()

    def set_pixmap(self, pixmap):
        self.pixmap = pixmap
        self.update()

    def set_failed(self):
        self.failed = True
        self.update()

    def paintEvent(self, event):
        theme = current_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        rect = QRectF(1, 1, self.width() - 2, self.height() - 1)
        radius = 13
        rounded = QPainterPath()
        rounded.addRoundedRect(rect, radius, radius)
        # Square off the bottom corners so the image meets the card body
        bottom = QPainterPath()
        bottom.addRect(QRectF(rect.left(), rect.bottom() - radius, rect.width(), radius))
        clip = rounded.united(bottom)
        painter.setClipPath(clip)

        if self.pixmap and not self.pixmap.isNull():
            scaled = self.pixmap.scaled(
                int(rect.width()), int(rect.height()),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - rect.width()) / 2
            y = (scaled.height() - rect.height()) / 2
            painter.drawPixmap(rect.toRect(), scaled, QRect(int(x), int(y), int(rect.width()), int(rect.height())))
        else:
            # Placeholder: soft gradient with the avatar's initial
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(theme["primary_soft"]))
            gradient.setColorAt(1, QColor(theme["input"]))
            painter.fillPath(clip, gradient)
            painter.setPen(QColor(theme["text_muted"]))
            if self.failed:
                painter.setFont(QFont("Segoe UI", 9))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Image unavailable")
            else:
                painter.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.name[:1].upper())

            # Bottom fade so badges stay readable on bright thumbnails
            fade = QLinearGradient(0, rect.bottom() - 50, 0, rect.bottom())
            fade.setColorAt(0, QColor(0, 0, 0, 0))
            fade.setColorAt(1, QColor(0, 0, 0, 90))
            painter.fillRect(QRectF(rect.left(), rect.bottom() - 50, rect.width(), 50), fade)
        painter.setClipping(False)

        # Badges
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        metrics = QFontMetrics(painter.font())

        def badge(x, y, text, bg, fg="white", align_right=False):
            width = metrics.horizontalAdvance(text) + 14
            if align_right:
                x = x - width
            badge_rect = QRectF(x, y, width, 20)
            path = QPainterPath()
            path.addRoundedRect(badge_rect, 10, 10)
            painter.fillPath(path, QColor(bg))
            painter.setPen(QColor(fg))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, text)
            return width

        x = 10
        for platform in self.platforms:
            x += badge(x, rect.bottom() - 28, platform, QColor(15, 17, 24, 190)) + 6

        if self.release_status in ("public", "private"):
            color = QColor(theme["success"] if self.release_status == "public" else theme["primary"])
            color.setAlpha(230)
            badge(rect.right() - 10, 10, self.release_status.capitalize(), color, align_right=True)


# Avatar Card Widget to display each avatar
class AvatarCard(QFrame):
    downloadRequested = pyqtSignal(dict)

    def __init__(self, avatar_data, api_client=None, parent=None):
        super().__init__(parent)
        self.avatar_data = avatar_data
        self.api_client = api_client
        self.setObjectName("avatarCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(CARD_WIDTH, CARD_HEIGHT)
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.thumbnail = AvatarThumbnail(self.avatar_data)
        main_layout.addWidget(self.thumbnail)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 12, 14, 14)
        content_layout.setSpacing(2)

        # Name, elided to one line with the full name as tooltip
        name = self.avatar_data.get('name') or 'Unknown Avatar'
        self.name_label = make_label("", "cardName")
        metrics = QFontMetrics(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.name_label.setText(metrics.elidedText(name, Qt.TextElideMode.ElideRight, CARD_WIDTH - 32))
        self.name_label.setToolTip(name)

        author = self.avatar_data.get('authorName') or 'Unknown Author'
        self.author_label = make_label(f"by {author}", "cardAuthor")

        description = (self.avatar_data.get('description') or "").strip()
        if description:
            self.setToolTip(description[:300])

        updated = format_date(self.avatar_data.get('updated_at'))
        self.meta_label = make_label(f"Updated {updated}" if updated else "", "cardMeta")

        self.download_btn = make_button("Download", "primary")
        self.download_btn.setFixedHeight(34)
        self.download_btn.clicked.connect(self.request_download)

        content_layout.addWidget(self.name_label)
        content_layout.addWidget(self.author_label)
        content_layout.addSpacing(2)
        content_layout.addWidget(self.meta_label)
        content_layout.addStretch(1)
        content_layout.addWidget(self.download_btn)

        main_layout.addWidget(content)
        self.load_avatar_image()

    def load_avatar_image(self):
        # Use thumbnail if available, otherwise use image URL
        image_url = self.avatar_data.get('thumbnailImageUrl') or self.avatar_data.get('imageUrl')
        if not image_url:
            self.thumbnail.set_failed()
            return

        cached = ImageCache.get(image_url)
        if cached:
            self.set_image(cached)
            return

        worker = Worker(self.download_image, image_url)
        worker.signals.result.connect(self.set_image)
        worker.signals.error.connect(lambda error: self.set_image(None))
        QThreadPool.globalInstance().start(worker)

    def download_image(self, url):
        try:
            headers = {
                "User-Agent": self.api_client.user_agent if self.api_client else USER_AGENT,
                "Accept": "*/*"
            }
            response = requests.get(url, headers=headers, cookies=cookies_from_client(self.api_client), timeout=20)
            if response.status_code == 200:
                ImageCache.put(url, response.content)
                return response.content
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
        return None

    def set_image(self, image_data):
        try:
            if image_data:
                pixmap = QPixmap()
                pixmap.loadFromData(image_data)
                self.thumbnail.set_pixmap(pixmap)
            else:
                self.thumbnail.set_failed()
        except RuntimeError:
            # The card was removed (page change) before the image arrived
            pass

    def request_download(self):
        self.download_btn.setText("Preparing…")
        self.download_btn.setEnabled(False)
        self.downloadRequested.emit(self.avatar_data)
        QTimer.singleShot(1200, self.reset_download_button)

    def reset_download_button(self):
        try:
            self.download_btn.setEnabled(True)
            self.download_btn.setText("Download")
        except RuntimeError:
            pass


# Theme Switch Button
class ThemeSwitchButton(QWidget):
    themeChanged = pyqtSignal(bool)  # True = dark

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 28)
        self.dark_mode = True
        self._value = 1.0  # 1 = dark (thumb right), 0 = light (thumb left)
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(220)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Toggle light / dark mode")

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.update()

    value = pyqtProperty(float, get_value, set_value)

    def paintEvent(self, event):
        theme = current_theme()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()

        track = QPainterPath()
        track.addRoundedRect(QRectF(0.5, 0.5, width - 1, height - 1), height / 2, height / 2)
        painter.fillPath(track, QColor(theme["input"]))
        painter.setPen(QPen(QColor(theme["border"]), 1))
        painter.drawPath(track)

        thumb_size = height - 8
        thumb_x = 4 + (width - thumb_size - 8) * self._value
        thumb_rect = QRectF(thumb_x, 4, thumb_size, thumb_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme["primary"]))
        painter.drawEllipse(thumb_rect)

        center = thumb_rect.center()
        painter.setBrush(QColor("white"))
        if self.dark_mode:
            # Moon: white disc with a bite taken out
            r = thumb_size * 0.27
            painter.drawEllipse(center, r, r)
            painter.setBrush(QColor(theme["primary"]))
            painter.drawEllipse(QPointF(center.x() + r * 0.55, center.y() - r * 0.45), r * 0.85, r * 0.85)
        else:
            # Sun: disc with rays
            r = thumb_size * 0.16
            painter.drawEllipse(center, r, r)
            painter.setPen(QPen(QColor("white"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for i in range(8):
                angle = math.radians(i * 45)
                direction = QPointF(math.cos(angle), math.sin(angle))
                painter.drawLine(center + direction * (r + 2), center + direction * (r + 4.5))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setDarkMode(not self.dark_mode)
            self.themeChanged.emit(self.dark_mode)

    def setDarkMode(self, is_dark):
        self.dark_mode = is_dark
        self.animation.stop()
        self.animation.setStartValue(self._value)
        self.animation.setEndValue(1.0 if is_dark else 0.0)
        self.animation.start()


# Pagination Widget
class PaginationWidget(QWidget):
    pageChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_page = 1
        self.total_pages = 1
        self.items_per_page = 50
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.prev_btn = make_button("‹  Prev", "secondary")
        self.prev_btn.setFixedHeight(34)
        self.prev_btn.clicked.connect(self.prev_page)

        self.page_label = make_label("", "secondary")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setMinimumWidth(110)

        self.next_btn = make_button("Next  ›", "secondary")
        self.next_btn.setFixedHeight(34)
        self.next_btn.clicked.connect(self.next_page)

        self.items_per_page_combo = QComboBox()
        self.items_per_page_combo.addItems(["10 per page", "25 per page", "50 per page", "100 per page"])
        self.items_per_page_combo.setCurrentIndex(2)  # Default to 50
        self.items_per_page_combo.currentIndexChanged.connect(self.change_items_per_page)

        layout.addWidget(self.prev_btn)
        layout.addWidget(self.page_label)
        layout.addWidget(self.next_btn)
        layout.addSpacing(10)
        layout.addWidget(self.items_per_page_combo)

        self.update_ui()

    def set_page_count(self, total_items):
        self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
        self.current_page = min(self.current_page, self.total_pages)
        self.update_ui()

    def update_ui(self):
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.update_ui()
            self.pageChanged.emit(self.current_page)

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.update_ui()
            self.pageChanged.emit(self.current_page)

    def change_items_per_page(self, index):
        items_map = {0: 10, 1: 25, 2: 50, 3: 100}
        new_items_per_page = items_map.get(index, 50)

        if new_items_per_page != self.items_per_page:
            self.items_per_page = new_items_per_page
            self.current_page = 1
            self.pageChanged.emit(self.current_page)


# Shared header for the login and 2FA dialogs
def dialog_header(layout, title, subtitle):
    logo = LogoMark(48)
    layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
    layout.addSpacing(6)

    title_label = make_label(title, "pageTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title_label)

    subtitle_label = make_label(subtitle, "pageSubtitle")
    subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle_label.setWordWrap(True)
    layout.addWidget(subtitle_label)
    layout.addSpacing(10)


# Login Dialog
class LoginDialog(QDialog):
    def __init__(self, parent=None, username="", password=""):
        super().__init__(parent)
        self.username = username
        self.password = password
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Sign in")
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 28)
        layout.setSpacing(6)

        dialog_header(layout, "Sign in to VRChat", "Your credentials are sent only to VRChat's servers.")

        layout.addWidget(make_label("USERNAME OR EMAIL", "fieldLabel"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("you@example.com")
        self.username_input.setText(self.username)
        layout.addWidget(self.username_input)
        layout.addSpacing(8)

        layout.addWidget(make_label("PASSWORD", "fieldLabel"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("••••••••")
        self.password_input.setText(self.password)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.password_input)
        layout.addSpacing(8)

        self.save_checkbox = QCheckBox("Remember me on this computer")
        self.save_checkbox.setChecked(True)
        layout.addWidget(self.save_checkbox)
        layout.addSpacing(16)

        self.login_btn = make_button("Sign in", "primary")
        self.login_btn.setFixedHeight(40)
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self.accept)

        self.cancel_btn = make_button("Cancel", "ghost")
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addWidget(self.cancel_btn, 1)
        button_layout.addWidget(self.login_btn, 2)
        layout.addLayout(button_layout)

        if not self.username:
            self.username_input.setFocus()
        else:
            self.password_input.setFocus()

    def get_credentials(self):
        return {
            "username": self.username_input.text(),
            "password": self.password_input.text(),
            "save": self.save_checkbox.isChecked()
        }


# 2FA Dialog
class TwoFactorDialog(QDialog):
    def __init__(self, parent=None, is_email=False):
        super().__init__(parent)
        self.is_email = is_email
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Two-Factor Authentication")
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 32, 36, 28)
        layout.setSpacing(6)

        title = "Check your email" if self.is_email else "Two-factor authentication"
        source = "we sent to your email" if self.is_email else "from your authenticator app"
        dialog_header(layout, title, f"Enter the 6-digit code {source}.")

        self.code_input = QLineEdit()
        self.code_input.setObjectName("codeInput")
        self.code_input.setMaxLength(6)
        self.code_input.setPlaceholderText("000000")
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.setFixedHeight(60)
        self.code_input.textChanged.connect(self.validate_code_input)
        layout.addWidget(self.code_input)
        layout.addSpacing(16)

        self.verify_btn = make_button("Verify", "primary")
        self.verify_btn.setFixedHeight(40)
        self.verify_btn.setDefault(True)
        self.verify_btn.setEnabled(False)
        self.verify_btn.clicked.connect(self.accept)
        layout.addWidget(self.verify_btn)

        self.code_input.setFocus()

    def validate_code_input(self, text):
        filtered_text = ''.join(filter(str.isdigit, text))
        if filtered_text != text:
            self.code_input.setText(filtered_text)
        self.verify_btn.setEnabled(len(filtered_text) == 6)

    def get_code(self):
        return self.code_input.text()


# Centered message used when there is nothing to show in the grid
class EmptyState(QWidget):
    actionClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        self.logo = LogoMark(56)
        self.title = make_label("", "emptyTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message = make_label("", "secondary")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        self.message.setFixedWidth(440)
        self.action_btn = make_button("", "primary")
        self.action_btn.setFixedHeight(38)
        self.action_btn.clicked.connect(self.actionClicked.emit)

        layout.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.message, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(12)
        layout.addWidget(self.action_btn, alignment=Qt.AlignmentFlag.AlignHCenter)

    def show_state(self, title, message, action_text=None):
        self.title.setText(title)
        self.message.setText(message)
        self.action_btn.setVisible(bool(action_text))
        if action_text:
            self.action_btn.setText(action_text)


# Main Window
class VRChatManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_client = None
        self.temp_api_client = None
        self.avatars_data = []
        self.filtered_avatars = []
        self.avatar_cards = []
        self.current_page = 1
        self.items_per_page = 50
        self.grid_columns = 0
        self.threadpool = QThreadPool()

        self.relayout_timer = QTimer(self)
        self.relayout_timer.setSingleShot(True)
        self.relayout_timer.timeout.connect(self.relayout_cards)

        self.load_config()
        self.setup_ui()

    def load_config(self):
        global is_dark_mode
        self.vrchat_username = ""
        self.vrchat_password = ""

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.vrchat_username = config.get("vrchat_username", "")
                self.vrchat_password = config.get("vrchat_password", "")
                is_dark_mode = config.get("dark_mode", True)
            except Exception as e:
                logger.error(f"Error loading config: {e}")

    def save_config(self, username="", password=""):
        try:
            config = {
                "vrchat_username": username if username else self.vrchat_username,
                "vrchat_password": password if password else self.vrchat_password,
                "dark_mode": is_dark_mode
            }
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info("Config saved successfully")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def setup_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 740)
        self.resize(1320, 860)

        central = QWidget()
        central.setObjectName("central")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        main_layout.addWidget(self.build_top_bar())

        self.pages = QStackedWidget()
        self.pages.addWidget(self.build_avatars_page())
        self.pages.addWidget(self.build_downloader_page())
        self.pages.addWidget(self.build_logs_page())
        self.pages.addWidget(self.build_about_page())
        main_layout.addWidget(self.pages, 1)

        self.setCentralWidget(central)

        # Create log handler to show logs in the UI
        self.log_handler = LogHandler()
        self.log_handler.bridge.message.connect(self.append_log)
        logger.addHandler(self.log_handler)

        self.update_theme()
        self.set_page(0)
        self.update_empty_state()

        # Check login status on startup
        QTimer.singleShot(500, self.check_login_status)

    def build_top_bar(self):
        bar = QFrame()
        bar.setObjectName("topBar")
        bar.setFixedHeight(68)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(22, 0, 22, 0)
        layout.setSpacing(12)

        # Brand
        layout.addWidget(LogoMark(36))
        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addStretch(1)
        brand.addWidget(make_label("Avatar Manager", "appTitle"))
        brand.addWidget(make_label("for VRChat", "appSubtitle"))
        brand.addStretch(1)
        layout.addLayout(brand)
        layout.addSpacing(28)

        # Navigation
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, name in enumerate(["Avatars", "File Downloader", "Logs", "About"]):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            self.nav_group.addButton(button, index)
            layout.addWidget(button)
        self.nav_group.idClicked.connect(self.set_page)

        layout.addStretch(1)

        # User status chip
        chip = QFrame()
        chip.setObjectName("userChip")
        chip.setFixedHeight(34)
        chip_layout = QHBoxLayout(chip)
        chip_layout.setContentsMargins(12, 0, 14, 0)
        chip_layout.setSpacing(8)
        self.status_icon = StatusDot()
        self.status_label = make_label("Not signed in", "userName")
        chip_layout.addWidget(self.status_icon)
        chip_layout.addWidget(self.status_label)
        layout.addWidget(chip)

        self.theme_switch = ThemeSwitchButton()
        self.theme_switch.dark_mode = is_dark_mode
        self.theme_switch.set_value(1.0 if is_dark_mode else 0.0)
        self.theme_switch.themeChanged.connect(self.toggle_theme)
        layout.addWidget(self.theme_switch)

        self.login_btn = make_button("Sign in", "primary")
        self.login_btn.setFixedHeight(36)
        self.login_btn.clicked.connect(self.login_to_vrchat)
        layout.addWidget(self.login_btn)

        return bar

    def build_page(self, title, subtitle):
        """Common page skeleton: padded column with a title and subtitle."""
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 26, 32, 22)
        layout.setSpacing(4)
        layout.addWidget(make_label(title, "pageTitle"))
        if subtitle:
            subtitle_label = make_label(subtitle, "pageSubtitle")
            layout.addWidget(subtitle_label)
        layout.addSpacing(14)
        return page, layout

    def build_avatars_page(self):
        page, layout = self.build_page("Your Avatars", "Browse and download the avatars uploaded to your account.")
        self.avatars_page_subtitle = page.findChild(QLabel, "pageSubtitle")

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, author or description…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(38)
        self.search_action = QAction(self.search_input)
        self.search_input.addAction(self.search_action, QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.textChanged.connect(self.filter_avatars)

        # Kept for compatibility with the old filter; the API filter crashed when changed quickly
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(SORT_OPTIONS)
        self.filter_combo.setFixedHeight(38)
        self.filter_combo.setToolTip("Sort avatars")
        self.filter_combo.currentIndexChanged.connect(self.filter_avatars)

        self.refresh_btn = make_button("Refresh", "secondary")
        self.refresh_btn.setFixedHeight(38)
        self.refresh_btn.clicked.connect(self.fetch_avatars)

        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(self.filter_combo)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)
        layout.addSpacing(14)

        # Grid / empty state
        self.avatar_stack = QStackedWidget()

        self.empty_state = EmptyState()
        self.empty_state.actionClicked.connect(self.on_empty_state_action)
        self.avatar_stack.addWidget(self.empty_state)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.avatar_container = QWidget()
        self.avatar_grid = QGridLayout(self.avatar_container)
        self.avatar_grid.setHorizontalSpacing(GRID_SPACING)
        self.avatar_grid.setVerticalSpacing(GRID_SPACING)
        self.avatar_grid.setContentsMargins(2, 2, 2, 2)
        self.avatar_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.scroll_area.setWidget(self.avatar_container)
        # QScrollArea turns on background filling; keep the page colour showing through
        self.avatar_container.setAutoFillBackground(False)
        self.scroll_area.viewport().setAutoFillBackground(False)
        # Re-flow the cards whenever the visible area changes size
        self.scroll_area.viewport().installEventFilter(self)
        self.avatar_stack.addWidget(self.scroll_area)

        layout.addWidget(self.avatar_stack, 1)
        layout.addSpacing(12)

        # Footer: status on the left, pagination on the right
        footer = QHBoxLayout()
        footer.setSpacing(12)
        self.avatars_status = make_label("Not signed in", "muted")
        self.avatars_progress = QProgressBar()
        self.avatars_progress.setFixedWidth(160)
        self.avatars_progress.setFixedHeight(6)
        self.avatars_progress.setTextVisible(False)
        self.avatars_progress.setVisible(False)

        self.pagination = PaginationWidget()
        self.pagination.pageChanged.connect(self.change_page)

        footer.addWidget(self.avatars_status)
        footer.addWidget(self.avatars_progress)
        footer.addStretch(1)
        footer.addWidget(self.pagination)
        layout.addLayout(footer)

        return page

    def build_downloader_page(self):
        page, layout = self.build_page("File Downloader", "Download any VRChat file you have access to by its URL.")

        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMaximumWidth(760)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 26, 28, 26)
        panel_layout.setSpacing(6)

        panel_layout.addWidget(make_label("FILE URL", "fieldLabel"))
        self.file_url_input = QLineEdit()
        self.file_url_input.setPlaceholderText("https://api.vrchat.cloud/api/1/file/file_…/1/file")
        self.file_url_input.setFixedHeight(40)
        panel_layout.addWidget(self.file_url_input)
        panel_layout.addSpacing(10)

        panel_layout.addWidget(make_label("SAVE TO", "fieldLabel"))
        output_layout = QHBoxLayout()
        output_layout.setSpacing(10)
        self.file_output_input = QLineEdit()
        self.file_output_input.setPlaceholderText("Choose where to save the file")
        self.file_output_input.setFixedHeight(40)
        self.file_output_browse = make_button("Browse…", "secondary")
        self.file_output_browse.setFixedHeight(40)
        self.file_output_browse.clicked.connect(self.browse_output_path)
        output_layout.addWidget(self.file_output_input, 1)
        output_layout.addWidget(self.file_output_browse)
        panel_layout.addLayout(output_layout)
        panel_layout.addSpacing(18)

        action_layout = QHBoxLayout()
        self.download_btn = make_button("Download File", "primary")
        self.download_btn.setFixedHeight(42)
        self.download_btn.setMinimumWidth(170)
        self.download_btn.clicked.connect(self.download_file)
        action_layout.addWidget(self.download_btn)
        action_layout.addStretch(1)
        panel_layout.addLayout(action_layout)
        panel_layout.addSpacing(14)

        self.file_progress = QProgressBar()
        self.file_progress.setFixedHeight(6)
        self.file_progress.setTextVisible(False)
        self.file_progress.setVisible(False)
        panel_layout.addWidget(self.file_progress)

        self.file_status = make_label("Paste a VRChat file URL to get started.", "secondary")
        self.file_status.setWordWrap(True)
        panel_layout.addWidget(self.file_status)

        layout.addWidget(panel)
        layout.addStretch(1)
        return page

    def build_logs_page(self):
        page, layout = self.build_page("Logs", "Everything the app is doing, useful when something goes wrong.")

        controls = QHBoxLayout()
        controls.addStretch(1)
        clear_log_btn = make_button("Clear", "ghost")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        save_log_btn = make_button("Save to file…", "secondary")
        save_log_btn.clicked.connect(self.save_log)
        controls.addWidget(clear_log_btn)
        controls.addWidget(save_log_btn)
        layout.addLayout(controls)
        layout.addSpacing(8)

        self.log_text = QTextEdit()
        self.log_text.setObjectName("logView")
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 1)
        return page

    def build_about_page(self):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(6)

        layout.addWidget(LogoMark(96), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(14)

        about_title = make_label(APP_NAME, "pageTitle")
        about_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(about_title)

        about_version = make_label(f"Version {APP_VERSION}", "muted")
        about_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(about_version)
        layout.addSpacing(14)

        about_desc = make_label(
            "A tool for browsing and downloading the VRChat avatars on your account.<br>"
            "It talks directly to VRChat's API and never sends your data anywhere else.<br><br>"
            "Made by Lunar with ❤️",
            "secondary",
        )
        about_desc.setWordWrap(True)
        about_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_desc.setFixedWidth(520)
        layout.addWidget(about_desc, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(20)

        github_btn = make_button("View on GitHub", "primary")
        github_btn.setFixedHeight(40)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/PrototypeX37/vrchat-avatar-manager")))
        layout.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignHCenter)
        return page

    def set_page(self, index):
        self.pages.setCurrentIndex(index)
        button = self.nav_group.button(index)
        if button:
            button.setChecked(True)

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def update_theme(self):
        theme_name = "dark" if is_dark_mode else "light"
        QApplication.instance().setPalette(build_palette(theme_name))
        QApplication.instance().setStyleSheet(build_stylesheet(theme_name))
        self.search_action.setIcon(make_search_icon(current_theme()["text_muted"]))
        # Custom painted widgets pick the new colours up on repaint
        for widget in self.findChildren(QWidget):
            if isinstance(widget, (LogoMark, StatusDot, AvatarThumbnail, ThemeSwitchButton)):
                widget.update()

    def toggle_theme(self, is_dark):
        global is_dark_mode
        is_dark_mode = is_dark
        self.update_theme()
        self.save_config()

    def save_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log File",
            f"vrchat_manager_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Log Saved", f"Log has been saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save log: {str(e)}")

    def append_log(self, html):
        self.log_text.append(html)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def set_status(self, text, state):
        self.status_label.setText(text)
        self.status_icon.set_state(state)

    def check_login_status(self):
        # If credentials are saved, try to login automatically
        if self.vrchat_username and self.vrchat_password:
            self.login_to_vrchat()

    def login_to_vrchat(self):
        login_dialog = LoginDialog(self, self.vrchat_username, self.vrchat_password)
        if login_dialog.exec():
            credentials = login_dialog.get_credentials()
            username = credentials["username"]
            password = credentials["password"]

            if credentials["save"]:
                self.vrchat_username = username
                self.vrchat_password = password
                self.save_config(username, password)

            self.set_status("Signing in…", "busy")
            self.login_btn.setEnabled(False)
            self.avatars_progress.setVisible(True)
            self.avatars_progress.setRange(0, 0)

            worker = Worker(self.login_worker, username, password)
            worker.signals.result.connect(self.handle_login_result)
            worker.signals.error.connect(self.handle_login_error)
            self.threadpool.start(worker)

    def login_worker(self, username, password):
        try:
            # Validation is off so null fields from the API don't break parsing
            configuration = api_patch.make_configuration(
                username=username,
                password=password
            )
            api_client = vrchatapi.ApiClient(configuration)
            # Set user agent as required by VRChat
            api_client.user_agent = USER_AGENT
            auth_api = authentication_api.AuthenticationApi(api_client)

            try:
                logger.info("Attempting to log in to VRChat")
                current_user = auth_api.get_current_user()
                logger.info(f"Successfully logged in as: {current_user.display_name}")
                return {
                    "success": True,
                    "api_client": api_client,
                    "user": current_user
                }
            except UnauthorizedException as e:
                # Handle 2FA
                if e.status == 200:
                    if "Email 2 Factor Authentication" in e.reason:
                        return {
                            "success": False,
                            "need_2fa": True,
                            "is_email": True,
                            "api_client": api_client,
                            "auth_api": auth_api
                        }
                    elif "2 Factor Authentication" in e.reason:
                        return {
                            "success": False,
                            "need_2fa": True,
                            "is_email": False,
                            "api_client": api_client,
                            "auth_api": auth_api
                        }
                logger.error(f"Authentication error: {e.reason}")
                return {
                    "success": False,
                    "error": e.reason
                }
            except ApiException as e:
                logger.error(f"API Exception during login: {str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        except Exception as e:
            logger.error(f"Error creating API client: {str(e)}")
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e)
            }

    def handle_login_result(self, result):
        self.login_btn.setEnabled(True)
        self.avatars_progress.setVisible(False)

        if result["success"]:
            self.api_client = result["api_client"]
            self.on_logged_in(result["user"])
        elif result.get("need_2fa", False):
            api_client = result["api_client"]
            auth_api = result["auth_api"]
            is_email = result.get("is_email", False)

            twofa_dialog = TwoFactorDialog(self, is_email)
            if twofa_dialog.exec():
                code = twofa_dialog.get_code()

                self.set_status("Verifying code…", "busy")
                self.avatars_progress.setVisible(True)
                self.login_btn.setEnabled(False)

                # Store API client for later use
                self.temp_api_client = api_client

                worker = Worker(self.verify_2fa_worker, auth_api, code, is_email)
                worker.signals.result.connect(self.handle_2fa_result)
                worker.signals.error.connect(self.handle_login_error)
                self.threadpool.start(worker)
            else:
                self.set_status("Not signed in", "offline")
        else:
            error = result.get("error", "Unknown error")
            self.set_status("Sign in failed", "offline")
            QMessageBox.critical(self, "Login Error", f"Failed to login: {error}")

    def verify_2fa_worker(self, auth_api, code, is_email):
        try:
            if is_email:
                auth_api.verify2_fa_email_code(
                    two_factor_email_code=TwoFactorEmailCode(code)
                )
            else:
                auth_api.verify2_fa(
                    two_factor_auth_code=TwoFactorAuthCode(code)
                )

            current_user = auth_api.get_current_user()
            logger.info(f"Successfully logged in with 2FA as: {current_user.display_name}")

            return {
                "success": True,
                "user": current_user
            }
        except Exception as e:
            # Any failure here (bad code, unexpected response data) is reported in the UI
            logger.error(f"2FA verification failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_2fa_result(self, result):
        self.login_btn.setEnabled(True)
        self.avatars_progress.setVisible(False)

        if result["success"]:
            self.api_client = self.temp_api_client
            self.on_logged_in(result["user"])
        else:
            error = result.get("error", "Unknown error")
            self.set_status("Verification failed", "offline")
            QMessageBox.critical(self, "Authentication Error", f"2FA verification failed: {error}")

    def on_logged_in(self, user):
        self.set_status(user.display_name, "online")
        self.login_btn.setText("Switch user")
        self.login_btn.setProperty("variant", "secondary")
        self.login_btn.style().unpolish(self.login_btn)
        self.login_btn.style().polish(self.login_btn)
        self.avatars_status.setText("Ready")
        self.fetch_avatars()

    def handle_login_error(self, error):
        self.login_btn.setEnabled(True)
        self.avatars_progress.setVisible(False)
        self.set_status("Sign in failed", "offline")
        QMessageBox.critical(self, "Login Error", f"An unexpected error occurred: {error}")

    # ------------------------------------------------------------------
    # Avatars
    # ------------------------------------------------------------------

    def on_empty_state_action(self):
        if not self.api_client:
            self.login_to_vrchat()
        elif self.search_input.text():
            self.search_input.clear()
        else:
            self.fetch_avatars()

    def update_empty_state(self):
        if not self.api_client:
            self.empty_state.show_state(
                "Sign in to see your avatars",
                "Log in with your VRChat account to browse and download the avatars you've uploaded.",
                "Sign in",
            )
        elif self.avatars_progress.isVisible() and not self.avatars_data:
            self.empty_state.show_state("Loading your avatars…", "This can take a few seconds for large collections.")
        elif not self.avatars_data:
            self.empty_state.show_state("No avatars yet", "We couldn't find any avatars uploaded to this account.", "Refresh")
        elif not self.filtered_avatars:
            self.empty_state.show_state(
                "No matches",
                f"No avatars match “{self.search_input.text()}”.",
                "Clear search",
            )
        else:
            self.avatar_stack.setCurrentWidget(self.scroll_area)
            return
        self.avatar_stack.setCurrentWidget(self.empty_state)

    def fetch_avatars(self):
        if not self.api_client:
            self.login_to_vrchat()
            return

        self.current_page = 1
        self.pagination.current_page = 1
        self.pagination.update_ui()

        self.avatars_status.setText("Fetching avatars…")
        self.avatars_progress.setVisible(True)
        self.avatars_progress.setRange(0, 0)
        self.refresh_btn.setEnabled(False)
        self.update_empty_state()

        worker = Worker(self.fetch_avatars_worker, "all")
        worker.signals.result.connect(self.handle_avatars_result)
        worker.signals.error.connect(self.handle_avatars_error)
        self.threadpool.start(worker)

    def fetch_avatars_worker(self, filter_type):
        try:
            # Direct requests instead of the SDK, using the SDK's session cookies
            cookies = cookies_from_client(self.api_client)
            headers = {
                "User-Agent": self.api_client.user_agent,
                "Accept": "application/json"
            }

            all_avatars = []
            offset = 0
            page_size = 100

            max_pages = 10
            for page in range(max_pages):
                params = {
                    "n": page_size,
                    "offset": offset,
                    "releaseStatus": "all",
                }

                if filter_type == "Private Avatars":
                    params["releaseStatus"] = "private"
                elif filter_type == "Public Avatars":
                    params["releaseStatus"] = "public"

                logger.info(f"Fetching avatars page {page+1} with params: {params}")
                response = requests.get(
                    "https://api.vrchat.cloud/api/1/avatars",
                    params=params,
                    headers=headers,
                    cookies=cookies,
                    timeout=30
                )

                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code} - {response.text[:200]}")
                    raise Exception(f"API error: {response.status_code}")

                avatars = response.json()
                logger.info(f"Received {len(avatars)} avatars in page {page+1}")

                if not avatars:
                    break

                all_avatars.extend(avatars)

                if len(avatars) < page_size:
                    break

                offset += page_size

            logger.info(f"Fetched a total of {len(all_avatars)} avatars")
            return all_avatars

        except Exception as e:
            logger.error(f"Error fetching avatars: {e}")
            traceback.print_exc()
            raise

    def handle_avatars_result(self, avatars):
        self.avatars_progress.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self.avatars_data = avatars
        self.items_per_page = self.pagination.items_per_page
        self.filter_avatars()

    def handle_avatars_error(self, error):
        self.avatars_progress.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self.avatars_status.setText(f"Error: {error}")
        self.update_empty_state()
        QMessageBox.critical(self, "Avatar Fetch Error", str(error))

    def sorted_avatars(self, avatars):
        sort_index = self.filter_combo.currentIndex()
        if sort_index == 1:
            return sorted(avatars, key=lambda a: (a.get('name') or '').lower())
        if sort_index == 2:
            return sorted(avatars, key=lambda a: (a.get('name') or '').lower(), reverse=True)
        return sorted(avatars, key=lambda a: a.get('updated_at') or '', reverse=True)

    def filter_avatars(self):
        filter_text = self.search_input.text().lower().strip()

        if filter_text:
            self.filtered_avatars = [
                avatar for avatar in self.avatars_data
                if filter_text in (avatar.get('name') or '').lower()
                or filter_text in (avatar.get('authorName') or '').lower()
                or filter_text in (avatar.get('description') or '').lower()
            ]
        else:
            self.filtered_avatars = list(self.avatars_data)
        self.filtered_avatars = self.sorted_avatars(self.filtered_avatars)

        self.current_page = 1
        self.pagination.current_page = 1
        self.pagination.set_page_count(len(self.filtered_avatars))
        self.display_current_page()

    def change_page(self, page_num):
        self.current_page = page_num
        self.items_per_page = self.pagination.items_per_page
        self.pagination.set_page_count(len(self.filtered_avatars))
        self.display_current_page()
        self.scroll_area.verticalScrollBar().setValue(0)

    def display_current_page(self):
        self.clear_avatar_grid()

        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.filtered_avatars))
        current_page_avatars = self.filtered_avatars[start_idx:end_idx]

        if self.filtered_avatars:
            total = len(self.avatars_data)
            shown = len(self.filtered_avatars)
            suffix = f" (filtered from {total})" if shown != total else ""
            self.avatars_status.setText(f"Showing {start_idx+1}–{end_idx} of {shown} avatars{suffix}")
            if hasattr(self, "avatars_page_subtitle"):
                self.avatars_page_subtitle.setText(f"{total} avatars on your account. Click Download to save a .vrca file.")
        elif self.api_client:
            self.avatars_status.setText("No avatars to show")

        self.display_avatars(current_page_avatars)
        self.update_empty_state()

    def clear_avatar_grid(self):
        while self.avatar_grid.count():
            item = self.avatar_grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self.avatar_cards = []

    def column_count(self):
        available = self.scroll_area.viewport().width() - 4
        return max(1, (available + GRID_SPACING) // (CARD_WIDTH + GRID_SPACING))

    def display_avatars(self, avatars):
        for avatar in avatars:
            card = AvatarCard(avatar, self.api_client)
            card.downloadRequested.connect(self.download_avatar)
            self.avatar_cards.append(card)
        self.grid_columns = 0
        self.relayout_cards()

    def relayout_cards(self):
        """Place the existing cards into the grid for the current window width."""
        cols = self.column_count()
        if cols == self.grid_columns:
            return
        self.grid_columns = cols
        for card in self.avatar_cards:
            self.avatar_grid.removeWidget(card)
        for i, card in enumerate(self.avatar_cards):
            self.avatar_grid.addWidget(card, i // cols, i % cols)

    def eventFilter(self, obj, event):
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Type.Resize:
            # Only re-flow cards (no rebuilding or re-downloading) and debounce while dragging
            self.relayout_timer.start(60)
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def download_avatar(self, avatar_data):
        """Download an avatar based on the avatar data"""
        logger.info(f"Attempting to download avatar: {avatar_data.get('name', 'Unknown')}")
        logger.info(f"Avatar ID: {avatar_data.get('id', 'Unknown')}")

        avatar_id = avatar_data.get('id')
        if not avatar_id:
            logger.error("Avatar ID not found in data")
            QMessageBox.warning(self, "Error", "Avatar ID not found")
            return

        self.avatars_progress.setVisible(True)
        self.avatars_progress.setRange(0, 0)
        self.avatars_status.setText("Fetching avatar details…")

        worker = Worker(self.fetch_detailed_avatar, avatar_id)
        worker.signals.result.connect(lambda result: self.continue_avatar_download(result, avatar_data))
        worker.signals.error.connect(self.handle_avatar_download_error)
        self.threadpool.start(worker)

    def continue_avatar_download(self, detailed_avatar, original_avatar):
        self.avatars_progress.setVisible(False)
        self.display_status_for_page()

        if not detailed_avatar:
            logger.error("Could not fetch detailed avatar information")
            QMessageBox.warning(
                self,
                "Download Error",
                "Could not fetch detailed avatar information. Please try again."
            )
            return

        avatar_data = detailed_avatar
        logger.info(f"Got detailed avatar data with keys: {list(avatar_data.keys())}")

        download_url = None
        file_ext = ".vrca"

        if avatar_data.get('unityPackages'):
            packages = avatar_data['unityPackages']
            logger.info(f"Found {len(packages)} unity packages")
            logger.info(f"Available platforms: {[pkg.get('platform', 'unknown') for pkg in packages]}")

            # PRIORITY 1: Look specifically for standalonewindows platform
            windows_packages = [pkg for pkg in packages if pkg.get('platform') == 'standalonewindows' and pkg.get('assetUrl')]
            if windows_packages:
                download_url = windows_packages[0]['assetUrl']
                logger.info(f"Found standalonewindows package URL: {download_url}")
            else:
                logger.info("No standalonewindows package with an assetUrl found")

            # PRIORITY 2: Any package with an assetUrl
            if not download_url:
                for package in packages:
                    if package.get('assetUrl'):
                        download_url = package['assetUrl']
                        logger.info(f"Using {package.get('platform', 'unknown')} package URL as fallback: {download_url}")
                        break
        else:
            logger.info("No unityPackages found in avatar data")

        # PRIORITY 3: Top-level assetUrl (older avatars)
        if not download_url and avatar_data.get('assetUrl'):
            download_url = avatar_data['assetUrl']
            logger.info(f"Using top-level assetUrl as last resort: {download_url}")

        if not download_url:
            logger.error("No download URL found for this avatar")
            QMessageBox.warning(
                self,
                "Download Error",
                "No downloadable file URL found for this avatar. You may not have permission to download it."
            )
            return

        if '/variant/security' in download_url:
            download_url = download_url.split('/variant/security')[0]
            logger.info(f"Fixed URL by removing variant/security: {download_url}")

        safe_name = re.sub(r'[\\/:*?"<>|]', '_', avatar_data.get('name') or 'avatar')
        default_filename = f"{safe_name}{file_ext}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Avatar File",
            default_filename,
            f"Avatar Files (*{file_ext})"
        )

        if not file_path:
            logger.info("Download canceled by user")
            return

        # Switch to the downloader page and populate fields
        self.set_page(1)
        self.file_url_input.setText(download_url)
        self.file_output_input.setText(file_path)
        QTimer.singleShot(300, self.download_file)

    def display_status_for_page(self):
        if self.filtered_avatars:
            start_idx = (self.current_page - 1) * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.filtered_avatars))
            self.avatars_status.setText(f"Showing {start_idx+1}–{end_idx} of {len(self.filtered_avatars)} avatars")

    def handle_avatar_download_error(self, error):
        self.avatars_progress.setVisible(False)
        self.avatars_status.setText(f"Error: {error}")
        QMessageBox.critical(self, "Download Error", str(error))

    def fetch_detailed_avatar(self, avatar_id):
        """Fetch detailed information about a specific avatar"""
        logger.info(f"Fetching detailed information for avatar ID: {avatar_id}")

        if not self.api_client:
            logger.error("Not logged in")
            return None

        headers = {
            "User-Agent": self.api_client.user_agent,
            "Accept": "application/json"
        }
        url = f"https://api.vrchat.cloud/api/1/avatars/{avatar_id}"
        logger.info(f"Making API request to: {url}")

        try:
            response = requests.get(url, headers=headers, cookies=cookies_from_client(self.api_client), timeout=30)
            if response.status_code == 200:
                logger.info("Successfully fetched detailed avatar data")
                return response.json()
            logger.error(f"Failed to fetch avatar details: {response.status_code}")
            logger.error(f"Response: {response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Error fetching avatar details: {str(e)}")
            return None

    def browse_output_path(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output Path",
            self.file_output_input.text(),
            "All Files (*.*)"
        )
        if file_path:
            self.file_output_input.setText(file_path)

    def set_file_status(self, text, kind=None):
        theme = current_theme()
        self.file_status.setText(text)
        color = {"success": theme["success"], "error": theme["error"]}.get(kind)
        self.file_status.setStyleSheet(f"color: {color}; font-weight: 600;" if color else "")

    def update_download_progress(self, percent, message=""):
        self.file_progress.setValue(percent)
        if message:
            self.set_file_status(message)

    def download_file(self):
        if not self.api_client:
            QMessageBox.warning(self, "Not Signed In", "Please sign in to download files")
            return

        file_url = self.file_url_input.text().strip()
        output_path = self.file_output_input.text().strip()

        if not file_url:
            QMessageBox.warning(self, "Missing URL", "Please enter a VRChat file URL")
            return

        if not output_path:
            self.browse_output_path()
            output_path = self.file_output_input.text().strip()
            if not output_path:
                return

        self.set_file_status("Starting download…")
        self.file_progress.setVisible(True)
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.download_btn.setEnabled(False)

        # Stored on self so download_file_worker can emit progress
        self.worker = Worker(self.download_file_worker, file_url, output_path)
        self.worker.signals.result.connect(self.handle_download_result)
        self.worker.signals.error.connect(self.handle_download_error)
        self.worker.signals.progress.connect(self.update_download_progress)
        self.threadpool.start(self.worker)

    def download_file_worker(self, file_url, output_path):
        try:
            logger.info(f"Starting download from URL: {file_url}")

            if '/variant/security' in file_url:
                file_url = file_url.split('/variant/security')[0]
                logger.info(f"Fixed URL by removing variant/security: {file_url}")

            cookies = cookies_from_client(self.api_client)
            logger.info(f"Using authentication cookies: {list(cookies.keys())}")

            headers = {
                "User-Agent": self.api_client.user_agent,
                "Accept": "*/*"
            }

            logger.info(f"Sending authenticated request to: {file_url}")
            response = requests.get(file_url, headers=headers, cookies=cookies, stream=True, timeout=60)

            if response.status_code != 200:
                logger.error(f"Download failed with status {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                logger.error(f"Response content: {response.text[:200]}")
                raise Exception(f"Download failed with status {response.status_code}")

            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"Download size: {total_size} bytes")

            downloaded = 0
            last_percent = -1
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        percent = int(downloaded * 100 / total_size)
                        if percent != last_percent:
                            last_percent = percent
                            self.worker.signals.progress.emit(
                                percent,
                                f"Downloading… {downloaded/(1024*1024):.1f} MB of {total_size/(1024*1024):.1f} MB ({percent}%)"
                            )

            logger.info(f"Download completed successfully: {output_path}")
            return {
                "success": True,
                "path": output_path
            }
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            traceback.print_exc()
            raise

    def handle_download_result(self, result):
        self.file_progress.setVisible(False)
        self.download_btn.setEnabled(True)

        if result["success"]:
            self.set_file_status(f"Saved to {result['path']}", "success")
            QMessageBox.information(
                self,
                "Download Complete",
                f"File has been downloaded to:\n{result['path']}"
            )
        else:
            self.set_file_status("Download failed", "error")

    def handle_download_error(self, error):
        self.file_progress.setVisible(False)
        self.download_btn.setEnabled(True)
        self.set_file_status(f"Error: {error}", "error")
        QMessageBox.critical(self, "Download Error", str(error))


# Custom log handler to display logs in the UI.
# Workers log from background threads, so records are handed to the GUI thread via a signal.
class LogHandler(logging.Handler):
    class Bridge(QObject):
        message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.bridge = LogHandler.Bridge()
        self.setFormatter(logging.Formatter('%(asctime)s  %(levelname)-7s  %(message)s', "%H:%M:%S"))

    def emit(self, record):
        msg = self.format(record).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        theme = current_theme()
        color = {
            logging.DEBUG: theme["text_muted"],
            logging.INFO: theme["text_secondary"],
            logging.WARNING: theme["warning"],
            logging.ERROR: theme["error"],
            logging.CRITICAL: theme["error"],
        }.get(record.levelno, theme["text"])
        self.bridge.message.emit(f'<span style="color:{color}; white-space:pre">{msg}</span>')


def make_splash():
    theme = THEME["dark"]
    width, height = 560, 320
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(theme["background"]))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Soft glow behind the logo
    glow = QLinearGradient(0, 0, width, height)
    glow.setColorAt(0, QColor(124, 108, 242, 70))
    glow.setColorAt(1, QColor(34, 211, 238, 40))
    painter.fillRect(0, 0, width, height, glow)

    size = 72
    paint_logo(painter, QRectF((width - size) / 2, 70, size, size), theme)

    painter.setPen(QColor(theme["text"]))
    painter.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
    painter.drawText(QRect(0, 166, width, 40), Qt.AlignmentFlag.AlignCenter, APP_NAME)
    painter.setPen(QColor(theme["text_muted"]))
    painter.setFont(QFont("Segoe UI", 10))
    painter.drawText(QRect(0, 204, width, 24), Qt.AlignmentFlag.AlignCenter, f"Version {APP_VERSION}  ·  Loading…")
    painter.end()
    return QSplashScreen(pixmap)


def main():
    os.makedirs(DATA_FOLDER, exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(make_app_icon())

    splash = make_splash()
    splash.show()
    app.processEvents()

    window = VRChatManager()
    splash.finish(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    # Make the API client accept null fields before anything talks to VRChat
    api_patch.apply_patches()
    main()

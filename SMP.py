import os
import json
import datetime
import requests
import logging
import traceback
import sys
import re
from io import BytesIO
from functools import partial
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QLabel, QLineEdit, QComboBox, QScrollArea, 
                           QGridLayout, QFrame, QFileDialog, QMessageBox, QProgressBar, 
                           QTabWidget, QTextEdit, QSplashScreen, QDialog, QFormLayout,
                           QCheckBox, QSpinBox, QStyleFactory, QGroupBox, QGraphicsOpacityEffect,
                           QRadioButton, QButtonGroup, QToolButton, QMenu, QSizePolicy, QSpacerItem, QGraphicsDropShadowEffect)
from PyQt6.QtCore import (Qt, QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QSize, 
                        QTimer, QUrl, QPropertyAnimation, QEasingCurve, QRect, QRectF, QPoint, QEvent,
                        QParallelAnimationGroup, QSequentialAnimationGroup, QAbstractAnimation,
                        pyqtProperty, QDateTime)
from PyQt6.QtGui import (QPixmap, QImage, QFont, QIcon, QColor, QPalette, QDesktopServices, 
                       QFontDatabase, QPainter, QPen, QBrush, QCursor, QLinearGradient, 
                       QTransform, QPageSize, QKeySequence, QShortcut, QPainterPath)
import vrchatapi
from vrchatapi.api import authentication_api, files_api, avatars_api
from vrchatapi.exceptions import UnauthorizedException, ApiException
from vrchatapi.models.two_factor_auth_code import TwoFactorAuthCode
from vrchatapi.models.two_factor_email_code import TwoFactorEmailCode

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('vrchat_avatar_manager')

# Constants
APP_NAME = "VRChat Avatar Manager"
APP_VERSION = "0.1.0"
DATA_FOLDER = "data"
CONFIG_FILE = os.path.join(DATA_FOLDER, "config.json")
IMAGES_FOLDER = os.path.join(DATA_FOLDER, "images")
CACHE_FOLDER = os.path.join(DATA_FOLDER, "cache")

# Theme Colors
THEME = {
    "dark": {
        "primary": "#6C5CE7",        # Purple
        "secondary": "#00CECE",      # Teal
        "accent": "#FC427B",         # Pink
        "background": "#1E1E2E",     # Dark blue-gray
        "card": "#2D2D44",           # Lighter blue-gray
        "text": "#FFFFFF",           # White text
        "text_secondary": "#A0A0A0", # Gray text
        "surface": "#2A2A3C",        # Medium blue-gray
        "error": "#FF5252",          # Red
        "warning": "#FFD740",        # Amber
        "success": "#4CAF50",        # Green
        "divider": "#3F3F5F",        # Divider color
        "hover": "#383854",          # Hover state
        "pressed": "#44446A",        # Pressed state
        "inactive": "#474765",       # Inactive
    },
    "light": {
        "primary": "#6C5CE7",        # Purple
        "secondary": "#00CECE",      # Teal
        "accent": "#FC427B",         # Pink
        "background": "#F8F9FC",     # Light grey-blue
        "card": "#FFFFFF",           # White
        "text": "#2E3440",           # Near black
        "text_secondary": "#4C566A", # Dark gray
        "surface": "#ECEFF4",        # Very light gray
        "error": "#FF5252",          # Red
        "warning": "#FFB300",        # Amber
        "success": "#4CAF50",        # Green
        "divider": "#E5E9F0",        # Divider color
        "hover": "#F5F7FA",          # Hover state
        "pressed": "#E1E5EB",        # Pressed state
        "inactive": "#D8DEE9",       # Inactive
    }
}

# Ensure directories exist
os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(IMAGES_FOLDER, exist_ok=True)
os.makedirs(CACHE_FOLDER, exist_ok=True)

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
            # Run the function
            result = self.fn(*self.args, **self.kwargs)
            # Emit the result
            self.signals.result.emit(result)
        except Exception as e:
            # Log the error
            logger.error(f"Worker error: {str(e)}")
            traceback.print_exc()
            # Emit the error
            self.signals.error.emit(str(e))
        finally:
            # Always emit finished signal
            self.signals.finished.emit()

# Custom Button with hover effects
class AnimatedButton(QPushButton):
    def __init__(self, text="", parent=None, primary=True, icon=None):
        super().__init__(text, parent)
        self.primary = primary
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setFlat(True)
        
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(18, 18))
        
        # Initialize animation properties
        self._opacity = 1.0
        self._hovered = False
        self._pressed = False
        
        # Default style
        self.update_style()
    
    def update_style(self):
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        if self.primary:
            base_color = theme["primary"]
            hover_color = self._lighten_color(base_color, 20) if is_dark_mode else self._darken_color(base_color, 10)
            text_color = "#FFFFFF"
        else:
            base_color = theme["surface"]
            hover_color = theme["hover"]
            text_color = theme["text"]
        
        self.setStyleSheet(f"""
            AnimatedButton {{
                background-color: {base_color};
                color: {text_color};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 14px;
            }}
            AnimatedButton:hover {{
                background-color: {hover_color};
            }}
            AnimatedButton:pressed {{
                background-color: {theme["pressed"]};
            }}
            AnimatedButton:disabled {{
                background-color: {theme["inactive"]};
                color: {theme["text_secondary"]};
            }}
        """)

    def _lighten_color(self, color, amount=30):
        # Convert hex to RGB
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        
        # Lighten
        r = min(255, r + amount)
        g = min(255, g + amount)
        b = min(255, b + amount)
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def _darken_color(self, color, amount=30):
        # Convert hex to RGB
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        
        # Darken
        r = max(0, r - amount)
        g = max(0, g - amount)
        b = max(0, b - amount)
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pressed = True
            
            # Create a "press" animation
            self.anim = QPropertyAnimation(self, b"geometry")
            self.anim.setDuration(100)
            rect = self.geometry()
            
            # Shrink slightly when pressed
            target = QRect(rect.x()+1, rect.y()+1, rect.width()-2, rect.height()-2)
            self.anim.setEndValue(target)
            self.anim.start()
            
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self._pressed:
            self._pressed = False
            
            # Create a "release" animation
            self.anim = QPropertyAnimation(self, b"geometry")
            self.anim.setDuration(100)
            self.anim.setEndValue(self.geometry().adjusted(-1, -1, 1, 1))
            self.anim.start()
            
        super().mouseReleaseEvent(event)
    
    def setTheme(self, is_dark):
        self.update_style()

# Custom LineEdit with animated focus effect
class AnimatedLineEdit(QLineEdit):
    def __init__(self, parent=None, placeholder="", icon=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        
        # Initialize state
        self._focused = False
        
        # Set up animations
        self.focusAnim = QPropertyAnimation(self, b"styleSheet")
        self.focusAnim.setDuration(200)
        
        # Initial style
        self.update_style()
        
        # Add icon if provided
        if icon:
            self.setTextMargins(30, 0, 0, 0)
            
            # Create icon label
            self.icon_label = QLabel(self)
            self.icon_label.setPixmap(icon.pixmap(16, 16))
            self.icon_label.setStyleSheet("background-color: transparent;")
            self.icon_label.setGeometry(8, (self.height() - 16) // 2, 16, 16)
            
            # Update icon position when the widget is resized
            self.resizeEvent = self._update_icon_position
    
    def _update_icon_position(self, event):
        if hasattr(self, 'icon_label'):
            self.icon_label.setGeometry(8, (self.height() - 16) // 2, 16, 16)
        super().resizeEvent(event)
    
    def update_style(self):
        theme = app_theme["dark" if is_dark_mode else "light"]
        bg_color = theme["surface"]
        border_color = theme["divider"]
        text_color = theme["text"]
        focus_color = theme["primary"]
        
        self.setStyleSheet(f"""
            AnimatedLineEdit {{
                background-color: {bg_color};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 8px 12px;
                selection-background-color: {focus_color};
            }}
            AnimatedLineEdit:focus {{
                border: 2px solid {focus_color};
            }}
        """)
    
    def focusInEvent(self, event):
        self._focused = True
        theme = app_theme["dark" if is_dark_mode else "light"]
        focus_color = theme["primary"]
        
        # Set up the animation
        self.focusAnim.setStartValue(self.styleSheet())
        new_style = self.styleSheet().replace("border: 1px solid", f"border: 2px solid {focus_color}")
        self.focusAnim.setEndValue(new_style)
        self.focusAnim.start()
        
        super().focusInEvent(event)
    
    def focusOutEvent(self, event):
        self._focused = False
        theme = app_theme["dark" if is_dark_mode else "light"]
        border_color = theme["divider"]
        
        # Set up the animation
        self.focusAnim.setStartValue(self.styleSheet())
        new_style = self.styleSheet().replace("border: 2px solid", f"border: 1px solid {border_color}")
        self.focusAnim.setEndValue(new_style)
        self.focusAnim.start()
        
        super().focusOutEvent(event)
    
    def setTheme(self, is_dark):
        self.update_style()

# Avatar Card Widget to display each avatar
class AvatarCard(QFrame):
    downloadRequested = pyqtSignal(dict)
    
    def __init__(self, avatar_data, api_client=None, parent=None):
        super().__init__(parent)
        
        if hasattr(self, 'download_btn'):
            self.download_btn.deleteLater()
            
        self.download_btn = AnimatedButton("Download", primary=True)
        self.download_btn.setFixedHeight(36)
        self.download_btn.clicked.connect(self.request_download)
        self.avatar_data = avatar_data
        self.api_client = api_client
        self.setup_ui()
        
        # Set up card hover animation
        self.setMouseTracking(True)
        self.hover_anim = QPropertyAnimation(self, b"geometry")
        self.hover_anim.setDuration(150)
        
        # Set up download button animation
        self.download_anim = QPropertyAnimation(self.download_btn, b"pos")
        self.download_anim.setDuration(150)
        self.download_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        
    def setup_ui(self):
        # Set card appearance
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedSize(300, 340)
        self.setStyleSheet(f"""
            AvatarCard {{
                background-color: {theme["card"]};
                border-radius: 12px;
                border: 1px solid {theme["divider"]};
            }}
            QLabel {{
                background-color: transparent;
                color: {theme["text"]};
            }}
        """)
        
        # Main layout with no margins for full-bleed image
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Image container at the top - spans the full width
        self.image_container = QFrame(self)
        self.image_container.setFixedHeight(180)
        self.image_container.setStyleSheet(f"""
            background-color: {theme["surface"]};
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid {theme["divider"]};
        """)
        
        image_layout = QVBoxLayout(self.image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        # Avatar image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(180)
        self.image_label.setScaledContents(False)
        self.image_label.setStyleSheet("background-color: transparent;")
        
        image_layout.addWidget(self.image_label)
        
        # Content container for the rest of the card
        content_container = QWidget()
        content_container.setStyleSheet(f"background-color: transparent;")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)
        
        # Avatar name with ellipsis for long names
        avatar_name = self.avatar_data.get('name', 'Unknown Avatar')
        self.name_label = QLabel(avatar_name)
        self.name_label.setFont(QFont('Segoe UI', 13, QFont.Weight.Bold))
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.name_label.setWordWrap(True)
        self.name_label.setMaximumHeight(40)
        self.name_label.setStyleSheet(f"color: {theme['text']}; background-color: transparent;")
        
        # Avatar author
        author_name = self.avatar_data.get('authorName', 'Unknown Author')
        self.author_label = QLabel(f"By: {author_name}")
        self.author_label.setFont(QFont('Segoe UI', 10))
        self.author_label.setStyleSheet(f"color: {theme['text_secondary']}; background-color: transparent;")
        
        # Avatar description (truncated)
        description = self.avatar_data.get('description', '')
        if not description:
            description = "No description provided"
        truncated_desc = description[:80] + ('...' if len(description) > 80 else '')
        self.desc_label = QLabel(truncated_desc)
        self.desc_label.setWordWrap(True)
        self.desc_label.setFixedHeight(50)
        self.desc_label.setStyleSheet(f"color: {theme['text_secondary']}; font-style: italic; font-size: 9pt; background-color: transparent;")
        
        # Download button
        self.download_btn = AnimatedButton("Download", primary=True)
        self.download_btn.setFixedHeight(36)
        self.download_btn.clicked.connect(self.request_download)
        
        # Add widgets to content layout
        content_layout.addWidget(self.name_label)
        content_layout.addWidget(self.author_label)
        content_layout.addWidget(self.desc_label)
        content_layout.addWidget(self.download_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Add containers to main layout
        main_layout.addWidget(self.image_container)
        main_layout.addWidget(content_container)
        
        # Set layout
        self.setLayout(main_layout)
        
        self.setAutoFillBackground(True)
        self.raise_()  # Raise above any previous widgets
        
        # Load the avatar image
        self.load_avatar_image()
    
    def update_theme(self):
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        self.setStyleSheet(f"""
            AvatarCard {{
                background-color: {theme["card"]};
                border-radius: 12px;
                border: 1px solid {theme["divider"]};
            }}
            QLabel {{
                background-color: transparent;
                color: {theme["text"]};
            }}
        """)
        
        self.image_container.setStyleSheet(f"""
            background-color: {theme["surface"]};
            border-top-left-radius: 12px;
            border-top-right-radius: 12px;
            border-bottom: 1px solid {theme["divider"]};
        """)
        
        self.name_label.setStyleSheet(f"color: {theme['text']}; background-color: transparent;")
        self.author_label.setStyleSheet(f"color: {theme['text_secondary']}; background-color: transparent;")
        self.desc_label.setStyleSheet(f"color: {theme['text_secondary']}; font-style: italic; font-size: 9pt; background-color: transparent;")
        
    def load_avatar_image(self):
        # Use thumbnail if available, otherwise use image URL
        image_url = self.avatar_data.get('thumbnailImageUrl') or self.avatar_data.get('imageUrl')
        if not image_url:
            self.image_label.setText("No Image Available")
            return
            
        # Create a worker to download the image
        worker = Worker(self.download_image, image_url)
        worker.signals.result.connect(self.set_image)
        worker.signals.error.connect(lambda error: self.image_label.setText(f"Error: {error}"))
        QThreadPool.globalInstance().start(worker)
    
    def download_image(self, url):
        try:
            # Get cookies from the API client
            cookies = {}
            if self.api_client:
                for cookie in self.api_client.rest_client.cookie_jar:
                    cookies[cookie.name] = cookie.value
                
            headers = {
                "User-Agent": self.api_client.user_agent if self.api_client else f"{APP_NAME}/{APP_VERSION}",
                "Accept": "*/*"  # Accept any content type
            }
            
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies
            )
            
            if response.status_code == 200:
                return response.content
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
        return None
        
    def setScrollingMode(self, is_scrolling):
        """Toggle between normal and simplified rendering for scrolling"""
        if is_scrolling:
            # Simplified mode for scrolling - disable fancy effects
            self.setGraphicsEffect(None)
            self.image_label.setGraphicsEffect(None)
            self.download_btn.setGraphicsEffect(None)
        else:
            # Normal mode - can restore simple effects if needed
            theme = app_theme["dark" if is_dark_mode else "light"]
            self.update_theme()
        
    
    def set_image(self, image_data):
        if image_data:
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)
            scaled_pixmap = pixmap.scaled(300, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("Failed to load image")
    
    def request_download(self):
        # Animate button press
        self.download_btn.setText("Downloading...")
        self.download_btn.setEnabled(False)
        
        # Signal to download the avatar
        self.downloadRequested.emit(self.avatar_data)
        
        # Re-enable and reset button text after a delay
        QTimer.singleShot(800, lambda: self.download_btn.setEnabled(True))
        QTimer.singleShot(800, lambda: self.download_btn.setText("Download"))
    
    def enterEvent(self, event):
        # Scale up slightly when hovering
        original_rect = self.geometry()
        target_rect = original_rect.adjusted(-2, -2, 2, 2)
        
        self.hover_anim.setEndValue(target_rect)
        self.hover_anim.start()
        
        # Add drop shadow when hovering using QGraphicsDropShadowEffect instead of box-shadow
        theme = app_theme["dark" if is_dark_mode else "light"]
        self.setStyleSheet(f"""
            AvatarCard {{
                background-color: {theme["card"]};
                border-radius: 12px;
                border: 1px solid {theme["primary"]};
            }}
            QLabel {{
                background-color: transparent;
                color: {theme["text"]};
            }}
        """)
        
        # Apply drop shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
    def leaveEvent(self, event):
        # Return to original size
        original_rect = self.geometry().adjusted(2, 2, -2, -2)
        
        self.hover_anim.setEndValue(original_rect)
        self.hover_anim.start()
        
        # Remove shadow
        self.update_theme()

# Theme Switch Button
class ThemeSwitchButton(QWidget):
    themeChanged = pyqtSignal(bool)  # Signal to indicate theme change (True = dark)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 30)
        self.dark_mode = True  # Start with dark mode
        self._value = 0  # Initialize the _value attribute here
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.animation.finished.connect(self.update)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
    
    def get_value(self):
        return self._value
        
    def set_value(self, value):
        self._value = value
        self.update()
        
    value = pyqtProperty(float, get_value, set_value)
    
    def paintEvent(self, event):
        # Custom painting to create an attractive toggle switch
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Get current colors based on theme
        theme = app_theme["dark" if is_dark_mode else "light"]
        bg_color = QColor(theme["background"])
        track_color = QColor(theme["inactive"])
        thumb_color = QColor(theme["primary"])
        
        # Draw the track
        track_path = QPainterPath()
        # Fix: Use the direct coordinate version of addRoundedRect instead of QRect
        track_path.addRoundedRect(0, 0, width, height, height/2, height/2)
        painter.fillPath(track_path, track_color)
        
        # Calculate thumb position
        thumb_size = height - 8
        thumb_x = 4 + (width - thumb_size - 8) * (self._value if self.dark_mode else 1 - self._value)
        
        # Draw the thumb - no need to cast to int
        thumb_rect = QRectF(thumb_x, 4, thumb_size, thumb_size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb_color)
        painter.drawEllipse(thumb_rect)
        
        # Draw icon in thumb
        icon_size = thumb_size * 0.5
        icon_rect = QRectF(thumb_x + (thumb_size - icon_size) / 2, 
                          4 + (thumb_size - icon_size) / 2, 
                          icon_size, icon_size)
        
        if self.dark_mode:
            # Draw moon icon
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawEllipse(icon_rect)
            
            # Draw "bite" out of moon
            offset = icon_size * 0.3
            painter.setBrush(QBrush(thumb_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(icon_rect.x() + offset, 
                                      icon_rect.y(), 
                                      icon_size, icon_size))
        else:
            # Draw sun icon
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            painter.drawEllipse(icon_rect)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dark_mode = not self.dark_mode
            self.animation.setStartValue(0 if self.dark_mode else 1)
            self.animation.setEndValue(1 if self.dark_mode else 0)
            self.animation.start()
            
            # Emit signal
            self.themeChanged.emit(self.dark_mode)
            
    def setDarkMode(self, is_dark):
        if is_dark != self.dark_mode:
            self.dark_mode = is_dark
            self.animation.setStartValue(0 if is_dark else 1)
            self.animation.setEndValue(1 if is_dark else 0)
            self.animation.start()

# Pagination Widget
# Fix for the pagination widget layout and functionality

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
        layout.setSpacing(10)  # Increased spacing
        
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        # Add spacer to push everything to center
        layout.addStretch(1)
        
        # Previous page button
        self.prev_btn = AnimatedButton("←", primary=False)
        self.prev_btn.setFixedSize(40, 36)  # Wider button
        self.prev_btn.clicked.connect(self.prev_page)
        
        # Page indicator
        self.page_container = QFrame()
        self.page_container.setFixedHeight(36)
        self.page_container.setMinimumWidth(150)  # Fixed width for stability
        self.page_container.setFrameShape(QFrame.Shape.NoFrame)
        self.page_container.setStyleSheet(f"background: transparent;")
        
        page_layout = QHBoxLayout(self.page_container)
        page_layout.setContentsMargins(10, 0, 10, 0)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.page_label = QLabel(f"Page {self.current_page} of {self.total_pages}")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet(f"color: {theme['text']}; font-size: 14px;")
        
        page_layout.addWidget(self.page_label)
        
        # Next page button
        self.next_btn = AnimatedButton("→", primary=False)
        self.next_btn.setFixedSize(40, 36)  # Wider button
        self.next_btn.clicked.connect(self.next_page)
        
        # Page size dropdown - in separate container for alignment
        self.per_page_container = QWidget()
        per_page_layout = QHBoxLayout(self.per_page_container)
        per_page_layout.setContentsMargins(15, 0, 0, 0)
        
        self.items_per_page_combo = QComboBox()
        self.items_per_page_combo.addItems(["10 per page", "25 per page", "50 per page", "100 per page"])
        self.items_per_page_combo.setCurrentIndex(2)  # Default to 50
        self.items_per_page_combo.currentIndexChanged.connect(self.change_items_per_page)
        self.items_per_page_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["divider"]};
                border-radius: 6px;
                padding: 4px 8px;
                min-width: 120px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme["card"]};
                color: {theme["text"]};
                border: 1px solid {theme["divider"]};
                selection-background-color: {theme["primary"]};
                selection-color: white;
            }}
        """)
        
        per_page_layout.addWidget(self.items_per_page_combo)
        
        # Add all components to main layout
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.page_container)
        layout.addWidget(self.next_btn)
        layout.addWidget(self.per_page_container)
        
        # Add spacer to push everything to center
        layout.addStretch(1)
        
        self.update_ui()
    
    def set_page_count(self, total_items):
        self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
        self.current_page = min(self.current_page, self.total_pages)
        self.update_ui()
    
    def update_ui(self):
        # Update the page label with current state
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
        
        # Enable/disable navigation buttons appropriately
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
        # Map combo box index to item count
        items_map = {0: 10, 1: 25, 2: 50, 3: 100}
        new_items_per_page = items_map.get(index, 50)
        
        # Only take action if this is a change
        if new_items_per_page != self.items_per_page:
            self.items_per_page = new_items_per_page
            
            # Emit signal to trigger page refresh with new item count
            self.current_page = 1
            self.pageChanged.emit(self.current_page)

# Login Dialog
class LoginDialog(QDialog):
    def __init__(self, parent=None, username="", password=""):
        super().__init__(parent)
        self.username = username
        self.password = password
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("VRChat Login")
        self.setFixedSize(400, 300)
        
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme["background"]};
                border-radius: 10px;
            }}
            QLabel {{
                color: {theme["text"]};
            }}
            QCheckBox {{
                color: {theme["text"]};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Logo/Header
        if is_dark_mode:
            header_color = theme["primary"]
        else:
            header_color = theme["primary"]
            
        logo_label = QLabel("VRChat Login")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet(f"""
            font-size: 24px;
            font-weight: bold;
            color: {header_color};
            margin-bottom: 10px;
        """)
        
        # Username field with animation
        self.username_input = AnimatedLineEdit(placeholder="Username or Email")
        self.username_input.setText(self.username)
        
        # Password field with animation
        self.password_input = AnimatedLineEdit(placeholder="Password")
        self.password_input.setText(self.password)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        # Remember me checkbox
        self.save_checkbox = QCheckBox("Remember my credentials")
        self.save_checkbox.setChecked(True)
        self.save_checkbox.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border: 1px solid {theme["divider"]};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {theme["primary"]};
                border: 1px solid {theme["primary"]};
                image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>');
            }}
        """)
        
        # Login button with animation
        self.login_btn = AnimatedButton("Sign In", primary=True)
        self.login_btn.setFixedHeight(40)
        self.login_btn.clicked.connect(self.accept)
        
        # Cancel button
        self.cancel_btn = AnimatedButton("Cancel", primary=False)
        self.cancel_btn.setFixedHeight(40)
        self.cancel_btn.clicked.connect(self.reject)
        
        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.login_btn)
        
        # Add everything to main layout
        layout.addWidget(logo_label)
        layout.addWidget(self.username_input)
        layout.addWidget(self.password_input)
        layout.addWidget(self.save_checkbox)
        layout.addSpacing(10)
        layout.addLayout(button_layout)
        
        # Set default focus
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
        self.setFixedSize(400, 250)
        
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme["background"]};
                border-radius: 10px;
            }}
            QLabel {{
                color: {theme["text"]};
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Determine title and message based on type
        title = "Email Verification" if self.is_email else "Authenticator Verification"
        source = "sent to your email" if self.is_email else "from your authenticator app"
        
        # Header
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont('Segoe UI', 18, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"color: {theme['primary']};")
        
        # Instructions
        self.info_label = QLabel(f"Please enter the 6-digit code {source}:")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setWordWrap(True)
        
        # Code input with special styling for each digit
        self.code_input = QLineEdit()
        self.code_input.setMaxLength(6)
        self.code_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.code_input.setFixedHeight(50)
        self.code_input.setFont(QFont('Segoe UI', 24))
        self.code_input.textChanged.connect(self.validate_code_input)
        self.code_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["divider"]};
                border-radius: 8px;
                padding: 8px;
                letter-spacing: 10px;
            }}
            QLineEdit:focus {{
                border: 2px solid {theme["primary"]};
            }}
        """)
        
        # Verify button
        self.verify_btn = AnimatedButton("Verify", primary=True)
        self.verify_btn.setFixedHeight(40)
        self.verify_btn.clicked.connect(self.accept)
        
        # Add to layout
        layout.addWidget(self.title_label)
        layout.addWidget(self.info_label)
        layout.addWidget(self.code_input)
        layout.addSpacing(10)
        layout.addWidget(self.verify_btn)
        
        # Focus the input
        self.code_input.setFocus()
    
    def validate_code_input(self, text):
        # Only allow digits
        filtered_text = ''.join(filter(str.isdigit, text))
        if filtered_text != text:
            self.code_input.setText(filtered_text)
    
    def get_code(self):
        return self.code_input.text()

# Main Window
class VRChatManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_client = None
        self.avatars_data = []
        self.filtered_avatars = []
        self.current_page = 1
        self.items_per_page = 50
        self.last_scroll_pos = 0
        self.last_scroll_time = 0
        self.is_scrolling = False
        self.threadpool = QThreadPool()
        
        # Set the global theme to start
        global app_theme, is_dark_mode
        app_theme = THEME
        is_dark_mode = True  # Start with dark mode
        
        self.load_config()
        self.setup_ui()
        
    def load_config(self):
        # Initialize config values
        self.vrchat_username = ""
        self.vrchat_password = ""
        self.dark_mode = True
        
        # Load from config file if exists
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.vrchat_username = config.get("vrchat_username", "")
                    self.vrchat_password = config.get("vrchat_password", "")
                    self.dark_mode = config.get("dark_mode", True)
                    
                    # Set global dark mode
                    global is_dark_mode
                    is_dark_mode = self.dark_mode
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
            
    def debug_avatar_structure(self, avatar_data):
        """Print detailed debug information about an avatar's structure"""
        logger.info(f"=== Debug Avatar Structure ===")
        logger.info(f"Avatar name: {avatar_data.get('name', 'Unknown')}")
        logger.info(f"Avatar ID: {avatar_data.get('id', 'Unknown')}")
        logger.info(f"Top-level keys: {list(avatar_data.keys())}")
        
        # Check for direct assetUrl
        if 'assetUrl' in avatar_data:
            logger.info(f"Direct assetUrl: {avatar_data['assetUrl']}")
        else:
            logger.info(f"No direct assetUrl found")
        
        # Check for unityPackages
        if 'unityPackages' in avatar_data and avatar_data['unityPackages']:
            logger.info(f"Unity packages count: {len(avatar_data['unityPackages'])}")
            for i, pkg in enumerate(avatar_data['unityPackages']):
                logger.info(f"  Package {i}:")
                logger.info(f"    Keys: {list(pkg.keys())}")
                if 'assetUrl' in pkg:
                    logger.info(f"    assetUrl: {pkg['assetUrl']}")
                logger.info(f"    platform: {pkg.get('platform', 'unknown')}")
        else:
            logger.info(f"No unityPackages found")
        
        logger.info(f"=== End Debug ===")
        
        
        
        
    def setup_scroll_optimization(self):
        """Apply aggressive anti-ghosting techniques for scrolling"""
        # Create a solid color background for the scrolling area
        theme = app_theme["dark" if is_dark_mode else "light"]
        self.scroll_area.viewport().setStyleSheet(f"background-color: {theme['background']};")
        
        # Enable background auto-fill for the container and viewport
        self.avatar_container.setAutoFillBackground(True)
        self.scroll_area.viewport().setAutoFillBackground(True)
        
        # Set color palettes explicitly to match
        palette = QPalette()
        bg_color = QColor(theme["background"])
        palette.setColor(QPalette.ColorRole.Window, bg_color)
        palette.setColor(QPalette.ColorRole.Base, bg_color)
        self.avatar_container.setPalette(palette)
        self.scroll_area.viewport().setPalette(palette)
        
        # Connect to scroll events
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scroll_change)
        
        # Create ghost-buster overlay
        self.ghost_overlay = QWidget(self.scroll_area)
        self.ghost_overlay.setStyleSheet(f"background-color: {theme['background']};")
        self.ghost_overlay.hide()
        
        
    def on_scroll_change(self, value):
        """Handle scroll events with ghost-busting technique"""
        # Only activate ghost-busting during rapid scrolling
        if not hasattr(self, 'last_scroll_pos'):
            self.last_scroll_pos = value
            self.last_scroll_time = QDateTime.currentMSecsSinceEpoch()
            return
        
        # Calculate scroll speed
        current_time = QDateTime.currentMSecsSinceEpoch()
        time_diff = current_time - self.last_scroll_time
        if time_diff < 1:  # Avoid division by zero
            time_diff = 1
        
        scroll_distance = abs(value - self.last_scroll_pos)
        scroll_speed = scroll_distance / time_diff
        
        # Update tracking values
        self.last_scroll_pos = value
        self.last_scroll_time = current_time
        
        # If scrolling quickly, use the ghost-buster
        if scroll_speed > 0.2:  # Threshold for "fast scrolling"
            # Show ghost overlay during fast scrolling
            self.ghost_overlay.setGeometry(self.scroll_area.viewport().rect())
            self.ghost_overlay.show()
            self.ghost_overlay.raise_()
            
            # Schedule to hide it shortly after scrolling stops
            QTimer.singleShot(100, self.hide_ghost_overlay)
        
    def hide_ghost_overlay(self):
        """Hide the ghost overlay after scrolling stops"""
        if hasattr(self, 'ghost_overlay'):
            self.ghost_overlay.hide()


    def fix_scroll_behavior(self):
        """Fix scrolling behavior issues with minimal changes"""
        # Set container width based on viewport
        self.avatar_container.setMinimumWidth(self.scroll_area.viewport().width() - 30)
        
        # Disable horizontal scrolling
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Make sure each card has a fixed size
        for i in range(self.avatar_grid.count()):
            item = self.avatar_grid.itemAt(i)
            if item and item.widget():
                item.widget().setFixedSize(300, 340)

    def on_scroll(self, value):
        """Handle scroll events to prevent layout shifts"""
        # Temporarily disable layout updates during scrolling
        self.avatar_container.setUpdatesEnabled(False)
        
        # Re-enable updates after a short delay
        QTimer.singleShot(50, lambda: self.avatar_container.setUpdatesEnabled(True))
        
        
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Delay refresh to avoid excessive updates during resizing
        QTimer.singleShot(200, self.refresh_avatar_panels)
        
    
    def setup_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1200, 800)
        
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header section with nice gradient background
        self.header = QFrame()
        self.header.setFixedHeight(70)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(20, 10, 20, 10)
        
        # App logo and title
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(10)
        
        self.logo_label = QLabel(APP_NAME)
        self.logo_label.setFont(QFont('Segoe UI', 18, QFont.Weight.Bold))
        
        logo_layout.addWidget(self.logo_label)
        
        # Right side controls
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(15)
        
        # Theme toggle
        self.theme_switch = ThemeSwitchButton()
        self.theme_switch.setDarkMode(is_dark_mode)
        self.theme_switch.themeChanged.connect(self.toggle_theme)
        
        # User status
        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(10)
        
        self.status_icon = QLabel()
        self.status_icon.setFixedSize(12, 12)
        self.status_icon.setStyleSheet("background-color: #ff5252; border-radius: 6px;")
        
        self.status_label = QLabel("Not logged in")
        
        self.status_layout.addWidget(self.status_icon)
        self.status_layout.addWidget(self.status_label)
        
        # Login button
        self.login_btn = AnimatedButton("Login", primary=True)
        self.login_btn.clicked.connect(self.login_to_vrchat)
        
        controls_layout.addLayout(self.status_layout)
        controls_layout.addWidget(self.theme_switch)
        controls_layout.addWidget(self.login_btn)
        
        # Add to header
        header_layout.addLayout(logo_layout)
        header_layout.addStretch(1)
        header_layout.addLayout(controls_layout)

        # Now that all UI elements are initialized, update the theme
        self.update_theme()
        
        # Content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # Tab widget with custom styling
        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        
        # Avatars tab
        self.avatars_tab = QWidget()
        avatars_layout = QVBoxLayout(self.avatars_tab)
        avatars_layout.setContentsMargins(15, 15, 15, 15)
        avatars_layout.setSpacing(15)
        
        # Search and filter bar
        search_container = QFrame()
        search_container.setFixedHeight(60)
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(10, 5, 10, 5)
        search_layout.setSpacing(15)
        
        # Avatar filter dropdown
        self.filter_combo = QComboBox()
        #self.filter_combo.addItems(["All Avatars", "Public Avatars", "Private Avatars"]) Crashes when changing too quickly. Will fix this later
        self.filter_combo.addItems(["All Avatars"])
        self.filter_combo.setFixedWidth(150)
        self.filter_combo.currentIndexChanged.connect(self.fetch_avatars)
        
        # Search with nice animation
        self.search_input = AnimatedLineEdit(placeholder="Search avatars by name...")
        self.search_input.textChanged.connect(self.filter_avatars)
        
        # Refresh button
        self.refresh_btn = AnimatedButton("Refresh", primary=False)
        self.refresh_btn.clicked.connect(self.fetch_avatars)
        
        search_layout.addWidget(QLabel("Show:"))
        search_layout.addWidget(self.filter_combo)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.refresh_btn)
        
        # Avatar grid container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        self.avatar_container = QWidget()
        self.avatar_grid = QGridLayout(self.avatar_container)
        self.avatar_grid.setHorizontalSpacing(20)
        self.avatar_grid.setVerticalSpacing(20)
        self.avatar_grid.setContentsMargins(10, 10, 10, 10)
        
        self.scroll_area.setWidget(self.avatar_container)
        
        # Pagination controls
        self.pagination = PaginationWidget()
        self.pagination.pageChanged.connect(self.change_page)
        
        # Status bar for avatars
        status_layout = QHBoxLayout()
        
        self.avatars_status = QLabel("Not logged in. Please login to browse avatars.")
        
        self.avatars_progress = QProgressBar()
        self.avatars_progress.setFixedWidth(200)
        self.avatars_progress.setFixedHeight(8)
        self.avatars_progress.setTextVisible(False)
        self.avatars_progress.setVisible(False)
        
        status_layout.addWidget(self.avatars_status)
        status_layout.addStretch(1)
        status_layout.addWidget(self.avatars_progress)
        
        # Add all elements to avatars tab
        avatars_layout.addWidget(search_container)
        avatars_layout.addWidget(self.scroll_area)
        avatars_layout.addWidget(self.pagination, alignment=Qt.AlignmentFlag.AlignCenter)
        avatars_layout.addLayout(status_layout)
        
        self.tab_widget.addTab(self.avatars_tab, "Browse Avatars")
        
        # File Downloader tab
        self.downloader_tab = QWidget()
        downloader_layout = QVBoxLayout(self.downloader_tab)
        downloader_layout.setContentsMargins(20, 20, 20, 20)
        downloader_layout.setSpacing(20)
        
        # Title
        downloader_title = QLabel("File Downloader")
        downloader_title.setFont(QFont('Segoe UI', 18, QFont.Weight.Bold))
        downloader_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Input form
        form_container = QFrame()
        form_layout = QFormLayout(form_container)
        form_layout.setContentsMargins(20, 20, 20, 20)
        form_layout.setSpacing(15)
        
        # URL input with nice icon
        self.file_url_input = AnimatedLineEdit(placeholder="Enter VRChat file URL to download")
        
        # Output path with browse button
        output_widget = QWidget()
        output_layout = QHBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(10)
        
        self.file_output_input = AnimatedLineEdit(placeholder="Save location (optional)")
        
        self.file_output_browse = AnimatedButton("Browse", primary=False)
        self.file_output_browse.clicked.connect(self.browse_output_path)
        
        output_layout.addWidget(self.file_output_input)
        output_layout.addWidget(self.file_output_browse)
        
        form_layout.addRow("VRChat File URL:", self.file_url_input)
        form_layout.addRow("Output Path:", output_widget)
        
        # Download button
        self.download_btn = AnimatedButton("Download File", primary=True)
        self.download_btn.setFixedWidth(200)
        self.download_btn.setFixedHeight(50)
        self.download_btn.setFont(QFont('Segoe UI', 12, QFont.Weight.Bold))
        self.download_btn.clicked.connect(self.download_file)
        
        # Status area
        status_container = QFrame()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(20, 20, 20, 20)
        status_layout.setSpacing(15)
        
        self.file_status = QLabel("Enter a VRChat file URL to download")
        self.file_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_status.setWordWrap(True)
        
        self.file_progress = QProgressBar()
        self.file_progress.setMinimumHeight(10)
        self.file_progress.setTextVisible(False)
        self.file_progress.setVisible(False)
        
        status_layout.addWidget(self.file_status)
        status_layout.addWidget(self.file_progress)
        
        # Add all to downloader tab
        downloader_layout.addWidget(downloader_title)
        downloader_layout.addWidget(form_container)
        downloader_layout.addWidget(self.download_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        downloader_layout.addWidget(status_container)
        downloader_layout.addStretch(1)
        
        self.tab_widget.addTab(self.downloader_tab, "File Downloader")
        
        # Logs tab
        self.logs_tab = QWidget()
        logs_layout = QVBoxLayout(self.logs_tab)
        logs_layout.setContentsMargins(15, 15, 15, 15)
        logs_layout.setSpacing(10)
        
        # Log controls
        log_controls = QHBoxLayout()
        
        log_title = QLabel("Application Logs")
        log_title.setFont(QFont('Segoe UI', 14, QFont.Weight.Bold))
        
        clear_log_btn = AnimatedButton("Clear Log", primary=False)
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        
        save_log_btn = AnimatedButton("Save Log", primary=False)
        save_log_btn.clicked.connect(self.save_log)
        
        log_controls.addWidget(log_title)
        log_controls.addStretch(1)
        log_controls.addWidget(clear_log_btn)
        log_controls.addWidget(save_log_btn)
        
        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Consolas', 10))
        
        logs_layout.addLayout(log_controls)
        logs_layout.addWidget(self.log_text)
        
        self.tab_widget.addTab(self.logs_tab, "Logs")
        
        # About tab
        self.about_tab = QWidget()
        about_layout = QVBoxLayout(self.about_tab)
        about_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_layout.setContentsMargins(40, 40, 40, 40)
        about_layout.setSpacing(15)
        
        # App logo - a placeholder gradient icon
        logo_frame = QFrame()
        logo_frame.setFixedSize(128, 128)
        
        # App info
        about_title = QLabel(APP_NAME)
        about_title.setFont(QFont('Segoe UI', 24, QFont.Weight.Bold))
        about_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        about_version = QLabel(f"Version {APP_VERSION}")
        about_version.setFont(QFont('Segoe UI', 14))
        about_version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Description with nice formatting
        about_desc = QLabel(
            "<p>A modern tool for browsing and downloading VRChat avatars and files.</p>"
            "<p>This application uses the unofficial VRChat API and provides an easy way "
            "to manage your avatar collection.</p>"
            "<p> Made by Lunar with ❤️ </p>"
        )
        about_desc.setWordWrap(True)
        about_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        about_desc.setFixedWidth(500)
        
        # GitHub button
        github_btn = AnimatedButton("Visit GitHub Repository", primary=True)
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/PrototypeX37/vrchat-avatar-manager")))
        
        about_layout.addWidget(logo_frame, alignment=Qt.AlignmentFlag.AlignCenter)
        about_layout.addWidget(about_title)
        about_layout.addWidget(about_version)
        about_layout.addSpacing(20)
        about_layout.addWidget(about_desc)
        about_layout.addSpacing(30)
        about_layout.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.tab_widget.addTab(self.about_tab, "About")
        
        # Add tab widget to content layout
        content_layout.addWidget(self.tab_widget)
        
        # Add header and content to main layout
        main_layout.addWidget(self.header)
        main_layout.addWidget(content_widget)
        
        # Set central widget
        self.setCentralWidget(main_widget)
        
        # Create log handler to show logs in the UI
        self.log_handler = LogHandler(self.log_text)
        logger.addHandler(self.log_handler)
        
        # Check login status on startup
        QTimer.singleShot(500, self.check_login_status)
    
    def update_theme(self):
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        # Main window
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {theme["background"]};
                color: {theme["text"]};
            }}
            QTabBar::tab {{
                background-color: {theme["surface"]};
                color: {theme["text_secondary"]};
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-width: 120px;
                padding: 10px;
                margin-right: 4px;
                border: none; /* Remove all borders */
            }}
            QTabBar::tab:selected {{
                background-color: {theme["primary"]};
                color: white;
            }}
            QTabWidget::tab-bar {{
                alignment: left;
                background-color: transparent;
                border: none;
            }}
            QTabBar {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea, QScrollBar {{
                background-color: {theme["background"]};
                border: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {theme["background"]};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {theme["inactive"]};
                border-radius: 5px;
                min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                border: none;
                background: none;
                height: 0px;
            }}
            QFrame {{
                background-color: {theme["surface"]};
                border-radius: 12px;
            }}
            QLabel {{
                background-color: transparent;
                color: {theme["text"]};
            }}
            QProgressBar {{
                border: none;
                background-color: {theme["surface"]};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {theme["primary"]};
                border-radius: 4px;
            }}
            QComboBox {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["divider"]};
                border-radius: 6px;
                padding: 5px 10px;
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: right;
                width: 15px;
                border-left: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {theme["card"]};
                color: {theme["text"]};
                border: 1px solid {theme["divider"]};
                selection-background-color: {theme["primary"]};
                selection-color: white;
            }}
            QTextEdit {{
                background-color: {theme["surface"]};
                color: {theme["text"]};
                border: 1px solid {theme["divider"]};
                border-radius: 6px;
                padding: 5px;
            }}
            QGroupBox {{
                background-color: {theme["surface"]};
                border: 1px solid {theme["divider"]};
                border-radius: 8px;
                font-weight: bold;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {theme["text"]};
            }}
        """)
        
        # Header styling
        header_bg_start = theme["primary"]
        header_bg_end = self._adjust_color(theme["primary"], -40 if is_dark_mode else 40)
        
        self.header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                            stop:0 {header_bg_start}, 
                                            stop:1 {header_bg_end});
                border-top-left-radius: 0;
                border-top-right-radius: 0;
                border-bottom-left-radius: 0;
                border-bottom-right-radius: 0;
            }}
            QLabel {{
                color: white;
                background: transparent;
            }}
        """)
        
        # Status indicator
        if self.api_client:
            self.status_icon.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
        else:
            self.status_icon.setStyleSheet("background-color: #ff5252; border-radius: 6px;")
        
        # Update widgets that have custom theme methods
        for widget in self.findChildren(QWidget):
            if hasattr(widget, 'setTheme') and callable(getattr(widget, 'setTheme')):
                widget.setTheme(is_dark_mode)
            elif hasattr(widget, 'update_theme') and callable(getattr(widget, 'update_theme')):
                widget.update_theme()
    
    def _adjust_color(self, color, amount):
        # Convert hex to RGB
        color = color.lstrip('#')
        r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        
        # Adjust based on amount (positive = lighten, negative = darken)
        if amount > 0:
            r = min(255, r + amount)
            g = min(255, g + amount)
            b = min(255, b + amount)
        else:
            r = max(0, r + amount)
            g = max(0, g + amount)
            b = max(0, b + amount)
        
        # Convert back to hex
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def toggle_theme(self, is_dark):
        global is_dark_mode
        is_dark_mode = is_dark
        
        # Update the UI
        self.update_theme()
        
        # Save the setting
        self.save_config()
        
        # Add a simple animation for theme transition
        fade = QGraphicsOpacityEffect(self.centralWidget())
        self.centralWidget().setGraphicsEffect(fade)
        
        # Fade out/in animation for smooth transition
        anim = QPropertyAnimation(fade, b"opacity")
        anim.setDuration(300)
        anim.setStartValue(0.7)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
    
    def save_log(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Log File",
            f"vrchat_manager_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Log Saved", f"Log has been saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save log: {str(e)}")
    
    def check_login_status(self):
        # If credentials are saved, try to login automatically
        if self.vrchat_username and self.vrchat_password:
            self.login_to_vrchat()
    
    def login_to_vrchat(self):
        # Show login dialog
        login_dialog = LoginDialog(self, self.vrchat_username, self.vrchat_password)
        if login_dialog.exec():
            credentials = login_dialog.get_credentials()
            username = credentials["username"]
            password = credentials["password"]
            
            # Save credentials if checked
            if credentials["save"]:
                self.vrchat_username = username
                self.vrchat_password = password
                self.save_config(username, password)
            
            # Show login in progress
            self.status_label.setText("Logging in...")
            theme = app_theme["dark" if is_dark_mode else "light"]
            self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
            self.login_btn.setEnabled(False)
            
            # Update progress
            self.avatars_progress.setVisible(True)
            self.avatars_progress.setRange(0, 0)
            
            # Login in background
            worker = Worker(self.login_worker, username, password)
            worker.signals.result.connect(self.handle_login_result)
            worker.signals.error.connect(self.handle_login_error)
            self.threadpool.start(worker)
    
    def login_worker(self, username, password):
        try:
            # Configure the API client
            configuration = vrchatapi.Configuration(
                username=username,
                password=password
            )
            # Create API client
            api_client = vrchatapi.ApiClient(configuration)
            # Set user agent as required by VRChat - MUST match exact format they expect
            api_client.user_agent = "SaveMyProjects/1.0.0 (none@gmial.com)"
            # Create authentication API instance
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
                    # For UI we need to signal back that 2FA is needed
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
        theme = app_theme["dark" if is_dark_mode else "light"]
        
        if result["success"]:
            # Login successful
            self.api_client = result["api_client"]
            user = result["user"]
            
            # Update status
            self.status_label.setText(f"Logged in: {user.display_name}")
            self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
            self.status_icon.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
            
            # Update UI
            self.avatars_status.setText("Ready to browse avatars")
            self.login_btn.setText("Switch User")
            
            # Fade in animation for status
            anim = QGraphicsOpacityEffect(self.status_label)
            self.status_label.setGraphicsEffect(anim)
            
            fade_anim = QPropertyAnimation(anim, b"opacity")
            fade_anim.setDuration(500)
            fade_anim.setStartValue(0.5)
            fade_anim.setEndValue(1.0)
            fade_anim.start()
            
            # Fetch avatars automatically
            self.fetch_avatars()
        elif result.get("need_2fa", False):
            # Need 2FA
            api_client = result["api_client"]
            auth_api = result["auth_api"]
            is_email = result.get("is_email", False)
            
            # Show 2FA dialog
            twofa_dialog = TwoFactorDialog(self, is_email)
            if twofa_dialog.exec():
                code = twofa_dialog.get_code()
                
                # Show verification in progress
                self.status_label.setText("Verifying 2FA...")
                self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
                self.avatars_progress.setVisible(True)
                self.login_btn.setEnabled(False)
                
                # Process 2FA in background
                worker = Worker(self.verify_2fa_worker, auth_api, code, is_email)
                worker.signals.result.connect(self.handle_2fa_result)
                worker.signals.error.connect(self.handle_login_error)
                self.threadpool.start(worker)
                
                # Store API client for later use
                self.temp_api_client = api_client
            else:
                self.status_label.setText("2FA canceled")
                self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
        else:
            # Login failed
            error = result.get("error", "Unknown error")
            self.status_label.setText("Login failed")
            self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
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
            
            # After 2FA verification, get current user
            current_user = auth_api.get_current_user()
            logger.info(f"Successfully logged in with 2FA as: {current_user.display_name}")
            
            return {
                "success": True,
                "user": current_user
            }
        except ApiException as e:
            logger.error(f"2FA verification failed: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def handle_2fa_result(self, result):
        self.login_btn.setEnabled(True)
        self.avatars_progress.setVisible(False)
        
        if result["success"]:
            # 2FA successful
            self.api_client = self.temp_api_client
            user = result["user"]
            
            # Update status
            self.status_label.setText(f"Logged in: {user.display_name}")
            self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
            self.status_icon.setStyleSheet("background-color: #4CAF50; border-radius: 6px;")
            
            # Update UI
            self.avatars_status.setText("Ready to browse avatars")
            self.login_btn.setText("Switch User")
            
            # Fetch avatars automatically
            self.fetch_avatars()
        else:
            # 2FA failed
            error = result.get("error", "Unknown error")
            self.status_label.setText("2FA verification failed")
            self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
            QMessageBox.critical(self, "Authentication Error", f"2FA verification failed: {error}")
    
    def handle_login_error(self, error):
        self.login_btn.setEnabled(True)
        self.avatars_progress.setVisible(False)
        self.status_label.setText("Login failed")
        self.status_label.setStyleSheet(f"color: white; font-weight: bold;")
        QMessageBox.critical(self, "Login Error", f"An unexpected error occurred: {error}")
    
    def fetch_avatars(self):
        if not self.api_client:
            QMessageBox.warning(self, "Not Logged In", "Please login to browse avatars")
            return
        
        # Reset pagination
        self.current_page = 1
        self.pagination.current_page = 1
        self.pagination.update_ui()
        
        # Update UI
        self.avatars_status.setText("Fetching avatars...")
        self.avatars_progress.setVisible(True)
        self.avatars_progress.setRange(0, 0)  # Indeterminate progress
        
        # Determine filter type
        filter_index = self.filter_combo.currentIndex()
        filter_type = ["all", "Public Avatars", "Private Avatars"][min(filter_index, 2)]
        
        # Fetch avatars in background
        worker = Worker(self.fetch_avatars_worker, filter_type)
        worker.signals.result.connect(self.handle_avatars_result)
        worker.signals.error.connect(self.handle_avatars_error)
        self.threadpool.start(worker)
    
    def fetch_avatars_worker(self, filter_type):
        try:
            # We'll use direct requests instead of the SDK
            # Get authentication cookies from the API client
            cookies = {}
            if self.api_client:
                for cookie in self.api_client.rest_client.cookie_jar:
                    cookies[cookie.name] = cookie.value
            
            # Set up headers
            headers = {
                "User-Agent": self.api_client.user_agent,
                "Accept": "application/json"
            }
            
            all_avatars = []
            offset = 0
            page_size = 100  # Fetch more at once for efficiency
            
            # Loop to fetch multiple pages
            max_pages = 10
            for page in range(max_pages):
                # Set parameters based on filter type
                params = {
                    "n": page_size,
                    "offset": offset,
                    "releaseStatus": "all"
                }
                
                if filter_type == "Private Avatars":
                    params["releaseStatus"] = "private"
                    params["sort"] = "updated"
                    params["order"] = "descending"
                elif filter_type == "Public Avatars":
                    params["sort"] = "updated"
                    params["order"] = "descending"
                    params["releaseStatus"] = "public"
                else:
                    # Default for "all avatars"
                    params["releaseStatus"] = "all"
                
                # Make direct API call to VRChat
                logger.info(f"Fetching avatars page {page+1} with params: {params}")
                response = requests.get(
                    "https://api.vrchat.cloud/api/1/avatars",
                    params=params,
                    headers=headers,
                    cookies=cookies
                )
                
                if response.status_code != 200:
                    logger.error(f"API error: {response.status_code} - {response.text[:200]}")
                    raise Exception(f"API error: {response.status_code}")
                
                # Parse JSON response
                avatars = response.json()
                
                # Log response
                logger.info(f"Received {len(avatars)} avatars in page {page+1}")
                
                # Check if we got any results
                if not avatars:
                    logger.info(f"No more avatars found on page {page+1}, stopping pagination")
                    break
                
                # Add to collection
                all_avatars.extend(avatars)
                
                # Break if we got fewer results than requested (last page)
                if len(avatars) < page_size:
                    logger.info(f"Received fewer than {page_size} avatars, this is the last page")
                    break
                
                # Update offset for next page
                offset += page_size
            
            logger.info(f"Fetched a total of {len(all_avatars)} avatars")
            return all_avatars
            
        except Exception as e:
            logger.error(f"Error fetching avatars: {e}")
            traceback.print_exc()
            raise
            
    def handle_avatars_result(self, avatars):
        # Update UI
        self.avatars_progress.setVisible(False)
        self.avatars_status.setText(f"Found {len(avatars)} avatars")
        
        # Store avatars data
        self.avatars_data = avatars
        
        # Set pagination
        self.pagination.set_page_count(len(avatars))
        self.items_per_page = self.pagination.items_per_page
        
        # Apply any current filter
        self.filter_avatars()
    
    def handle_avatars_error(self, error):
        # Update UI
        self.avatars_progress.setVisible(False)
        self.avatars_status.setText(f"Error: {error}")
        QMessageBox.critical(self, "Avatar Fetch Error", str(error))
    
    def filter_avatars(self):
        # Get filter text
        filter_text = self.search_input.text().lower()
        
        # Filter avatars from the ENTIRE dataset
        if filter_text:
            self.filtered_avatars = []
            for avatar in self.avatars_data:  # Use full dataset
                if (filter_text in avatar.get('name', '').lower() or 
                    filter_text in avatar.get('authorName', '').lower() or 
                    filter_text in avatar.get('description', '').lower()):
                    self.filtered_avatars.append(avatar)
            
            # Update status
            self.avatars_status.setText(f"Found {len(self.filtered_avatars)} of {len(self.avatars_data)} avatars matching '{filter_text}'")
        else:
            # No filter, use all avatars
            self.filtered_avatars = self.avatars_data
            self.avatars_status.setText(f"Showing all {len(self.avatars_data)} avatars")
        
        # Reset to page 1 when filtering
        self.current_page = 1
        self.pagination.current_page = 1
        self.pagination.update_ui()
        
        # Update pagination for filtered results
        self.pagination.set_page_count(len(self.filtered_avatars))
        
        # Display the current page
        self.display_current_page()
    

    def change_page(self, page_num):
        self.current_page = page_num
        
        # Get the current items_per_page from pagination widget
        self.items_per_page = self.pagination.items_per_page
        
        # Recalculate pagination
        if self.filtered_avatars:
            self.pagination.set_page_count(len(self.filtered_avatars))
            
        # Display the current page
        self.display_current_page()
        
        
    def display_avatars_anti_ghost(self, avatars):
        """Display avatars with ghost prevention techniques"""
        if not avatars:
            return
            
        # Calculate columns based on fixed width
        container_width = self.scroll_area.viewport().width() - 30
        cols = max(3, min(4, container_width // 340))
        
        # Calculate required height
        rows = (len(avatars) + cols - 1) // cols
        total_height = rows * 360
        
        # Set fixed container size
        self.avatar_container.setFixedHeight(total_height)
        
        # Temporarily suspend layout updates
        self.avatar_container.setUpdatesEnabled(False)
        
        # Create cards with anti-ghosting properties
        for i, avatar in enumerate(avatars):
            row = i // cols
            col = i % cols
            
            # Create the card with ghost-resistant settings
            card = AvatarCard(avatar, self.api_client)
            card.downloadRequested.connect(self.download_avatar)
            card.setFixedSize(300, 340)
            
            # Anti-ghost settings
            card.setAutoFillBackground(True)
            
            # The crucial part: add each card as a completely opaque entity
            theme = app_theme["dark" if is_dark_mode else "light"]
            card.setStyleSheet(f"""
                AvatarCard {{
                    background-color: {theme["card"]};
                    border-radius: 12px;
                    border: 1px solid {theme["divider"]};
                }}
            """)
            
            # Add to grid
            self.avatar_grid.addWidget(card, row, col)
        
        # Re-enable updates
        self.avatar_container.setUpdatesEnabled(True)
        
    

    def display_current_page(self):
        """Display the current page of avatars with simpler approach"""
        # Clear current grid using reliable technique
        self.clear_avatar_grid()
        
        # Get avatars for current page
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.filtered_avatars))
        current_page_avatars = self.filtered_avatars[start_idx:end_idx]
        
        # Update status text
        if self.filtered_avatars:
            self.avatars_status.setText(
                f"Showing avatars {start_idx+1}-{end_idx} of {len(self.filtered_avatars)}"
            )
        else:
            self.avatars_status.setText("No avatars found matching your search")
        
        # Use simpler display function that we know works
        self.display_avatars(current_page_avatars)
    


    def clear_avatar_grid(self):
        """Completely remove all widgets from the grid"""
        # Process any pending events first
        QApplication.processEvents()
        
        # Clear the grid layout
        while self.avatar_grid.count():
            item = self.avatar_grid.takeAt(0)
            if item and item.widget():
                widget = item.widget()
                # Remove any effects
                widget.setGraphicsEffect(None)
                # Delete the widget
                widget.deleteLater()
        
        # Process delete events immediately
        QApplication.processEvents()
                
    def showEvent(self, event):
        """Handle window show event"""
        super().showEvent(event)
        
        # This helps ensure the scroll area is properly initialized
        QTimer.singleShot(200, lambda: self.scroll_area.setWidgetResizable(True))
        QTimer.singleShot(300, self.fix_scroll_behavior)
        


    def setup_anti_flicker(self):
        """Configure optimizations to prevent flickering during scrolling"""
        # Set scroll mode to avoid flickering 
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Set widget attributes to reduce flickering
        self.avatar_container.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.avatar_container.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        
        # Connect scroll events for smoother scrolling
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.valueChanged.connect(self.on_scroll_start)
        
        # Store state for scroll optimization 
        self.is_scrolling = False
        self.scroll_timer = QTimer(self)
        self.scroll_timer.setSingleShot(True)
        self.scroll_timer.timeout.connect(self.on_scroll_end)

    def on_scroll_start(self, value):
        """Optimize rendering during active scrolling"""
        # Set scrolling state
        self.is_scrolling = True
        
        # Reset timer on each scroll event
        if hasattr(self, 'scroll_timer'):
            self.scroll_timer.stop()
            self.scroll_timer.start(200)
        
        # Temporarily reduce rendering quality during scrolling
        # Instead of removing effects, we'll reduce card details
        if not self.avatar_container.property("simplifiedForScrolling"):
            self.avatar_container.setProperty("simplifiedForScrolling", True)
            
            # Apply simplified rendering to visible cards
            for i in range(self.avatar_grid.count()):
                item = self.avatar_grid.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    # Apply a simpler style during scrolling
                    card.setStyleSheet(card.styleSheet() + "\nbackground-color: rgba(45, 45, 68, 1.0);")
                    # Just hide fancy elements instead of removing effects
                    if hasattr(card, 'setScrollingMode'):
                        card.setScrollingMode(True)

    def on_scroll_end(self):
        """Restore full rendering quality after scrolling stops"""
        self.is_scrolling = False
        
        # Restore normal rendering
        if self.avatar_container.property("simplifiedForScrolling"):
            self.avatar_container.setProperty("simplifiedForScrolling", False)
            
            # Restore normal appearance
            for i in range(self.avatar_grid.count()):
                item = self.avatar_grid.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    # Update style
                    theme = app_theme["dark" if is_dark_mode else "light"]
                    card.setStyleSheet(f"""
                        AvatarCard {{
                            background-color: {theme["card"]};
                            border-radius: 12px;
                            border: 1px solid {theme["divider"]};
                        }}
                        QLabel {{
                            background-color: transparent;
                            color: {theme["text"]};
                        }}
                    """)
                    # Restore fancy elements
                    if hasattr(card, 'setScrollingMode'):
                        card.setScrollingMode(False)
        
                
    
    def display_avatars(self, avatars):
        # Calculate columns based on available width
        container_width = self.scroll_area.viewport().width() - 30
        
        # Use a fixed number of columns for consistency
        cols = max(3, min(4, container_width // 340))
        
        # Calculate total height required
        rows = (len(avatars) + cols - 1) // cols  # Ceiling division
        total_height = rows * 360  # 340 for card + 20 for spacing
        
        # Set container height
        self.avatar_container.setMinimumHeight(total_height)
        
        # Display avatars in grid
        for i, avatar in enumerate(avatars):
            row = i // cols
            col = i % cols
            
            card = AvatarCard(avatar, self.api_client)
            card.downloadRequested.connect(self.download_avatar)
            card.setFixedSize(300, 340)
            
            # Add to grid
            self.avatar_grid.addWidget(card, row, col)
        
        # Apply scroll behavior fixes but nothing else
        QTimer.singleShot(100, self.fix_scroll_behavior)
    
    def download_avatar(self, avatar_data):
        """Download an avatar based on the avatar data"""
        # Log details for debugging
        logger.info(f"Attempting to download avatar: {avatar_data.get('name', 'Unknown')}")
        logger.info(f"Avatar ID: {avatar_data.get('id', 'Unknown')}")
        
        # Get the avatar ID
        avatar_id = avatar_data.get('id')
        if not avatar_id:
            logger.error("Avatar ID not found in data")
            QMessageBox.warning(self, "Error", "Avatar ID not found")
            return
        
        # Show download progress
        self.avatars_progress.setVisible(True)
        self.avatars_progress.setRange(0, 0)
        self.avatars_status.setText("Fetching detailed avatar information...")
        
        # Fetch detailed avatar in background
        worker = Worker(self.fetch_detailed_avatar, avatar_id)
        worker.signals.result.connect(lambda result: self.continue_avatar_download(result, avatar_data))
        worker.signals.error.connect(self.handle_avatar_download_error)
        self.threadpool.start(worker)
    
    def continue_avatar_download(self, detailed_avatar, original_avatar):
        # Hide progress
        self.avatars_progress.setVisible(False)
        
        if not detailed_avatar:
            logger.error(f"Could not fetch detailed avatar information")
            QMessageBox.warning(
                self, 
                "Download Error", 
                "Could not fetch detailed avatar information. Please try again."
            )
            return
        
        # Now use the detailed avatar data which contains download URLs
        avatar_data = detailed_avatar
        
        # Debug info
        logger.info(f"Got detailed avatar data with keys: {list(avatar_data.keys())}")
        
        # Find the best download URL
        download_url = None
        file_ext = ".vrca"  # Default to .vrca as requested
        
        # Check unityPackages array (this is where most download URLs are)
        if 'unityPackages' in avatar_data and avatar_data['unityPackages']:
            packages = avatar_data['unityPackages']
            logger.info(f"Found {len(packages)} unity packages")
            
            # Log all available platforms for debugging
            platforms = [pkg.get('platform', 'unknown') for pkg in packages]
            logger.info(f"Available platforms: {platforms}")
            
            # PRIORITY 1: Look specifically for standalonewindows platform
            windows_packages = [pkg for pkg in packages if pkg.get('platform') == 'standalonewindows']
            if windows_packages:
                windows_pkg = windows_packages[0]
                if 'assetUrl' in windows_pkg and windows_pkg['assetUrl']:
                    download_url = windows_pkg['assetUrl']
                    logger.info(f"Found standalonewindows package URL: {download_url}")
                else:
                    logger.info("Windows package found but no assetUrl available")
            else:
                logger.info("No standalonewindows platform package found")
                
            # PRIORITY 2: If still no URL, check any package with an assetUrl
            if not download_url:
                for package in packages:
                    if 'assetUrl' in package and package['assetUrl']:
                        platform = package.get('platform', 'unknown')
                        download_url = package['assetUrl']
                        logger.info(f"Using {platform} package URL as fallback: {download_url}")
                        break
        else:
            logger.info("No unityPackages found in avatar data")
        
        # PRIORITY 3: Check top-level assetUrl (fallback for older avatars)
        if not download_url and 'assetUrl' in avatar_data and avatar_data['assetUrl']:
            download_url = avatar_data['assetUrl']
            logger.info(f"Using top-level assetUrl as last resort: {download_url}")
        
        # If we still don't have a URL, show error
        if not download_url:
            logger.error("No download URL found for this avatar")
            QMessageBox.warning(
                self,
                "Download Error",
                "No downloadable file URL found for this avatar. You may not have permission to download it."
            )
            return
        
        # Remove '/variant/security' from the URL if present
        if '/variant/security' in download_url:
            download_url = download_url.split('/variant/security')[0]
            logger.info(f"Fixed URL by removing variant/security: {download_url}")
        
        # Sanitize avatar name for filename
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', avatar_data.get('name', 'avatar'))
        default_filename = f"{safe_name}{file_ext}"
        
        # Ask user where to save the file
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Avatar File",
            default_filename,
            f"Avatar Files (*{file_ext})"
        )
        
        if not file_path:
            logger.info("Download canceled by user")
            return
        
        # Switch to the downloader tab and populate fields
        self.tab_widget.setCurrentIndex(1)  # Switch to downloader tab
        self.file_url_input.setText(download_url)
        self.file_output_input.setText(file_path)
        
        # Start the download
        QTimer.singleShot(300, self.download_file)  # Short delay for better UX
    
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
        
        # Get authentication cookies
        cookies = {}
        for cookie in self.api_client.rest_client.cookie_jar:
            cookies[cookie.name] = cookie.value
        
        headers = {
            "User-Agent": self.api_client.user_agent,
            "Accept": "application/json"
        }
        
        # Make direct API call to get detailed avatar info
        url = f"https://api.vrchat.cloud/api/1/avatars/{avatar_id}"
        logger.info(f"Making API request to: {url}")
        
        try:
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies
            )
            
            if response.status_code == 200:
                avatar_data = response.json()
                logger.info(f"Successfully fetched detailed avatar data")
                return avatar_data
            else:
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
            "",
            "All Files (*.*)"
        )
        
        if file_path:
            self.file_output_input.setText(file_path)
            
    def handle_avatars_result(self, avatars):
        # Update UI
        self.avatars_progress.setVisible(False)
        self.avatars_status.setText(f"Found {len(avatars)} avatars")
        
        # Store avatars data
        self.avatars_data = avatars
        
        # Set pagination
        self.pagination.set_page_count(len(avatars))
        self.items_per_page = self.pagination.items_per_page
        
        # Apply any current filter
        self.filter_avatars()
        
        # Add a slight delay before refreshing to ensure layout is ready
        QTimer.singleShot(300, self.refresh_avatar_panels)
            
            
    def refresh_avatar_panels(self):
        """Force a complete refresh of the current page of avatars"""
        if hasattr(self, 'filtered_avatars') and self.filtered_avatars:
            # This will completely clear and redisplay the avatars
            current_page = self.current_page
            
            # First clear everything
            self.clear_avatar_grid()
            
            # Then re-display with the same pagination state
            start_idx = (current_page - 1) * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.filtered_avatars))
            current_page_avatars = self.filtered_avatars[start_idx:end_idx]
            
            # Update status text
            if self.filtered_avatars:
                self.avatars_status.setText(
                    f"Showing avatars {start_idx+1}-{end_idx} of {len(self.filtered_avatars)}"
                )
            
            # Display avatars with fresh layout calculations
            self.display_avatars(current_page_avatars)
            logger.info("Avatar panels refreshed completely")
            
    def update_download_progress(self, percent, message=""):
        self.file_progress.setValue(percent)
        if message:
            self.file_status.setText(message)
    
    def download_file(self):
        if not self.api_client:
            QMessageBox.warning(self, "Not Logged In", "Please login to download files")
            return
        
        file_url = self.file_url_input.text().strip()
        output_path = self.file_output_input.text().strip()
        
        if not file_url:
            QMessageBox.warning(self, "Missing URL", "Please enter a VRChat file URL")
            return
        
        # Update UI
        self.file_status.setText("Downloading file...")
        self.file_progress.setVisible(True)
        self.file_progress.setRange(0, 100)
        self.file_progress.setValue(0)
        self.download_btn.setEnabled(False)
        
        # Store worker as instance attribute so it can be accessed in download_file_worker
        self.worker = Worker(self.download_file_worker, file_url, output_path)
        self.worker.signals.result.connect(self.handle_download_result)
        self.worker.signals.error.connect(self.handle_download_error)
        self.worker.signals.progress.connect(self.update_download_progress)
        self.threadpool.start(self.worker)
    
    def download_file_worker(self, file_url, output_path):
        try:
            logger.info(f"Starting download from URL: {file_url}")
            
            # Fix URL - remove variant/security at the end if present
            if '/variant/security' in file_url:
                file_url = file_url.split('/variant/security')[0]
                logger.info(f"Fixed URL by removing variant/security: {file_url}")
            
            # Get cookies from API client
            cookies = {}
            if self.api_client:
                for cookie in self.api_client.rest_client.cookie_jar:
                    cookies[cookie.name] = cookie.value
            
            # Log cookies for debugging (without values for security)
            logger.info(f"Using authentication cookies: {list(cookies.keys())}")
            
            # Set up headers with proper auth
            headers = {
                "User-Agent": self.api_client.user_agent,
                "Accept": "*/*"  # Accept any content type
            }
            
            # Make the download request with proper authentication
            logger.info(f"Sending authenticated request to: {file_url}")
            response = requests.get(
                file_url,
                headers=headers,
                cookies=cookies,
                stream=True  # Stream for large files
            )
            
        
            # Verify response
            if response.status_code != 200:
                logger.error(f"Download failed with status {response.status_code}")
                logger.error(f"Response headers: {dict(response.headers)}")
                logger.error(f"Response content: {response.text[:200]}")
                raise Exception(f"Download failed with status {response.status_code}")
            
            # Get content length for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            logger.info(f"Download size: {total_size} bytes")
            
            # Save the file with progress updates
            downloaded = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress
                        if total_size > 0:
                            percent = int(downloaded * 100 / total_size)
                            # Only update UI every 1% to prevent too many updates
                            if percent % 1 == 0:
                                self.worker.signals.progress.emit(
                                    percent, 
                                    f"Downloading file... {downloaded/(1024*1024):.1f} MB / {total_size/(1024*1024):.1f} MB ({percent}%)"
                                )
                                
                        # Log progress for large files
                        if total_size > 1000000 and downloaded % 5000000 == 0:  # Every 5MB
                            percent = int(downloaded * 100 / total_size) if total_size > 0 else 0
                            logger.info(f"Download progress: {percent}% ({downloaded}/{total_size} bytes)")
            
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
        # Update UI
        self.file_progress.setVisible(False)
        self.download_btn.setEnabled(True)
        
        if result["success"]:
            self.file_status.setText(f"File downloaded successfully to: {result['path']}")
            
            # Create a success animation
            theme = app_theme["dark" if is_dark_mode else "light"]
            self.file_status.setStyleSheet(f"color: {theme['success']}; font-weight: bold;")
            
            # Show completion dialog
            QMessageBox.information(
                self, 
                "Download Complete", 
                f"File has been downloaded to:\n{result['path']}"
            )
        else:
            self.file_status.setText("Download failed")
            self.file_status.setStyleSheet(f"color: {theme['error']}; font-weight: bold;")
    
    def handle_download_error(self, error):
        # Update UI
        self.file_progress.setVisible(False)
        self.download_btn.setEnabled(True)
        
        theme = app_theme["dark" if is_dark_mode else "light"]
        self.file_status.setText(f"Error: {error}")
        self.file_status.setStyleSheet(f"color: {theme['error']}; font-weight: bold;")
        
        QMessageBox.critical(self, "Download Error", str(error))

# Custom log handler to display logs in the UI
class LogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
    def emit(self, record):
        msg = self.format(record)
        
        # Add color based on log level
        color = {
            logging.DEBUG: "#6c757d",    # Gray
            logging.INFO: "#0d6efd",     # Blue
            logging.WARNING: "#fd7e14",  # Orange
            logging.ERROR: "#dc3545",    # Red
            logging.CRITICAL: "#7f0000"  # Dark red
        }.get(record.levelno, "#212529")
        
        # Add to text widget
        self.text_widget.append(f'<span style="color:{color}">{msg}</span>')
        
        # Auto-scroll to bottom
        self.text_widget.verticalScrollBar().setValue(
            self.text_widget.verticalScrollBar().maximum()
        )

def main():
    # Ensure data directory exists
    os.makedirs(DATA_FOLDER, exist_ok=True)
    
    # Create application
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # Set modern font
    font_id = QFontDatabase.addApplicationFont(":/fonts/segoe-ui.ttf")
    if font_id != -1:
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        app.setFont(QFont(font_family, 10))
    else:
        app.setFont(QFont("Segoe UI", 10))
    
    # Create splash screen
    splash_pixmap = QPixmap(600, 350)
    painter = QPainter(splash_pixmap)
    
    # Create a gradient background
    gradient = QLinearGradient(0, 0, 600, 350)
    gradient.setColorAt(0, QColor("#6C5CE7"))  # Purple
    gradient.setColorAt(1, QColor("#00CECE"))  # Teal
    painter.fillRect(0, 0, 600, 350, gradient)
    
    # Add app name
    painter.setPen(QColor("white"))
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRect(0, 120, 600, 50), Qt.AlignmentFlag.AlignCenter, APP_NAME)
    
    # Add version
    font = QFont("Segoe UI", 14)
    painter.setFont(font)
    painter.drawText(QRect(0, 180, 600, 30), Qt.AlignmentFlag.AlignCenter, f"Version {APP_VERSION}")
    
    # Add loading text
    font = QFont("Segoe UI", 12)
    painter.setFont(font)
    painter.drawText(QRect(0, 280, 600, 30), Qt.AlignmentFlag.AlignCenter, "Loading...")
    
    painter.end()
    
    splash = QSplashScreen(splash_pixmap)
    splash.show()
    app.processEvents()
    
    # Create and show main window
    window = VRChatManager()
    
    # Close splash and show main window
    splash.finish(window)
    window.show()
    
    # Refresh avatar panels after window is shown
    QTimer.singleShot(300, window.refresh_avatar_panels)
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    # Make global theme and mode variable accessible to all classes
    app_theme = THEME
    is_dark_mode = True
    main()
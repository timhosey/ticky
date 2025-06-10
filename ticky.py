import sys
import webbrowser
import feedparser
import requests
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QLabel, QWidget, QGraphicsOpacityEffect, QMenu, QSystemTrayIcon,
    QVBoxLayout, QPushButton, QComboBox, QSpinBox, QColorDialog, QCheckBox, QLabel as QtLabel, QHBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation
from PyQt6.QtGui import QFont, QMouseEvent, QFontDatabase, QAction, QIcon

class RssTicker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(100, 100, 800, 50)
        # self.setStyleSheet("background-color: black;")

        self.drag_pos = None
        self.dragging = False
        self.feed_urls = []
        self.load_feeds_from_file()

        # Add a QFrame to contain the label and apply border/background to it
        self.frame = QFrame(self)
        self.frame.setGeometry(self.rect())
        self.frame.setStyleSheet("background-color: black; border: 2px solid lime;")
        self.frame.lower()  # make sure it stays behind other widgets

        self.label = QLabel(self.frame)
        self.overlay_label = QLabel("Ticky", self)
        self.overlay_label.setFont(QFont("Courier", 12, QFont.Weight.Bold))
        self.overlay_label.setStyleSheet("color: lime; background-color: transparent;")
        self.overlay_label.setGeometry(10, 5, 100, 20)
        self.overlay_label.hide()
        # Attempt to load bundled digital font
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "PressStart2P.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            digital_font = QFont(font_family, 24)
            print(f"Loaded bundled font: {font_family}")
        else:
            print("Bundled digital font not found or failed to load, falling back to Courier")
            digital_font = QFont("Courier", 20)
        self.label.setFont(digital_font)
        self.label.setStyleSheet("color: lime; background-color: transparent; border: none; padding: 0px;")
        self.label.setGeometry(0, 0, 2000, 50)  # super wide, so text can scroll

        # Opacity effect and fade-in animation
        self.opacity_effect = QGraphicsOpacityEffect(self.label)
        self.label.setGraphicsEffect(self.opacity_effect)
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(500)  # milliseconds

        self.headlines = []
        self.current_index = 0
        self.x_pos = self.width()

        self.fetch_feeds()

        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.scroll_text)
        self.scroll_timer.start(30)  # smaller = faster

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.fetch_feeds)
        self.refresh_timer.start(600000)  # refresh every 10 min

        self.settings_window = SettingsWindow(self)

        # Load and apply settings.json on startup
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                print("Applying saved settings on startup.")
                self.apply_settings(settings)
            except Exception as e:
                print(f"Error applying settings.json on startup: {e}")

        assets_dir = os.path.join(os.path.dirname(__file__), "assets")
        if not os.path.exists(assets_dir):
            try:
                os.makedirs(assets_dir)
                print("Created assets/ directory.")
            except Exception as e:
                print(f"Error creating assets/: {e}")

        icon_path = os.path.join(assets_dir, "icon.png")
        if os.path.exists(icon_path):
            self.tray_icon = QSystemTrayIcon(QIcon(icon_path))
            print("Loaded tray icon from assets/icon.png")
        else:
            self.tray_icon = QSystemTrayIcon(QIcon())
            print("Tray icon not found, using default icon.")
        self.tray_icon.setToolTip("RSS Ticker")

        tray_menu = QMenu()
        show_action = QAction("Show Ticker", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        settings_action = QAction("Open Settings", self)
        settings_action.triggered.connect(self.open_settings)
        tray_menu.addAction(settings_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(exit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def load_feeds_from_file(self):
        import os
        default_feeds = [
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://feeds.bbci.co.uk/news/rss.xml"
        ]
        if not os.path.exists('feeds.txt'):
            try:
                with open('feeds.txt', 'w') as f:
                    f.write("# Add your RSS feed URLs below. Lines starting with '#' are ignored.\n")
                    for url in default_feeds:
                        f.write(url + "\n")
                print("Created default feeds.txt")
            except Exception as e:
                print(f"Error creating feeds.txt: {e}")
                self.feed_urls = default_feeds
                return

        try:
            with open('feeds.txt', 'r') as f:
                self.feed_urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            print(f"Loaded {len(self.feed_urls)} feeds from feeds.txt")
        except Exception as e:
            print(f"Error loading feeds.txt: {e}")
            self.feed_urls = default_feeds

    def fetch_feeds(self):
        print("Fetching feeds...")
        self.headlines.clear()
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; RSS-Ticker/1.0; +https://example.com)"
        }

        for url in self.feed_urls:
            try:
                print(f"Fetching: {url}")
                resp = requests.get(url, headers=headers, timeout=10)
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)

                for entry in feed.entries:
                    headline = f"{entry.title}     "
                    link = entry.link
                    self.headlines.append((headline, link))

            except Exception as e:
                print(f"Error fetching {url}: {e}")

        if not self.headlines:
            self.headlines.append(("No headlines available", ""))

        self.current_index = 0
        self.update_label()

    def update_label(self):
        headline_text, _ = self.headlines[self.current_index]
        frame_padding = 5
        self.label.setText(headline_text)
        self.label.adjustSize()
        self.label.setGeometry(frame_padding, frame_padding, self.label.width(), self.frame.height() - 2 * frame_padding)
        self.x_pos = self.frame.width()
        self.label.move(self.x_pos, frame_padding)

        # Fade-in animation
        self.fade_anim.stop()
        self.opacity_effect.setOpacity(0.0)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.start()

    def scroll_text(self):
        self.x_pos -= 2  # pixels per frame
        self.label.move(self.x_pos, 5)

        if self.x_pos + self.label.width() < 0:
            self.current_index = (self.current_index + 1) % len(self.headlines)
            self.update_label()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            # Show context menu
            menu = QMenu(self)
            open_link_action = QAction("Open Current Link", self)
            open_link_action.triggered.connect(self.open_current_link)
            open_settings_action = QAction("Open Settings", self)
            open_settings_action.triggered.connect(self.open_settings)

            menu.addAction(open_link_action)
            menu.addAction(open_settings_action)

            exit_action = QAction("Exit", self)
            exit_action.triggered.connect(QApplication.quit)
            menu.addAction(exit_action)

            menu.exec(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging and self.drag_pos:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            event.accept()

    def open_current_link(self):
        _, link = self.headlines[self.current_index]
        if link:
            webbrowser.open(link)

    def open_settings(self):
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def apply_settings(self, settings):
        # Update font
        font_path = os.path.join(os.path.dirname(__file__), "fonts", settings["font_name"])
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            new_font = QFont(font_family, settings["font_size"])
            print(f"Applying font: {font_family}, size {settings['font_size']}")
            self.label.setFont(new_font)

        # Apply window style (background + border) to self.frame
        window_style = f"background-color: {settings.get('background_color', '#000000')};"
        if settings.get("show_border", False):
            window_style += f" border: {settings.get('border_thickness', 1)}px solid {settings.get('border_color', '#00FF00')};"
        else:
            window_style += " border: none;"
        if settings.get("use_rounded_corners", False):
          window_style += f" border-radius: {settings.get('border_radius', 10)}px;"
        self.frame.setStyleSheet(window_style)

        # Ensure overlay label stays floating and clean
        self.overlay_label.setStyleSheet("color: lime; background-color: transparent; border: none;")

        # Apply label style (font color, transparent background, no border or padding)
        label_style = f"color: {settings.get('font_color', '#00FF00')}; background-color: transparent; border: none; padding: 0px;"
        self.label.setStyleSheet(label_style)

        # Show/hide overlay
        if settings.get("show_overlay_text", False):
            self.overlay_label.show()
        else:
            self.overlay_label.hide()

class SettingsWindow(QWidget):
    def __init__(self, parent_ticker):
        super().__init__()
        self.parent_ticker = parent_ticker
        self.setWindowTitle("RSS Ticker Settings")
        self.setGeometry(200, 200, 400, 400)
        self.setStyleSheet("background-color: black; color: lime;")

        layout = QVBoxLayout()

        # Font selector
        self.font_dropdown = QComboBox()
        self.populate_fonts()
        layout.addWidget(QtLabel("Font:"))
        layout.addWidget(self.font_dropdown)

        # Font size
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 72)
        self.font_size_spin.setValue(24)
        layout.addWidget(QtLabel("Font Size:"))
        layout.addWidget(self.font_size_spin)

        # Font color
        self.font_color_button = QPushButton("Choose Font Color")
        self.font_color_button.clicked.connect(self.choose_font_color)
        layout.addWidget(self.font_color_button)

        # Background color
        self.bg_color_button = QPushButton("Choose Background Color")
        self.bg_color_button.clicked.connect(self.choose_bg_color)
        layout.addWidget(self.bg_color_button)

        # Border settings
        self.border_checkbox = QCheckBox("Show Border")
        layout.addWidget(self.border_checkbox)

        self.border_thickness_spin = QSpinBox()
        self.border_thickness_spin.setRange(0, 20)
        self.border_thickness_spin.setValue(1)
        layout.addWidget(QtLabel("Border Thickness:"))
        layout.addWidget(self.border_thickness_spin)

        self.border_color_button = QPushButton("Choose Border Color")
        self.border_color_button.clicked.connect(self.choose_border_color)
        layout.addWidget(self.border_color_button)

        # Rounded corners
        self.border_radius_checkbox = QCheckBox("Rounded Corners")
        layout.addWidget(self.border_radius_checkbox)

        self.border_radius_spin = QSpinBox()
        self.border_radius_spin.setRange(0, 50)
        self.border_radius_spin.setValue(10)
        layout.addWidget(QtLabel("Corner Radius:"))
        layout.addWidget(self.border_radius_spin)

        # Overlay text option
        self.overlay_text_checkbox = QCheckBox('Show "Ticky" Overlay Text')
        layout.addWidget(self.overlay_text_checkbox)

        # Save & Close button
        self.save_close_button = QPushButton("Save & Close")
        self.save_close_button.clicked.connect(self.save_and_close)
        layout.addWidget(self.save_close_button)

        self.setLayout(layout)

        self.font_color = "#00FF00"
        self.background_color = "#000000"
        self.border_color = "#00FF00"

        self.load_settings()

    def populate_fonts(self):
        fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
        if not os.path.exists(fonts_dir):
            os.makedirs(fonts_dir)

        fonts = [f for f in os.listdir(fonts_dir) if f.lower().endswith(".ttf")]
        self.font_dropdown.clear()
        self.font_dropdown.addItems(fonts)

    def choose_font_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.font_color = color.name()
            print(f"Selected font color: {self.font_color}")

    def choose_bg_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.background_color = color.name()
            print(f"Selected background color: {self.background_color}")

    def choose_border_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.border_color = color.name()
            print(f"Selected border color: {self.border_color}")

    def load_settings(self):
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        if not os.path.exists(settings_path):
            return  # No settings yet

        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            font_name = settings.get("font_name", "")
            index = self.font_dropdown.findText(font_name)
            if index != -1:
                self.font_dropdown.setCurrentIndex(index)

            self.font_size_spin.setValue(settings.get("font_size", 24))
            self.border_checkbox.setChecked(settings.get("show_border", False))
            self.border_thickness_spin.setValue(settings.get("border_thickness", 1))
            self.overlay_text_checkbox.setChecked(settings.get("show_overlay_text", False))

            self.border_radius_checkbox.setChecked(settings.get("use_rounded_corners", False))
            self.border_radius_spin.setValue(settings.get("border_radius", 10))

            self.font_color = settings.get("font_color", "#00FF00")
            self.background_color = settings.get("background_color", "#000000")
            self.border_color = settings.get("border_color", "#00FF00")
        except Exception as e:
            print(f"Error loading settings.json: {e}")

    def save_and_close(self):
        print("Saving settings...")
        settings = {
            "font_name": self.font_dropdown.currentText(),
            "font_size": self.font_size_spin.value(),
            "show_border": self.border_checkbox.isChecked(),
            "border_thickness": self.border_thickness_spin.value(),
            "show_overlay_text": self.overlay_text_checkbox.isChecked(),
            "font_color": self.font_color,
            "background_color": self.background_color,
            "border_color": self.border_color,
            "use_rounded_corners": self.border_radius_checkbox.isChecked(),
            "border_radius": self.border_radius_spin.value(),
        }

        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=2)
            print("Settings saved.")
        except Exception as e:
            print(f"Error saving settings.json: {e}")

        # OPTIONAL: apply settings live to the ticker label
        self.parent_ticker.apply_settings(settings)

        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ticker = RssTicker()
    ticker.show()
    sys.exit(app.exec())
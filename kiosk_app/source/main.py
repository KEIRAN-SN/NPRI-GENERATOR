import sys
import os
import threading
import json
import random
from datetime import datetime
from PyQt6.QtCore import (
    QUrl,
    pyqtSignal,
    QObject,
    QPropertyAnimation,
    QEasingCurve,
    Qt,
    QTimer,
    QRect,
    QPointF
)
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
    QPlainTextEdit,
    QLabel,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from pynput import keyboard

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))

# --- PERFORMANCE & STABILITY FLAGS ---
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--enable-gpu-rasterization "
    "--ignore-gpu-blocklist "
    "--disable-features=CalculateNativeWinOcclusion "
    "--disable-background-timer-throttling "
    "--disable-backgrounding-occluded-windows "
    "--disable-renderer-backgrounding "
    "--enable-begin-frame-scheduling"
)

# --- CONFIGURATION & EXTERNAL DATA ---
TIMEOUT_DURATION = 0.5
LIBRARY_FOLDER = "Kiosk_Library"
CONFIG_FILE = "config.json"

# These will now hold the nested dictionaries
locations = {}
timeframes = {}
pollutants = {}

def load_external_config():
    global locations, timeframes, pollutants
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                locations = data.get("locations", {})
                timeframes = data.get("timeframes", {})
                pollutants = data.get("pollutants", {})
            print(f"Successfully loaded configuration from {CONFIG_FILE}")
        else:
            print(f"Warning: {CONFIG_FILE} not found.")
    except Exception as e:
        print(f"Error loading {CONFIG_FILE}: {e}")

class CommSignal(QObject):
    update_url = pyqtSignal(str)
    log_message = pyqtSignal(str, str)
    toggle_console = pyqtSignal()

# --- ANIMATED CHIMNEY COMPONENT ---
class AnimatedChimney(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 250)
        self.smoke_offset = 0
        self.smoke_timer = QTimer(self)
        self.smoke_timer.timeout.connect(self.update_animation)
        self.smoke_timer.start(30)

    def update_animation(self):
        self.smoke_offset = (self.smoke_offset + 2) % 100
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(148, 163, 184, 180))) 
        for i in range(3):
            y_pos = 80 - ((self.smoke_offset + (i * 33)) % 100)
            size = 20 + (80 - y_pos) / 2
            x_wobble = 10 * (1 if i % 2 == 0 else -1)
            painter.drawEllipse(QPointF(100 + x_wobble, y_pos), size, size * 0.7)
        painter.setBrush(QBrush(QColor(30, 41, 59))) 
        painter.drawRect(70, 100, 60, 100)
        painter.setBrush(QBrush(QColor(51, 65, 85))) 
        painter.drawRect(65, 100, 70, 15)

# --- GROWING TREES COMPONENT ---
class GrowingTrees(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(400, 250)
        self.growth = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.grow)
        self.timer.start(30)

    def grow(self):
        if self.growth < 100:
            self.growth += 1
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        tree_positions = [(100, 1.2), (200, 1.5), (300, 1.1)]
        for x, scale in tree_positions:
            h = (self.growth / 100.0) * 120 * scale
            painter.setBrush(QBrush(QColor(120, 113, 108)))
            painter.drawRect(int(x-10), int(220-h/4), 20, int(h/4))
            painter.setBrush(QBrush(QColor(34, 197, 94)))
            points = [QPointF(x, 220-h), QPointF(x-40, 220-h/3), QPointF(x+40, 220-h/3)]
            painter.drawPolygon(points)

class KioskWindow(QMainWindow):
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.setWindowTitle("Environmental Dashboard Kiosk")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.showFullScreen()
        self.setStyleSheet("background-color: #0f172a;")

        self.is_loading = False
        self.last_output = "" 
        self.rfid_ref = None 
        self.good_news_timer = None 

        self.container = QWidget()
        self.container.setStyleSheet("background-color: #0f172a;")
        self.setCentralWidget(self.container)

        self.screen_size = QApplication.primaryScreen().size()

        self.browser_primary = QWebEngineView(self.container)
        self.browser_secondary = QWebEngineView(self.container)

        for b in [self.browser_primary, self.browser_secondary]:
            b.page().setBackgroundColor(QColor.fromRgb(15, 23, 42))
            b.resize(self.screen_size)
            b.move(0, 0)
            self.configure_settings(b)

        self.mask_widget = QWidget(self.container)
        self.mask_widget.resize(self.screen_size)
        self.mask_widget.move(0, 0)
        self.mask_layout = QVBoxLayout(self.mask_widget)
        self.mask_layout.setSpacing(10)

        self.funny_messages = {
            "EN": ["Scrubbing the smokestacks...", "Consulting the periodic table...", "Filtering out the noise..."],
            "FR": ["Nettoyage des cheminées...", "Consultation du tableau périodique...", "Filtrage du bruit..."]
        }

        self.chimney = AnimatedChimney()
        self.trees = GrowingTrees()
        self.trees.hide() 
        self.loading_label = QLabel("Syncing Data...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("color: #38bdf8; font-family: 'Outfit'; font-size: 42px; font-weight: bold;")
        self.sub_label = QLabel("Please wait...")
        self.sub_label.setWordWrap(True)
        self.sub_label.setFixedWidth(850)
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("color: #94a3b8; font-family: 'Outfit'; font-size: 24px; font-style: italic;")
        
        self.mask_layout.addStretch()
        self.mask_layout.addWidget(self.chimney, 0, Qt.AlignmentFlag.AlignCenter)
        self.mask_layout.addWidget(self.trees, 0, Qt.AlignmentFlag.AlignCenter)
        self.mask_layout.addWidget(self.loading_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.mask_layout.addWidget(self.sub_label, 0, Qt.AlignmentFlag.AlignCenter)
        self.mask_layout.addStretch()

        self.mask_effect = QGraphicsOpacityEffect()
        self.mask_widget.setGraphicsEffect(self.mask_effect)
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.update_pulse_color)
        self.pulse_val, self.pulse_direction = 0, 1
        self.is_environmental_theme = False

        self.mask_fade = QPropertyAnimation(self.mask_effect, b"opacity")
        self.mask_fade.setDuration(600)
        self.mask_fade.setEasingCurve(QEasingCurve.Type.InOutSine)

        self.active_browser, self.hidden_browser = self.browser_primary, self.browser_secondary
        self.active_browser.raise_()
        self.mask_widget.raise_()
        self.mask_effect.setOpacity(0.0) 

        self.signals.update_url.connect(self.trigger_transition)
        self.load_page("help") 

    def update_pulse_color(self):
        self.pulse_val += (2 * self.pulse_direction)
        if self.pulse_val >= 40 or self.pulse_val <= 0: self.pulse_direction *= -1
        if self.is_environmental_theme:
            self.mask_widget.setStyleSheet(f"background-color: rgb(20, {40 + self.pulse_val}, 30);")
        else:
            color_val = 26 + self.pulse_val
            self.mask_widget.setStyleSheet(f"background-color: rgb(15, {color_val-10}, {color_val});")

    def configure_settings(self, browser):
        s = browser.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)

    def trigger_transition(self, output_name):
        if self.good_news_timer:
            self.good_news_timer.stop()
            self.good_news_timer = None

        if output_name == self.last_output and not self.is_loading: return
        
        filename = f"{output_name}.html"
        next_path = os.path.abspath(os.path.join(LIBRARY_FOLDER, filename))
        self.is_loading = True
        self.mask_fade.stop()
        self.mask_fade.setStartValue(self.mask_effect.opacity())
        self.mask_fade.setEndValue(1.0)

        current_lang = "FR" if (self.rfid_ref and self.rfid_ref.language_suffix == "_FR") else "EN"

        if os.path.exists(next_path):
            self.is_environmental_theme = False
            self.chimney.show()
            self.trees.hide()
            self.loading_label.setText("Syncing Data..." if current_lang == "EN" else "Synchronisation...")
            self.loading_label.setStyleSheet("color: #38bdf8; font-family: 'Outfit'; font-size: 42px; font-weight: bold;")
            self.sub_label.setText(random.choice(self.funny_messages[current_lang]))
            
            def start_load():
                self.hidden_browser.loadFinished.connect(self.on_load_finished)
                self.hidden_browser.setUrl(QUrl.fromLocalFile(next_path))
            try: self.mask_fade.finished.disconnect()
            except: pass
            self.mask_fade.finished.connect(start_load)
        else:
            self.is_environmental_theme = True
            self.chimney.hide()
            self.trees.growth = 0
            self.trees.show()
            self.loading_label.setText("Good News!" if current_lang == "EN" else "Bonne nouvelle!")
            self.sub_label.setText("No pollutants released!" if current_lang == "EN" else "Aucun polluant rejeté!")
            self.loading_label.setStyleSheet("color: #4ade80; font-family: 'Outfit'; font-size: 42px; font-weight: bold;")
            
            try: self.mask_fade.finished.disconnect()
            except: pass
            self.good_news_timer = QTimer(self)
            self.good_news_timer.setSingleShot(True)
            self.good_news_timer.timeout.connect(self.auto_clear_to_help)
            self.mask_fade.finished.connect(lambda: self.good_news_timer.start(5000))

        self.pulse_timer.start(30)
        self.mask_fade.start()

    def auto_clear_to_help(self):
        self.good_news_timer = None 
        lang_suffix = self.rfid_ref.language_suffix if self.rfid_ref else ""
        self.is_loading = False 
        self.signals.update_url.emit(f"help{lang_suffix}")

    def on_load_finished(self, success):
        self.hidden_browser.loadFinished.disconnect(self.on_load_finished)
        if success: QTimer.singleShot(400, self.reveal_new_page)
        else: self.is_loading = False

    def reveal_new_page(self):
        self.hidden_browser.raise_()
        self.mask_widget.raise_()
        self.active_browser, self.hidden_browser = self.hidden_browser, self.active_browser
        self.active_browser.page().runJavaScript("if(typeof releaseDashboard === 'function') { releaseDashboard(); }")
        self.pulse_timer.stop()
        self.mask_fade.stop()
        self.mask_fade.setStartValue(1.0)
        self.mask_fade.setEndValue(0.0)
        try: self.mask_fade.finished.disconnect()
        except: pass
        self.mask_fade.finished.connect(lambda: setattr(self, 'is_loading', False))
        self.mask_fade.start()
        self.last_output = os.path.basename(self.active_browser.url().toLocalFile()).replace(".html", "")

    def load_page(self, name):
        path = os.path.abspath(os.path.join(LIBRARY_FOLDER, f"{name}.html"))
        if os.path.exists(path):
            self.active_browser.setUrl(QUrl.fromLocalFile(path))
            self.active_browser.raise_()
            self.last_output = name

# --- RFID LISTENER ---
class RFIDListener:
    def __init__(self, signals):
        self.signals, self.buffer = signals, ""
        self.current_data = {"L": None, "P": None, "T": None}
        self.timer, self.language_suffix = None, ""
        self.help_active = True 
        self.stored_state = "help" 

    def process_tag(self):
        raw_input = self.buffer.strip()
        self.buffer = ""
        if not raw_input: return
        
        # Language/Help Toggles
        if raw_input.lower() == "e": self.language_suffix = ""; self.handle_language_refresh(); return
        if raw_input.lower() == "f": self.language_suffix = "_FR"; self.handle_language_refresh(); return
        if raw_input.lower() == "h":
            if self.help_active:
                if all(self.current_data.values()):
                    self.help_active = False
                    target = f"{self.current_data['L']}_{self.current_data['P']}_{self.current_data['T']}{self.language_suffix}"
                    self.signals.update_url.emit(target)
            else:
                self.help_active = True
                self.signals.update_url.emit(f"help{self.language_suffix}")
            return

        # NEW NESTED LOOKUP LOGIC
        # We now check inside each item's "tag" field
        matched = None
        
        # Check Locations
        for key, val in locations.items():
            if raw_input == val.get("tag") or raw_input == key:
                self.current_data["L"] = val.get("name")
                matched = "L"
                break
        
        # Check Pollutants
        if not matched:
            for key, val in pollutants.items():
                if raw_input == val.get("tag") or raw_input == key:
                    self.current_data["P"] = val.get("name")
                    matched = "P"
                    break
        
        # Check Timeframes
        if not matched:
            for key, val in timeframes.items():
                if raw_input == val.get("tag") or raw_input == key:
                    self.current_data["T"] = val.get("name")
                    matched = "T"
                    break

        if matched: 
            self.help_active = False
            self.check_and_trigger_update()

    def handle_language_refresh(self):
        if self.help_active: self.signals.update_url.emit(f"help{self.language_suffix}")
        elif all(self.current_data.values()): self.check_and_trigger_update()
        else: self.signals.update_url.emit(f"help{self.language_suffix}")

    def check_and_trigger_update(self):
        if all(self.current_data.values()):
            target = f"{self.current_data['L']}_{self.current_data['P']}_{self.current_data['T']}{self.language_suffix}"
            self.signals.update_url.emit(target)

    def reset_timer(self):
        if self.timer: self.timer.cancel()
        self.timer = threading.Timer(0.5, self.process_tag); self.timer.start()

    def on_press(self, key):
        try:
            if hasattr(key, "char"):
                if key.char == "\x04": self.signals.toggle_console.emit(); return
                self.buffer += key.char; self.reset_timer()
            elif key == keyboard.Key.esc: QApplication.quit()
        except Exception: pass

if __name__ == "__main__":
    load_external_config()
    app = QApplication(sys.argv)
    sigs = CommSignal()
    window = KioskWindow(sigs)
    window.show()
    rfid = RFIDListener(sigs)
    window.rfid_ref = rfid 
    listener = keyboard.Listener(on_press=rfid.on_press)
    listener.start()
    sys.exit(app.exec())
import sys
import os
import threading
import time
import psutil
import pyqtgraph as pg
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

try:
    from PyQt6.QtSvg import QSvgRenderer
except ImportError:
    print("Hata: PyQt6-Svg bileşeni bulunamadı.")

from core.privacy_scanner import PrivacyScanner
from core.webrtc_blocker import WebRTCBlocker

# --- AetherMap Sınıfı ---
class AetherMap(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lat, self.lon = 0.0, 0.0
        self.city = "Bilinmiyor"
        self.is_active = False
        self.svg_path = os.path.join("assets", "world_map.svg")
        self.renderer = None
        if os.path.exists(self.svg_path):
            self.renderer = QSvgRenderer(self.svg_path)
        
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.update)
        self.pulse_timer.start(50)

    @pyqtSlot(float, float, str)
    def set_location(self, lat, lon, city):
        self.lat, self.lon, self.city = lat, lon, city
        self.is_active = True
        self.update()

    def reset(self):
        self.is_active = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        painter.fillRect(rect, QColor("#0d1117"))
        
        if self.renderer and self.renderer.isValid():
            painter.setOpacity(0.15)
            self.renderer.render(painter, QRectF(rect))
            painter.setOpacity(1.0)
            
        if self.is_active and self.lat != 0:
            px = (self.lon + 180) * (rect.width() / 360)
            py = (90 - self.lat) * (rect.height() / 180)
            
            pulse_val = abs(int(10 * (time.time() % 1.5) - 5))
            glow = QRadialGradient(QPointF(px, py), 15 + pulse_val)
            glow.setColorAt(0, QColor(0, 255, 136, 180))
            glow.setColorAt(1, Qt.GlobalColor.transparent)
            
            painter.setBrush(glow)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(px, py), 15 + pulse_val, 15 + pulse_val)
            
            painter.setBrush(QColor("#00ff88"))
            painter.drawEllipse(QPointF(px, py), 4, 4)
            
            painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(int(px) + 12, int(py) + 5, self.city.upper())

# --- Ana Pencere ---
class MainWindow(QMainWindow):
    def __init__(self, tor_manager, proxy_config, settings, expiry_date): 
        super().__init__()
        self.tor = tor_manager
        self.proxy = proxy_config
        self.settings = settings
        self.scanner = PrivacyScanner()
        self.webrtc_blocker = WebRTCBlocker() # WebRTC Modülü
        self.expiry_date = expiry_date
        self.is_connected = False
        self.angle = 0
        self.drag_pos = QPoint()
        
        self.real_ip = "Tespit Ediliyor..."
        self.current_ip = "Koruma Yok"
        self.last_net_io = psutil.net_io_counters()

        # Ülke Listesi (Multi-Hop için)
        self.countries = {
            "Otomatik": "any", "Almanya": "de", "ABD": "us", "İngiltere": "gb", 
            "Fransa": "fr", "Hollanda": "nl", "İsviçre": "ch", "Japonya": "jp", 
            "Kanada": "ca", "Rusya": "ru"
        }

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 720)
        
        self.init_ui()
        self.setup_signals()
        self.setup_tray()
        self.load_stylesheet()
        self.load_settings_to_ui()
        
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.traffic_timer = QTimer()
        self.traffic_timer.timeout.connect(self.update_traffic_chart)
        self.traffic_data = [0] * 50

        QShortcut(QKeySequence("Ctrl+Shift+X"), self).activated.connect(self.toggle_window)
        QTimer.singleShot(1000, self.get_initial_ip)

    def init_ui(self):
        self.main_container = QFrame(self)
        self.main_container.setObjectName("MainContainer")
        self.main_container.setFixedSize(400, 720)
        
        layout = QVBoxLayout(self.main_container)
        layout.setContentsMargins(15, 10, 15, 15)
        layout.setSpacing(10)
        
        # Header
        header = QHBoxLayout()
        self.logo_label = QLabel(); self.logo_label.setFixedSize(30, 30); self.draw_logo()
        title = QLabel("AETHERNODE PRO"); title.setObjectName("AppTitle")
        
        self.btn_settings = QPushButton("⚙"); self.btn_settings.setObjectName("IconBtn")
        self.btn_settings.clicked.connect(self.toggle_settings)
        btn_min = QPushButton("—"); btn_min.setObjectName("MinBtn"); btn_min.clicked.connect(self.hide)
        btn_close = QPushButton("×"); btn_close.setObjectName("CloseBtn"); btn_close.clicked.connect(QApplication.instance().quit)
        
        header.addWidget(self.logo_label); header.addWidget(title); header.addStretch()
        header.addWidget(self.btn_settings); header.addWidget(btn_min); header.addWidget(btn_close)
        layout.addLayout(header)

        # Dashboard Page
        self.page_dash = QWidget()
        dash_layout = QVBoxLayout(self.page_dash)
        dash_layout.setContentsMargins(0, 0, 0, 0)
        dash_layout.setSpacing(15)
        
        self.ip_card = QFrame(); self.ip_card.setObjectName("IPCard")
        ip_layout = QVBoxLayout(self.ip_card)
        self.lbl_real_ip = QLabel(f"YEREL IP: {self.real_ip}")
        self.lbl_curr_ip = QLabel(f"AKTİF IP: {self.current_ip}")
        self.lbl_security_info = QLabel("GÜVENLİK ANALİZİ: BEKLENİYOR...")
        
        for lbl in [self.lbl_real_ip, self.lbl_curr_ip, self.lbl_security_info]:
            lbl.setStyleSheet("color: #8b949e; font-size: 10px; font-family: 'Consolas';")
            ip_layout.addWidget(lbl)
        dash_layout.addWidget(self.ip_card)

        # Connect Button
        self.btn_connect = QPushButton("BAĞLAN"); self.btn_connect.setObjectName("ConnectBtnLarge")
        self.btn_connect.setFixedSize(140, 140)
        self.btn_connect.clicked.connect(self.handle_connection)
        dash_layout.addWidget(self.btn_connect, alignment=Qt.AlignmentFlag.AlignCenter)

        self.lbl_status = QLabel("KORUMA DEVRE DIŞI"); self.lbl_status.setObjectName("StatusText")
        dash_layout.addWidget(self.lbl_status, alignment=Qt.AlignmentFlag.AlignCenter)

        self.map_view = AetherMap(); self.map_view.setFixedHeight(150)
        dash_layout.addWidget(self.map_view)

        self.graph_widget = pg.PlotWidget(); self.graph_widget.setBackground('#0d1117'); self.graph_widget.setFixedHeight(80)
        self.graph_widget.hideAxis('bottom'); self.graph_widget.hideAxis('left')
        self.curve = self.graph_widget.plot(pen=pg.mkPen(color='#00ff88', width=2))
        dash_layout.addWidget(self.graph_widget)
        
        layout.addWidget(self.page_dash)

        # Settings Overlay (Multi-Hop ve WebRTC Eklenmiş)
        self.settings_panel = QFrame(self.main_container)
        self.settings_panel.setObjectName("OverlayPanel")
        self.settings_panel.setGeometry(20, 60, 360, 620)
        self.settings_panel.hide()
        set_layout = QVBoxLayout(self.settings_panel)
        
        self.tabs = QTabWidget()
        self.tabs.setObjectName("SettingsTabs")

        sec_tab = QWidget()
        sec_layout = QVBoxLayout(sec_tab)
        
        self.cb_killswitch = QCheckBox("Advanced Kill Switch")
        self.cb_dns_leak = QCheckBox("DNS Leak Protection")
        self.cb_webrtc = QCheckBox("WebRTC Shield")
        self.cb_adblock = QCheckBox("Ad-Block & Tracker Filter")
        self.cb_bridge = QCheckBox("Bridge (obfs4) Mode")
        self.cb_stealth = QCheckBox("Stealth (Snowflake)")
        
        # --- Multi-Hop Panel ---
        mh_group = QGroupBox("Multi-Hop (Özel Devre)")
        mh_layout = QGridLayout()
        self.cmb_entry = QComboBox(); self.cmb_entry.addItems(self.countries.keys())
        self.cmb_exit = QComboBox(); self.cmb_exit.addItems(self.countries.keys())
        mh_layout.addWidget(QLabel("Giriş:"), 0, 0); mh_layout.addWidget(self.cmb_entry, 0, 1)
        mh_layout.addWidget(QLabel("Çıkış:"), 1, 0); mh_layout.addWidget(self.cmb_exit, 1, 1)
        mh_group.setLayout(mh_layout)
        # -----------------------

        self.sp_rotation = QSpinBox()
        self.sp_rotation.setRange(0, 60); self.sp_rotation.setSuffix(" dk")
        self.sp_rotation.setObjectName("SettingsSpinBox")
        
        for cb in [self.cb_killswitch, self.cb_dns_leak, self.cb_webrtc, self.cb_adblock, self.cb_bridge, self.cb_stealth]:
            sec_layout.addWidget(cb)
            cb.stateChanged.connect(self.save_settings_on_change)
        
        sec_layout.addWidget(mh_group) # Multi-hop paneli ekle
        sec_layout.addWidget(QLabel("IP Rotasyon Süresi:"))
        sec_layout.addWidget(self.sp_rotation)
        
        self.sp_rotation.valueChanged.connect(self.save_settings_on_change)
        self.cmb_entry.currentIndexChanged.connect(self.save_settings_on_change)
        self.cmb_exit.currentIndexChanged.connect(self.save_settings_on_change)
        
        sec_layout.addStretch()
        
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_screen = QTextEdit(); self.log_screen.setReadOnly(True); self.log_screen.setObjectName("SettingsLogScreen")
        log_layout.addWidget(self.log_screen)
        
        self.tabs.addTab(sec_tab, "GÜVENLİK")
        self.tabs.addTab(log_tab, "SİSTEM LOGLARI")
        set_layout.addWidget(self.tabs)
        
        btn_close_settings = QPushButton("TAMAM"); btn_close_settings.setObjectName("SaveBtn")
        btn_close_settings.clicked.connect(self.toggle_settings)
        set_layout.addWidget(btn_close_settings)

    # ... mousePressEvent, mouseMoveEvent, setup_signals, append_log, update_bootstrap metodları aynı ...

    def handle_connection(self):
        if not self.is_connected:
            self.btn_connect.setText("BAĞLANIYOR...")
            self.btn_connect.setEnabled(False)
            
            self.log_screen.clear()
            self.lbl_status.setText("TÜNEL HAZIRLANIYOR...")
            self.lbl_security_info.setText("GÜVENLİK ANALİZİ: TEST EDİLİYOR...")
            self.anim_timer.start(15); self.traffic_timer.start(1000)
            
            # Multi-hop değerlerini al
            entry_code = self.countries[self.cmb_entry.currentText()]
            exit_code = self.countries[self.cmb_exit.currentText()]
            
            self.tor.start_tor_thread(
                country_code=exit_code,
                entry_node=entry_code, # Yeni eklenen Multi-Hop parametresi
                bridge=self.cb_bridge.isChecked(),
                killswitch=self.cb_killswitch.isChecked(),
                dns_leak=self.cb_dns_leak.isChecked(),
                stealth=self.cb_stealth.isChecked(),
                rotate_min=self.sp_rotation.value(),
                adblock_active=self.cb_adblock.isChecked()
            )
        else:
            self.btn_connect.setText("DURDURULUYOR...")
            self.btn_connect.setEnabled(False)
            self.tor.stop_tor()

    def update_status(self, status):
        self.btn_connect.setEnabled(True)
        if status == "CONNECTED":
            self.is_connected = True
            self.proxy.enable_proxy()
            self.btn_connect.setText("DURDUR")
            self.lbl_status.setText("GİZLİLİK KALKANI AKTİF")
            self.run_privacy_test()
        else:
            self.is_connected = False
            self.proxy.disable_proxy()
            self.btn_connect.setText("BAĞLAN")
            self.lbl_status.setText("KORUMA DEVRE DIŞI")
            self.lbl_security_info.setText("GÜVENLİK ANALİZİ: BEKLENİYOR...")
            self.anim_timer.stop(); self.traffic_timer.stop()
            self.map_view.reset()

    def save_settings_on_change(self):
        # Ayarları kaydet
        self.settings.set("kill_switch", self.cb_killswitch.isChecked())
        self.settings.set("dns_leak_protection", self.cb_dns_leak.isChecked())
        self.settings.set("webrtc_shield", self.cb_webrtc.isChecked())
        self.settings.set("adblock_active", self.cb_adblock.isChecked())
        self.settings.set("bridge_usage", self.cb_bridge.isChecked())
        self.settings.set("stealth_mode", self.cb_stealth.isChecked())
        self.settings.set("rotation_min", self.sp_rotation.value())
        self.settings.set("entry_node", self.cmb_entry.currentText())
        self.settings.set("exit_node", self.cmb_exit.currentText())

        # WebRTC Blocker'ı anlık tetikle
        msg = self.webrtc_blocker.toggle_block(self.cb_webrtc.isChecked())
        if "Aktif" in msg: self.append_log(f"[GÜVENLİK] {msg}")

    def load_settings_to_ui(self):
        self.cb_killswitch.setChecked(self.settings.get("kill_switch"))
        self.cb_dns_leak.setChecked(self.settings.get("dns_leak_protection"))
        self.cb_webrtc.setChecked(self.settings.get("webrtc_shield"))
        self.cb_adblock.setChecked(self.settings.get("adblock_active", False))
        self.cb_bridge.setChecked(self.settings.get("bridge_usage"))
        self.cb_stealth.setChecked(self.settings.get("stealth_mode", False))
        self.sp_rotation.setValue(self.settings.get("rotation_min", 0))
        
        # ComboBox seçimlerini yükle
        idx_entry = self.cmb_entry.findText(self.settings.get("entry_node", "Otomatik"))
        self.cmb_entry.setCurrentIndex(idx_entry if idx_entry >= 0 else 0)
        idx_exit = self.cmb_exit.findText(self.settings.get("exit_node", "Otomatik"))
        self.cmb_exit.setCurrentIndex(idx_exit if idx_exit >= 0 else 0)

    # ... Diğer metodlar (draw_logo, setup_tray, traffic_chart vb.) aynı ...
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.drag_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.drag_pos.isNull():
            delta = event.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta); self.drag_pos = event.globalPosition().toPoint()
    def setup_signals(self):
        self.tor.status_signal.connect(self.update_status)
        self.tor.log_signal.connect(self.append_log)
        self.tor.bootstrap_signal.connect(self.update_bootstrap)
    @pyqtSlot(str)
    def append_log(self, text):
        self.log_screen.append(f"<span style='color:#58a6ff'>></span> {text}")
        self.log_screen.moveCursor(QTextCursor.MoveOperation.End)
    def update_bootstrap(self, val): self.lbl_status.setText(f"TÜNEL HAZIRLANIYOR: %{val}")
    def draw_logo(self):
        pixmap = QPixmap(40, 40); pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#58a6ff"), 2.5)); p.drawEllipse(5, 5, 30, 30)
        p.setPen(QPen(QColor("#00ff88"), 2)); p.drawLine(20, 12, 12, 28); p.drawLine(20, 12, 28, 28)
        p.end(); self.logo_label.setPixmap(pixmap)
    def setup_tray(self):
        self.tray = QSystemTrayIcon(self); self.tray.setIcon(QIcon(self.logo_label.pixmap()))
        menu = QMenu(); menu.addAction("Aç", self.showNormal); menu.addAction("Kapat", QApplication.instance().quit)
        self.tray.setContextMenu(menu); self.tray.show()
    def update_traffic_chart(self):
        io = psutil.net_io_counters()
        diff = (io.bytes_sent + io.bytes_recv) - (self.last_net_io.bytes_sent + self.last_net_io.bytes_recv)
        self.last_net_io = io
        val = min(int(diff / 1024), 500)
        self.traffic_data.pop(0); self.traffic_data.append(val if self.is_connected else 0)
        self.curve.setData(self.traffic_data)
    def get_initial_ip(self):
        def task():
            data = self.scanner.get_privacy_data(use_proxy=False)
            if data and "ip" in data: QMetaObject.invokeMethod(self.lbl_real_ip, "setText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"YEREL IP: {data['ip']}"))
        threading.Thread(target=task, daemon=True).start()
    def run_privacy_test(self):
        def task():
            time.sleep(3)
            data = self.scanner.get_privacy_data(use_proxy=True)
            if data and "ip" in data:
                score = self.scanner.get_security_score(self.is_connected, self.cb_killswitch.isChecked(), self.cb_dns_leak.isChecked())
                QMetaObject.invokeMethod(self.lbl_curr_ip, "setText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"AKTİF IP: {data['ip']}"))
                QMetaObject.invokeMethod(self.lbl_security_info, "setText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"GÜVENLİK SKORU: %{score} | DNS: {data.get('dns_leak', 'OK')}"))
                QMetaObject.invokeMethod(self.map_view, "set_location", Qt.ConnectionType.QueuedConnection, Q_ARG(float, float(data.get("lat",0))), Q_ARG(float, float(data.get("lon",0))), Q_ARG(str, data.get("city","Unknown")))
        threading.Thread(target=task, daemon=True).start()
    def toggle_settings(self): self.settings_panel.setVisible(not self.settings_panel.isVisible())
    def toggle_window(self): (self.hide() if self.isVisible() else (self.showNormal(), self.activateWindow()))
    def update_animation(self): self.angle = (self.angle + 8) % 360; self.update()
    def load_stylesheet(self):
        if os.path.exists("ui/styles.css"):
            with open("ui/styles.css", "r") as f: self.setStyleSheet(f.read())
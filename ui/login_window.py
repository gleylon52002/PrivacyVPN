from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from core.security import check_license, get_local_key
import datetime

class LoginWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(350, 480)
        self.expiry_date = "Bilinmiyor"
        self.init_ui()
        
        # OTOMATİK GİRİŞ KONTROLÜ
        # Küçük bir gecikme ekleyerek arayüzün önce yüklenmesini sağlıyoruz
        QTimer.singleShot(500, self.auto_login)

    def init_ui(self):
        layout = QVBoxLayout()
        self.container = QFrame()
        self.container.setObjectName("LoginContainer")
        # Stil bilgilerini stylesheet yerine nesne üzerinden veya main.py'deki CSS'den alabilir
        self.container.setStyleSheet("""
            #LoginContainer {
                background-color: #0d1117; 
                border: 2px solid #30363d; 
                border-radius: 20px;
            }
        """)
        c_layout = QVBoxLayout(self.container)

        # Header / Kapatma Butonu
        top_bar = QHBoxLayout()
        top_bar.addStretch()
        btn_close = QPushButton("×")
        btn_close.setFixedSize(30, 30)
        btn_close.setStyleSheet("""
            QPushButton { color: #8b949e; font-size: 20px; border: none; background: transparent; } 
            QPushButton:hover { color: #f85149; }
        """)
        btn_close.clicked.connect(self.reject)
        top_bar.addWidget(btn_close)
        c_layout.addLayout(top_bar)

        # Logo Alanı (Opsiyonel: Bir icon eklenebilir)
        title = QLabel("AETHERNODE PRO")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 20px; font-family: 'Consolas';")
        
        subtitle = QLabel("GÜVENLİ ERİŞİM PANELİ")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8b949e; font-size: 10px; letter-spacing: 2px;")
        
        c_layout.addWidget(title)
        c_layout.addWidget(subtitle)
        c_layout.addSpacing(40)

        # Giriş Alanı
        self.input_key = QLineEdit()
        self.input_key.setPlaceholderText("LİSANS ANAHTARI (AETH-XXXX-...)")
        self.input_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_key.setStyleSheet("""
            QLineEdit {
                background: #161b22; 
                border: 1px solid #30363d; 
                color: #00ff88; 
                padding: 12px; 
                border-radius: 10px;
                font-family: 'Consolas';
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #58a6ff; }
        """)

        self.lbl_msg = QLabel("Donanım kimliği doğrulanıyor...")
        self.lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_msg.setStyleSheet("color: #8b949e; font-size: 11px;")
        self.lbl_msg.setWordWrap(True)

        # Doğrulama Butonu
        self.btn_verify = QPushButton("SİSTEME GİRİŞ YAP")
        self.btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_verify.setStyleSheet("""
            QPushButton { 
                background: #238636; 
                color: white; 
                padding: 15px; 
                border-radius: 10px; 
                font-weight: bold; 
                font-size: 12px;
            } 
            QPushButton:hover { background: #2ea043; }
            QPushButton:disabled { background: #161b22; color: #484f58; }
        """)
        self.btn_verify.clicked.connect(self.verify)

        c_layout.addWidget(self.input_key)
        c_layout.addWidget(self.lbl_msg)
        c_layout.addStretch()
        c_layout.addWidget(self.btn_verify)
        
        # Alt Bilgi
        footer = QLabel("© 2025 AetherNode Privacy Operations")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #484f58; font-size: 9px;")
        c_layout.addWidget(footer)
        c_layout.addSpacing(10)

        layout.addWidget(self.container)
        self.setLayout(layout)

    def auto_login(self):
        saved_key = get_local_key()
        if saved_key:
            self.input_key.setText(saved_key)
            self.lbl_msg.setText("Kayıtlı lisans otomatik doğrulanıyor...")
            # Otomatik girişte butona basılmış gibi verify tetikle
            self.verify()
        else:
            self.lbl_msg.setText("Lütfen geçerli bir abonelik anahtarı girin.")

    def verify(self):
        key = self.input_key.text().strip()
        if not key: 
            self.lbl_msg.setText("Anahtar alanı boş bırakılamaz.")
            return
        
        # Görsel geri bildirim
        self.btn_verify.setEnabled(False)
        self.btn_verify.setText("DOĞRULANIYOR...")
        self.lbl_msg.setText("Bulut sunucusu ile el sıkışılıyor...")
        self.lbl_msg.setStyleSheet("color: #58a6ff;")
        
        # Thread kullanmadan basit bir işlem olduğu için ProcessEvents ile UI donmasını engelliyoruz
        QApplication.processEvents()
        
        success, result = check_license(key)
        
        if success:
            self.expiry_date = result
            self.lbl_msg.setText(f"Erişim Onaylandı! Bitiş: {result}")
            self.lbl_msg.setStyleSheet("color: #00ff88;")
            QTimer.singleShot(800, self.accept) # Başarı mesajını görmesi için kısa bekleme
        else:
            self.btn_verify.setEnabled(True)
            self.btn_verify.setText("SİSTEME GİRİŞ YAP")
            self.lbl_msg.setText(result)
            self.lbl_msg.setStyleSheet("color: #f85149; font-size: 11px;")

    # Sürükle-Bırak Özelliği (Pencereyi taşımak için)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()
            
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()
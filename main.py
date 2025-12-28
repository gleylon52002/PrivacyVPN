import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication, QDialog
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from ui.login_window import LoginWindow
from core.settings import SettingsManager
from core.tor_manager import TorManager
from core.proxy_config import ProxyConfig

def resource_path(relative_path):
    """ EXE içindeki (bin, ui, css vb.) statik dosyalara güvenli erişim sağlar. """
    try:
        # PyInstaller dosyaları geçici olarak buraya çıkartır
        base_path = sys._MEIPASS
    except Exception:
        # Geliştirme aşamasında normal dizini kullanır
        base_path = os.path.abspath(".")
    
    path = os.path.join(base_path, relative_path).replace("\\", "/")
    return path

def get_writable_path(filename):
    """ Yazılabilir dosyaları (settings, log, torrc) Windows APPDATA klasöründe tutar. """
    # Uygulamanın verilerini güvenli bir yerde saklamak için APPDATA kullanılır
    app_data = os.path.join(os.environ.get('APPDATA', os.path.abspath(".")), "AetherNodePro")
    if not os.path.exists(app_data):
        os.makedirs(app_data, exist_ok=True)
    return os.path.join(app_data, filename).replace("\\", "/")

def is_admin():
    """ Firewall ve Kill Switch işlemleri için yönetici yetkisi kontrolü. """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    # 1. Uygulama Genel Ayarları
    app = QApplication(sys.argv)
    app.setApplicationName("AetherNode Pro")
    
    # Pencere kapansa bile uygulamanın tray üzerinden devam etmesini sağlar
    app.setQuitOnLastWindowClosed(False) 

    # --- TASARIM (CSS) YÜKLEME ---
    css_path = resource_path("ui/styles.css")
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
        except Exception as e:
            print(f"Stil dosyası yükleme hatası: {e}")

    # 2. LİSANS / GİRİŞ KONTROLÜ
    login_screen = LoginWindow()
    
    # Kullanıcı giriş yapıp lisans onaylandığında Accepted döner
    if login_screen.exec() == QDialog.DialogCode.Accepted:
        # Lisans doğrulanınca gelen bilgileri alıyoruz
        expiry_date = getattr(login_screen, 'expiry_date', "Ömür Boyu")
        
        # 3. CORE MODÜLLERİNİ BAŞLATMA
        # Ayarlar yöneticisini başlat (Kullanıcı tercihleri burada saklanır)
        settings = SettingsManager()
        
        # Proxy yapılandırıcısını başlat (Sistem ayarları ve WebRTC koruması için)
        # writable_path_func inject edilerek dns_blocklist.txt'ye erişim sağlanır
        proxy = ProxyConfig(writable_path_func=get_writable_path)
        
        # Tor motorunu başlat
        tor = TorManager(
            settings_manager=settings, 
            resource_path_func=resource_path, 
            writable_path_func=get_writable_path
        )
        
        # 4. ANA PENCEREYİ OLUŞTURMA
        # MainWindow artık tüm bu motorları merkezi olarak yönetir
        window = MainWindow(tor, proxy, settings, expiry_date)
        window.show()
        
        # 5. YÖNETİCİ YETKİSİ UYARISI (Kill Switch için gerekli)
        if not is_admin():
            print("Uyarı: Uygulama yönetici olarak çalıştırılmadı. Bazı Firewall özellikleri kısıtlanabilir.")
        
        # Uygulama döngüsüne gir
        sys.exit(app.exec())
    else:
        # Kullanıcı giriş yapmazsa veya iptal ederse temiz bir çıkış yap
        sys.exit(0)

if __name__ == "__main__":
    main()
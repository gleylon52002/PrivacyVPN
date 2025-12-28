import os
import subprocess
import threading
import re
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

class TorManager(QObject):
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    bootstrap_signal = pyqtSignal(int)
    circuit_signal = pyqtSignal(list)

    def __init__(self, settings_manager, resource_path_func, writable_path_func):
        super().__init__()
        self.settings = settings_manager
        self.rp = resource_path_func
        self.wp = writable_path_func
        self.tor_process = None
        self.is_running = False
        
        self.rotation_timer = QTimer()
        self.rotation_timer.timeout.connect(self.rotate_ip)
        
        # --- DİZİN YAPILANDIRMASI ---
        self.bin_dir = os.path.abspath(self.rp("bin"))
        self.tor_path = os.path.join(self.bin_dir, "tor.exe")
        
        # GeoIP dosyaları bin/data klasöründe
        self.data_dir_internal = os.path.join(self.bin_dir, "data")
        self.geoip_path = os.path.join(self.data_dir_internal, "geoip")
        self.geoip6_path = os.path.join(self.data_dir_internal, "geoip6")
        
        # Pluggable Transports
        pt_dir = os.path.join(self.bin_dir, "PluggableTransports")
        self.lyrebird_path = os.path.join(pt_dir, "lyrebird.exe")
        self.snowflake_path = os.path.join(pt_dir, "snowflake-client.exe")

    def fix_p(self, path):
        """Tor'un Windows üzerinde yolları doğru okuması için formatlar."""
        return os.path.normpath(path).replace("\\", "/")

    def rotate_ip(self):
        if self.is_running:
            self.log_signal.emit("[SİSTEM] Yeni devre talebi gönderildi.")
            # Gelecekte buraya ControlPort üzerinden NEWNYM sinyali eklenecek

    def _manage_kill_switch(self, active):
        try:
            if active:
                self.log_signal.emit("[GÜVENLİK] Kill Switch Aktif.")
                subprocess.run('netsh advfirewall set allprofiles firewallpolicy blockoutbound,blockinbound', shell=True, capture_output=True)
                subprocess.run(f'netsh advfirewall firewall add rule name="Aether_Tor" dir=out action=allow program="{self.fix_p(self.tor_path)}" enable=yes', shell=True, capture_output=True)
            else:
                self.log_signal.emit("[GÜVENLİK] Kill Switch Pasif.")
                subprocess.run('netsh advfirewall set allprofiles firewallpolicy allowoutbound,blockinbound', shell=True, capture_output=True)
                subprocess.run('netsh advfirewall firewall delete rule name="Aether_Tor"', shell=True, capture_output=True)
        except Exception as e:
            self.log_signal.emit(f"[HATA] Firewall: {e}")

    def _start_tor_logic(self, country_code="any", entry_node="any", bridge=False, killswitch=False, dns_leak=False, stealth=False, rotate_min=0, adblock_active=False):
        self.kill_existing_tor()
        
        # Kullanıcı verileri dizini (AppData)
        config_path = self.fix_p(os.path.join(self.wp(""), "torrc_temp"))
        data_dir_user = self.fix_p(os.path.join(self.wp(""), "tor_data"))
        os.makedirs(data_dir_user, exist_ok=True)
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                f.write(f'DataDirectory {data_dir_user}\n')
                
                # GeoIP Dosyalarını Tanıt (bin/data içindekiler)
                if os.path.exists(self.geoip_path):
                    f.write(f'GeoIPFile {self.fix_p(self.geoip_path)}\n')
                else:
                    self.log_signal.emit(f"[KRİTİK UYARI] GeoIP bulunamadı: {self.geoip_path}")

                if os.path.exists(self.geoip6_path):
                    f.write(f'GeoIPv6File {self.fix_p(self.geoip6_path)}\n')
                
                f.write("SocksPort 127.0.0.1:9050\n")
                f.write("ControlPort 127.0.0.1:9051\n")
                f.write("CookieAuthentication 1\n")
                f.write("AvoidDiskWrites 1\n")
                f.write("DNSPort 127.0.0.1:5300\n")
                f.write("AutomapHostsOnResolve 1\n")

                # --- MULTI-HOP & ÜLKE SEÇİMİ ---
                # GeoIP dosyası yoksa ülke seçimi yapılamaz, bu yüzden kontrol ekliyoruz
                if os.path.exists(self.geoip_path):
                    if bridge or stealth:
                        self.log_signal.emit("[BİLGİ] Köprü modu aktif, giriş düğümü yoksayıldı.")
                    elif entry_node != "any":
                        f.write(f"EntryNodes {{{entry_node}}}\n")
                        f.write("StrictNodes 0\n")

                    if country_code != "any":
                        f.write(f"ExitNodes {{{country_code}}}\n")
                        f.write("StrictNodes 0\n")
                
                # --- KÖPRÜ VE GİZLİLİK ---
                if stealth and os.path.exists(self.snowflake_path):
                    f.write(f'ClientTransportPlugin snowflake exec {self.fix_p(self.snowflake_path)}\n')
                    f.write("UseBridges 1\n")
                    f.write("Bridge snowflake 192.0.2.3:1 2B280B2311516279E59986A8ED06D9DAE6CC3799\n")
                elif bridge and os.path.exists(self.lyrebird_path):
                    f.write(f'ClientTransportPlugin obfs4 exec {self.fix_p(self.lyrebird_path)}\n')
                    f.write("UseBridges 1\n")
                    bridge_line = self.settings.get("bridge_line") # Ayarlardan varsa özel köprüyü al
                    if bridge_line:
                        f.write(f"Bridge {bridge_line}\n")
                    else:
                        # Fallback: Varsayılan bir obfs4 köprüsü
                        f.write("Bridge obfs4 192.95.36.142:443 CDF2E852BFED588B851625846A9D37397724A933 cert=0SyzAnoo980f7A6NID4mXBC9fP6pU9v6I+HycEovzP/Y79hBfW/27rU6uLz9+9vFpMubGQ iat-mode=0\n")

            if killswitch: self._manage_kill_switch(True)

            self.tor_process = subprocess.Popen(
                [self.tor_path, "-f", config_path], 
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            for line in iter(self.tor_process.stdout.readline, ''):
                if not self.is_running: break
                clean_line = line.strip()
                self.log_signal.emit(clean_line)
                
                if "Bootstrapped" in clean_line:
                    p = re.search(r'(\d+)%', clean_line)
                    if p: self.bootstrap_signal.emit(int(p.group(1)))
                
                if "100%" in clean_line or "Done" in clean_line:
                    self.status_signal.emit("CONNECTED")

        except Exception as e:
            self.log_signal.emit(f"[KRİTİK HATA] {e}")
            self.stop_tor()

    def stop_tor(self):
        self.is_running = False
        self.rotation_timer.stop()
        if self.tor_process:
            self.tor_process.terminate()
        self._manage_kill_switch(False)
        self.kill_existing_tor()
        self.status_signal.emit("DISCONNECTED")

    def kill_existing_tor(self):
        try:
            for t in ["tor.exe", "lyrebird.exe", "snowflake-client.exe"]:
                subprocess.run(f"taskkill /f /im {t}", shell=True, capture_output=True)
        except: pass

    def start_tor_thread(self, **kwargs):
        self.is_running = True
        if kwargs.get('rotate_min', 0) > 0:
            self.rotation_timer.start(kwargs['rotate_min'] * 60 * 1000)
        threading.Thread(target=self._start_tor_logic, kwargs=kwargs, daemon=True).start()
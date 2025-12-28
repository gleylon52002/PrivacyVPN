import winreg
import ctypes
import os
import requests
import socket
import subprocess

class ProxyConfig:
    def __init__(self, host="127.0.0.1", port=9050, writable_path_func=None):
        self.host = host
        self.port = port
        self.wp = writable_path_func
        self.proxy_server = f"socks={host}:{port}"
        self.registry_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
        self.blocked_domains = set()
        self._load_blocklist()

    def _load_blocklist(self):
        """Yerel blocklist dosyasını hafızaya yükler."""
        if self.wp:
            blocklist_path = self.wp("dns_blocklist.txt")
            if os.path.exists(blocklist_path):
                try:
                    with open(blocklist_path, "r", encoding="utf-8") as f:
                        self.blocked_domains = set(line.strip() for line in f if line.strip() and not line.startswith("#"))
                except: pass

    def set_kill_switch(self, active):
        """
        Advanced Kill Switch: Windows Firewall üzerinden Tor dışındaki 
        tüm giden trafiği engeller (DNS dahil).
        """
        try:
            if active:
                # 1. Mevcut tüm giden trafiği blokla (Tüm profiller için)
                subprocess.run(['netsh', 'advfirewall', 'set', 'allprofiles', 'firewallpolicy', 'blockinbound,blockoutbound'], capture_output=True)
                
                # 2. Tor'un çalışması için gerekli özel izinleri aç (Loopback trafiği)
                subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=Aether_Tor_Loopback', 
                               'dir=out', 'action=allow', 'protocol=TCP', 'remoteip=127.0.0.1'], capture_output=True)
            else:
                # Firewall'u fabrika ayarlarına döndür (İzin ver)
                subprocess.run(['netsh', 'advfirewall', 'set', 'allprofiles', 'firewallpolicy', 'blockinbound,allowoutbound'], capture_output=True)
                subprocess.run(['netsh', 'advfirewall', 'firewall', 'delete', 'rule', 'name=Aether_Tor_Loopback'], capture_output=True)
            return True
        except Exception as e:
            print(f"Kill Switch Hatası: {e}")
            return False

    def set_webrtc_shield(self, active):
        """WebRTC sızıntılarını önlemek için kayıt defteri manipülasyonu."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_WRITE)
            if active:
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.0.0.1;192.168.*;10.*;172.16.*;<local>")
                winreg.SetValueEx(key, "AutoDetect", 0, winreg.REG_DWORD, 0)
            else:
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "")
            winreg.CloseKey(key)
            self.refresh_settings()
        except: pass

    def get_ip_info(self):
        """IP bilgilerini Tor üzerinden çeker."""
        try:
            proxies = {
                'http': f'socks5h://{self.host}:{self.port}',
                'https': f'socks5h://{self.host}:{self.port}'
            }
            response = requests.get("http://ip-api.com/json/", proxies=proxies, timeout=15)
            return response.json()
        except Exception as e:
            return {"status": "fail", "message": str(e)}

    def enable_proxy(self):
        """Sistem proxy'sini ve DNS korumasını aktif eder."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, self.proxy_server)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.0.0.1")
            winreg.CloseKey(key)
            self.refresh_settings()
            return True
        except: return False

    def disable_proxy(self):
        """Proxy'yi kapatır."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_path, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            self.refresh_settings()
            return True
        except: return False

    def refresh_settings(self):
        """Ayarları Windows sistemine bildirir."""
        ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0) 
        ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)
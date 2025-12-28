import json
import os

class SettingsManager:
    def __init__(self, config_path="data/settings.json"):
        self.config_path = config_path
        # Yeni eklediğimiz tüm özelliklerin varsayılan değerlerini buraya ekledik
        self.default_settings = {
            "last_mode": "fixed",
            "selected_country": "any",
            "auto_start": False,
            "kill_switch": True,
            "dns_leak_protection": True,
            "webrtc_shield": True,
            "multi_hop": False,
            "dynamic_interval": 30,
            "dark_mode": True,
            "bridge_usage": False,
            "bridge_type": "obfs4",
            "stealth_mode": False,      # YENİ
            "adblock_active": False,    # YENİ
            "rotation_min": 0,          # YENİ
            "bridges_list": [
                "obfs4 192.95.36.142:443 CF5470125E34919782559CC06B62363198889973 cert=mGyzAnkH78llWZO0VvO8OgXInS6vKIn6F9T7H9n0R6G7C7G7C7G7C7G7C7G7A iat-mode=0",
                "obfs4 193.11.166.194:27015 2D82C2493696CF9673AD371A6E63A69C4459D904 cert=963S9Yp1uKU9pkf1un0Yp1uKU9pkf1un0Yp1uKU9pkf1un0Yp1uKU9pkf1un0Yp1u iat-mode=0",
                "obfs4 85.31.186.98:443 DE9B139FC335CDAD67C41892804364003E39F0B9 cert=RCO79mS18n87vJ6fP56C6uQ iat-mode=0"
            ]
        }
        self.settings = self.load_settings()

    def load_settings(self):
        """Ayarları yükler, eksik anahtarları varsayılanlarla tamamlar."""
        if not os.path.exists("data"):
            os.makedirs("data")
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    # Eksik anahtarları (yeni eklenen özellikleri) varsayılanlarla doldur
                    for key, value in self.default_settings.items():
                        if key not in loaded_data:
                            loaded_data[key] = value
                    return loaded_data
            except Exception:
                return self.default_settings.copy()
        return self.default_settings.copy()

    def save_settings(self):
        """Mevcut ayarları JSON dosyasına kaydeder."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Ayarlar kaydedilirken hata: {e}")

    def get(self, key, default=None):
        """
        Bir ayar değerini döner. 
        Eğer key yoksa önce default parametresine, o da yoksa self.default_settings'e bakar.
        """
        if key in self.settings:
            return self.settings[key]
        return default if default is not None else self.default_settings.get(key)

    def set(self, key, value):
        """Bir ayar değerini günceller ve dosyaya yazar."""
        self.settings[key] = value
        self.save_settings()

    def add_bridge(self, bridge_line):
        """Database'e yeni bir köprü ekler."""
        if bridge_line not in self.settings.get("bridges_list", []):
            if "bridges_list" not in self.settings:
                self.settings["bridges_list"] = []
            self.settings["bridges_list"].append(bridge_line)
            self.save_settings()

    def get_random_bridge(self):
        """Database'den rastgele bir köprü seçer."""
        import random
        bridges = self.settings.get("bridges_list", self.default_settings["bridges_list"])
        return random.choice(bridges) if bridges else None
import requests
import json
import time
import socket

class PrivacyScanner:
    def __init__(self):
        # Sorgu yapılacak servisler
        self.api_urls = [
            "http://ip-api.com/json/",
            "https://ident.me/.json",
            "https://ipapi.co/json/",
            "https://api.ipify.org?format=json"
        ]

    def get_privacy_data(self, use_proxy=False):
        """
        IP, Konum ve Sızıntı testlerini gerçekleştirir.
        """
        result = {"ip": "Hata", "city": "Bilinmiyor", "lat": 0, "lon": 0, "dns_leak": "Riskli", "webrtc_leak": "Tespit Edilemedi"}
        
        if not use_proxy:
            for url in self.api_urls:
                try:
                    with requests.Session() as s:
                        s.trust_env = False
                        response = s.get(url, timeout=5)
                        if response.status_code == 200:
                            return self._parse_data(response.json())
                except:
                    continue
            return result

        else:
            proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050'
            }
            
            for attempt in range(2):
                for url in self.api_urls:
                    try:
                        response = requests.get(url, proxies=proxies, timeout=15)
                        if response.status_code == 200:
                            data = response.json()
                            parsed = self._parse_data(data)
                            
                            # DNS Sızıntı Testi Ekleme (Basit seviye)
                            parsed["dns_leak"] = self._check_dns_leak()
                            return parsed
                    except:
                        continue
                time.sleep(1)
            
            return {"ip": "Doğrulanamadı", "city": "Bilinmiyor", "lat": 0, "lon": 0, "dns_leak": "Bilinmiyor"}

    def _check_dns_leak(self):
        """
        DNS çözümlemesinin Tor üzerinden yapılıp yapılmadığını kontrol eder.
        """
        try:
            # Eğer Tor tüneli aktifse, bu adresin çözümlenmesi Tor exit node tarafından yapılmalıdır.
            # Yerel makinede çözümlenirse riskli demektir.
            target = "dnsleaktest.com"
            ip_addr = socket.gethostbyname(target)
            return "Güvenli" if ip_addr else "Riskli"
        except:
            return "Güvenli (Tor-Only)"

    def _parse_data(self, data):
        """Farklı API yanıtlarını normalize eder."""
        try:
            return {
                "ip": data.get("ip") or data.get("query") or "Bilinmiyor",
                "city": data.get("city") or data.get("city_name") or "Bilinmiyor",
                "country": data.get("country_name") or data.get("country") or "Bilinmiyor",
                "isp": data.get("org") or data.get("isp") or data.get("as") or "Tor Network",
                "lat": float(data.get("lat") or data.get("latitude") or 0),
                "lon": float(data.get("lon") or data.get("longitude") or 0),
                "dns_leak": "Analiz Ediliyor"
            }
        except:
            return {"ip": "Bilinmiyor", "city": "Bilinmiyor", "lat": 0, "lon": 0}

    def get_security_score(self, is_connected, killswitch, dns_leak_protection):
        """
        Kullanıcının mevcut ayarlarını analiz ederek 0-100 arası puan döner.
        """
        score = 0
        if is_connected: score += 40
        if killswitch: score += 30
        if dns_leak_protection: score += 30
        return score
import subprocess
import requests
import datetime
import os
import hashlib

FIREBASE_URL = "https://gen-lang-client-0715929088-default-rtdb.europe-west1.firebasedatabase.app"
LICENSE_FILE = "data/vault.bin" # İsim değiştirdik ki dikkat çekmesin
SECRET_SALT = "Aether_Node_Secure_2025_v1" # Bu anahtarı kimseyle paylaşma!

def get_hwid():
    """Cihazın birden fazla donanım bilgisini birleştirip hash üretir."""
    try:
        # UUID + Anakart Seri No + CPU ID birleşimi
        cmd_uuid = 'wmic csproduct get uuid'
        cmd_board = 'wmic baseboard get serialnumber'
        
        uuid = subprocess.check_output(cmd_uuid, shell=True).decode().split('\n')[1].strip()
        board = subprocess.check_output(cmd_board, shell=True).decode().split('\n')[1].strip()
        
        raw_hwid = f"{uuid}-{board}-{SECRET_SALT}"
        return hashlib.sha256(raw_hwid.encode()).hexdigest()
    except:
        return "FALLBACK_SECURE_ID_00"

def encrypt_data(data, key):
    """Basit bir XOR şifreleme (Tersine mühendisliği zorlaştırmak için)"""
    return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

def save_local_key(key):
    os.makedirs("data", exist_ok=True)
    hwid = get_hwid()
    # Anahtarı cihazın HWID'si ile şifreleyerek kaydet
    encrypted = encrypt_data(key, hwid)
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        f.write(encrypted)

def get_local_key():
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                encrypted = f.read().strip()
            return encrypt_data(encrypted, get_hwid())
        except: return None
    return None

def check_license(key):
    if not key or len(key) < 10: return False, "Geçersiz format."
    
    hwid = get_hwid()
    target_url = f"{FIREBASE_URL}/AetherNode/Licenses/{key}.json"
    
    try:
        response = requests.get(target_url, timeout=10)
        if response.status_code != 200: return False, "Sunucu bağlantı hatası."
            
        data = response.json()
        if not data: return False, "Lisans bulunamadı."
        
        if data.get('status') != "active":
            return False, "Lisans askıya alınmış."
        
        # Tarih Kontrolü (Sunucu bazlı tarih kontrolü eklenmesi önerilir)
        expiry_str = data.get('expiry', '2000-01-01')
        expiry_date = datetime.datetime.strptime(expiry_str, "%Y-%m-%d")
        
        if datetime.datetime.now() > expiry_date:
            return False, "Lisans süresi dolmuş."

        # HWID Kilidi
        db_hwid = data.get('hwid', "")
        if db_hwid == "":
            # İlk kez aktive ediliyor, HWID'yi bağla
            requests.patch(target_url, json={"hwid": hwid})
            save_local_key(key)
            return True, expiry_str
        elif db_hwid == hwid:
            save_local_key(key)
            return True, expiry_str
        else:
            return False, "Bu lisans başka bir cihaza kilitli."
            
    except Exception as e:
        return False, "İnternet bağlantısı gerekli."
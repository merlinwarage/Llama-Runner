"""settings_store (split from server_panel.py)"""
import configparser
import os

from server.constants import DEFAULT_SRV


def load_srv_settings(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.isfile(path):
        cp.read(path, encoding="utf-8-sig")
    s = dict(DEFAULT_SRV)
    for k in DEFAULT_SRV:
        if cp.has_option("server", k):
            s[k] = cp.get("server", k).strip()
    s["models_ini"] = cp.get("paths", "models_ini", fallback="models.ini").strip() or "models.ini"
    s["last_model"] = cp.get("state", "server_last_model", fallback="").strip()
    s["gguf_dir"] = cp.get("state", "gguf_dir", fallback="").strip()
    return s

def write_setting(path, section, kv):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.isfile(path):
        cp.read(path, encoding="utf-8-sig")
    if not cp.has_section(section):
        cp.add_section(section)
    for k, v in kv.items():
        cp.set(section, k, str(v))
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)

"""netutil (split from server_panel.py)"""
import os
import socket
import webbrowser

from server.constants import IS_WIN


def port_busy(port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
            return True
    except Exception:
        return False

def open_url(url):
    ok = False
    try:
        ok = webbrowser.open(url)
    except Exception:
        pass
    if not ok and IS_WIN:
        try:
            os.startfile(url)
            ok = True
        except Exception:
            pass
    return ok

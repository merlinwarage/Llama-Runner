"""runner (split from server_panel.py)"""

class Runner:
    def __init__(self, name):
        self.name = name
        self.proc = None
        self.lines = []
        self.state = "idle"
        self.started = None
        self.host, self.port = "127.0.0.1", "8080"
        self.pp = self.tg = ""
        self.stopping = False
        self.probing = False
        self.code = None

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

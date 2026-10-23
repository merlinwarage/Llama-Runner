"""BenchPanel: llama-bench view, composed from per-view mixins."""
import os
import queue
import tkinter as tk

from bench.constants import SETTINGS_FILE
from bench.settings_store import load_settings

from bench.views.shell import ShellMixin
from bench.views.run import RunViewMixin
from bench.views.models import ModelsMixin
from bench.views.settings import SettingsMixin
from bench.views.output import OutputMixin
from bench.services.runner import RunnerMixin
from bench.views.common import CommonMixin


class BenchPanel(
    ShellMixin,
    RunViewMixin,
    ModelsMixin,
    SettingsMixin,
    OutputMixin,
    RunnerMixin,
    CommonMixin,
    tk.Frame,
):
    def __init__(self, master, T, Btn, fonts, app_dir):
        super().__init__(master, bg=T["bg"])
        self.T, self.Btn, self.F, self.app_dir = T, Btn, fonts, app_dir
        self.settings_path = os.path.join(app_dir, SETTINGS_FILE)
        self.cfg = load_settings(self.settings_path)
        self.models, self.model_names, self.visible = {}, [], []
        self.selected = None
        self.q = queue.Queue()
        self.proc = None
        self.running = False
        self.stop_flag = False
        self.vars = {}
        self._build()
        self.reload_models()
        self.after(50, self._pump)

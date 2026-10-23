"""ServerPanel: llama-server runner view, composed from per-view mixins."""
import os
import queue
import tkinter as tk

from server.constants import SETTINGS_FILE
from server.ini_doc import IniDoc
from server.settings_store import load_srv_settings

from server.views.shell import ShellMixin
from server.views.header import HeaderMixin
from server.views.console import ConsoleMixin
from server.views.sidebar import SidebarMixin
from server.views.settings import SettingsMixin
from server.views.config.general import ConfigGeneralMixin
from server.views.config.advanced import ConfigAdvancedMixin
from server.views.config.form import ConfigFormMixin
from server.views.config.actions import ModelActionsMixin
from server.services.ini_store import IniStoreMixin
from server.services.mcp import McpMixin
from server.services.process import ProcessMixin
from server.views.common import CommonMixin


class ServerPanel(
    ShellMixin,
    HeaderMixin,
    ConsoleMixin,
    SidebarMixin,
    SettingsMixin,
    ConfigGeneralMixin,
    ConfigAdvancedMixin,
    ConfigFormMixin,
    ModelActionsMixin,
    IniStoreMixin,
    McpMixin,
    ProcessMixin,
    CommonMixin,
    tk.Frame,
):
    def __init__(self, master, T, Btn, fonts, app_dir, on_ini_changed=None, on_activate=None):
        super().__init__(master, bg=T["bg"])
        self.T, self.Btn, self.F, self.app_dir = T, Btn, fonts, app_dir
        self.on_ini_changed, self.on_activate = on_ini_changed, on_activate
        self.settings_path = os.path.join(app_dir, SETTINGS_FILE)
        self.s = load_srv_settings(self.settings_path)
        self.runners, self.items, self.visible = {}, {}, []
        self.selected = None
        self.dirty = False
        self._loading = False
        self._comment_orig = ""
        self.q = queue.Queue()
        self.restart = set()
        self.pending_start = None
        self.pending = []
        self.tab = "config"
        self.doc = IniDoc()
        self.ini_path, self.ini_mtime, self.ini_err = "", None, None
        self.fvars, self.hints, self.flagvars, self.svars = {}, {}, {}, {}
        self.advvars, self.adv_hints, self.adv_groups = {}, {}, []
        self.mcp_var = tk.StringVar(value="default")
        self._flash_id = None
        self._build()
        self.after(40, self._pump)
        self.after(1000, self._tick)

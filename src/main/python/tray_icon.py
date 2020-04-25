import sys
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu

class TrayIcon(QSystemTrayIcon):
    def __init__(self, default_icon, _new_song_icon, parent=None):
        super().__init__(default_icon, parent)

        menu = QMenu(parent)
        exit_ = menu.addAction('Exit')
        exit_.triggered.connect(lambda: sys.exit())
        self.setContextMenu(menu)

        self._default_icon = default_icon
        self._new_song_icon = _new_song_icon

    def set_default_icon(self):
        if self._default_icon is not None:
            self.setIcon(self._default_icon)

    def set_new_song_icon(self):
        if self._new_song_icon is not None:
            self.setIcon(self._new_song_icon)

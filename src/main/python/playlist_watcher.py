from PyQt5.QtWidgets import QLineEdit, QSpinBox, QDateTimeEdit, QPushButton, QTableView, \
    QMainWindow, QSystemTrayIcon
from PyQt5 import uic
from PyQt5.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt5.QtCore import QSettings, QTimer, Qt, QDateTime
from yandex_music.client import Client, Playlist
from tray_icon import TrayIcon

SETTINGS_URL = 'settings/url'
SETTINGS_UPDATE_PERIOD = 'settings/update_period'

class PlaylistWatcher(QMainWindow):
    def __init__(self, app_context):
        super().__init__()
        uic.loadUi(app_context.get_resource('mainwindow.ui'), self)

        self._playlist_url_edit = self.findChild(QLineEdit, 'playlistUrlEdit')
        self._update_interval_edit = self.findChild(QSpinBox, 'updateIntervalEdit')
        self._last_modified_edit = self.findChild(QDateTimeEdit, 'lastModifiedEdit')
        self._tracks_count_edit = self.findChild(QSpinBox, 'tracksCountEdit')
        self._watch_button = self.findChild(QPushButton, 'watchButton')
        self._playlist_view = self.findChild(QTableView, 'playlistView')

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_playlist)

        self._settings = QSettings('settings.ini', QSettings.IniFormat, self)
        self._playlist_url_edit.setText(self._settings.value(SETTINGS_URL, ''))
        self._update_interval_edit.setValue(self._settings.value(SETTINGS_UPDATE_PERIOD, 5, type=int))

        self._playlist_view_model = QStandardItemModel(self)
        self._playlist_view_model.setColumnCount(2)
        self._playlist_view_model.setHeaderData(0, Qt.Horizontal, 'Artist')
        self._playlist_view_model.setHeaderData(1, Qt.Horizontal, 'Song')
        self._playlist_view.setModel(self._playlist_view_model)
        horizontal_header = self._playlist_view.horizontalHeader()
        horizontal_header.setStretchLastSection(True)

        self._watch_button.clicked.connect(self._toggle_watch)
        self._playlist_url_edit.editingFinished.connect(self._save_url)
        self._update_interval_edit.valueChanged[int].connect(self._save_update_period)

        self._tray_icon = TrayIcon(QIcon(app_context.get_resource('tree.ico')), \
            QIcon(app_context.get_resource('squirrel.ico')), self)
        self._tray_icon.show()
        self._tray_icon.messageClicked.connect(self._on_tray_message_clicked)
        self._tray_icon.activated.connect(self._on_tray_icon_activated)
        self._tray_icon_message_icon = app_context.get_resource('squirrel.png')

        self._yandex_music_client = Client(None, False)
        self._playlist_url = None

    def _toggle_watch(self):
        if self._timer.isActive():
            self._timer.stop()
            self._watch_button.setText('Watch')
            self._playlist_url_edit.setDisabled(False)
            self._update_interval_edit.setDisabled(False)
            self._last_modified_edit.setDisabled(True)
            self._tracks_count_edit.setDisabled(True)
            self._clear_playlist()
        else:
            url = self._playlist_url_edit.text()
            split = url.split('/', 3)
            if len(split) < 4:
                return

            self._playlist_url = f'{self._yandex_music_client.base_url}/{split[3]}'

            self._update_playlist()
            interval = self._update_interval_edit.value() * 60 * 1000 # minutes to ms
            self._timer.start(interval)
            self._watch_button.setText('Stop watching')
            self._playlist_url_edit.setDisabled(True)
            self._update_interval_edit.setDisabled(True)
            self._last_modified_edit.setDisabled(False)
            self._tracks_count_edit.setDisabled(False)

    def _update_playlist(self):
        result = self._yandex_music_client.request.get(self._playlist_url)

        pls = Playlist.de_json(result, self._yandex_music_client)
        if pls is None:
            self._clear_playlist()
            return

        last_modified = QDateTime.fromString(pls.modified, Qt.ISODate).toLocalTime()
        if last_modified == self._last_modified_edit.dateTime():
            return
        self._last_modified_edit.setDateTime(last_modified)

        tracks_count = len(pls.tracks)
        diff = tracks_count - self._tracks_count_edit.value()
        self._tracks_count_edit.setValue(tracks_count)
        self._playlist_view_model.setRowCount(tracks_count)

        if tracks_count == 0:
            return

        start_index = 0
        if diff > 0:
            start_index = tracks_count - diff

        tracks = []
        if pls.tracks[0].track is None:
            track_ids = []
            for track in pls.tracks[start_index:]:
                track_ids.append('{0}:{1}'.format(track.id, track.album_id))
            tracks = self._yandex_music_client.tracks(track_ids)
        else:
            for track in pls.tracks[start_index:]:
                tracks.append(track.track)

        row = start_index
        for track in tracks:
            artist_item = QStandardItem(track.artists[0].name)
            song_item = QStandardItem(track.title)
            self._playlist_view_model.setItem(row, 0, artist_item)
            self._playlist_view_model.setItem(row, 1, song_item)
            row += 1

        if  0 < diff < tracks_count:
            track = tracks[diff-1]
            songs = []
            for track in tracks:
                songs.append('{0} - {1}'.format(track.artists[0].name, track.title))
            self._tray_icon.showMessage("Аааааааааааа!", \
                "Добавились новые песенки: {0}, иди слушай скорей!".format(', '.join(songs)), \
                QIcon(self._tray_icon_message_icon), 30000)
            self._tray_icon.set_new_song_icon()

    def _save_url(self):
        self._settings.setValue(SETTINGS_URL, self._playlist_url_edit.text())
        self._settings.sync()

    def _save_update_period(self):
        self._settings.setValue(SETTINGS_UPDATE_PERIOD, self._update_interval_edit.value())
        self._settings.sync()

    def _on_tray_message_clicked(self):
        self.show()
        self.raise_()
        self.setFocus()
        self._tray_icon.set_default_icon()

    def _on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show()
            self.raise_()
            self.setFocus()
            self._tray_icon.set_default_icon()

    def _clear_playlist(self):
        self._tracks_count_edit.setValue(0)
        self._last_modified_edit.setDateTime(self._last_modified_edit.minimumDateTime())
        self._playlist_view_model.setRowCount(0)
        self._tray_icon.set_default_icon()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

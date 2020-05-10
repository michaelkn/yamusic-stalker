from PyQt5.QtWidgets import QLineEdit, QSpinBox, QDateTimeEdit, QPushButton, QTableView, \
    QMainWindow, QSystemTrayIcon, QAbstractItemView, QToolButton
from PyQt5 import uic
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import QSettings, QTimer, Qt, QDateTime, QUrl
from PyQt5.QtSql import QSqlRelation, QSqlTableModel
from yandex_music.client import Client, Playlist
from tray_icon import TrayIcon
from song_database import SongDatabase
from playlist_view_model import PlaylistViewModel

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

        self._song_db = SongDatabase('songs.sqlite')
        self._playlist_model = PlaylistViewModel(self)
        self._playlist_model.setTable('playlist')
        self._playlist_model.setRelation(3, QSqlRelation('songs', 'track_id', 'artist'))
        self._playlist_model.setRelation(4, QSqlRelation('songs', 'track_id', 'title'))
        self._playlist_model.setSort(1, Qt.AscendingOrder)
        self._playlist_model.setHeaderData(3, Qt.Horizontal, 'Artist')
        self._playlist_model.setHeaderData(4, Qt.Horizontal, 'Title')
        self._playlist_model.setEditStrategy(QSqlTableModel.OnFieldChange)
        self._playlist_model.select()
        self._tracks_count_edit.setValue(self._playlist_model.rowCount())

        self._playlist_view.setModel(self._playlist_model)
        self._playlist_view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._playlist_view.setSelectionMode(QAbstractItemView.NoSelection)
        self._playlist_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._playlist_view.setColumnHidden(0, True)
        self._playlist_view.setColumnHidden(1, True)
        self._playlist_view.setColumnHidden(2, True)
        horizontal_header = self._playlist_view.horizontalHeader()
        horizontal_header.setStretchLastSection(True)
        self._playlist_view.clicked.connect(self._on_song_clicked)

        self._watch_button.clicked.connect(self._toggle_watch)
        self._playlist_url_edit.editingFinished.connect(self._save_url)
        self._update_interval_edit.valueChanged[int].connect(self._save_update_period)
        open_playlist_button = self.findChild(QToolButton, 'openPlaylistButton')
        open_playlist_button.clicked.connect(self._open_playlist_url)

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
        playlist_json = self._yandex_music_client.request.get(self._playlist_url)
        playlist = Playlist.de_json(playlist_json, self._yandex_music_client)
        if playlist is None:
            self._clear_playlist()
            return

        last_modified = QDateTime.fromString(playlist.modified, Qt.ISODate).toLocalTime()
        if last_modified == self._last_modified_edit.dateTime():
            return
        self._last_modified_edit.setDateTime(last_modified)

        old_position_by_track = self._song_db.get_playlist()
        new_position_by_track = {playlist.tracks[i].id: i for i in range(len(playlist.tracks))}

        old_tracks = set(old_position_by_track.keys())
        new_tracks = set(new_position_by_track.keys())
        common_tracks = new_tracks.intersection(old_tracks)
        added_tracks = new_tracks - common_tracks
        removed_tracks = old_tracks - common_tracks
        changed_tracks = list()
        for track_id in common_tracks:
            if old_position_by_track[track_id] != new_position_by_track[track_id]:
                changed_tracks.append((track_id, new_position_by_track[track_id]))

        if len(removed_tracks) > 0:
            self._song_db.remove_tracks(removed_tracks)

        if len(changed_tracks) > 0:
            self._song_db.update_tracks_position(changed_tracks)

        if len(added_tracks) > 0:
            positions = list()
            for track_id in added_tracks:
                position = new_position_by_track[track_id]
                positions.append(position)
                if not self._song_db.has_song(track_id):
                    self._add_track(playlist.tracks[position])
            self._song_db.add_tracks(list(added_tracks), positions)
            songs = self._song_db.get_songs(added_tracks)
            self._tray_icon.showMessage('Аааааааааааа!',
                                        ('Добавились новые '
                                         'песенки: {0}, иди слушай скорей!')
                                        .format(', '.join(songs)),
                                        QIcon(self._tray_icon_message_icon), 15000)
            self._tray_icon.set_new_song_icon()

        self._playlist_model.select()
        self._tracks_count_edit.setValue(self._playlist_model.rowCount())

    def _add_track(self, track):
        track_info = None
        if track.track is None:
            full_tracks = self._yandex_music_client.tracks(track.track_id)
            if len(full_tracks) > 0:
                track_info = full_tracks[0]
        else:
            track_info = track.track
        if track_info is not None:
            self._song_db.add_song(track.id, track_info.albums[0].id, track_info.title, track_info.artists)

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
        self._tray_icon.set_default_icon()

    def _open_playlist_url(self):
        url = self._playlist_url_edit.text()
        QDesktopServices.openUrl(QUrl(url, QUrl.TolerantMode))

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def _on_song_clicked(self, index):
        self._playlist_model.reset_is_new_flag(index)

from typing import List, Dict
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
import log

DB_USER_VERSION = 1

class SongDatabase():
    def __init__(self, db_path):
        self._logger = log.get_logger(__name__)
        db_ = QSqlDatabase.addDatabase('QSQLITE')
        db_.setDatabaseName(db_path)
        if not db_.open():
            self._logger.error('Cannot open database: %s', db_.lastError())
            return

        tables = db_.tables()
        if len(tables) == 0:
            self._create_tables()
        elif not self._check_and_update_version():
            db_.close()

    def _create_tables(self) -> None:
        query = QSqlQuery()
        query.exec(('CREATE TABLE IF NOT EXISTS songs '
                    '(track_id INTEGER NOT NULL UNIQUE, '
                    'album_id INTEGER NOT NULL, '
                    'title TEXT, '
                    'artist TEXT, '
                    'PRIMARY KEY (track_id));'))
        query.exec(('CREATE TABLE IF NOT EXISTS playlist '
                    '(id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE, '
                    'position INTEGER NOT NULL, '
                    'is_new INTEGER NOT NULL, '
                    'title INTEGER NOT NULL, '
                    'artist INTEGER NOT NULL, '
                    'timestamp TEXT);'))
        query.exec('PRAGMA user_version = {0}'.format(DB_USER_VERSION))

    def _check_and_update_version(self) -> bool:
        query = QSqlQuery()
        query.exec('PRAGMA user_version')
        if not query.next():
            self._logger.error('Cannot get user_version: %s', query.lastError())
            return False

        version = query.value(0)
        if version == DB_USER_VERSION:
            return True
        if version > DB_USER_VERSION:
            self._logger.error('DB version %d is greater than app verison %d', \
                version, DB_USER_VERSION)
            return False
        if version == 0:
            query.exec('DELETE FROM playlist')
            query.exec('ALTER TABLE playlist ADD COLUMN timestamp TEXT')

        query.exec('PRAGMA user_version = {0}'.format(DB_USER_VERSION))
        return True

    def has_song(self, track_id) -> bool:
        query = QSqlQuery('SELECT 1 FROM songs WHERE track_id = {0}'.format(track_id))
        return query.next()

    def add_song(self, track_id, album_id, title, artist_info) -> None:
        artists = []
        for artist in artist_info:
            artists.append(artist.name)
        artist = ', '.join(artists)
        query = QSqlQuery()
        query.prepare(('INSERT INTO songs (track_id, album_id, title, artist) '
                       'VALUES (:track_id, :album_id, :title, :artist)'))
        query.bindValue(':track_id', track_id)
        query.bindValue(':album_id', album_id)
        query.bindValue(':title', title)
        query.bindValue(':artist', artist)
        if not query.exec():
            self._logger.warning('Unable to add song: %s', query.lastError())

    def get_songs(self, track_ids) -> List[str]:
        songs = list()
        query = QSqlQuery()
        for track_id in track_ids:
            query.exec(('SELECT artist, title FROM songs '
                        'WHERE track_id = {0}').format(track_id))
            if query.next():
                songs.append('{0} - {1}'.format(query.value(0), query.value(1)))
        return songs

    def get_playlist(self) -> Dict[int, int]:
        songs = dict()
        query = QSqlQuery()
        query.setForwardOnly(True)
        query.exec('SELECT title, position FROM playlist')
        while query.next():
            songs[query.value(0)] = query.value(1)
        return songs

    def add_tracks(self, track_ids, positions, is_new, timestamps) -> None:
        query = QSqlQuery()
        query.prepare(('INSERT INTO playlist (position, is_new, title, artist, timestamp)'
                       ' VALUES (?, ?, ?, ?, ?)'))
        query.addBindValue(positions)
        query.addBindValue([is_new]*len(positions))
        query.addBindValue(track_ids)
        query.addBindValue(track_ids)
        query.addBindValue(timestamps)
        if not query.execBatch():
            self._logger.warning('Insert tracks query has failed: %s', query.lastError())

    def remove_tracks(self, track_ids) -> None:
        query = QSqlQuery()
        for track_id in track_ids:
            query.exec(('DELETE FROM playlist '
                        'WHERE title = {0}').format(track_id))

    def update_tracks_position(self, position_by_track) -> None:
        query = QSqlQuery()
        for track_id, position in position_by_track:
            query.exec(('UPDATE playlist SET position = {0} '
                        'WHERE title = {1}')
                       .format(position, track_id))

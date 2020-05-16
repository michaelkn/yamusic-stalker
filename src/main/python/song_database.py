from typing import List, Dict
from PyQt5.QtSql import QSqlDatabase, QSqlQuery

class SongDatabase():
    def __init__(self, db_path):
        db_ = QSqlDatabase.addDatabase('QSQLITE')
        db_.setDatabaseName(db_path)
        if not db_.open():
            print(db_.lastError())
            return

        db_.exec(('CREATE TABLE IF NOT EXISTS songs '
                  '(track_id INTEGER NOT NULL UNIQUE, '
                  'album_id INTEGER NOT NULL, '
                  'title TEXT, '
                  'artist TEXT, '
                  'PRIMARY KEY (track_id));'))
        db_.exec(('CREATE TABLE IF NOT EXISTS playlist '
                  '(id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE, '
                  'position INTEGER NOT NULL, '
                  'is_new INTEGER NOT NULL, '
                  'title INTEGER NOT NULL, '
                  'artist INTEGER NOT NULL);'))

    def has_song(self, track_id) -> bool:
        query = QSqlQuery()
        if not query.exec('SELECT 1 FROM songs WHERE track_id = {0}'.format(track_id)):
            return None
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
        query.exec()

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

    def add_tracks(self, track_ids, positions):
        query = QSqlQuery()
        query.prepare(('INSERT INTO playlist (position, is_new, title, artist)'
                       ' VALUES (?, ?, ?, ?)'))
        query.addBindValue(positions)
        query.addBindValue([1]*len(positions))
        query.addBindValue(track_ids)
        query.addBindValue(track_ids)
        query.execBatch()

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

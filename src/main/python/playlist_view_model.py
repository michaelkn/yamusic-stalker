from PyQt5.QtSql import QSqlRelationalTableModel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

IS_NEW_COLUMN = 2

class PlaylistViewModel(QSqlRelationalTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.BackgroundColorRole:
            if super().data(self.index(index.row(), IS_NEW_COLUMN)) == 1:
                return QColor('gold')
        return super().data(index, role)

    def reset_is_new_flag(self, index):
        row = index.row()
        is_new_index = self.index(row, IS_NEW_COLUMN)
        self.setData(is_new_index, 0)

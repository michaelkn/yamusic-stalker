import sys
import logging
from fbs_runtime.application_context.PyQt5 import ApplicationContext
from PyQt5.QtCore import QCoreApplication
from playlist_watcher import PlaylistWatcher
import log

def main():
    logging.basicConfig(level=logging.DEBUG, handlers=[log.get_file_handler()])
    QCoreApplication.setOrganizationName('quant-cyber')
    QCoreApplication.setApplicationName('Yandex Music Stalker')
    app_context = ApplicationContext()
    window = PlaylistWatcher(app_context)
    window.show()
    exit_code = app_context.app.exec_()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()

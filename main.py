# -*- coding: utf-8 -*-

import sys
import os
import subprocess
from urllib.parse import urlparse

# --- Wybór biblioteki GUI ---
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLineEdit, QPushButton, QLabel, QListWidget, QProgressBar,
        QFileDialog, QMessageBox, QComboBox, QListWidgetItem, QStyleFactory
    )
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
    from PyQt6.QtGui import QPalette, QColor
    GUI_LIB = "PyQt6"
except ImportError:
    try:
        from PyQt5.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QLineEdit, QPushButton, QLabel, QListWidget, QProgressBar,
            QFileDialog, QMessageBox, QComboBox, QListWidgetItem, QStyleFactory
        )
        from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
        from PyQt5.QtGui import QPalette, QColor
        GUI_LIB = "PyQt5"
    except ImportError:
        print("Błąd: Zainstaluj PyQt6 lub PyQt5 (`pip install PyQt6` lub `pip install PyQt5`)")
        sys.exit(1)

# --- Import yt-dlp ---
try:
    import yt_dlp
except ImportError:
    print("Błąd: Zainstaluj yt-dlp (`pip install yt-dlp`)")
    sys.exit(1)

# --- Sprawdzenie dostępności FFmpeg ---
def check_ffmpeg():
    try:
        subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True, check=True,
            text=True,
            startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.CREATE_NO_WINDOW)
              if sys.platform == 'win32' else None
        )
        print("FFmpeg znaleziony.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Ostrzeżenie: FFmpeg nie znaleziono w PATH. Może być wymagany do łączenia niektórych formatów.")
        return False

FFMPEG_AVAILABLE = check_ffmpeg()


# =============================================================================
# Klasa DownloadWorker (obsługa pobierania w osobnym wątku)
# =============================================================================
class DownloadWorker(QThread):
    progress_signal = pyqtSignal(str, int)      # (task_id, percent)
    status_signal   = pyqtSignal(str, str)      # (task_id, status_message)
    finished_signal = pyqtSignal(str, str, str) # (task_id, final_status, info)
    info_signal     = pyqtSignal(str, dict)     # (task_id, video_info)

    def __init__(self, task_id, url, save_path, quality_format, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self.url = url
        self.save_path = save_path
        self.quality_format = quality_format
        self._is_running = True
        self.ydl_instance = None

    def _progress_hook(self, d):
        if not self._is_running:
            raise yt_dlp.utils.DownloadError("Pobieranie przerwane przez użytkownika.")

        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes_estimate') or d.get('total_bytes')
            done  = d.get('downloaded_bytes')
            if total and done:
                percent = int(done / total * 100)
                if percent % 2 == 0 or percent == 100:
                    self.progress_signal.emit(self.task_id, percent)

            fn    = os.path.basename(d.get('filename', 'plik'))
            sp    = d.get('speed', 0) or 0
            speed = f"{sp/1024/1024:.2f} MB/s" if sp else "N/A"
            eta   = d.get('eta', 0) or 0
            eta_s = f"{int(eta//60):02d}:{int(eta%60):02d}" if eta else "N/A"
            msg = f"Pobieranie: {fn} ({percent}%) @ {speed}, ETA: {eta_s}"
            self.status_signal.emit(self.task_id, msg)

        elif status == 'finished':
            self.status_signal.emit(self.task_id, "Pobieranie zakończone, przetwarzanie...")
        elif status == 'error':
            self.status_signal.emit(self.task_id, "Błąd pobierania")

    def run(self):
        if not self._is_running:
            self.finished_signal.emit(self.task_id, "Przerwano", "")
            return

        self.status_signal.emit(self.task_id, "Rozpoczynanie...")

        try:
            ydl_opts = {
                'format': self.quality_format,
                'outtmpl': os.path.join(self.save_path, '%(title)s [%(id)s].%(ext)s'),
                'progress_hooks': [self._progress_hook],
                'noplaylist': True,
                'merge_output_format': 'mp4',
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
                'quiet': True,
                'no_warnings': True,
            }
            self.ydl_instance = yt_dlp.YoutubeDL(ydl_opts)

            self.status_signal.emit(self.task_id, "Pobieranie informacji...")
            info = self.ydl_instance.extract_info(self.url, download=False)
            title = info.get('title', 'Nieznany tytuł')
            self.info_signal.emit(self.task_id, {'title': title})

            self.status_signal.emit(self.task_id, "Rozpoczynanie pobierania...")
            if self._is_running:
                self.ydl_instance.download([self.url])

            final = "Ukończono" if self._is_running else "Przerwano"
            self.finished_signal.emit(self.task_id, final, title)

        except yt_dlp.utils.DownloadError as e:
            err = f"Błąd yt-dlp: {e}"
            print(f"[{self.task_id}] {err}")
            self.finished_signal.emit(self.task_id, "Błąd", err)

        except Exception as e:
            err = f"Nieoczekiwany błąd: {e}"
            print(f"[{self.task_id}] {err}")
            self.finished_signal.emit(self.task_id, "Błąd", err)

        finally:
            self.ydl_instance = None

    def stop(self):
        self._is_running = False
        self.status_signal.emit(self.task_id, "Przerywanie...")
        print(f"[{self.task_id}] Sygnał stop wysłany.")


# =============================================================================
# Klasa MainWindow (Główne okno aplikacji)
# =============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader GUI")
        self.setGeometry(100, 100, 700, 500)

        QApplication.setStyle(QStyleFactory.create('Fusion'))

        self.save_directory = os.path.expanduser("~")
        self.download_queue = {}
        self.current_task_id_counter = 0
        self.active_download_task_id = None

        self.init_ui()

        if not FFMPEG_AVAILABLE:
            QMessageBox.warning(
                self, "Brak FFmpeg",
                "Nie znaleziono programu FFmpeg w PATH.\n"
                "Pobieranie w najwyższej jakości może nie działać poprawnie."
            )

    def init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main = QVBoxLayout(central)

        # Wprowadzanie linku
        link_lay = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Wklej link do filmu YouTube...")
        self.add_button = QPushButton("Dodaj do kolejki")
        self.add_button.clicked.connect(self.add_to_queue)
        link_lay.addWidget(QLabel("Link:"))
        link_lay.addWidget(self.url_input)
        link_lay.addWidget(self.add_button)
        main.addLayout(link_lay)

        # Lista kolejki
        main.addWidget(QLabel("Kolejka pobierania:"))
        self.queue_list = QListWidget()
        self.queue_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        main.addWidget(self.queue_list)

        # Kontrolki kolejki
        qc = QHBoxLayout()
        self.remove_button = QPushButton("Usuń zaznaczone")
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button  = QPushButton("Wyczyść kolejkę")
        self.clear_button.clicked.connect(self.clear_queue)
        qc.addWidget(self.remove_button)
        qc.addWidget(self.clear_button)
        qc.addStretch()
        main.addLayout(qc)

        # Jakość + ścieżka
        settings = QHBoxLayout()
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("Najlepsza dostępna (MP4)", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best")
        self.quality_combo.addItem("Najlepsza dostępna (WebM)", "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best")
        self.quality_combo.addItem("Max 1080p (MP4)", "bestvideo[height<=?1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=?1080][ext=mp4]/best[ext=mp4]/best")
        self.quality_combo.addItem("Max 720p (MP4)", "bestvideo[height<=?720][ext=mp4]+bestaudio[ext=m4a]/best[height<=?720][ext=mp4]/best[ext=mp4]/best")
        self.quality_combo.addItem("Max 480p (MP4)", "bestvideo[height<=?480][ext=mp4]+bestaudio[ext=m4a]/best[height<=?480][ext=mp4]/best[ext=mp4]/best")
        self.quality_combo.addItem("Tylko Audio (najlepsze)", "bestaudio/best")
        self.quality_combo.addItem("Tylko Audio (M4A)", "bestaudio[ext=m4a]/bestaudio")
        self.quality_combo.addItem("Tylko Audio (MP3 - wymaga konwersji)", "bestaudio/best")
        self.quality_combo.setCurrentIndex(0)

        self.save_path_btn = QPushButton("Zmień folder zapisu")
        self.save_path_btn.clicked.connect(self.select_save_directory)
        self.save_path_label = QLabel(f"Zapisz w: {self.save_directory}")
        self.save_path_label.setWordWrap(True)

        settings.addWidget(QLabel("Jakość:"))
        settings.addWidget(self.quality_combo)
        settings.addWidget(self.save_path_btn)
        settings.addStretch()
        main.addLayout(settings)
        main.addWidget(self.save_path_label)

        # Pasek postępu i przyciski
        prog = QHBoxLayout()
        self.progress_bar  = QProgressBar()
        self.progress_bar.setValue(0)
        self.start_button  = QPushButton("Rozpocznij pobieranie")
        self.start_button.clicked.connect(self.start_next_download)
        self.start_button.setEnabled(False)
        self.cancel_button = QPushButton("Anuluj bieżące")
        self.cancel_button.clicked.connect(self.cancel_current_download)
        self.cancel_button.setEnabled(False)
        prog.addWidget(self.progress_bar)
        prog.addWidget(self.start_button)
        prog.addWidget(self.cancel_button)
        main.addLayout(prog)

        # Status
        self.status_label = QLabel("Gotowy.")
        main.addWidget(self.status_label)

        central.setLayout(main)

    def generate_task_id(self):
        self.current_task_id_counter += 1
        return f"task_{self.current_task_id_counter}"

    def add_to_queue(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Pusty link", "Wprowadź link do YouTube.")
            return
        parsed = urlparse(url)
        if not (parsed.scheme in ('http','https') and parsed.netloc.endswith(('youtube.com','youtu.be'))):
            QMessageBox.warning(self, "Nieprawidłowy link", "To nie wygląda na link YouTube.")
            return

        tid = self.generate_task_id()
        item = QListWidgetItem(f"[{tid}] {url} - Oczekuje")
        item.setData(Qt.ItemDataRole.UserRole, tid)
        self.queue_list.addItem(item)
        self.download_queue[tid] = {
            'url': url, 'widget_item': item,
            'worker': None, 'status': 'Oczekuje', 'progress': 0
        }
        self.url_input.clear()
        self.update_start_button_state()

    def remove_selected(self):
        sel = self.queue_list.selectedItems()
        if not sel:
            QMessageBox.information(self, "Nic nie zaznaczono", "Zaznacz element, aby usunąć.")
            return
        item = sel[0]
        tid = item.data(Qt.ItemDataRole.UserRole)
        if tid == self.active_download_task_id:
            QMessageBox.warning(self, "W toku", "Anuluj bieżące przed usunięciem.")
            return
        del self.download_queue[tid]
        self.queue_list.takeItem(self.queue_list.row(item))
        self.update_start_button_state()

    def clear_queue(self):
        if self.active_download_task_id:
            QMessageBox.warning(self, "W toku", "Anuluj bieżące przed czyszczeniem.")
            return
        if not self.download_queue:
            QMessageBox.information(self, "Pusta kolejka", "Brak zadań.")
            return
        rep = QMessageBox.question(
            self, "Usuń wszystkie?", "Na pewno usunąć wszystkie zadania?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if rep == QMessageBox.StandardButton.Yes:
            self.download_queue.clear()
            self.queue_list.clear()
            self.status_label.setText("Kolejka wyczyszczona.")
            self.update_start_button_state()

    def select_save_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Wybierz folder", self.save_directory)
        if d:
            self.save_directory = d
            self.save_path_label.setText(f"Zapisz w: {d}")

    def update_start_button_state(self):
        can = any(t['status'] == 'Oczekuje' for t in self.download_queue.values()) \
              and self.active_download_task_id is None
        self.start_button.setEnabled(can)
        self.cancel_button.setEnabled(self.active_download_task_id is not None)

    def start_next_download(self):
        if self.active_download_task_id:
            return
        next_tid = next((tid for tid,t in self.download_queue.items() if t['status'] == 'Oczekuje'), None)
        if not next_tid:
            self.status_label.setText("Brak zadań.")
            return

        self.active_download_task_id = next_tid
        info = self.download_queue[next_tid]
        url  = info['url']
        item = info['widget_item']

        idx = self.quality_combo.currentIndex()
        fmt = self.quality_combo.itemData(idx)

        worker = DownloadWorker(next_tid, url, self.save_directory, fmt)
        worker.progress_signal.connect(self.update_progress)
        worker.status_signal.connect(self.update_status)
        worker.info_signal.connect(self.update_video_info)
        worker.finished_signal.connect(self.download_finished)

        info['worker'] = worker
        info['status'] = 'Rozpoczynanie...'
        item.setText(f"[{next_tid}] {url} - Rozpoczynanie...")
        worker.start()

        self.status_label.setText(f"Rozpoczęto: {next_tid}")
        self.progress_bar.setValue(0)
        self.update_start_button_state()

    def cancel_current_download(self):
        tid = self.active_download_task_id
        if not tid:
            return
        worker = self.download_queue[tid]['worker']
        if worker and worker.isRunning():
            worker.stop()
            self.download_queue[tid]['status'] = 'Anulowanie...'
            self.download_queue[tid]['widget_item'].setText(
                f"[{tid}] {self.download_queue[tid]['url']} - Anulowanie..."
            )
            self.status_label.setText(f"Anulowanie: {tid}")
            self.cancel_button.setEnabled(False)

    @pyqtSlot(str, dict)
    def update_video_info(self, task_id, info):
        if task_id not in self.download_queue:
            return
        ti = self.download_queue[task_id]
        title = info.get('title', ti['url'])
        if ti['status'] not in ('Ukończono', 'Błąd', 'Przerwano'):
            suffix = f" ({ti['progress']}%)" if ti['status'] == 'Pobieranie' else ""
            ti['widget_item'].setText(f"[{task_id}] {title}{suffix}")

    @pyqtSlot(str, str)
    def update_status(self, task_id, msg):
        if task_id != self.active_download_task_id:
            return

        ti = self.download_queue[task_id]
        ti['status'] = msg
        self.status_label.setText(f"[{task_id}] {msg}")

        short = msg.split(':')[0]
        base  = ti['widget_item'].text().split(' - ')[0]
        prog_txt = f" ({ti['progress']}%)" if short == "Pobieranie" else ""
        ti['widget_item'].setText(f"{base} - {short}{prog_txt}")

    @pyqtSlot(str, int)
    def update_progress(self, task_id, pct):
        if task_id != self.active_download_task_id:
            return
        self.progress_bar.setValue(pct)
        ti = self.download_queue[task_id]
        ti['progress'] = pct
        if ti['status'].startswith("Pobieranie"):
            base = ti['widget_item'].text().split(' - ')[0]
            ti['widget_item'].setText(f"{base} - Pobieranie ({pct}%)")

    @pyqtSlot(str, str, str)
    def download_finished(self, task_id, final_status, info_msg):
        if task_id not in self.download_queue:
            return
        ti = self.download_queue[task_id]
        item = ti['widget_item']
        base = item.text().split(' - ')[0]

        ti['status'] = final_status
        item.setText(f"{base} - {final_status}")

        if final_status == "Ukończono":
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Pobieranie '{info_msg}' zakończone.")
        elif final_status == "Błąd":
            self.progress_bar.setValue(0)
            self.status_label.setText("Wystąpił błąd.")
            QMessageBox.critical(self, "Błąd pobierania", info_msg)
            col = QColor("red") if GUI_LIB == "PyQt6" else Qt.GlobalColor.red
            item.setForeground(col)
        elif final_status == "Przerwano":
            self.progress_bar.setValue(0)
            self.status_label.setText("Pobieranie przerwane.")
            QMessageBox.warning(self, "Przerwane", info_msg)
            col = QColor("orange") if GUI_LIB == "PyQt6" else Qt.GlobalColor.darkYellow
            item.setForeground(col)

        if task_id == self.active_download_task_id:
            self.active_download_task_id = None
            ti['worker'] = None

        self.start_next_download()
        self.update_start_button_state()

    def closeEvent(self, event):
        if self.active_download_task_id:
            rep = QMessageBox.question(
                self, "Zamykanie",
                "Trwa pobieranie. Zamknąć i przerwać?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if rep == QMessageBox.StandardButton.Yes:
                self.cancel_current_download()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# =============================================================================
# Uruchomienie aplikacji
# =============================================================================
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

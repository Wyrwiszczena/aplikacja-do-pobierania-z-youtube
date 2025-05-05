# aplikacja-do-pobierania-z-youtube
Aplikacja która ma pobierać z youtube. Pierwszy test git hub

Myślał przez 4 s


Poniżej znajdziesz szczegółową instrukcję uruchomienia Twojej aplikacji „YouTube Downloader GUI” krok po kroku. Założyłem, że pracujesz na systemie Windows, ale dodałem też warianty dla Linux/macOS tam, gdzie to potrzebne.

---

## 1. Przygotowanie środowiska Pythona

1. **Zainstaluj Pythona 3.7+**

   * Pobierz instalator z [https://www.python.org/downloads/](https://www.python.org/downloads/)
   * Podczas instalacji zaznacz opcję **Add Python to PATH**.

2. **(Opcjonalnie) Utwórz i aktywuj wirtualne środowisko**
   Dzięki temu pip zainstaluje paczki tylko dla tego projektu.

   ```powershell
   cd ŚCIEŻKA\DO\PROJEKTU
   python -m venv .venv
   .\.venv\Scripts\activate
   ```

   Na Linux/macOS:

   ```bash
   cd /ścieżka/do/projektu
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Zaktualizuj pip**

   ```bash
   pip install --upgrade pip
   ```

---

## 2. Instalacja wymaganych pakietów Python

W katalogu projektu masz plik `requirements.txt` zawierający:

```
PyQt6
yt-dlp
```

W terminalu (z aktywnym venv, jeśli używasz):

```bash
pip install -r requirements.txt
```

> **Uwaga:** jeśli napotkasz konflikt z PyQt6, możesz spróbować z PyQt5:
>
> ```bash
> pip install PyQt5
> ```

---

## 3. Instalacja FFmpeg

Aplikacja sprawdza, czy w systemie jest dostępny program `ffmpeg` – niezbędny do łączenia (mergu) materiału wideo i audio.

* **Windows**

  1. Pobierz statyczny build FFmpeg z [https://ffmpeg.org/download.html#build-windows](https://ffmpeg.org/download.html#build-windows)
  2. Rozpakuj archiwum, np. do `C:\ffmpeg\`
  3. Dodaj ścieżkę `C:\ffmpeg\bin` do zmiennej środowiskowej `PATH`:

     * Panel Sterowania → System → Zaawansowane ustawienia systemu → Zmienne środowiskowe → w „Path” dodaj `C:\ffmpeg\bin`
  4. Otwórz nowy terminal i sprawdź:

     ```bash
     ffmpeg -version
     ```

* **Linux (Debian/Ubuntu)**

  ```bash
  sudo apt update
  sudo apt install ffmpeg
  ```

* **macOS (Homebrew)**

  ```bash
  brew install ffmpeg
  ```

Jeśli po uruchomieniu zobaczysz ostrzeżenie:

> „Ostrzeżenie: FFmpeg nie znaleziono w PATH. Może być wymagany do łączenia niektórych formatów.”

– aplikacja wciąż będzie działać, ale pobrane wideo-audio w formatach rozdzielonych (np. mkv czy webm) może nie zostać poprawnie zmergowane do MP4.

---

## 4. Uruchomienie aplikacji

1. Otwórz terminal w katalogu projektu (tam, gdzie jest `main.py`).

2. Upewnij się, że masz zainstalowane pakiety i dostępne `ffmpeg` (ew. venv aktywny).

3. Wpisz:

   ```bash
   python main.py
   ```

   lub na niektórych systemach:

   ```bash
   python3 main.py
   ```

4. Powinno otworzyć się okno GUI „YouTube Downloader GUI”.

   * Wklej link w pola „Link”,
   * wybierz jakość,
   * zmień folder zapisu (opcjonalnie),
   * naciśnij „Dodaj do kolejki” → „Rozpocznij pobieranie”.

---

## 5. (Opcjonalnie) Docker

Masz też w projekcie plik `Dockerfile`. Jeśli wolisz odpalić w kontenerze:

1. Zbuduj obraz:

   ```bash
   docker build -t yt-downloader .
   ```

2. Uruchom (montując katalog do zapisu):

   ```bash
   docker run --rm -it -v /ścieżka/do/zapisu:/downloads yt-downloader
   ```

   Wewnątrz kontenera GUI zadziała dopiero, gdy skonfigurujesz X11/Wayland (lub użyjesz VNC). Ten wariant jest przydatny bardziej do CLI-owych testów niż do GUI.

---

### Podsumowanie

1. Zainstaluj Python 3.7+
2. (Opcjonalnie) Utwórz i aktywuj wirtualne środowisko
3. `pip install -r requirements.txt`
4. Zainstaluj FFmpeg i dodaj do PATH
5. `python main.py` – gotowe!

W razie problemów daj znać, a pomogę z konkretnymi błędami.

# iospt

Download YouTube audio and send it directly to Spotify on a USB-connected iPhone.

---

## Requirements

| Tool | Install |
|---|---|
| Python 3.10+ | pre-installed on most systems |
| yt-dlp | `pip install yt-dlp` |
| ffmpeg | `sudo apt install ffmpeg` |
| ifuse | `sudo apt install ifuse` |
| libimobiledevice | `sudo apt install libimobiledevice-utils` |

> Missing tools are detected at runtime and you'll be prompted to install them automatically.

---

## Setup

1. Plug your iPhone in via USB and unlock it
2. Trust the computer on the device if prompted
3. Make sure Spotify is installed on the iPhone

---

## Usage

### Interactive mode

Run with no arguments to be guided through the process:

```bash
python iospt.py
```

You'll be prompted for a YouTube URL, then given the option to rename the track before it's copied.

---

### Single track

Pass a URL directly with `-u` to skip the interactive prompt:

```bash
python iospt.py -u "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

> Always wrap YouTube URLs in quotes — the `&` in URLs is interpreted by the shell otherwise.

---

### Playlist

Download an entire YouTube playlist into a named folder on the iPhone:

```bash
python iospt.py -p "https://www.youtube.com/playlist?list=XXXXXXXXXXX"
```

You'll be asked for a folder name. All tracks are downloaded and copied into that folder in Spotify's local files. Unavailable videos are skipped automatically.

---

### Options

| Flag | Description |
|---|---|
| `-u, --url` | YouTube video URL (single track, non-interactive) |
| `-p, --playlist` | YouTube playlist URL (bulk download) |
| `--keep` | Save a local copy of the MP3(s) in the current directory |

---

## Finding tracks in Spotify

After the script finishes, open Spotify on your iPhone:

**Settings → Local Files**

Tracks and playlist folders will appear there.

---

## Notes

- Audio is downloaded at maximum quality and converted to MP3 via ffmpeg
- Tracks are transferred over USB using ifuse — no Wi-Fi needed
- Temporary files are cleaned up automatically after each run

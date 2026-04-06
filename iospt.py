#!/usr/bin/env python3
"""
iospt.py
Downloads a YouTube video as MP3 and copies it into the Spotify
local-files folder on a USB-connected iPhone.

Dependencies (install with your package manager / pip):
  yt-dlp        – pip install yt-dlp
  ffmpeg        – sudo apt install ffmpeg
  ifuse         – sudo apt install ifuse
  libimobiledevice – sudo apt install libimobiledevice-utils
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile

SPOTIFY_BUNDLE_ID = "com.spotify.client"
MOUNT_POINT = os.path.join(tempfile.gettempdir(), "iospt_spotify_mount")

# Maps a binary name to its apt package (pip packages handled separately)
APT_PACKAGES: dict[str, str] = {
    "ffmpeg":     "ffmpeg",
    "ifuse":      "ifuse",
    "fusermount": "fuse",
}

def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, text=True,
                          capture_output=True)

def _find_tool(name: str) -> str | None:
    """Like shutil.which but also checks ~/.local/bin."""
    found = shutil.which(name)
    if found:
        return found
    local_bin = os.path.join(os.path.expanduser("~"), ".local", "bin", name)
    return local_bin if os.path.isfile(local_bin) else None

def _pip_install_cmd(package: str) -> list[str]:
    """Return the best available pip install command for *package*."""
    # Prefer pip3 / pip binaries on PATH, fall back to python -m pip
    for pip_bin in ("pip3", "pip"):
        if shutil.which(pip_bin):
            return [pip_bin, "install", "--user", package]
    # Last resort: use the running interpreter's -m pip
    return [sys.executable, "-m", "pip", "install", "--user", package]

def require_tool(name: str) -> None:
    if _find_tool(name) is not None:
        return

    if name == "yt-dlp":
        install_cmd = _pip_install_cmd("yt-dlp")
        install_desc = " ".join(install_cmd)
    elif name in APT_PACKAGES:
        install_cmd = ["sudo", "apt", "install", "-y", APT_PACKAGES[name]]
        install_desc = " ".join(install_cmd)
    else:
        sys.exit(f"[error] '{name}' not found and no install command is known. "
                 "Please install it manually.")

    print(f"[!] '{name}' not found.")
    print(f"    Install command: {install_desc}")
    answer = input("    Install now? [y/N] ").strip().lower()
    if answer != "y":
        sys.exit(f"[error] '{name}' is required. Aborting.")

    try:
        result = subprocess.run(install_cmd)
    except FileNotFoundError:
        sys.exit(f"[error] Install command not found: {install_cmd[0]}\n"
                 "        Try installing pip:  sudo apt install python3-pip")
    if result.returncode != 0:
        sys.exit(f"[error] Failed to install '{name}'. "
                 "Try running the command above manually.")

    # Re-add ~/.local/bin to PATH so newly installed tools are found
    local_bin = os.path.join(os.path.expanduser("~"), ".local", "bin")
    os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")

    if _find_tool(name) is None:
        sys.exit(f"[error] '{name}' still not found after install. "
                 "You may need to restart your shell or check your PATH.")
    print(f"[ok] '{name}' installed successfully.")

def download_mp3(url: str, output_dir: str) -> str:
    """Download audio from *url* as MP3 into *output_dir*.
    Returns the path of the downloaded file."""
    template = os.path.join(output_dir, "%(title)s.%(ext)s")
    yt_dlp_bin = _find_tool("yt-dlp") or "yt-dlp"
    run([
        yt_dlp_bin,
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--output", template,
        "--no-playlist",
        url,
    ])
    mp3_files = [f for f in os.listdir(output_dir) if f.endswith(".mp3")]
    if not mp3_files:
        sys.exit("[error] yt-dlp finished but no MP3 file was created.")
    return os.path.join(output_dir, mp3_files[0])

def download_playlist(url: str, output_dir: str) -> list[str]:
    """Download all tracks from a YouTube playlist as MP3s into *output_dir*.
    Returns a list of downloaded file paths."""
    before = set(os.listdir(output_dir))
    template = os.path.join(output_dir, "%(title)s.%(ext)s")
    yt_dlp_bin = _find_tool("yt-dlp") or "yt-dlp"
    result = subprocess.run(
        [
            yt_dlp_bin,
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--output", template,
            "--yes-playlist",
            "--ignore-errors",
            "--no-warnings",
            url,
        ],
        text=True, capture_output=True,
    )
    if result.returncode != 0:
        # Show yt-dlp's actual error output before bailing
        print(result.stderr[-2000:] if result.stderr else "(no stderr)", flush=True)
    after = set(os.listdir(output_dir))
    new_files = sorted(after - before)
    mp3_files = [f for f in new_files if f.endswith(".mp3")]
    if not mp3_files:
        sys.exit("[error] yt-dlp finished but no MP3 files were created.")
    return [os.path.join(output_dir, f) for f in mp3_files]

def mount_spotify() -> None:
    os.makedirs(MOUNT_POINT, exist_ok=True)
    result = run(
        ["ifuse", "--documents", SPOTIFY_BUNDLE_ID, MOUNT_POINT],
        check=False,
    )
    if result.returncode != 0:
        sys.exit(
            f"[error] Could not mount Spotify documents folder.\n"
            f"{result.stderr.strip()}\n\n"
            "Make sure:\n"
            "  • The iPhone is plugged in and unlocked\n"
            "  • You have trusted this computer on the device\n"
            "  • Spotify is installed on the iPhone"
        )

def unmount_spotify() -> None:
    # Kill the daemon first so fusermount doesn't block waiting for it.
    subprocess.run(
        ["pkill", "-f", f"ifuse.*{SPOTIFY_BUNDLE_ID}"],
        check=False, capture_output=True,
    )
    # Lazy unmount (-z) detaches immediately without waiting for FUSE ACKs.
    subprocess.run(["fusermount", "-uz", MOUNT_POINT], check=False, capture_output=True)

def copy_to_spotify(mp3_path: str, folder: str | None = None) -> None:
    filename = os.path.basename(mp3_path)
    dest_dir = os.path.join(MOUNT_POINT, folder) if folder else MOUNT_POINT
    os.makedirs(dest_dir, exist_ok=True)
    shutil.copyfile(mp3_path, os.path.join(dest_dir, filename))
    display = f"{folder}/{filename}" if folder else filename
    print(f"[ok] Copied '{display}' to Spotify local files.")

def rename_mp3(mp3_path: str) -> str:
    """Prompt the user to optionally rename the MP3. Returns the final path."""
    stem = os.path.splitext(os.path.basename(mp3_path))[0]
    print(f"\n  Song name: {stem}")
    new_stem = input("  Rename (leave blank to keep): ").strip()
    if not new_stem:
        return mp3_path
    new_path = os.path.join(os.path.dirname(mp3_path), new_stem + ".mp3")
    os.rename(mp3_path, new_path)
    print(f"  Renamed to: {new_stem}.mp3")
    return new_path

def main():
    parser = argparse.ArgumentParser(
        description="Download a YouTube video as MP3 and send it to "
                    "Spotify on a connected iPhone."
    )
    parser.add_argument("-u", "--url", default=None, help="YouTube video URL (skip interactive prompt)")
    parser.add_argument("-p", "--playlist", default=None, help="YouTube playlist URL — downloads all tracks without prompting")
    parser.add_argument(
        "--keep", action="store_true",
        help="Keep the downloaded MP3(s) in the current directory after copying"
    )
    args = parser.parse_args()

    for tool in ("yt-dlp", "ffmpeg", "ifuse", "fusermount"):
        require_tool(tool)

    # ── Playlist mode ────────────────────────────────────────────────────────
    if args.playlist:
        folder_name = input("  Folder name for this playlist: ").strip()
        if not folder_name:
            sys.exit("[error] No folder name provided.")

        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"\n[*] Downloading playlist: {args.playlist}")
            mp3_paths = download_playlist(args.playlist, tmpdir)
            print(f"[*] Downloaded {len(mp3_paths)} track(s).")

            if args.keep:
                keep_dir = os.path.join(os.getcwd(), folder_name)
                os.makedirs(keep_dir, exist_ok=True)
                for p in mp3_paths:
                    shutil.copy2(p, os.path.join(keep_dir, os.path.basename(p)))
                    print(f"[*] Saved local copy: {folder_name}/{os.path.basename(p)}")

            print("\n[*] Mounting Spotify documents folder on iPhone...")
            mount_spotify()
            try:
                for p in mp3_paths:
                    copy_to_spotify(p, folder=folder_name)
            finally:
                unmount_spotify()
                print("[*] Unmounted.")

        print(f"[done] {len(mp3_paths)} track(s) added to '{folder_name}'. Open Spotify on your iPhone → Settings → Local Files.")
        os._exit(0)

    # ── Single track mode ────────────────────────────────────────────────────
    if args.url:
        url = args.url
    else:
        print("iospt — YouTube → iPhone Spotify\n")
        url = input("  YouTube URL: ").strip()
        if not url:
            sys.exit("[error] No URL provided.")

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\n[*] Downloading audio from: {url}")
        mp3_path = download_mp3(url, tmpdir)
        print(f"[*] Downloaded: {os.path.basename(mp3_path)}")

        mp3_path = rename_mp3(mp3_path)

        if args.keep:
            dest_local = os.path.join(os.getcwd(), os.path.basename(mp3_path))
            shutil.copy2(mp3_path, dest_local)
            print(f"[*] Saved local copy: {dest_local}")

        print("\n[*] Mounting Spotify documents folder on iPhone...")
        mount_spotify()
        try:
            copy_to_spotify(mp3_path)
        finally:
            unmount_spotify()
            print("[*] Unmounted.")

    print("[done] Open Spotify on your iPhone → Settings → Local Files to find the track.")
    os._exit(0)

if __name__ == "__main__":
    main()
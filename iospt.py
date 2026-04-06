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

def copy_to_spotify(mp3_path: str) -> None:
    filename = os.path.basename(mp3_path)
    dest = os.path.join(MOUNT_POINT, filename)
    shutil.copyfile(mp3_path, dest)
    print(f"[ok] Copied '{filename}' to Spotify local files.")

def main():
    parser = argparse.ArgumentParser(
        description="Download a YouTube video as MP3 and send it to "
                    "Spotify on a connected iPhone."
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--keep", action="store_true",
        help="Keep the downloaded MP3 in the current directory after copying"
    )
    args = parser.parse_args()

    for tool in ("yt-dlp", "ffmpeg", "ifuse", "fusermount"):
        require_tool(tool)

    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"[*] Downloading audio from: {args.url}")
        mp3_path = download_mp3(args.url, tmpdir)
        print(f"[*] Downloaded: {os.path.basename(mp3_path)}")

        if args.keep:
            dest_local = os.path.join(os.getcwd(), os.path.basename(mp3_path))
            shutil.copy2(mp3_path, dest_local)
            print(f"[*] Saved local copy: {dest_local}")

        print("[*] Mounting Spotify documents folder on iPhone...")
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
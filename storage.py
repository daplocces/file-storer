import os
import sys
import json
import shutil
from datetime import datetime

from send2trash import send2trash

from constants import STORAGE_DIR_NAME, META_FILENAME

if getattr(sys, "frozen", False):
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

STORAGE_DIR = os.path.join(ROOT_DIR, STORAGE_DIR_NAME)
META_PATH = os.path.join(STORAGE_DIR, META_FILENAME)
SETTINGS_PATH = os.path.join(ROOT_DIR, "settings.json")
TRASH_DIR = os.path.join(STORAGE_DIR, "_session_trash")

os.makedirs(STORAGE_DIR, exist_ok=True)
if os.path.isdir(TRASH_DIR):
    shutil.rmtree(TRASH_DIR, ignore_errors=True)
os.makedirs(TRASH_DIR, exist_ok=True)


def load_meta():
    if os.path.exists(META_PATH):
        with open(META_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = {}

    changed = False
    for channel, files in raw.items():
        for fname, value in list(files.items()):
            if isinstance(value, str):
                files[fname] = {"display": value, "added": ""}
                changed = True

    if changed:
        save_meta(raw)

    return raw


def save_meta(meta):
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def load_settings():
    if os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(settings):
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def channel_dir(channel):
    return os.path.join(STORAGE_DIR, channel)


def create_channel(meta, name):
    meta[name] = {}
    os.makedirs(channel_dir(name), exist_ok=True)
    save_meta(meta)


def delete_channel(meta, name):
    shutil.rmtree(channel_dir(name), ignore_errors=True)
    del meta[name]
    save_meta(meta)


def file_exists_in_channel(meta, channel, fname):
    return fname in meta.get(channel, {})


def _unique_fname(meta, channel, fname):
    if fname not in meta[channel] and not os.path.exists(os.path.join(channel_dir(channel), fname)):
        return fname
    base, ext = os.path.splitext(fname)
    i = 1
    candidate = f"{base} ({i}){ext}"
    while candidate in meta[channel] or os.path.exists(os.path.join(channel_dir(channel), candidate)):
        i += 1
        candidate = f"{base} ({i}){ext}"
    return candidate


def add_file(meta, channel, src_path):
    fname = _unique_fname(meta, channel, os.path.basename(src_path))
    dest = os.path.join(channel_dir(channel), fname)
    shutil.copy(src_path, dest)
    meta[channel][fname] = {
        "display": fname,
        "added": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    save_meta(meta)
    return fname


def rename_file(meta, channel, fname, new_display):
    meta[channel][fname]["display"] = new_display
    save_meta(meta)


def move_file(meta, src_channel, dest_channel, fname):
    if src_channel == dest_channel:
        return fname
    entry = meta[src_channel][fname]
    new_fname = _unique_fname(meta, dest_channel, fname)
    src_path = os.path.join(channel_dir(src_channel), fname)
    dest_path = os.path.join(channel_dir(dest_channel), new_fname)
    if os.path.exists(src_path):
        shutil.move(src_path, dest_path)
    del meta[src_channel][fname]
    meta[dest_channel][new_fname] = entry
    save_meta(meta)
    return new_fname


def soft_delete_file(meta, channel, fname):
    """Moves the file into a session-only trash folder (not the real
    Recycle Bin) so Undo can restore it during this run."""
    src = os.path.join(channel_dir(channel), fname)
    token = f"{channel}__{fname}__{datetime.now().strftime('%H%M%S%f')}"
    dest = os.path.join(TRASH_DIR, token)
    entry = meta[channel].pop(fname)
    save_meta(meta)
    if os.path.exists(src):
        shutil.move(src, dest)
    return {"token": token, "channel": channel, "fname": fname, "entry": entry}


def restore_file(meta, record):
    channel = record["channel"]
    fname = record["fname"]
    entry = record["entry"]
    token = record["token"]
    if channel not in meta:
        return False
    src = os.path.join(TRASH_DIR, token)
    dest = os.path.join(channel_dir(channel), fname)
    if os.path.exists(src):
        shutil.move(src, dest)
    meta[channel][fname] = entry
    save_meta(meta)
    return True


def purge_session_trash():
    shutil.rmtree(TRASH_DIR, ignore_errors=True)
    os.makedirs(TRASH_DIR, exist_ok=True)


def display_to_fname(meta, channel, display_name):
    for fname, info in meta[channel].items():
        if info.get("display") == display_name:
            return fname
    return None


def file_info(channel, fname, entry):
    path = os.path.join(channel_dir(channel), fname)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    added = entry.get("added") or ""
    if not added and os.path.exists(path):
        added = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
    ext = os.path.splitext(fname)[1]
    ext_label = ext.lower() if ext else "—"
    return {
        "display": entry.get("display", fname),
        "added": added,
        "size": size,
        "size_text": format_bytes(size),
        "type": ext_label,
    }


def channel_size_bytes(channel):
    total = 0
    d = channel_dir(channel)
    if os.path.isdir(d):
        for f in os.listdir(d):
            fp = os.path.join(d, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total


def overall_size_bytes(meta):
    return sum(channel_size_bytes(ch) for ch in meta.keys())


def disk_usage():
    total, used, free = shutil.disk_usage(STORAGE_DIR)
    return total, used, free


def app_used_and_available(meta):
    _, _, free = disk_usage()
    app_used = overall_size_bytes(meta)
    available_for_app = app_used + free
    return app_used, available_for_app


def channel_quota_bytes(meta):
    num_channels = len(meta)
    if num_channels == 0:
        return 0
    _, available_for_app = app_used_and_available(meta)
    return available_for_app // num_channels


def enforce_channel_quota(meta, channel):
    quota = channel_quota_bytes(meta)
    d = channel_dir(channel)
    if not os.path.isdir(d):
        return []

    files = [(f, os.path.getsize(os.path.join(d, f))) for f in os.listdir(d)
              if os.path.isfile(os.path.join(d, f))]
    files.sort(key=lambda x: x[1], reverse=True)

    used = sum(sz for _, sz in files)
    trashed_display = []
    i = 0
    while used > quota and i < len(files):
        fname, size = files[i]
        display = meta[channel].get(fname, {}).get("display", fname)
        send2trash(os.path.join(d, fname))
        meta[channel].pop(fname, None)
        used -= size
        trashed_display.append(display)
        i += 1

    if trashed_display:
        save_meta(meta)
    return trashed_display


def enforce_all_quotas(meta):
    result = {}
    for ch in list(meta.keys()):
        trashed = enforce_channel_quota(meta, ch)
        if trashed:
            result[ch] = trashed
    return result


def export_channel_zip(channel, dest_path_no_ext):
    return shutil.make_archive(dest_path_no_ext, "zip", channel_dir(channel))


def format_bytes(n):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(n)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
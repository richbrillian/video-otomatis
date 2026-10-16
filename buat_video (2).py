"""
Video Tanya Jawab otomatis
Sheet (status 'siap') -> Pixabay (latar) -> ElevenLabs (suara) -> FFmpeg (rakit) -> Google Drive -> Sheet

Semua kunci rahasia diambil dari GitHub Secrets (environment variable), tidak ditulis di file ini.
"""
import base64
import datetime
import json
import os
import subprocess
import sys
import tempfile
import traceback

import requests

# ---------------- PENGATURAN (boleh diubah) ----------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1y1snWob1-V8IwQakheoBSpYK5c2oqezABHX1rL4IRn8")
SHEET_NAME = os.environ.get("SHEET_NAME", "Untitled")
DRIVE_FOLDER_NAME = os.environ.get("DRIVE_FOLDER_NAME", "Video Otomatis GitHub")
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "1"))
VOICE_ID = os.environ.get("VOICE_ID", "XrExE9yKIg1WjnnlVkGX")  # suara 'Matilda' (premade ElevenLabs)
MODEL_ID = os.environ.get("MODEL_ID", "eleven_multilingual_v2")
JEDA_DETIK = float(os.environ.get("JEDA_DETIK", "3"))
FONT_FILE = os.environ.get("FONT_FILE", "fonts/Poppins-Bold.ttf")
W, H = 1080, 1920

# Kolom (0 = A)
COL_NO, COL_TANYA, COL_JAWAB, COL_STATUS = 0, 1, 2, 4
COL_LINK, COL_ERROR, COL_WAKTU, COL_KATAKUNCI, COL_SUMBER = 7, 8, 9, 10, 11


def cek(r, langkah):
    """Hentikan proses dengan pesan error yang jelas (termasuk penjelasan dari Google/Pixabay)."""
    if r.status_code >= 400:
        raise RuntimeError(f"{langkah} gagal ({r.status_code}): {r.text[:400]}")
    return r


def col_letter(i):
    return chr(ord("A") + i)


# ---------------- GOOGLE ----------------
def google_token():
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    cek(r, "Login Google (token)")
    return r.json()["access_token"]


def sheet_get(tok):
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!A1:L2000"
    r = requests.get(url, headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    cek(r, "Membaca Google Sheet")
    return r.json().get("values", [])


def sheet_set(tok, row_number, updates):
    """updates = {kolom_index: nilai}"""
    data = [{"range": f"{SHEET_NAME}!{col_letter(c)}{row_number}", "values": [[v]]} for c, v in updates.items()]
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values:batchUpdate"
    r = requests.post(url, headers={"Authorization": f"Bearer {tok}"},
                      json={"valueInputOption": "USER_ENTERED", "data": data}, timeout=30)
    cek(r, "Menulis Google Sheet")


def drive_folder(tok):
    q = (f"name = '{DRIVE_FOLDER_NAME}' and mimeType = 'application/vnd.google-apps.folder' "
         f"and trashed = false")
    r = requests.get("https://www.googleapis.com/drive/v3/files", params={"q": q, "fields": "files(id)"},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    cek(r, "Google Drive / Pixabay")
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    r = requests.post("https://www.googleapis.com/drive/v3/files", headers={"Authorization": f"Bearer {tok}"},
                      json={"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}, timeout=30)
    cek(r, "Google Drive / Pixabay")
    return r.json()["id"]


def drive_upload(tok, path, name, folder_id):
    meta = {"name": name, "parents": [folder_id]}
    with open(path, "rb") as f:
        files = {
            "metadata": ("metadata", json.dumps(meta), "application/json; charset=UTF-8"),
            "file": (name, f, "video/mp4"),
        }
        r = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,webViewLink",
            headers={"Authorization": f"Bearer {tok}"}, files=files, timeout=600)
    cek(r, "Google Drive / Pixabay")
    return r.json()["webViewLink"]


# ---------------- PIXABAY ----------------
def pixabay_video(keyword, out_path):
    r = requests.get("https://pixabay.com/api/videos/", params={
        "key": os.environ["PIXABAY_API_KEY"], "q": keyword[:100], "per_page": 10,
        "safesearch": "true", "video_type": "film"}, timeout=30)
    cek(r, "Google Drive / Pixabay")
    hits = r.json().get("hits", [])
    if not hits:
        raise RuntimeError(f"Pixabay tidak menemukan video untuk kata kunci '{keyword}'. Ganti kata kunci di kolom K.")
    # Utamakan video vertikal, lalu yang paling panjang
    hits.sort(key=lambda h: (h["videos"]["medium"]["height"] > h["videos"]["medium"]["width"], h.get("duration", 0)),
              reverse=True)
    hit = hits[0]
    url = hit["videos"]["medium"]["url"] or hit["videos"]["small"]["url"]
    with requests.get(url, stream=True, timeout=120) as v:
        cek(v, "Unduh video Pixabay")
        with open(out_path, "wb") as f:
            for chunk in v.iter_content(1 << 20):
                f.write(chunk)
    return hit["pageURL"]


# ---------------- ELEVENLABS ----------------
def tts(text, out_mp3):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
        json={"text": text, "model_id": MODEL_ID,
              "voice_settings": {"stability": 0.6, "similarity_boost": 0.75}},
        timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs error {r.status_code}: {r.text[:300]}")
    d = r.json()
    with open(out_mp3, "wb") as f:
        f.write(base64.b64decode(d["audio_base64"]))
    al = d.get("alignment") or d.get("normalized_alignment")
    return al  # characters, character_start_times_seconds, character_end_times_seconds


def words_from_alignment(al, offset):
    words, cur, start, end = [], "", None, None
    for ch, s, e in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if ch.isspace():
            if cur:
                words.append((cur, start + offset, end + offset))
            cur, start = "", None
            continue
        if start is None:
            start = s
        cur += ch
        end = e
    if cur:
        words.append((cur, start + offset, end + offset))
    return words


# ---------------- AUDIO & VIDEO ----------------
def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("FFmpeg gagal: " + p.stderr[-500:])
    return p.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


def build_audio(q_mp3, a_mp3, out_m4a):
    run(["ffmpeg", "-y", "-i", q_mp3, "-i", a_mp3, "-filter_complex",
         f"[0:a]aresample=44100,apad=pad_dur={JEDA_DETIK}[q];[1:a]aresample=44100[a];[q][a]concat=n=2:v=0:a=1[out]",
         "-map", "[out]", "-c:a", "aac", "-b:a", "160k", out_m4a])


def ass_time(t):
    t = max(t, 0)
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def ass_escape(s):
    return s.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(question, words, total, out_ass, font_name):
    # Kelompokkan kata jadi potongan pendek (maks 4 kata / 24 huruf) agar mudah dibaca
    chunks, cur = [], []
    for w in words:
        if cur and (len(cur) >= 4 or len(" ".join(x[0] for x in cur + [w])) > 24):
            chunks.append(cur); cur = []
        cur.append(w)
        if w[0][-1] in ".?!,":
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)

    lines = []
    for i, c in enumerate(chunks):
        start = c[0][1]
        end = chunks[i + 1][0][1] if i + 1 < len(chunks) else c[-1][2] + 0.4
        end = min(end, c[-1][2] + 0.8)
        text = " ".join(x[0] for x in c)
        lines.append(f"Dialogue: 1,{ass_time(start)},{ass_time(end)},Sub,,0,0,0,,{ass_escape(text)}")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Tanya,{font_name},68,&H003D2114,&H003D2114,&H0011A3FC,&H0011A3FC,-1,0,0,0,100,100,0,0,3,22,0,8,90,90,300,1
Style: Sub,{font_name},76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,6,2,5,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,{ass_time(0)},{ass_time(total)},Tanya,,0,0,0,,{ass_escape(question)}
"""
    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")


def render(bg_mp4, audio_m4a, ass_path, out_mp4, total, fonts_dir):
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30,"
          f"eq=brightness=-0.18:saturation=0.9,"
          f"subtitles={ass_path}:fontsdir={fonts_dir}")
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg_mp4, "-i", audio_m4a,
         "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "1:a",
         "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", out_mp4])


# ---------------- PROSES SATU BARIS ----------------
def proses(tok, folder_id, row_number, row):
    get = lambda c: row[c].strip() if len(row) > c else ""
    no, tanya, jawab, kunci = get(COL_NO), get(COL_TANYA), get(COL_JAWAB), get(COL_KATAKUNCI)
    if not tanya or not jawab:
        raise RuntimeError("Kolom B (Pertanyaan) atau C (Jawaban) kosong.")
    if not kunci:
        kunci = "family home"

    with tempfile.TemporaryDirectory() as d:
        p = lambda n: os.path.join(d, n)
        sumber = pixabay_video(kunci, p("bg.mp4"))
        tts(tanya, p("q.mp3"))
        q_len = duration(p("q.mp3"))
        al = tts(jawab, p("a.mp3"))
        words = words_from_alignment(al, q_len + JEDA_DETIK)
        build_audio(p("q.mp3"), p("a.mp3"), p("audio.m4a"))
        total = duration(p("audio.m4a")) + 0.6
        build_ass(tanya, words, total, p("sub.ass"), "Poppins")
        render(p("bg.mp4"), p("audio.m4a"), p("sub.ass"), p("out.mp4"), total,
               os.path.dirname(os.path.abspath(FONT_FILE)))
        link = drive_upload(tok, p("out.mp4"), f"video_{no or row_number}.mp4", folder_id)
    return link, sumber


def main():
    tok = google_token()
    rows = sheet_get(tok)
    targets = [(i + 1, r) for i, r in enumerate(rows) if i > 0 and len(r) > COL_STATUS
               and r[COL_STATUS].strip().lower() == "siap"][:MAX_PER_RUN]
    if not targets:
        print("Tidak ada baris berstatus 'siap'. Selesai.")
        return
    folder_id = drive_folder(tok)
    gagal = 0
    for row_number, row in targets:
        print(f"Memproses baris {row_number}: {row[COL_TANYA] if len(row) > 1 else ''}")
        sheet_set(tok, row_number, {COL_STATUS: "proses", COL_ERROR: ""})
        try:
            link, sumber = proses(tok, folder_id, row_number, row)
            waktu = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
            sheet_set(tok, row_number, {COL_STATUS: "selesai", COL_LINK: link, COL_ERROR: "",
                                        COL_WAKTU: waktu, COL_SUMBER: sumber})
            print(f"  -> selesai: {link}")
        except Exception as e:
            gagal += 1
            traceback.print_exc()
            sheet_set(tok, row_number, {COL_STATUS: "gagal", COL_ERROR: str(e)[:450]})
    if gagal:
        sys.exit(1)


if __name__ == "__main__":
    main()

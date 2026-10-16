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

import random
import textwrap

import requests

# ---------------- PENGATURAN (boleh diubah) ----------------
SPREADSHEET_ID = os.environ.get("SPREADSHEET_ID", "1y1snWob1-V8IwQakheoBSpYK5c2oqezABHX1rL4IRn8")
SHEET_NAME = os.environ.get("SHEET_NAME", "Untitled")
DRIVE_FOLDER_NAME = os.environ.get("DRIVE_FOLDER_NAME", "Video Otomatis GitHub")
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "3"))
VOICE_ID = os.environ.get("VOICE_ID", "gmnazjXOFoOcWA59sd5m")  # suara pilihan dari Voice Library
MODEL_ID = os.environ.get("MODEL_ID", "eleven_multilingual_v2")
JEDA_DETIK = float(os.environ.get("JEDA_DETIK", "3"))
FONT_FILE = os.environ.get("FONT_FILE", "fonts/Poppins-Bold.ttf")
W, H = 1080, 1920
DETIK_PER_KLIP = float(os.environ.get("DETIK_PER_KLIP", "6"))   # latar berganti tiap ~6 detik
MAKS_KLIP = int(os.environ.get("MAKS_KLIP", "8"))
KATA_KUNCI_CADANGAN = os.environ.get("KATA_KUNCI_CADANGAN", "family home")
UKURAN_PERTANYAAN = int(os.environ.get("UKURAN_PERTANYAAN", "33"))
UKURAN_SUBTITLE = int(os.environ.get("UKURAN_SUBTITLE", "50"))
FONT_REGULAR = os.environ.get("FONT_REGULAR", "fonts/Poppins-Regular.ttf")

# Kolom (0 = A)
COL_NO, COL_TANYA, COL_JAWAB, COL_STATUS = 0, 1, 2, 4
COL_LINK, COL_ERROR, COL_WAKTU, COL_KATAKUNCI, COL_SUMBER, COL_UNDUH = 7, 8, 9, 10, 11, 12
STATUS_JADI = os.environ.get("STATUS_JADI", "siap posting")  # dibaca Make untuk diposting ke Facebook


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
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{SHEET_NAME}!A1:N2000"
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
    cek(r, "Google Drive")
    files = r.json().get("files", [])
    if files:
        return files[0]["id"]
    r = requests.post("https://www.googleapis.com/drive/v3/files", headers={"Authorization": f"Bearer {tok}"},
                      json={"name": DRIVE_FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}, timeout=30)
    cek(r, "Google Drive")
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
    cek(r, "Upload ke Google Drive")
    info = r.json()
    # Buka akses 'siapa saja yang punya link' agar Facebook bisa mengambil videonya
    r2 = requests.post(f"https://www.googleapis.com/drive/v3/files/{info['id']}/permissions",
                       headers={"Authorization": f"Bearer {tok}"}, json={"role": "reader", "type": "anyone"},
                       timeout=30)
    cek(r2, "Membuka akses link video")
    unduh = f"https://drive.google.com/uc?export=download&id={info['id']}"
    return info["webViewLink"], unduh


# ---------------- PIXABAY ----------------
def pixabay_videos(keyword, folder, jumlah):
    """Ambil beberapa klip berbeda dari Pixabay (acak) agar latar berganti-ganti."""
    r = requests.get("https://pixabay.com/api/videos/", params={
        "key": os.environ["PIXABAY_API_KEY"], "q": keyword[:100], "per_page": 20,
        "safesearch": "true", "video_type": "film"}, timeout=30)
    cek(r, "Cari video Pixabay")
    hits = r.json().get("hits", [])
    if len(hits) < jumlah:  # kata kunci terlalu sempit -> tambah dari kata kunci umum
        r2 = requests.get("https://pixabay.com/api/videos/", params={
            "key": os.environ["PIXABAY_API_KEY"], "q": KATA_KUNCI_CADANGAN, "per_page": 20,
            "safesearch": "true", "video_type": "film"}, timeout=30)
        if r2.status_code == 200:
            hits += r2.json().get("hits", [])
    if not hits:
        raise RuntimeError(f"Pixabay tidak menemukan video untuk kata kunci '{keyword}'. Ganti kata kunci di kolom K.")
    random.shuffle(hits)
    paths, sumber = [], []
    for hit in hits[:jumlah]:
        url = hit["videos"]["medium"]["url"] or hit["videos"]["small"]["url"]
        path = os.path.join(folder, f"bg{len(paths)}.mp4")
        with requests.get(url, stream=True, timeout=120) as v:
            cek(v, "Unduh video Pixabay")
            with open(path, "wb") as f:
                for chunk in v.iter_content(1 << 20):
                    f.write(chunk)
        paths.append(path)
        sumber.append(hit["pageURL"])
    return paths, sumber


# ---------------- ELEVENLABS ----------------
def tts(text, out_mp3, stability=0.35, style=0.35):
    r = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps",
        headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"},
        json={"text": text, "model_id": MODEL_ID,
              "voice_settings": {"stability": stability, "similarity_boost": 0.8, "style": style,
                                 "use_speaker_boost": True}},
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

    # Ukuran font di subtitle (ASS) dihitung beda dengan di gambar; samakan supaya tampil sama besar
    # (diukur: untuk font Poppins, ukuran ASS x 0,56 = ukuran huruf di gambar)
    ukuran_ass = round(UKURAN_SUBTITLE * 1.78)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,{font_name},{ukuran_ass},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{max(2, round(UKURAN_SUBTITLE * 0.09))},1,2,70,70,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    with open(out_ass, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(lines) + "\n")


NAMA_DEPAN = ["rina", "dewi", "budi", "ayu", "sari", "putri", "andi", "rizky", "fajar", "nisa", "wulan", "dimas",
              "intan", "yoga", "tika", "eko", "maya", "bayu", "indah", "fitri", "agus", "lina", "reza", "mega"]
NAMA_BELAKANG = ["ayu", "sari", "pratama", "lestari", "putra", "wijaya", "rahma", "kusuma", "saputra", "dewi",
                 "anggraini", "permata", "hidayat", "nugraha"]
TEMA_AVATAR = ["cat", "kitten", "dog", "puppy", "rabbit", "bird", "flower", "rose", "sunflower", "coffee cup",
               "tea", "cake", "sunset", "mountain", "beach", "forest", "leaf", "bicycle", "book", "plant", "moon"]


def nama_acak():
    """Nama fiktif acak, contoh: 'Rina' atau 'Dimas Pratama'"""
    depan = random.choice(NAMA_DEPAN).capitalize()
    if random.random() < 0.5:
        return depan
    return f"{depan} {random.choice(NAMA_BELAKANG).capitalize()}"


def avatar_acak(ukuran):
    """Foto profil acak dari Pixabay: hewan/benda/alam (bukan foto orang). Bulat. None kalau gagal."""
    try:
        from PIL import Image, ImageDraw, ImageOps
        import io
        r = requests.get("https://pixabay.com/api/", params={
            "key": os.environ["PIXABAY_API_KEY"], "q": random.choice(TEMA_AVATAR), "image_type": "photo",
            "safesearch": "true", "per_page": 30}, timeout=30)
        hits = r.json().get("hits", []) if r.status_code == 200 else []
        if not hits:
            return None
        hit = random.choice(hits)
        foto = requests.get(hit["webformatURL"], timeout=60).content
        im = ImageOps.fit(Image.open(io.BytesIO(foto)).convert("RGB"), (ukuran, ukuran))
        mask = Image.new("L", (ukuran, ukuran), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, ukuran - 1, ukuran - 1], fill=255)
        im.putalpha(mask)
        return im
    except Exception:
        return None


def kartu_komentar(question, out_png):
    """Gambar kartu putih bergaya 'Membalas komentar' (seperti balasan komentar TikTok/Reels).
    Semua ukuran mengikuti UKURAN_PERTANYAAN."""
    from PIL import Image, ImageDraw, ImageFont
    u = UKURAN_PERTANYAAN
    bold = ImageFont.truetype(FONT_FILE, u)
    small = ImageFont.truetype(FONT_REGULAR, max(14, round(u * 0.62)))
    ikon = max(36, round(u * 1.7))
    pad = max(16, round(u * 0.75))
    maks_lebar = 900
    # bungkus teks sesuai lebar maksimal kartu
    baris, cur = [], ""
    for k in question.split():
        uji = (cur + " " + k).strip()
        if bold.getlength(uji) <= maks_lebar - 2 * pad:
            cur = uji
        else:
            baris.append(cur); cur = k
    if cur:
        baris.append(cur)
    label = "Balas komentar " + nama_acak()
    lebar_isi = max([bold.getlength(b) for b in baris] + [ikon + pad * 0.6 + small.getlength(label)])
    lebar = int(lebar_isi + 2 * pad)
    tinggi_baris = int(u * 1.3)
    jarak = round(u * 0.45)
    tinggi = pad + ikon + jarak + tinggi_baris * len(baris) + pad
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0 = (W - lebar) // 2, 300
    r = round(u * 0.8)
    d.rounded_rectangle([x0 + 5, y0 + 6, x0 + lebar + 5, y0 + tinggi + 6], r, fill=(0, 0, 0, 90))
    d.rounded_rectangle([x0, y0, x0 + lebar, y0 + tinggi], r, fill=(255, 255, 255, 255))
    e = round(u * 0.9)
    d.polygon([(x0 + r, y0 + tinggi - 2), (x0 + r + e, y0 + tinggi - 2), (x0 + r - e // 3, y0 + tinggi + e)],
              fill=(255, 255, 255, 255))
    ay = y0 + pad
    foto = avatar_acak(ikon)
    if foto is not None:
        img.alpha_composite(foto, (x0 + pad, ay))
    else:
        d.ellipse([x0 + pad, ay, x0 + pad + ikon, ay + ikon], fill=(252, 163, 17, 255))
    d.text((x0 + pad + ikon + round(pad * 0.5), ay + ikon / 2), label, font=small, fill=(110, 110, 110, 255),
           anchor="lm")
    ty = ay + ikon + jarak
    for b in baris:
        d.text((x0 + pad, ty), b, font=bold, fill=(20, 20, 20, 255))
        ty += tinggi_baris
    img.save(out_png)


def render(bg_list, audio_m4a, ass_path, kartu_png, out_mp4, total, fonts_dir, folder):
    # 1) potong tiap klip latar jadi segmen ~6 detik, ukuran 1080x1920
    n = len(bg_list)
    seg = total / n
    potongan = []
    for i, bg in enumerate(bg_list):
        out = os.path.join(folder, f"seg{i}.mp4")
        run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg, "-t", f"{seg:.3f}", "-an",
             "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30,"
                    f"eq=brightness=-0.15:saturation=0.9",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out])
        potongan.append(out)
    daftar = os.path.join(folder, "daftar.txt")
    with open(daftar, "w") as f:
        f.writelines(f"file '{x}'\n" for x in potongan)
    latar = os.path.join(folder, "latar.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", daftar, "-c", "copy", latar])
    # 2) tempel kartu komentar + subtitle + suara
    run(["ffmpeg", "-y", "-i", latar, "-loop", "1", "-i", kartu_png, "-i", audio_m4a,
         "-filter_complex", f"[0:v][1:v]overlay=0:0:shortest=1,subtitles={ass_path}:fontsdir={fonts_dir}[v]",
         "-map", "[v]", "-map", "2:a", "-t", f"{total:.2f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", out_mp4])


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
        tts(tanya, p("q.mp3"), stability=0.3, style=0.5)  # nada bertanya lebih hidup
        q_len = duration(p("q.mp3"))
        al = tts(jawab, p("a.mp3"))
        words = words_from_alignment(al, q_len + JEDA_DETIK)
        build_audio(p("q.mp3"), p("a.mp3"), p("audio.m4a"))
        total = duration(p("audio.m4a")) + 0.6
        jumlah_klip = max(1, min(MAKS_KLIP, round(total / DETIK_PER_KLIP)))
        latar, sumber = pixabay_videos(kunci, d, jumlah_klip)
        build_ass(tanya, words, total, p("sub.ass"), "Poppins")
        kartu_komentar(tanya, p("kartu.png"))
        render(latar, p("audio.m4a"), p("sub.ass"), p("kartu.png"), p("out.mp4"), total,
               os.path.dirname(os.path.abspath(FONT_FILE)), d)
        if total > 89:
            print(f"  Peringatan: durasi {total:.0f} detik, lebih dari batas Reels Facebook (90 detik).")
        link, unduh = drive_upload(tok, p("out.mp4"), f"video_{no or row_number}.mp4", folder_id)
    return link, " ".join(sumber), unduh


def persiapan():
    try:
        import PIL  # noqa
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "pillow"], check=True)
    os.makedirs(os.path.dirname(FONT_REGULAR) or ".", exist_ok=True)
    if not os.path.exists(FONT_REGULAR):
        r = requests.get("https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf", timeout=60)
        cek(r, "Unduh font")
        with open(FONT_REGULAR, "wb") as f:
            f.write(r.content)


def main():
    persiapan()
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
            link, sumber, unduh = proses(tok, folder_id, row_number, row)
            waktu = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
            sheet_set(tok, row_number, {COL_STATUS: STATUS_JADI, COL_LINK: link, COL_ERROR: "",
                                        COL_WAKTU: waktu, COL_SUMBER: sumber, COL_UNDUH: unduh})
            print(f"  -> selesai: {link}")
        except Exception as e:
            gagal += 1
            traceback.print_exc()
            sheet_set(tok, row_number, {COL_STATUS: "gagal", COL_ERROR: str(e)[:450]})
    if gagal:
        sys.exit(1)


if __name__ == "__main__":
    main()

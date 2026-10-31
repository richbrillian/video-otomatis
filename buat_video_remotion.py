"""Video fakta pendek dengan Remotion: hook besar di awal, teks per kata, latar animasi hasil kode.

Mode (variabel MODE):
  contoh -> uji tampilan saja: tanpa Sheet dan tanpa ElevenLabs (suara hening, waktu kata palsu)
  sheet  -> alur nyata: Sheet (status 'siap') -> ElevenLabs (hook + jawaban)
            -> Remotion -> Google Drive -> Sheet (status 'siap posting')

Latar default = animasi hasil kode (tanpa footage stok). Footage Pixabay bisa dinyalakan
(default aktif; LATAR_KLIP=0 untuk animasi saja).
Musik latar dibuat sendiri lewat kode (buat_musik.py, bebas hak cipta). Matikan dengan MUSIK=0,
atur volume dengan MUSIK_VOLUME (default 0.22).

Fungsi login Google, Sheet, Drive, Pixabay, dan ElevenLabs dipakai dari buat_video.py, jadi
kunci rahasia tetap dari GitHub Secrets dan kolom Sheet sama dengan alur lama.
Status akhir tetap "siap posting", sehingga skenario Make yang sudah ada tidak perlu diubah.
"""
import datetime
import json
import os
import random
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import buat_video as bv
from buat_musik import buat_musik

RDIR = Path(__file__).resolve().parent / "remotion"
JOB = RDIR / "public" / "job"
OUT = RDIR / "out"

COL_JAWAB_SUARA, COL_HOOK = 3, 16  # kolom D (Jawaban Suara) dan Q (Hook)
LABEL = os.environ.get("LABEL_KANAL", "DAILY FACT BITES")
WARNA = ["#FFC400", "#00E5FF", "#FF4D8D", "#7CFF6B"]
DETIK_PER_KLIP = float(os.environ.get("DETIK_PER_KLIP_RM", "4"))
BROWSER = os.environ.get("BROWSER_EXECUTABLE", "")  # kosong = Remotion mengunduh Chrome sendiri
MUSIK = os.environ.get("MUSIK", "1") != "0"
MUSIK_VOLUME = float(os.environ.get("MUSIK_VOLUME", "0.22"))


def siapkan_folder():
    shutil.rmtree(JOB, ignore_errors=True)
    JOB.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)


def ambil_klip(kunci, dur):
    """Unduh klip latar dari Pixabay. Bila gagal, kembalikan daftar kosong (latar gradasi)."""
    if os.environ.get("LATAR_KLIP", "1") != "1":
        return [], ""  # LATAR_KLIP=0: hanya animasi kode
    n = max(3, min(bv.MAKS_KLIP, round(dur / DETIK_PER_KLIP)))
    # Coba kata kunci dari kolom K, lalu kata pertamanya, lalu cadangan umum.
    kandidat = [kunci or "nature", (kunci or "nature").split()[0], "wildlife animals", "nature"]
    for k in dict.fromkeys(kandidat):
        try:
            paths, sumber = bv.pixabay_videos(k, str(JOB), n)
            return [f"job/{Path(x).name}" for x in paths], " ".join(sumber)
        except Exception as e:  # noqa: BLE001
            print(f"  Pixabay '{k}' gagal:", str(e)[:150])
            for f in JOB.glob("bg*.mp4"):
                f.unlink()
    print("  Semua kata kunci gagal, pakai animasi saja")
    return [], ""


def siapkan_musik(dur):
    """Buat musik latar sepanjang video. Bila gagal, video tetap jadi tanpa musik."""
    if not MUSIK:
        return ""
    try:
        gaya = buat_musik(JOB / "musik.mp3", dur)
        print(f"  Musik latar: gaya {gaya}")
        return "job/musik.mp3"
    except Exception as e:  # noqa: BLE001
        print("  Musik gagal dibuat, lanjut tanpa musik:", str(e)[:200])
        return ""


def susun_props(hook, words, dur, clips, music=""):
    if not words:
        raise RuntimeError("Tidak ada data kata dari ElevenLabs.")
    hook_n = min(max(1, len(hook.split())), len(words))
    hook_end = words[hook_n - 1][2] + 0.25
    return {
        "hook": hook,
        "label": LABEL,
        "words": [{"t": w[0], "s": round(w[1], 3), "e": round(w[2], 3)} for w in words],
        "hookWordCount": hook_n,
        "hookEnd": round(hook_end, 3),
        "durationSec": round(dur, 2),
        "clips": clips,
        "audio": "job/voice.mp3",
        "accent": random.choice(WARNA),
        "music": music,
        "musicVolume": MUSIK_VOLUME,
    }


def render_remotion(props, out_mp4):
    (RDIR / "props.json").write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    cmd = ["npx", "remotion", "render", "src/index.ts", "FactVideo", str(out_mp4),
           "--props=props.json", "--codec=h264", "--crf=22", "--log=warn"]
    if BROWSER:
        cmd.append(f"--browser-executable={BROWSER}")
    p = subprocess.run(cmd, cwd=RDIR, capture_output=True, text=True, timeout=1500)
    if p.returncode != 0:
        raise RuntimeError("Remotion gagal: " + (p.stderr or p.stdout)[-450:])
    if not Path(out_mp4).exists():
        raise RuntimeError("Remotion tidak menghasilkan file video.")


# ---------------- MODE CONTOH ----------------
def mode_contoh():
    hook = "Your banana is slightly radioactive."
    jawab = ("Bananas contain natural potassium, and a tiny part of it is radioactive. "
             "The amount is so small that it is completely harmless. Follow for more.")
    siapkan_folder()
    kata = (hook + " " + jawab).split()
    words = [(w, i * 0.38, i * 0.38 + 0.34) for i, w in enumerate(kata)]
    dur = len(kata) * 0.38 + 0.8
    bv.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", f"{dur:.2f}", "-q:a", "9", str(JOB / "voice.mp3")])
    clips, _ = ambil_klip("banana fruit", dur)
    props = susun_props(hook, words, dur, clips, siapkan_musik(dur))
    out = OUT / "contoh.mp4"
    render_remotion(props, out)
    print(f"Selesai: {out} ({dur:.1f} detik, klip latar: {len(clips)})")


# ---------------- MODE SHEET ----------------
def proses(tok, folder_id, row_number, row):
    def get(c):
        return row[c].strip() if len(row) > c else ""

    no, tanya = get(bv.COL_NO), get(bv.COL_TANYA)
    jawab = get(COL_JAWAB_SUARA) or get(bv.COL_JAWAB)
    hook = get(COL_HOOK) or tanya
    kunci = get(bv.COL_KATAKUNCI) or "nature science"
    if not hook or not jawab:
        raise RuntimeError("Kolom Hook/Pertanyaan atau Jawaban kosong.")

    siapkan_folder()
    bv.SUARA_AKTIF = random.choice(bv.VOICE_IDS)
    mp3 = JOB / "voice.mp3"
    al = bv.tts(f"{hook} {jawab}", str(mp3), stability=0.4, style=0.45)
    if not al:
        raise RuntimeError("ElevenLabs tidak mengirim data waktu kata.")
    words = bv.words_from_alignment(al, 0.0)
    dur = bv.duration(str(mp3)) + 0.6
    clips, sumber = ambil_klip(kunci, dur)
    props = susun_props(hook, words, dur, clips, siapkan_musik(dur))
    out = OUT / f"video_{no or row_number}.mp4"
    render_remotion(props, out)
    link, unduh = bv.drive_upload(tok, str(out), out.name, folder_id)
    return link, sumber, unduh


def main():
    mode = os.environ.get("MODE", "sheet").strip().lower()
    if mode == "contoh":
        mode_contoh()
        return

    tok = bv.google_token()
    rows = bv.sheet_get(tok)
    targets = [(i + 1, r) for i, r in enumerate(rows)
               if i > 0 and len(r) > bv.COL_STATUS and r[bv.COL_STATUS].strip().lower() == "siap"][:bv.MAX_PER_RUN]
    if not targets:
        print("Tidak ada baris berstatus 'siap'. Selesai.")
        return
    folder_id = bv.drive_folder(tok)
    gagal = 0
    for row_number, row in targets:
        print(f"Memproses baris {row_number}: {row[bv.COL_TANYA] if len(row) > 1 else ''}")
        bv.sheet_set(tok, row_number, {bv.COL_STATUS: "proses", bv.COL_ERROR: ""})
        try:
            link, sumber, unduh = proses(tok, folder_id, row_number, row)
            waktu = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).strftime("%Y-%m-%d %H:%M")
            bv.sheet_set(tok, row_number, {bv.COL_STATUS: bv.STATUS_JADI, bv.COL_LINK: link, bv.COL_ERROR: "",
                                           bv.COL_WAKTU: waktu, bv.COL_SUMBER: sumber, bv.COL_UNDUH: unduh})
            print(f"  -> selesai: {link}")
        except Exception as e:  # noqa: BLE001
            gagal += 1
            traceback.print_exc()
            pesan = str(e)[:450]
            if "ElevenLabs error 401" in pesan or "ElevenLabs error 402" in pesan:
                # Masalah kunci/kredit, bukan masalah baris ini: kembalikan ke 'siap' dan berhenti
                # supaya tidak menghabiskan baris lain dan bisa diulang otomatis setelah kunci diganti.
                bv.sheet_set(tok, row_number, {bv.COL_STATUS: "siap", bv.COL_ERROR: pesan})
                print("  Kunci/kredit ElevenLabs bermasalah, berhenti.")
                break
            bv.sheet_set(tok, row_number, {bv.COL_STATUS: "gagal", bv.COL_ERROR: pesan})
    if gagal:
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Video ULASAN / PENJELASAN (transformatif) dari cuplikan video lain.

Susunan video:
  1) Cuplikan asli singkat (maks ~5 detik) + label kredit pembuat aslinya
  2) Penjelasan kita sendiri: narasi ElevenLabs + latar video stok Pixabay + kartu hook + subtitle
Semua fungsi pembuat video dipakai ulang dari buat_video.py.

Input lewat environment variable (diisi dari form "Run workflow"):
  SRC_FILE_ID  : ID file video sumber di Google Drive
  CLIP_START   : detik mulai cuplikan (mis. 8)
  CLIP_DUR     : panjang cuplikan dalam detik (maks 5)
  CREDIT       : nama pembuat asli untuk label kredit
  HOOK         : teks kartu di bagian penjelasan (mis. "Would you eat this egg?")
  NARASI       : naskah narasi penjelasan
  KATA_KUNCI   : kata kunci latar Pixabay (bahasa Inggris)
  NAMA_FILE    : nama file hasil di Drive
"""
import os
import subprocess
import tempfile

import requests

import buat_video as bv


def unduh_sumber(tok, file_id, path):
    """Unduh video sumber dari Drive (pakai login Google; kalau ditolak, coba link publik)."""
    r = requests.get(f"https://www.googleapis.com/drive/v3/files/{file_id}", params={"alt": "media"},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=300)
    if r.status_code != 200:
        r = requests.get("https://drive.usercontent.google.com/download",
                         params={"id": file_id, "export": "download", "confirm": "t"}, timeout=300)
    bv.cek(r, "Unduh video sumber dari Drive")
    if r.content[:200].lstrip().startswith(b"<"):
        raise RuntimeError("Video sumber tidak bisa diunduh (mungkin belum dibagikan 'siapa saja yang punya link').")
    with open(path, "wb") as f:
        f.write(r.content)


def esc_drawtext(s):
    return s.replace("\\", "").replace(":", "\\:").replace("'", "").replace("%", "")


def main():
    bv.persiapan()
    tok = bv.google_token()
    file_id = os.environ["SRC_FILE_ID"].strip()
    mulai = float(os.environ.get("CLIP_START", "0") or 0)
    durasi = min(5.0, float(os.environ.get("CLIP_DUR", "4") or 4))
    kredit = os.environ.get("CREDIT", "").strip() or "original creator"
    hook = os.environ["HOOK"].strip()
    narasi = os.environ["NARASI"].strip()
    kunci = os.environ.get("KATA_KUNCI", "").strip() or bv.KATA_KUNCI_CADANGAN
    nama = os.environ.get("NAMA_FILE", "").strip() or f"ulasan_{file_id[:8]}"
    font = os.path.abspath(bv.FONT_FILE)
    W, H = bv.W, bv.H

    with tempfile.TemporaryDirectory() as d:
        p = lambda n: os.path.join(d, n)
        unduh_sumber(tok, file_id, p("src.mp4"))

        # 1) Cuplikan asli (singkat) + label kredit
        label = esc_drawtext(f"Clip: {kredit}")
        bv.run(["ffmpeg", "-y", "-ss", f"{mulai:.2f}", "-t", f"{durasi:.2f}", "-i", p("src.mp4"),
                "-f", "lavfi", "-t", f"{durasi:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
                "-filter_complex",
                f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30,"
                f"drawtext=fontfile={font}:text='{label}':fontsize=42:fontcolor=white:box=1:"
                f"boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=170[v];"
                f"[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];[a0][1:a]amix=inputs=2:duration=first[a]",
                "-map", "[v]", "-map", "[a]", "-t", f"{durasi:.2f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-ar", "44100", p("bag1.mp4")])

        # 2) Penjelasan kita sendiri
        bv.SUARA_AKTIF = bv.random.choice(bv.VOICE_IDS)
        al = bv.tts(narasi, p("n.mp3"))
        words = bv.words_from_alignment(al, 0.3)
        bv.run(["ffmpeg", "-y", "-i", p("n.mp3"), "-af", "adelay=300|300,aresample=44100",
                "-c:a", "aac", "-b:a", "160k", "-ac", "2", p("n.m4a")])
        total = bv.duration(p("n.m4a")) + 0.6
        jumlah = max(2, min(bv.MAKS_KLIP, round(total / bv.DETIK_PER_KLIP)))
        latar, sumber = bv.pixabay_videos(kunci, d, jumlah)
        bv.build_ass(hook, words, total, p("sub.ass"), "Poppins")
        bv.kartu_komentar(hook, p("kartu.png"), "")
        bv.render(latar, p("n.m4a"), p("sub.ass"), p("kartu.png"), p("bag2.mp4"), total,
                  os.path.dirname(font), d)

        # 3) Gabungkan
        bv.run(["ffmpeg", "-y", "-i", p("bag1.mp4"), "-i", p("bag2.mp4"), "-filter_complex",
                "[0:v]setsar=1,fps=30[v0];[1:v]setsar=1,fps=30[v1];"
                "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];"
                "[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];"
                "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
                p("hasil.mp4")])
        print(f"Durasi total: {bv.duration(p('hasil.mp4')):.1f} detik (cuplikan asli {durasi:.1f} detik)")
        link, unduh = bv.drive_upload(tok, p("hasil.mp4"), f"{nama}.mp4", bv.drive_folder(tok))
        print("Selesai:", link)
        print("Sumber latar:", " ".join(sumber))


if __name__ == "__main__":
    main()

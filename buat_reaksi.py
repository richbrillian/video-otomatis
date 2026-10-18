"""
Video ULASAN / PENJELASAN (transformatif) dari cuplikan video lain.

Susunan video:
  1) Cuplikan asli singkat (maks 8 detik, suara asli dimatikan) + label kredit pembuat aslinya
  2) Penjelasan kita sendiri: narasi ElevenLabs + latar video stok Pixabay + kartu hook + subtitle
Semua fungsi pembuat video dipakai ulang dari buat_video.py.

Input lewat environment variable (diisi dari form "Run workflow"):
  SRC_FILE_ID  : ID file video sumber di Google Drive
  CLIP_START   : detik mulai cuplikan (mis. 8)
  CLIP_DUR     : panjang cuplikan dalam detik (maks 8)
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
    durasi = min(8.0, float(os.environ.get("CLIP_DUR", "6") or 6))  # maks 8 detik cuplikan asli
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

        # 1) Narasi kita (dipakai di sepanjang video, termasuk saat cuplikan asli tampil)
        bv.SUARA_AKTIF = bv.random.choice(bv.VOICE_IDS)
        al = bv.tts(narasi, p("n.mp3"))
        words = bv.words_from_alignment(al, 0.3)
        bv.run(["ffmpeg", "-y", "-i", p("n.mp3"), "-af", "adelay=300|300,aresample=44100",
                "-c:a", "aac", "-b:a", "160k", "-ac", "2", p("n.m4a")])
        total = bv.duration(p("n.m4a")) + 0.6
        durasi = min(durasi, max(2.0, total - 6))  # bagian penjelasan kita minimal ~6 detik

        # 2) Cuplikan asli TANPA suara asli + label kredit
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps=30"
        label = esc_drawtext(f"Clip: {kredit}")
        bv.run(["ffmpeg", "-y", "-ss", f"{mulai:.2f}", "-t", f"{durasi:.2f}", "-i", p("src.mp4"), "-an",
                "-vf", vf + f",drawtext=fontfile={font}:text='{label}':fontsize=42:fontcolor=white:box=1:"
                f"boxcolor=black@0.55:boxborderw=18:x=(w-text_w)/2:y=170",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", p("seg_asli.mp4")])

        # 3) Latar stok Pixabay untuk sisa durasi
        sisa = total - durasi
        jumlah = max(1, min(bv.MAKS_KLIP, round(sisa / bv.DETIK_PER_KLIP)))
        latar, sumber = bv.pixabay_videos(kunci, d, jumlah)
        potongan = [p("seg_asli.mp4")]
        for i, bg in enumerate(latar):
            out = p(f"seg{i}.mp4")
            bv.run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bg, "-t", f"{sisa / len(latar):.3f}", "-an",
                    "-vf", vf + ",eq=brightness=-0.15:saturation=0.9",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", out])
            potongan.append(out)
        with open(p("daftar.txt"), "w") as f:
            f.writelines(f"file '{x}'\n" for x in potongan)
        bv.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", p("daftar.txt"), "-c", "copy", p("latar.mp4")])

        # 4) Kartu hook (muncul setelah cuplikan asli) + subtitle + narasi
        bv.build_ass(hook, words, total, p("sub.ass"), "Poppins")
        bv.kartu_komentar(hook, p("kartu.png"), "")
        bv.run(["ffmpeg", "-y", "-i", p("latar.mp4"), "-loop", "1", "-i", p("kartu.png"), "-i", p("n.m4a"),
                "-filter_complex",
                f"[0:v][1:v]overlay=0:0:shortest=1:enable='gte(t,{durasi:.2f})',"
                f"subtitles={p('sub.ass')}:fontsdir={os.path.dirname(font)}[v]",
                "-map", "[v]", "-map", "2:a", "-t", f"{total:.2f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-movflags", "+faststart", p("hasil.mp4")])
        print(f"Durasi total: {bv.duration(p('hasil.mp4')):.1f} detik (cuplikan asli {durasi:.1f} detik)")
        link, unduh = bv.drive_upload(tok, p("hasil.mp4"), f"{nama}.mp4", bv.drive_folder(tok))
        print("Selesai:", link)
        print("Sumber latar:", " ".join(sumber))


if __name__ == "__main__":
    main()

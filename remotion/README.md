# Template video fakta (Remotion)

Video 1080x1920 (Shorts/Reels): hook besar di 2-3 detik pertama, lalu teks per kata dengan kata
yang sedang diucapkan disorot, latar klip bergantian dengan zoom pelan, label kanal, dan progress bar.

Dipakai oleh `buat_video_remotion.py` lewat workflow **Buat Video Fakta (Remotion)**.

## Uji tampilan tanpa biaya
Actions -> Buat Video Fakta (Remotion) -> Run workflow -> mode **contoh**.
Tidak memakai Sheet maupun ElevenLabs. Videonya ada di bagian Artifacts pada run itu.

## Proses baris dari Sheet
Mode **sheet**: memproses baris berstatus `siap`, hook diambil dari kolom Q (Hook), narasi dari
kolom D (Jawaban Suara). Hasil ke Google Drive, status jadi `siap posting` (sama seperti alur lama).

## Mengubah tampilan
Semua ada di `src/FactVideo.tsx`: ukuran teks, warna (`accent` dipilih acak dari `WARNA` di
`buat_video_remotion.py`), posisi teks, dan lama hook.
Pratinjau lokal: `npm install` lalu `npm run studio`.

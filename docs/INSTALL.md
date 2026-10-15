# Memasang REDCap Uploader · Installing REDCap Uploader

*Bahasa Indonesia di bawah ini; English further down.*

## Bahasa Indonesia

### Windows

1. Buka file `REDCap-Uploader-<versi>-Windows-Setup.exe`.
2. Jika muncul layar biru **"Windows protected your PC"** (SmartScreen), klik **More info**, lalu **Run anyway**. Peringatan ini muncul karena aplikasinya belum ditandatangani secara digital. Itu tidak berarti aplikasinya berbahaya.
3. Ikuti langkah pemasangan. Secara bawaan, aplikasi dipasang hanya untuk akun Anda, jadi tidak perlu hak administrator.
4. Buka **REDCap Uploader** dari menu Start.

Untuk menghapus: buka **Settings → Apps**, cari REDCap Uploader, lalu klik **Uninstall**.

### macOS (Apple silicon: M1, M2, M3, M4)

1. Buka file `REDCap-Uploader-<versi>-macOS-arm64.dmg`, lalu seret **REDCap Uploader** ke folder **Applications**.
2. Buka aplikasinya dari Applications. Pada pembukaan pertama, macOS akan memblokirnya karena aplikasi belum dinotarisasi oleh Apple.
3. Buka **System Settings → Privacy & Security**, gulir ke bawah, lalu klik **Open Anyway** di samping pesan tentang REDCap Uploader. Konfirmasi sekali lagi.
4. Sesudah itu aplikasi terbuka seperti biasa.

### Mulai dengan mode Demo

Aplikasi terbuka dalam **mode Demo**: REDCap latihan di dalam aplikasi, tanpa akun dan tanpa internet.

1. Klik **Hubungkan**, lalu **Lanjut**.
2. Pada langkah **Pilih file**, klik **Bersih** di "Atau coba contoh" untuk memuat file contoh sintetis.
3. Klik **Lanjut** di setiap langkah sampai **Hasil**. Buka **Apa yang terjadi?** di bawah setiap langkah untuk melihat penjelasannya.

Untuk memakai proyek REDCap sungguhan, pilih **Proyek REDCap saya** pada langkah pertama. Masukkan URL API dan token dari halaman API proyek Anda, lalu pilih file kunci pseudonim tim Anda.

### Jika ada masalah

Log aplikasi disimpan di folder data aplikasi pengguna (Windows: `%LOCALAPPDATA%\RPRI\REDCap Uploader\logs`; macOS: `~/Library/Application Support/RPRI/REDCap Uploader/logs`). Log tidak pernah berisi token atau identitas pasien, jadi aman untuk dibagikan kepada pengembang.

## English

### Windows

1. Open `REDCap-Uploader-<version>-Windows-Setup.exe`.
2. If a blue **"Windows protected your PC"** screen appears (SmartScreen), click **More info**, then **Run anyway**. The warning appears because the app is not yet digitally signed. It does not mean the app is harmful.
3. Follow the steps. By default the app is installed for your account only, so no administrator rights are needed.
4. Open **REDCap Uploader** from the Start menu.

To remove it: go to **Settings → Apps**, find REDCap Uploader, and click **Uninstall**.

### macOS (Apple silicon: M1, M2, M3, M4)

1. Open `REDCap-Uploader-<version>-macOS-arm64.dmg` and drag **REDCap Uploader** into **Applications**.
2. Open it from Applications. The first time, macOS blocks it because the app is not yet notarised by Apple.
3. Go to **System Settings → Privacy & Security**, scroll down, and click **Open Anyway** next to the message about REDCap Uploader. Confirm once more.
4. From then on, it opens normally.

### Start in Demo mode

The app opens in **Demo mode**: a practice REDCap inside the app, with no account and no internet needed.

1. Click **Connect**, then **Next**.
2. On **Choose file**, click **Clean** under "Or try a sample" to load a synthetic sample file.
3. Click **Next** on each step until **Result**. Open **What's happening?** under any step to see what it does.

To use a real REDCap project, choose **My REDCap project** on the first step. Enter the API URL and token from your project's API page, and choose your team's pseudonym key file (it asks for the key's passphrase). If your team has no key yet, **Create a new key…** makes one; save the backup copy it asks for.

### If something goes wrong

The app's log is in your user app-data folder (Windows: `%LOCALAPPDATA%\RPRI\REDCap Uploader\logs`; macOS: `~/Library/Application Support/RPRI/REDCap Uploader/logs`). It never contains the token or patient identifiers, so it is safe to send to the developer.

# Data Mart Perjalanan Bus Antarkota

Proyek ini membangun data mart untuk studi kasus perjalanan bus antarkota
multi-leg dan loyalitas penumpang. Data yang digunakan bersifat sintetis dan
mencakup penjualan tiket, perjalanan penumpang pada setiap leg, serta transaksi
poin loyalitas.

## Hasil akhir

Hasil akhir proyek disimpan di folder [`reports`](reports/):

- [`Laporan_DWBI_Bus_Antarkota.pdf`](reports/Laporan_DWBI_Bus_Antarkota.pdf)
  berisi laporan dimensional modeling, pembuatan data sintetis, ETL, verifikasi,
  dan visualisasi.
- [`Presentasi_DWBI_Bus_Antarkota.pdf`](reports/Presentasi_DWBI_Bus_Antarkota.pdf)
  berisi slide presentasi proyek.

Visualisasi dibuat menggunakan Tableau dan Python. Workbook Tableau tersedia di
[`tableau/visualisasi-bus-antarkota.twbx`](tableau/visualisasi-bus-antarkota.twbx),
sedangkan dashboard Python tersedia di
[`visualisai-data-py/dashboard.py`](visualisai-data-py/dashboard.py).

## Ringkasan proses

Alur pengerjaan proyek adalah sebagai berikut:

1. Membuat data operasional sintetis dalam bentuk CSV.
2. Menjalankan ETL untuk membentuk dimension table dan fact table.
3. Memeriksa kualitas data dan menjalankan query analitik.
4. Membuat dashboard dengan Python dan Tableau.
5. Menyusun laporan dan slide presentasi dengan LaTeX.

Data mart mempunyai tiga fact table utama:

- `fct_ticket_sales`, sebanyak 25.000 baris;
- `fct_passenger_itinerary_leg`, sebanyak 24.980 baris; dan
- `fct_loyalty_transaction`, sebanyak 13.928 baris.

Sebanyak 20 itinerary leg yang melampaui kapasitas armada disimpan sebagai
rejected record dan tetap dicatat dalam rekonsiliasi data.

## Struktur folder

```text
.
├── reports/                       PDF laporan dan presentasi
├── contents/                      Isi Bab 1 dan Bab 2 dalam LaTeX
├── figures/                       Gambar diagram dan dashboard untuk laporan
├── synthetic-data-generation/    Generator dan data operasional sintetis
├── data-mart/                     ETL, skema, data dictionary, dan hasil data mart
├── verifikasi-data-mart/          Notebook query analitik dan data quality check
├── visualisai-data-py/            Dashboard Python dan screenshot hasil
├── tableau/                       Packaged workbook Tableau
├── images/                        Aset template LaTeX
├── Makalah.tex                    Dokumen utama laporan
├── Slide Tugas II DWBI.tex        Dokumen utama presentasi
└── Makefile                       Perintah render LaTeX
```

Folder `render/` digunakan untuk hasil kompilasi sementara dan tidak ikut
disimpan ke Git.

## Menjalankan di lokal

### 1. Persiapan Python

Gunakan Python 3 dan buat virtual environment di folder generator. Folder ini
sudah tercantum dalam `.gitignore`:

```bash
python3 -m venv synthetic-data-generation/.venv
source synthetic-data-generation/.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r synthetic-data-generation/requirements.txt
python -m pip install -r verifikasi-data-mart/requirements.txt
python -m pip install -r visualisai-data-py/requirements.txt
```

### 2. Membuat data sintetis

```bash
python synthetic-data-generation/generate.py
```

Data mentah disimpan di `synthetic-data-generation/data/raw/`. Generator akan
melewati proses pembuatan apabila folder tersebut sudah berisi data agar hasil
yang digunakan tidak tertimpa.

### 3. Menjalankan ETL

```bash
python data-mart/etl.py
```

Hasil ETL disimpan di `data-mart/output/`, terdiri atas dimension table, fact
table, manifest, dan rejected record.

### 4. Menjalankan verifikasi

```bash
jupyter notebook verifikasi-data-mart/verification.ipynb
```

Notebook memuat CSV data mart ke SQLite in-memory, menjalankan lima query
analitik, dan memeriksa kualitas data.

### 5. Menjalankan dashboard Python

```bash
python -m streamlit run visualisai-data-py/dashboard.py
```

Dashboard akan menampilkan alamat lokal, biasanya `http://localhost:8501`.

### 6. Membuka dashboard Tableau

Buka berkas berikut menggunakan Tableau Desktop atau Tableau Public:

```text
tableau/visualisasi-bus-antarkota.twbx
```

Format `.twbx` sudah menyertakan workbook dan sumber CSV yang digunakan.

### 7. Render laporan dan slide

Pastikan `latexmk` dan distribusi LaTeX sudah terpasang, kemudian jalankan:

```bash
make all
```

Perintah terpisah juga tersedia:

```bash
make makalah
make slide
```

Hasil kompilasi disimpan di folder `render/`.

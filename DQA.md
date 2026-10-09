# GreenGrid Energy — Data Dictionary & Data Quality Assessment Framework

Dokumen ini dirancang untuk project Renewable Curtailment & Energy Surplus Analysis menggunakan tujuh raw table versi V2.2. Tujuannya bukan hanya menjelaskan arti setiap kolom, tetapi juga menetapkan standar kualitas data yang dapat digunakan saat melakukan data profiling, data cleaning, validasi hubungan antartabel, dan rekonstruksi metrik analisis.

Prinsip utamanya adalah memisahkan data sumber (raw data) dari metrik hasil perhitungan (derived metrics). Dengan demikian, Anda dapat membangun formula sendiri selama proses analisis, bukan sekadar menggunakan KPI yang sudah disediakan oleh generator.

## 1. Konvensi dan aturan umum

Sebelum menilai setiap tabel, gunakan konvensi berikut.

* Raw layer: tujuh CSV utama dari sistem operasional simulasi. Kolom hasil perhitungan seperti `potential_generation_mwh`, `actual_generation_mwh`, `curtailment_mwh`, dan `soc_mwh` sengaja tidak diekspor.

* Grain: satu baris mewakili satu unit observasi bisnis, misalnya satu aset per jam atau satu wilayah per jam.

* Primary key (PK): kolom atau kombinasi kolom yang seharusnya mengidentifikasi setiap baris secara unik setelah duplikasi ditangani.

* Candidate foreign key (FK): kolom yang menghubungkan sebuah tabel dengan tabel referensi atau tabel lain.

* Expected range: batas nilai yang secara bisnis atau fisik masuk akal. Nilai di luar rentang tidak selalu harus langsung dihapus; lakukan investigasi terlebih dahulu.

* Hard validation: aturan yang jika dilanggar menunjukkan data tidak valid, misalnya `availability_pct` di atas 100%.

* Soft validation: aturan yang mengindikasikan anomali atau membutuhkan investigasi, misalnya perubahan permintaan listrik yang sangat tajam.

Perlu dibedakan pula antara validitas satu baris dan konsistensi antartabel. Sebuah nilai dapat berada dalam rentang yang wajar tetapi tetap salah apabila tidak cocok dengan catatan sumber lain.

Rentang tanggal operasional yang menjadi acuan adalah 1 Januari–31 Desember 2025, dengan pencatatan utama per jam. Data mentah sengaja mengandung duplikasi, nilai hilang, inkonsistensi format, dan anomali tertentu. Karena itu, jumlah baris raw tidak selalu sama dengan jumlah observasi unik yang diharapkan.

## 2. Ringkasan ketujuh raw table

| Raw table                          | Grain                            | Perkiraan jumlah baris raw | Fungsi utama                           |
| ---------------------------------- | -------------------------------- | -------------------------- | -------------------------------------- |
| `asset_registry_raw.csv`           | Satu baris per aset              | 6                          | Referensi aset pembangkit              |
| `weather_station_raw.csv`          | Satu stasiun per waktu observasi | 8.777                      | Kondisi sumber daya cuaca              |
| `scada_generation_raw.csv`         | Satu aset per jam                | 52.665                     | Status dan ketersediaan aset           |
| `ems_operations_raw.csv`           | Satu observasi sistem per jam    | 8.777                      | Permintaan listrik dan batas ekspor    |
| `bess_operations_raw.csv`          | Satu wilayah per jam             | 17.555                     | Aktivitas baterai penyimpanan energi   |
| `market_price_raw.csv`             | Satu observasi harga per jam     | 8.777                      | Konteks harga pasar listrik            |
| `dispatch_curtailment_log_raw.csv` | Satu kejadian curtailment        | 306                        | Catatan kejadian dan tindakan operator |

Jumlah baris di atas merupakan jumlah raw yang diharapkan dari versi generator ini, termasuk duplikasi yang sengaja disisipkan. Angka tersebut bukan target jumlah baris setelah cleaning. Jumlah observasi unik harus ditentukan dari grain dan periode data.

# 3. Data Dictionary dan DQA per tabel

## Tabel 1 — `asset_registry_raw.csv`

Tujuan bisnis: mengidentifikasi aset pembangkit yang dikelola GreenGrid Energy dan menyediakan atribut referensi untuk analisis berdasarkan teknologi, wilayah, dan kapasitas.

Grain: satu baris per aset pembangkit.

Primary key: `asset_id`.

Candidate foreign keys: tidak ada FK wajib ke enam tabel lainnya. Sebaliknya, `asset_id` berfungsi sebagai parent key bagi `scada_generation_raw.asset_id`.

| Kolom             | Data type yang seharusnya | Unit | Business meaning                    | Expected range / domain                                                |
| ----------------- | ------------------------- | ---- | ----------------------------------- | ---------------------------------------------------------------------- |
| `asset_id`        | String                    | —    | Identitas unik aset                 | Non-null, unik; pola ID konsisten                                      |
| `asset_name`      | String                    | —    | Nama operasional aset               | Non-null, tidak kosong                                                 |
| `technology`      | Categorical string        | —    | Teknologi pembangkit                | `Solar PV`, `Wind`                                                     |
| `region`          | Categorical string        | —    | Wilayah operasional aset            | `North`, `Central`                                                     |
| `grid_node`       | Categorical string        | —    | Node jaringan tempat aset terhubung | `NORTH_A`, `NORTH_B`, `CENTRAL_A`, `CENTRAL_B`                         |
| `capacity_mw`     | Decimal / Float           | MW   | Kapasitas nominal aset              | Lebih besar dari 0; sesuai master aset                                 |
| `commission_date` | Date                      | —    | Tanggal aset mulai beroperasi       | Tanggal valid, tidak lebih awal dari batas logis aset                  |
| `asset_status`    | Categorical string        | —    | Status aset dalam registry          | Domain status harus distandardisasi; konfirmasi kategori yang tersedia |
| `source_system`   | String / Categorical      | —    | Sistem sumber data                  | Non-null, nilai konsisten                                              |

### Validity rules

1. `asset_id` harus unik dan tidak boleh null.

2. `asset_name`, `technology`, `region`, dan `grid_node` tidak boleh kosong.

3. `capacity_mw` harus berupa angka positif.

4. `technology` harus konsisten dengan model aset. Sebagai contoh, aset solar harus menggunakan parameter pembangkitan solar, bukan kurva daya angin.

5. `region` dan `grid_node` harus konsisten. Aset di North tidak semestinya terhubung ke node Central.

6. `commission_date` harus dapat diparsing menjadi tanggal dan tidak boleh berada setelah tanggal observasi ketika aset diasumsikan telah beroperasi.

7. Nilai kategorikal seperti `north`, `North` , dan `NORTH` perlu dinormalisasi sebelum validasi domain.

### Relationship rules

* `asset_id` harus menjadi referensi valid untuk seluruh baris di `scada_generation_raw`.

* `capacity_mw` dalam registry harus cocok dengan kapasitas aset pada tabel SCADA setelah pembersihan tipe data.

* Satu `asset_id` hanya boleh memiliki satu kombinasi atribut master yang berlaku dalam periode analisis, kecuali memang terdapat riwayat perubahan aset yang dimodelkan secara eksplisit.

### Potential data quality issues

* ID aset duplikat.

* Perbedaan kapitalisasi atau spasi pada `technology`, `region`, dan `asset_status`.

* Kapasitas tersimpan sebagai teks atau menggunakan format numerik yang tidak konsisten.

* Nilai kapasitas nol atau negatif.

* Aset di tabel SCADA yang tidak ditemukan dalam registry.

* Perbedaan kapasitas antara registry dan SCADA.

Penanganan yang disarankan: bersihkan spasi dan kapitalisasi kategori, konversi kapasitas menjadi numerik, kemudian validasi keunikan `asset_id` dan kecocokan kapasitas dengan SCADA. Jangan menghapus duplikasi registry sebelum memeriksa apakah atribut pada baris yang duplikat identik.

## Tabel 2 — `weather_station_raw.csv`

Tujuan bisnis: menyediakan informasi cuaca yang membantu menjelaskan ketersediaan sumber daya solar dan wind pada setiap waktu observasi.

Grain: satu stasiun cuaca per waktu observasi.

Primary key kandidat: (`timestamp`, `station_id`).

Candidate foreign keys: `station_id` menuju master stasiun cuaca, apabila tabel master tersebut tersedia. Dalam tujuh tabel yang ada, master stasiun cuaca terpisah belum disediakan.

| Kolom                    | Data type yang seharusnya | Unit            | Business meaning                          | Expected range / domain                                |
| ------------------------ | ------------------------- | --------------- | ----------------------------------------- | ------------------------------------------------------ |
| `timestamp`              | Datetime                  | Waktu observasi | Waktu pengukuran cuaca                    | 2025-01-01 00:00 sampai 2025-12-31 23:00               |
| `station_id`             | String                    | —               | Identitas stasiun cuaca                   | Non-null, kategori konsisten                           |
| `solar_irradiance_index` | Decimal / Float           | Indeks relatif  | Indikator intensitas sumber daya matahari | Non-negatif; batas maksimum mengikuti definisi indeks  |
| `wind_speed_mps`         | Decimal / Float           | m/s             | Kecepatan angin                           | Secara fisik non-negatif; nilai ekstrem perlu ditinjau |
| `temperature_c`          | Decimal / Float           | °C              | Temperatur udara                          | Rentang fisik yang masuk akal untuk lokasi simulasi    |
| `source_system`          | String / Categorical      | —               | Sistem sumber                             | Non-null, konsisten                                    |
| `record_status`          | Categorical string        | —               | Status rekaman sumber                     | Domain status distandardisasi                          |

### Validity rules

1. `timestamp` harus dapat diparsing ke datetime tanpa kehilangan informasi jam.

2. Format waktu yang berbeda harus dinormalisasi ke format dan zona waktu yang sama. Karena data utama bersifat hourly, jangan membulatkan timestamp sembarangan.

3. `station_id` tidak boleh null.

4. `solar_irradiance_index` tidak boleh negatif. Jangan menetapkan batas atas numerik sebelum memastikan apakah indeks tersebut dinormalisasi atau memiliki skala tertentu.

5. `wind_speed_mps` tidak boleh negatif. Nilai yang sangat tinggi harus diperiksa terhadap kemungkinan kesalahan sensor atau konversi satuan.

6. `temperature_c` harus numerik dan berada dalam rentang yang masuk akal secara fisik. Rentang operasional yang spesifik sebaiknya ditentukan dari asumsi iklim simulasi, bukan diterapkan tanpa dasar.

7. Observasi yang hilang tidak boleh otomatis diisi dengan nol: nol berarti tidak ada intensitas sumber daya, sedangkan null berarti tidak tersedia pengukuran.

### Relationship rules

* Jika model analisis menggunakan satu stasiun per wilayah, perlu tersedia pemetaan `station_id` ke wilayah atau grid node. Karena kolom wilayah tidak tersedia pada tabel ini, pemetaan tersebut harus ditetapkan secara eksplisit sebelum menghubungkan data cuaca ke aset.

* Kombinasi (`timestamp`, `station_id`) seharusnya unik setelah duplikasi dibersihkan.

* Jika cuaca digunakan untuk menghitung potensi pembangkitan, pastikan setiap aset dipetakan ke stasiun yang relevan dan tidak menghasilkan penggandaan baris.

### Potential data quality issues

* Timestamp dengan format campuran.

* Duplikasi observasi stasiun dan waktu.

* Nilai `wind_speed_mps` yang hilang atau tidak masuk akal.

* Nilai numerik tersimpan sebagai teks.

* ID stasiun dengan spasi atau kapitalisasi tidak konsisten.

* Ketidakjelasan skala `solar_irradiance_index`.

* Hubungan stasiun–wilayah belum tersedia secara eksplisit.

Penanganan yang disarankan: normalisasi timestamp, periksa keunikan kunci kandidat, konversi variabel pengukuran ke numerik, dan tandai anomali fisik. Pertahankan kolom penanda kualitas atau buat kolom hasil cleaning agar nilai asli tetap dapat ditelusuri.

## Tabel 3 — `scada_generation_raw.csv`

Tujuan bisnis: merepresentasikan status operasional masing-masing aset pembangkit pada setiap jam. Tabel ini menjadi salah satu input utama untuk merekonstruksi potensi pembangkitan dan membandingkannya dengan energi aktual jika pengukuran aktual tersedia.

Grain: satu aset pembangkit per jam.

Primary key kandidat: (`timestamp`, `asset_id`).

Candidate foreign keys: `asset_id` → `asset_registry_raw.asset_id`.

| Kolom              | Data type yang seharusnya | Unit            | Business meaning                                    | Expected range / domain        |
| ------------------ | ------------------------- | --------------- | --------------------------------------------------- | ------------------------------ |
| `timestamp`        | Datetime                  | Waktu observasi | Waktu pencatatan status aset                        | Tahun 2025, interval hourly    |
| `asset_id`         | String                    | —               | Identitas aset pembangkit                           | Harus ada dalam asset registry |
| `capacity_mw`      | Decimal / Float           | MW              | Kapasitas nominal aset menurut rekaman SCADA        | Positif; cocok dengan registry |
| `availability_pct` | Decimal / Float           | %               | Persentase kapasitas yang tersedia untuk beroperasi | 0–100%                         |
| `source_system`    | String / Categorical      | —               | Sistem sumber data                                  | Non-null, konsisten            |
| `reading_status`   | Categorical string        | —               | Status pembacaan SCADA                              | Domain status distandardisasi  |

### Validity rules

1. `timestamp` dan `asset_id` wajib tersedia.

2. Kombinasi (`timestamp`, `asset_id`) harus unik setelah duplikasi ditangani.

3. `capacity_mw` harus numerik dan positif.

4. `availability_pct` harus berada pada rentang 0–100%.

5. `capacity_mw` harus sesuai dengan `asset_registry_raw.capacity_mw`. Perbedaan perlu ditelusuri, bukan langsung dirata-ratakan.

6. Setiap `asset_id` harus valid dalam registry dan tanggal observasinya harus konsisten dengan status operasional aset.

7. Nilai `availability_pct` yang hilang tidak boleh otomatis diganti dengan 100%, sebab itu akan mengasumsikan aset beroperasi penuh tanpa bukti.

### Relationship rules

* Setiap baris SCADA harus merujuk ke tepat satu aset di registry.

* Untuk setiap jam, jumlah observasi aset seharusnya enam pada konfigurasi ini, sebelum memperhitungkan aturan commissioning atau status aset.

* Kapasitas agregat per wilayah harus dihitung setelah memastikan tidak ada aset yang terduplikasi.

* Cuaca dapat digunakan untuk menghitung potensi energi, tetapi hubungan aset–stasiun harus ditetapkan secara eksplisit.

### Potential data quality issues

* Duplikasi aset dan timestamp.

* Nilai `availability_pct` null, berupa teks, atau di luar rentang, termasuk nilai negatif dan lebih dari 100%.

* Kapasitas tidak cocok dengan asset registry.

* Timestamp tidak valid atau tidak konsisten.

* Aset yang tidak dikenal dalam master.

* Observasi hilang pada jam tertentu.

Catatan penting untuk analisis: tabel V2.2 ini tidak memiliki `actual_generation_mwh` ataupun `potential_generation_mwh`. Artinya, Anda tidak dapat menghitung curtailment hanya dari tabel ini. `availability_pct` juga tidak sama dengan capacity factor: availability menggambarkan kesiapan aset, sedangkan capacity factor berkaitan dengan output energi relatif terhadap kapasitas nominal.

Jika Anda ingin merekonstruksi potensi pembangkitan, Anda membutuhkan kapasitas, ketersediaan, data sumber daya cuaca, dan asumsi atau model pembangkitan yang sesuai. Untuk menghitung curtailment secara langsung, Anda juga membutuhkan output aktual yang terukur atau model dispatch yang dapat direkonsiliasi.

## Tabel 4 — `ems_operations_raw.csv`

Tujuan bisnis: menyediakan konteks operasi sistem berupa permintaan listrik dan batas ekspor jaringan yang dapat memengaruhi kemampuan sistem menyerap energi terbarukan.

Grain: satu observasi sistem per jam.

Primary key kandidat: `timestamp`.

Candidate foreign keys: tidak ada FK langsung yang wajib. `timestamp` berfungsi sebagai kunci waktu untuk menghubungkan data ke tabel hourly lain.

| Kolom                     | Data type yang seharusnya | Unit            | Business meaning                                                    | Expected range / domain                                    |
| ------------------------- | ------------------------- | --------------- | ------------------------------------------------------------------- | ---------------------------------------------------------- |
| `timestamp`               | Datetime                  | Waktu observasi | Waktu pengamatan operasi sistem                                     | Tahun 2025, interval hourly                                |
| `total_demand_mwh`        | Decimal / Float           | MWh per jam     | Energi yang diminta atau dikonsumsi sistem selama interval satu jam | Non-negatif                                                |
| `north_export_limit_mw`   | Decimal / Float           | MW              | Batas daya ekspor dari wilayah North                                | Non-negatif; sesuai konfigurasi jaringan                   |
| `central_export_limit_mw` | Decimal / Float           | MW              | Batas daya ekspor dari wilayah Central                              | Non-negatif; sesuai konfigurasi jaringan                   |
| `source_system`           | String / Categorical      | —               | Sistem sumber data                                                  | Non-null, konsisten                                        |
| `demand_unit`             | Categorical string        | —               | Unit yang dicatat pada data permintaan                              | Unit harus teridentifikasi dan dikonversi secara konsisten |
| `record_status`           | Categorical string        | —               | Status rekaman EMS                                                  | Domain status distandardisasi                              |

### Validity rules

1. `timestamp` harus valid dan unik setelah duplikasi dihapus.

2. `total_demand_mwh` harus berupa angka non-negatif setelah konversi tipe data dan unit.

3. Batas ekspor harus berupa angka non-negatif dan tidak boleh berubah secara tidak masuk akal tanpa perubahan konfigurasi jaringan.

4. `demand_unit` harus diperiksa sebelum menggunakan angka permintaan. Jangan mengasumsikan seluruh nilai MWh hanya berdasarkan nama kolom.

5. Jika data menunjukkan permintaan dalam MW, konversi ke MWh membutuhkan durasi interval yang benar. Untuk interval satu jam, secara numerik MW × 1 jam menghasilkan MWh.

6. Permintaan yang hilang tidak boleh otomatis diisi nol karena dapat menciptakan surplus energi palsu.

7. Lonjakan permintaan yang ekstrem merupakan soft validation: periksa kemungkinan kesalahan satuan, format numerik, atau nilai input.

### Relationship rules

* Idealnya terdapat satu observasi EMS per timestamp.

* Timestamp harus konsisten dengan timestamp pada SCADA, BESS, weather, dan market.

* Batas ekspor EMS harus digunakan sesuai wilayah. Jangan menjumlahkan atau mengalokasikan batas jaringan secara sembarang tanpa memahami bagaimana jaringan dimodelkan.

* `total_demand_mwh` adalah permintaan sistem total. Data ini tidak otomatis menjelaskan berapa permintaan North dan Central secara terpisah.

### Potential data quality issues

* Duplikasi timestamp.

* Nilai demand hilang atau berupa teks.

* Ketidakkonsistenan unit MW dan MWh.

* Batas ekspor bernilai negatif atau tidak sesuai konfigurasi.

* Timestamp tidak cocok dengan tabel hourly lain.

* Demand yang tampak ekstrem karena kesalahan skala.

Catatan analitis: nama `total_demand_mwh` perlu dibaca sesuai definisi intervalnya. MWh merupakan energi selama suatu periode, bukan daya sesaat. Selain itu, jangan mengasumsikan bahwa demand sistem dapat dialokasikan ke setiap wilayah secara proporsional tanpa aturan alokasi yang jelas.

## Tabel 5 — `bess_operations_raw.csv`

Tujuan bisnis: menganalisis peran Battery Energy Storage System (BESS) dalam menyerap surplus energi, melepaskan energi ketika dibutuhkan, dan membantu mengurangi curtailment.

Grain: satu wilayah per jam.

Primary key kandidat: (`timestamp`, `region`).

Candidate foreign keys: `region` menuju domain wilayah dalam asset registry; `timestamp` menuju dimensi waktu atau timestamp pada tabel hourly lain.

| Kolom                         | Data type yang seharusnya | Unit            | Business meaning                                | Expected range / domain                          |
| ----------------------------- | ------------------------- | --------------- | ----------------------------------------------- | ------------------------------------------------ |
| `timestamp`                   | Datetime                  | Waktu observasi | Waktu pencatatan aktivitas baterai              | Tahun 2025, interval hourly                      |
| `region`                      | Categorical string        | —               | Wilayah tempat BESS beroperasi                  | `North`, `Central`                               |
| `battery_power_capacity_mw`   | Decimal / Float           | MW              | Batas daya pengisian atau pelepasan baterai     | Positif; sesuai spesifikasi                      |
| `battery_energy_capacity_mwh` | Decimal / Float           | MWh             | Kapasitas energi maksimum baterai               | Positif; sesuai spesifikasi                      |
| `charge_mwh`                  | Decimal / Float           | MWh per jam     | Energi yang masuk ke baterai selama interval    | Non-negatif, dibatasi daya dan ruang penyimpanan |
| `discharge_mwh`               | Decimal / Float           | MWh per jam     | Energi yang dikeluarkan baterai selama interval | Non-negatif, dibatasi daya dan energi tersimpan  |
| `source_system`               | String / Categorical      | —               | Sistem sumber data                              | Non-null, konsisten                              |
| `record_status`               | Categorical string        | —               | Status rekaman BESS                             | Domain status distandardisasi                    |

### Validity rules

1. Kombinasi (`timestamp`, `region`) harus unik setelah duplikasi dihapus.

2. `region` harus termasuk domain wilayah yang digunakan oleh GreenGrid.

3. Kapasitas daya dan energi baterai harus positif dan konsisten dengan konfigurasi.

4. `charge_mwh` dan `discharge_mwh` harus numerik serta tidak negatif.

5. Untuk interval satu jam, energi pengisian dan pelepasan tidak semestinya melebihi batas daya baterai dikalikan durasi interval. Dengan kapasitas daya 50 MW dan interval satu jam, batas idealnya 50 MWh per arah, sebelum mempertimbangkan definisi pengukuran dan toleransi operasional.

6. Pengisian dan pelepasan yang terjadi bersamaan pada interval yang sama perlu ditandai untuk investigasi. Beberapa sistem dapat mencatat keduanya akibat resolusi pengukuran, tetapi keadaan tersebut tidak boleh langsung dianggap normal.

7. Kapasitas energi harus tetap konsisten dengan spesifikasi baterai, kecuali terdapat catatan perubahan konfigurasi.

### Relationship rules

* `region` harus konsisten dengan domain wilayah dalam asset registry.

* Idealnya ada satu baris BESS untuk setiap kombinasi wilayah dan jam.

* Timestamp harus konsisten dengan tabel hourly lain agar pengaruh penyimpanan terhadap dispatch dapat dianalisis.

* `charge_mwh` dan `discharge_mwh` dapat digunakan untuk merekonstruksi state of charge (SOC), tetapi perhitungan membutuhkan SOC awal dan efisiensi pengisian/pelepasan.

### Potential data quality issues

* Duplikasi timestamp dan region.

* Nilai charge/discharge berupa teks atau null.

* Energi charge/discharge negatif atau melebihi batas daya.

* Kapasitas baterai yang tidak konsisten antarjam.

* Nama wilayah tidak konsisten.

* Rekonstruksi SOC menghasilkan nilai negatif atau melebihi kapasitas energi.

* Perbedaan konvensi apakah `discharge_mwh` berarti energi keluar dari baterai atau energi yang sampai ke jaringan.

Catatan analitis: pada konfigurasi generator, kapasitas daya BESS adalah 50 MW dan kapasitas energi 200 MWh per wilayah. SOC awal adalah 170 MWh untuk North dan 150 MWh untuk Central. Parameter ini penting jika Anda membangun formula SOC sendiri.

Dengan efisiensi pengisian 94% dan efisiensi pelepasan 92%, salah satu model rekonstruksi SOC adalah:

SOCt=SOCt−1+0.94 Charget−Discharget0.92SOC_t = SOC_{t-1} + 0.94\,Charge_t - \frac{Discharge_t}{0.92}SOCt=SOCt−1+0.94Charget−0.92Discharget

Formula ini berlaku jika `charge_mwh` merupakan energi input sebelum rugi pengisian dan `discharge_mwh` merupakan energi yang keluar dari baterai setelah rugi pelepasan sesuai definisi model tersebut. Jika konvensi metering berbeda, formulanya perlu disesuaikan. Rekonstruksi juga harus memperhitungkan data yang hilang dan urutan timestamp; SOC tidak boleh dihitung seolah-olah tidak ada observasi yang terlewat.

## Tabel 6 — `market_price_raw.csv`

Tujuan bisnis: menyediakan konteks harga listrik untuk mengevaluasi nilai ekonomi energi terbarukan yang tidak dapat dimanfaatkan. Harga pasar merupakan variabel kontekstual; harga itu sendiri bukan ukuran pendapatan yang hilang.

Grain: satu observasi harga pasar per jam.

Primary key kandidat: `timestamp`, dengan asumsi satu harga agregat per jam.

Candidate foreign keys: `timestamp` menuju dimensi waktu atau tabel hourly lain. Tidak tersedia kolom market zone atau node sehingga granularitas geografis harga harus dikonfirmasi.

| Kolom                      | Data type yang seharusnya | Unit            | Business meaning              | Expected range / domain                                                          |
| -------------------------- | ------------------------- | --------------- | ----------------------------- | -------------------------------------------------------------------------------- |
| `timestamp`                | Datetime                  | Waktu observasi | Waktu harga pasar berlaku     | Tahun 2025, interval hourly                                                      |
| `market_price_usd_per_mwh` | Decimal / Float           | USD/MWh         | Harga listrik per unit energi | Harus berupa nilai numerik; negatif hanya diperbolehkan jika sesuai aturan pasar |
| `source_system`            | String / Categorical      | —               | Sistem sumber harga           | Non-null, konsisten                                                              |
| `record_status`            | Categorical string        | —               | Status rekaman harga          | Domain status distandardisasi                                                    |

### Validity rules

1. `timestamp` harus valid dan unik setelah duplikasi dibersihkan.

2. Harga harus dikonversi menjadi angka dengan format desimal yang konsisten.

3. Jangan langsung menandai seluruh harga negatif sebagai invalid. Harga negatif dapat terjadi pada pasar listrik tertentu, walaupun perlu sesuai dengan asumsi pasar dalam simulasi.

4. Nilai harga yang sangat tinggi atau sangat rendah perlu diperiksa sebagai soft validation.

5. Nilai harga yang hilang tidak boleh otomatis diganti nol karena akan mengubah hasil estimasi nilai ekonomi.

6. Pastikan satuan USD/MWh benar dan tidak tertukar dengan USD/kWh atau mata uang lain.

### Relationship rules

* Idealnya ada satu observasi harga per timestamp.

* Harga hanya boleh dikaitkan dengan curtailment jika periode harga sesuai dengan waktu kejadian dan zona pasar relevan.

* Sebelum menghitung estimasi nilai ekonomi curtailment, periksa apakah harga berlaku untuk wilayah atau node yang sama dengan aset yang dianalisis.

### Potential data quality issues

* Duplikasi timestamp.

* Nilai harga berupa teks.

* Nilai hilang.

* Perbedaan unit atau mata uang.

* Timestamp tidak cocok dengan tabel dispatch atau SCADA.

* Ketidakjelasan market zone dan aturan harga.

* Korelasi harga dengan kondisi surplus yang dibangun oleh generator sintetis, sehingga hubungan keduanya tidak dapat dianggap sebagai bukti kausal dunia nyata.

Catatan bisnis: estimasi sederhana nilai energi yang ter-curtail dapat menggunakan:

Estimated Value=Curtailed Energy (MWh)×Market Price (USD/MWh)Estimated\ Value = Curtailed\ Energy\ (MWh) \times Market\ Price\ (USD/MWh)Estimated Value=Curtailed Energy (MWh)×Market Price (USD/MWh)

Hasilnya adalah estimasi nilai ekonomi indikatif, bukan otomatis kehilangan pendapatan aktual. Estimasi ini juga tidak memperhitungkan kontrak listrik, biaya variabel yang terhindarkan, biaya penyimpanan, batas penyelesaian pasar, atau apakah energi tersebut benar-benar dapat dijual.

## Tabel 7 — `dispatch_curtailment_log_raw.csv`

Tujuan bisnis: merepresentasikan catatan kejadian curtailment dan respons operasional. Tabel ini membantu menghubungkan analisis kuantitatif dengan alasan operasional yang tercatat oleh operator.

Grain: satu kejadian curtailment per baris.

Primary key: `event_id`, dengan asumsi setiap event mempunyai ID unik.

Candidate foreign keys: `region` menuju domain wilayah aset; `start_time` dan `end_time` menghubungkan kejadian dengan interval hourly pada tabel operasi.

| Kolom             | Data type yang seharusnya   | Unit          | Business meaning                    | Expected range / domain                                              |
| ----------------- | --------------------------- | ------------- | ----------------------------------- | -------------------------------------------------------------------- |
| `event_id`        | String                      | —             | Identitas unik kejadian             | Non-null, unik                                                       |
| `region`          | Categorical string          | —             | Wilayah tempat kejadian berlangsung | `North`, `Central`                                                   |
| `start_time`      | Datetime                    | Waktu mulai   | Awal kejadian curtailment           | Timestamp valid pada periode operasi                                 |
| `end_time`        | Datetime                    | Waktu selesai | Akhir kejadian curtailment          | Lebih besar dari atau sama dengan waktu mulai, sesuai definisi event |
| `reason`          | Categorical string          | —             | Alasan operasional yang dicatat     | Domain alasan distandardisasi                                        |
| `operator_action` | Categorical string / String | —             | Tindakan operator terhadap kejadian | Domain tindakan ditentukan dari data                                 |
| `source_system`   | String / Categorical        | —             | Sistem sumber event                 | Non-null, konsisten                                                  |
| `record_status`   | Categorical string          | —             | Status rekaman event                | Domain status distandardisasi                                        |

### Validity rules

1. `event_id` wajib terisi dan unik.

2. `region` harus cocok dengan domain wilayah.

3. `start_time` dan `end_time` harus dapat diparsing sebagai datetime.

4. `end_time` tidak boleh mendahului `start_time`.

5. Durasi event dapat dihitung dari kedua timestamp, tetapi interpretasinya perlu mengikuti konvensi pencatatan event. Jika timestamp menandai jam pertama dan terakhir yang terdampak, durasi yang dihitung dari selisih timestamp mungkin tidak sama dengan jumlah interval jam yang terdampak.

6. `reason` yang hilang harus ditandai untuk investigasi; jangan langsung mengisinya dengan alasan yang paling umum.

7. `operator_action` harus diperiksa terhadap domain tindakan yang masuk akal dan tidak boleh dianggap sebagai bukti bahwa tindakan tersebut berhasil.

8. Format timestamp yang berbeda perlu dinormalisasi tanpa mengubah makna waktu.

### Relationship rules

* Event seharusnya cocok dengan catatan hourly yang menunjukkan curtailment pada wilayah dan periode yang sama.

* Event log dapat mencakup beberapa jam. Karena itu, satu event tidak boleh langsung digabungkan dengan seluruh baris SCADA tanpa mengontrol grain.

* Rentang event yang tumpang tindih pada wilayah yang sama perlu diperiksa: bisa merupakan duplikasi, kejadian yang berbeda, atau konvensi pencatatan yang tumpang tindih.

* Alasan dan tindakan operasional sebaiknya dibandingkan dengan pola operasi aktual sebelum digunakan sebagai dasar root-cause analysis.

### Potential data quality issues

* Duplikasi `event_id` atau event yang tercatat lebih dari sekali dengan ID berbeda.

* `reason` hilang atau memiliki variasi ejaan/kapitalisasi.

* Timestamp tidak valid atau formatnya bercampur.

* `end_time` lebih awal daripada `start_time`.

* Event yang tidak cocok dengan catatan curtailment hourly.

* Event tumpang tindih.

* Ketidaksesuaian wilayah.

* Durasi event atau jumlah energi curtailment yang tidak cocok dengan hasil rekonstruksi.

Catatan analitis: versi raw tidak menyediakan `duration_hours`, `severity`, maupun `curtailed_energy_mwh`. Ketiganya dapat Anda bangun sebagai metrik turunan. Energi curtailment suatu event sebaiknya dihitung dari data hourly yang sudah dibersihkan dan direkonsiliasi, bukan sekadar mengalikan durasi event dengan satu nilai rata-rata tanpa memeriksa profil per jam.

# 4. Framework Data Quality Assessment lintas tabel

Data dictionary menetapkan definisi dan batas validitas. DQA menerjemahkannya menjadi serangkaian pemeriksaan yang dapat dijalankan berulang kali setiap kali data dimuat.

Saya menyarankan framework dengan delapan dimensi berikut.

| Dimensi kualitas                | Pertanyaan utama                                 | Contoh pemeriksaan                                            |
| ------------------------------- | ------------------------------------------------ | ------------------------------------------------------------- |
| Completeness                    | Apakah nilai wajib tersedia?                     | Persentase null per kolom                                     |
| Uniqueness                      | Apakah satu observasi dicatat lebih dari sekali? | Duplikasi PK atau candidate key                               |
| Validity                        | Apakah format dan nilai sesuai aturan?           | Persentase tanggal gagal parsing, availability di luar 0–100% |
| Consistency                     | Apakah nilai sesuai antarkolom dan antartabel?   | Kapasitas SCADA dibandingkan registry                         |
| Referential integrity           | Apakah semua FK memiliki parent yang valid?      | `asset_id` SCADA yang tidak ada di registry                   |
| Timeliness / temporal integrity | Apakah observasi berada pada waktu yang tepat?   | Timestamp di luar periode, jam yang hilang                    |
| Plausibility                    | Apakah nilai masuk akal secara fisik dan bisnis? | Charge BESS melebihi batas daya                               |
| Reconciliation                  | Apakah perhitungan dapat direkonsiliasi?         | Potensi − aktual − curtailment                                |

## 4.1. Matriks pemeriksaan per tabel

| Tabel          | Pemeriksaan wajib                                       | Pemeriksaan lanjutan                                       |
| -------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| Asset registry | PK unik, kolom wajib, kapasitas positif                 | Konsistensi region–grid node dan kapasitas dengan SCADA    |
| Weather        | Timestamp valid, key kandidat unik, nilai cuaca numerik | Kewajaran sensor dan pemetaan stasiun ke aset/wilayah      |
| SCADA          | Key kandidat unik, FK valid, availability 0–100%        | Kapasitas cocok dengan registry dan cakupan aset per jam   |
| EMS            | Timestamp unik, demand valid, unit konsisten            | Perubahan demand dan batas ekspor                          |
| BESS           | Key kandidat unik, nilai charge/discharge valid         | Batas daya, rekonstruksi SOC, kontinuitas SOC              |
| Market price   | Timestamp unik, harga numerik, unit terverifikasi       | Outlier harga dan konsistensi zona pasar                   |
| Dispatch log   | `event_id` unik, timestamp valid, reason diperiksa      | Event overlap, durasi, dan rekonsiliasi dengan data hourly |

## 4.2. Menetapkan severity dan prioritas temuan

Tidak semua masalah kualitas data harus ditangani dengan cara yang sama. Gunakan klasifikasi berikut untuk menentukan urutan perbaikan.

Critical — menghalangi analisis

Contoh: PK tidak dapat ditentukan, timestamp tidak dapat diparsing, kapasitas aset tidak diketahui, atau FK SCADA tidak memiliki pasangan dalam registry.

Tindakan: karantina atau perbaiki sebelum membangun metrik.

High — berpotensi mengubah hasil KPI

Contoh: demand hilang, availability melebihi 100%, unit demand tidak jelas, atau charge BESS melebihi batas daya.

Tindakan: investigasi dan koreksi sebelum analisis KPI terkait.

Medium / Low — tidak selalu menghalangi analisis

Contoh: variasi kapitalisasi kategori, inkonsistensi label, atau kolom metadata yang tidak terisi.

Tindakan: standarisasi dan dokumentasikan; evaluasi dampaknya terhadap penggunaan data.

Tingkat severity tersebut adalah rancangan awal untuk project, bukan klasifikasi yang sudah dihasilkan dari pengukuran aktual. Sebaiknya tambahkan kolom `severity`, `affected_rows`, `issue_rate_pct`, `business_impact`, `resolution_status`, dan `resolution_note` pada laporan hasil DQA.

## 4.3. KPI kualitas data yang perlu dihitung

Gunakan metrik berikut untuk setiap tabel dan kolom yang relevan.

| KPI kualitas data          | Formula                                               | Interpretasi                                                      |
| -------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------- |
| Completeness rate          | Non-null rows / Total rows × 100%                     | Proporsi nilai yang tersedia                                      |
| Duplicate rate             | Duplicate rows / Total rows × 100%                    | Proporsi baris yang teridentifikasi duplikat menurut aturan kunci |
| Validity rate              | Valid non-null values / Non-null values × 100%        | Proporsi nilai non-null yang memenuhi aturan validitas            |
| Referential integrity rate | Valid FK rows / Rows requiring FK × 100%              | Proporsi baris yang mempunyai referensi valid                     |
| Timestamp coverage         | Observed unique intervals / Expected intervals × 100% | Cakupan interval waktu yang tersedia                              |
| Reconciliation error       | Actual difference − Expected difference               | Selisih yang harus dijelaskan oleh model atau data                |

Untuk `duplicate rate`, definisikan terlebih dahulu apakah denominator adalah seluruh baris raw dan apakah yang dihitung merupakan baris duplikat tambahan atau semua baris dalam kelompok duplikat. Gunakan definisi yang sama sepanjang project agar hasilnya dapat dibandingkan.

Target awal yang dapat digunakan:

* PK unik setelah deduplikasi: 100%.

* FK valid: 100%, atau setiap pengecualian harus terdokumentasi.

* Nilai availability di luar 0–100%: 0 baris setelah penyelesaian anomali.

* Timestamp valid dan berada pada periode analisis: 100%.

* Error rekonsiliasi energi: mendekati nol dalam toleransi numerik yang ditentukan.

Untuk completeness, jangan memaksakan target 100% pada seluruh kolom tanpa membedakan tingkat kepentingannya. Kolom seperti `event_id` wajib lengkap, sementara kolom `reason` yang hilang mungkin masih memungkinkan analisis energi, tetapi membatasi analisis root cause.

# 5. Relationship rules dan data model

Hal yang paling penting dalam project ini adalah menjaga grain setiap tabel. Jangan langsung melakukan join semua tabel hanya karena semuanya memiliki kolom `timestamp`.

`asset_registry_raw`

1 baris per aset · PK: asset_id

1 → banyak

`scada_generation_raw`

1 baris per aset per jam · PK kandidat: timestamp + asset_id

`weather_station_raw`

Stasiun × waktu

`ems_operations_raw`

Sistem × waktu

`bess_operations_raw`

Wilayah × waktu

`market_price_raw`

Harga pasar × waktu

Keempat tabel di atas memiliki grain berbeda atau asumsi referensi waktu yang berbeda. Validasi kunci sebelum melakukan join.

`dispatch_curtailment_log_raw`

1 baris per event · PK: event_id

Hubungkan ke data hourly berdasarkan wilayah dan interval event setelah definisi waktu diverifikasi.

### Risiko utama: row multiplication

SCADA mempunyai satu baris per aset per jam, sedangkan BESS mempunyai satu baris per wilayah per jam. Apabila kedua tabel langsung di-join hanya berdasarkan timestamp, beberapa baris BESS dapat berulang untuk setiap aset. Akibatnya, energi BESS berpotensi dihitung berkali-kali.

Contoh: pada satu jam terdapat enam baris SCADA dan dua baris BESS. Join berdasarkan timestamp saja dapat menghasilkan 12 baris. Jika seluruh nilai BESS kemudian dijumlahkan, angka agregat bisa menjadi berlipat.

Solusinya:

1. Bersihkan dan validasi tiap tabel secara terpisah.

2. Tentukan grain analisis yang ingin dibangun.

3. Agregasikan data SCADA ke tingkat wilayah-jam sebelum menggabungkannya dengan BESS, jika memang sesuai kebutuhan analisis.

4. Untuk analisis tingkat sistem, agregasikan data pada grain sistem-jam.

5. Untuk analisis event, kaitkan event ke interval hourly dengan aturan inklusi waktu yang konsisten.

6. Verifikasi jumlah baris dan total energi sebelum serta sesudah setiap join.

# 6. Urutan implementasi Data Quality Assessment

Berikut urutan kerja yang saya rekomendasikan untuk membangun pipeline cleaning project ini.

1. Load raw data dan simpan salinan asli. Jangan menimpa tujuh CSV raw; simpan hasil cleaning di folder atau layer terpisah.

2. Data profiling. Periksa jumlah baris, tipe data aktual, null, nilai unik, duplikasi, dan statistik numerik setiap kolom.

3. Standardisasi tipe dan format. Parsing timestamp, konversi numerik, standarisasi kategori, dan validasi unit.

4. Deduplikasi berdasarkan grain. Gunakan PK atau candidate key yang telah diverifikasi. Jika baris dengan kunci sama memiliki nilai berbeda, investigasi sebelum menentukan baris yang dipertahankan.

5. Validasi rentang dan plausibility. Periksa kapasitas, availability, kecepatan angin, demand, harga pasar, dan operasi BESS.

6. Tangani missing values. Pilih antara imputasi, rekonstruksi, pengecualian, atau mempertahankan null berdasarkan makna bisnis dan dampak terhadap KPI.

7. Validasi referensi dan relasi. Periksa asset ID, region, kapasitas, timestamp, serta konsistensi event dengan data hourly.

8. Bangun derived metrics. Hitung potensi pembangkitan, aktual, curtailment, surplus, SOC, durasi event, dan estimasi nilai ekonomi dengan formula yang terdokumentasi.

9. Rekonsiliasi dan audit. Periksa hubungan matematis, bandingkan hasil dengan referensi validasi, dokumentasikan perbedaan, dan baru kemudian gunakan data untuk analisis bisnis.

## 7. Hal yang perlu diperhatikan sebelum membangun formula analisis

Ada satu batasan penting dalam desain raw V2.2: beberapa metrik yang sebelumnya tersedia di layer simulasi sengaja tidak diekspor. Dengan demikian, menghitung ulang KPI tidak selalu sesederhana menerapkan satu formula ke satu tabel.

* Potential generation: memerlukan kapasitas, availability, dan input cuaca yang relevan, disertai model pembangkitan solar atau wind yang sesuai.

* Actual generation: tidak tersedia sebagai pengukuran langsung dalam raw SCADA V2.2. Anda memerlukan pengukuran aktual tambahan atau model dispatch dan absorpsi sistem yang terdokumentasi.

* Curtailment: membutuhkan potential dan actual generation yang dihitung dengan basis yang konsisten.

* BESS SOC: memerlukan SOC awal, urutan waktu yang benar, efisiensi, serta aturan penanganan data hilang.

* Economic value: membutuhkan curtailed energy yang telah direkonsiliasi dan harga pasar yang relevan.

Karena itu, `reference/clean_truth_hourly.csv` dan `reference/expected_kpis.csv` pada paket generator sebaiknya diperlakukan sebagai referensi validasi, bukan sebagai pengganti proses analisis dari raw data. Gunakan referensi itu untuk menguji apakah rekonstruksi Anda konsisten, bukan untuk memasukkan hasil akhirnya langsung ke dataset analitis.

## 8. Checklist DQA yang dapat Anda gunakan

## DQA readiness checklist
Asset registry
[ ] asset_id unik dan lengkap
[ ] Kapasitas positif dan cocok dengan SCADA
[ ] Domain technology, region, dan grid_node konsisten

Weather
[ ] Timestamp berhasil diparsing
[ ] Kunci timestamp + station_id unik
[ ] Pengukuran cuaca numerik dan masuk akal
[ ] Pemetaan stasiun ke aset/wilayah terdokumentasi

SCADA
[ ] Kunci timestamp + asset_id unik
[ ] Seluruh asset_id ditemukan di registry
[ ] availability_pct berada pada 0–100%
[ ] Cakupan observasi aset per jam diperiksa

EMS
[ ] Timestamp unik
[ ] Demand numerik dan non-negatif
[ ] Unit demand telah diverifikasi
[ ] Export limit valid dan sesuai konfigurasi

BESS
[ ] Kunci timestamp + region unik
[ ] Charge dan discharge valid
[ ] Energi per interval tidak melebihi batas daya
[ ] Rekonstruksi SOC lolos validasi kontinuitas

Market
[ ] Timestamp unik
[ ] Harga numerik dan satuan valid
[ ] Outlier diperiksa
[ ] Kesesuaian periode dan zona harga diperiksa

Dispatch log
[ ] event_id unik
[ ] Timestamp mulai dan selesai valid
[ ] Reason yang hilang ditandai
[ ] Event cocok dengan curtailment hourly

Cross-table
[ ] Tidak ada row multiplication tak disengaja
[ ] Foreign key dan cakupan waktu diperiksa
[ ] Rekonsiliasi energi dan KPI terdokumentasi

Kesimpulan: Data Dictionary menjelaskan bagaimana setiap kolom harus ditafsirkan, sedangkan DQA memastikan bahwa nilai dan relasinya layak digunakan. Jika keduanya diterapkan secara konsisten, project ini akan menunjukkan kemampuan yang lebih mendalam daripada sekadar dashboard: Anda dapat memperlihatkan bagaimana data mentah yang tidak sempurna diubah menjadi dataset analitis yang valid, dapat ditelusuri, dan siap mendukung keputusan bisnis mengenai renewable curtailment dan energy surplus.

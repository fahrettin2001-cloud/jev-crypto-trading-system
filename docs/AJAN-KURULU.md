# Ajan kurulu — TradingAgents gölge modu

Durum: Kod ve testler hazır (16 Kasım 2026). Sunucuya kurulmadı; bir model API anahtarı ve Hostinger erişimi olan bir ekip üyesi gerekiyor.

## Ne yapar?

[TradingAgents](https://github.com/TauricResearch/TradingAgents) (Tauric Research, Apache-2.0, sabitlenen sürüm v0.7.1 / `9fa1196`) bir yatırım şirketini taklit eden çok ajanlı bir LLM sistemidir. Her gün BTCUSDT ve ETHUSDT için şu ajanlar çalışır:

1. **Analistler** (aynı anda): piyasa/teknik ve haber. Haber analisti `FRED_API_KEY` varsa makro verileri (faiz, enflasyon) da kullanır. Duygu analisti (Reddit, StockTwits; `/etc/jev/typesafe.env` varsa gönderiler **Jev** ile elenir) varsayılan olarak kapalı, çünkü bu siteler Hostinger'ın veri merkezi IP'sinden 403 veriyor. Açmak için servis satırına `--analysts market news social` yazılır.
2. **Boğa ve ayı araştırmacıları** tartışır; araştırma yöneticisi bir plan yazar.
3. **Trader** öneri verir; **risk ekibi** (agresif, nötr, temkinli) tartışır.
4. **Portföy yöneticisi** son notu verir: Buy / Overweight / Hold / Underweight / Sell.

`jev.ajan_kurulu` bu notu karar günlüğümüze yazar: Buy ve Overweight → BUY, Hold → HOLD, Underweight ve Sell → SELL. Okunamayan not HOLD + "inceleme" olarak kaydedilir.

## Güvenlik sınırları

- **Emir yok, sanal portföy de değişmez.** Modül `jev.live`, SQLite portföyü veya risk katmanını kullanmaz; bunu bir test de denetler. Canlı sanal bot aynen çalışmaya devam eder.
- API anahtarları yalnızca sunucudaki `/etc/jev/ajan.env` dosyasında durur (yalnızca root okur, 600; Jev gölge modunun `/etc/jev/typesafe.env` kuralıyla aynı). Depoya ve sonuç deposuna girmez.
- Analiz günü her zaman kapanmış bir gündür (varsayılan: dün, UTC). Fiyat o günün kapanışıdır, geleceğe ait veri kullanılmaz.
- Aynı gün ve coin ikinci kez çalıştırılmaz; böylece yanlışlıkla iki kez ücret ödenmez.
- Bir coinde hata olursa diğerleri yine çalışır; hata `gunluk.log` dosyasına yazılır.

## Nasıl ölçülür?

Karar gününün kapanışından **5 gün sonraki** kapanışa bakılır. Fiyat %1'den fazla yükseldiyse BUY haklı sayılır, %1'den fazla düştüyse SELL, ±%1 içinde kaldıysa HOLD haklı sayılır. `ozet.md` coin ve eylem bazında isabeti ve son 20 kararı gösterir. **En az 20 ölçülmüş karar** (2 coinle yaklaşık 2 hafta) olmadan sonuca güvenilmemeli. Ajanlar gerçek bir katkı gösterirse filtre olarak stratejiye eklenmesi ayrı bir karar ve PR olacak.

## Maliyet

Bir coin için tek çalışma onlarca LLM çağrısı yapar. İlk gece Sonnet 5.5 ile (2 coin, 3 analist) yaklaşık 1,66 USD tuttu. Bu yüzden 16 Kasım 2026'dan itibaren düşük maliyet ayarı kullanılıyor: iki katman da `claude-haiku-5-5`, tartışma turu 1, analist başına en fazla 8 veri çekme turu (`TRADINGAGENTS_MAX_TOOL_ROUNDS=8`), duygu analisti kapalı. Haiku 5.5 TradingAgents v0.7.1 listesinde olmadığı için günlükte "unknown model" uyarısı görünür, çalışmayı etkilemez. Kaliteyi artırmak için önce derin katman (yöneticiler) `claude-sonnet-5-5` yapılabilir.

## Sunucuya kurulum (root)

```bash
cd /opt/jev/app && git pull
bash deploy/install-ajan.sh          # ilk çalıştırmada /etc/jev/ajan.env oluşturur ve durur
nano /etc/jev/ajan.env               # bir model API anahtarı girin (ör. ANTHROPIC_API_KEY)
bash deploy/install-ajan.sh          # kurar, dünkü gün için bir deneme yapar, zamanlayıcıyı açar
```

Python 3.11 veya üstü gerekir; sunucuda daha eski bir sürüm varsa `PY=/usr/bin/python3.12 bash deploy/install-ajan.sh` gibi çalıştırın. TradingAgents ayrı bir sanal ortama (`/opt/jev/ajan-venv`) kurulur, canlı botun Python'una dokunulmaz.

- Zamanlayıcı: `jev-ajan.timer` her gün 00:30 UTC'de (03:30 TR) çalışır.
- Yayın: Mevcut `jev-sonuc.timer` sabah 08:20 TR'de çıktıları sonuç deposunun `son/ajan/` klasörüne kopyalar (`ozet.md`, `ajan_kararlar.jsonl`, son 14 günün raporları).
- El ile çalıştırmak: `systemctl start jev-ajan.service`. Durum: `journalctl -u jev-ajan.service -n 50`.
- Durdurmak: `systemctl disable --now jev-ajan.timer`.

## Yönetim ve raporlama

Ajanların çıktıları herkese açık sonuç deposunda durur. Bulutta çalışan zamanlanmış bir Claude görevi her sabah bu çıktıları okuyup bir yönetim raporu hazırlar:

- ajanlar çalıştı mı, hata var mı,
- verdikleri notlar ve gerekçelerinin özeti,
- bugüne kadarki isabet ve canlı sanal botla kıyas,
- maliyete değip değmediği ve önerilen ayar değişiklikleri.

Bu rapor tavsiye niteliğindedir. Ayar ve kod değişiklikleri yine PR ve ekip incelemesiyle yapılır.

## Kullanım (yerel)

```bash
python -m jev.ajan_kurulu calistir --dir ./ajan-deneme --symbols BTCUSDT --date 2026-11-14
python -m jev.ajan_kurulu ozet --dir ./ajan-deneme
```

Testler TradingAgents kurulmadan, sahte ajan ve sahte Binance verisiyle çalışır: `python -m unittest tests.test_ajan_kurulu`.

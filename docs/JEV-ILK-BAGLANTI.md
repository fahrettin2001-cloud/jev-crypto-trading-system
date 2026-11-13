# Jev: ilk bağlantı denemesi

Bu taslak yalnızca TypeSafe'in Jev servisine tek seferlik sentetik bir örnek gönderir. İşlem stratejisi, emir, Binance bağlantısı veya otomatik işlem içermez. Bulut ajanı 13 Kasım 2026'da sentetik örneği bir kez çalıştırdığını ve başarılı yanıt aldığını bildirdi; PR henüz ana dala birleşmedi.

## Gerekenler

- Python 3.10 veya üzeri ve erişilebilir bir sanal ortam.
- TypeSafe hesabı, API anahtarı ve kullanılabilir kredi. Güncel ücret ve koşullar: https://help.typesafe.ai/articles/5187202169-how-much-does-jev-cost
- API anahtarını GitHub'a, Obsidian'a, ekran görüntüsüne veya sohbete koymayın. İş bitince anahtarı koruyun; sızarsa iptal edin.

## Windows PowerShell ile deneme

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install typesafe-sdk
$env:TYPESAFE_API_KEY = Read-Host 'TypeSafe API anahtarı'
.\.venv\Scripts\python.exe -m examples.jev_baglanti
Remove-Item Env:TYPESAFE_API_KEY
```

Read-Host anahtarı ekranda gösterebilir; ekran paylaşırken çalıştırmayın. Anahtar yalnızca açık PowerShell oturumunda tutulur; terminaldeki komut geçmişine doğrudan anahtar yazmayın. Örnek bir kez API çağrısı yapar ve ücretli olabilir. Başarılı sonuç bağlantıyı gösterir; modelin piyasa tahmini veya kâr yeteneğini kanıtlamaz. Hatalarda işlem yapılmaz.

## Sonraki adımlar

Gerçek piyasa veya haber verisi eklemeden önce veri sözleşmesi, gecikme, maliyet limiti, hata yönetimi ve gizlilik değerlendirilecek. Jev yanıtları çevrimdışı örneklerde ölçülecek; ayrı risk katmanı ve sanal işlem kontrolü korunacak. Gerçek emir açma ayrı bir geliştirme ve değerlendirme gerektirir.

Resmî başlangıç rehberi: https://docs.typesafe.ai/introduction/quickstart

## Bulut bağlantı denemesi — 13 Kasım 2026

Bulut ajanı, ayrı sanal ortamda `typesafe-sdk 0.7.5` ile sentetik örneği çalıştırdığını ve fiyat artışı sorusuna 0,99 yanıtı aldığını bildirdi. Tek istek sınırı için denemede otomatik yeniden denemeler kapatıldı. Bu sonuç yalnızca bağlantı ve örnek ifadeyi değerlendirir; piyasa tahmini veya kârlılık doğrulaması değildir. API anahtarı paylaşılmadı; bu notu güncelleyen ajan denemeyi bağımsız tekrarlamadı.

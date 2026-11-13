# Risk politikasının yeniden açılışta korunması

13 Kasım 2026 — Fahrettin'in inceleme talebi.

## Önceki davranış ve doğrulanan sorun

PR #8 sürümünde bakiye, başlangıç bakiyesi, pozisyonlar, işlem geçmişi ve komisyon
oranları SQLite'ta tutuluyordu. Risk limitleri yalnızca Python nesnesindeydi.
`SQLitePortfolio.open(path)` çağrısı `risk` olmadan boş `RiskLimits()` oluşturuyordu.
Geçici dosyada 50 tutar sınırının reddettiği 100 tutarlı alışın yeniden açılışta
kabul edildiği doğrulandı. CLI de farklı/boş bir risk dosyasıyla limitleri
kaldırabiliyordu. Bu davranış güvenli bir yeniden başlatma varsayımı sağlamıyordu.

## Uygulanan çözüm önerisi

- Politika tüm alanlarıyla SQLite `risk_policies` tablosunda sürümlü saklanır.
- Limit verilmeden yeniden açma kayıtlı politikayı kullanır. `open(..., risk=...)`
  yalnızca eşit politikayı kabul eder; açılış sırasında farklı politika yazılmaz.
- Yeni/eskiden kalma politikasız hesap okunabilir ama alış/satış yapamaz.
- Politika eksik, bozuk veya şema sürümü desteklenmiyorsa işlem reddedilir.
- Değişiklik yalnızca açık `set_risk` / CLI `risk-set` adımıyla yapılır; eski
  sürümler tutulur. CLI beklenen mevcut sürümü zorunlu ister. Eski bir ekrandan
  başka kişinin yeni ayarının ezilmesi engellenir.
- Her alış/satış `BEGIN IMMEDIATE` altında en güncel politikayı okur. Açık kalmış
  eski bağlantı yeni limitleri atlayamaz. İşlemle politika sürümü birlikte yazılır.
- Eski hesaplar veri kaybı olmadan göç ettirilir; eski işlemlerin risk sürümü
  bilinmediğinden NULL kalır. Eski politikalar tahmin edilmez.

## Kullanım

Yeni hesap: `python -m jev --db paper.db init 10000 --risk risk.json`.
Yeniden açma ve işlemler kayıtlı politikayı kullanır; işlemde `--risk` verilmesi
zorunlu değildir. Verilirse kayıtlı politikayla aynı olması gerekir.
`risk-show` sürümü ve politikayı gösterir.
Eski politikasız hesapta veya bilinçli değişiklikte:

```bash
python -m jev --db paper.db risk-set --risk risk.json --expected-version 0
```

0, politika bulunmayan eski/yeni hesap içindir. Sonraki değişiklikte `risk-show`
ile görülen sürüm kullanılır. Boş `{}` açıkça seçilmiş sınırsız sanal politika
olarak kabul edilir; otomatik varsayılan değildir. Ekip sayısal limitleri seçmelidir.
Python'da `account.set_risk(limits, expected_version=version)` kullanılır.
`account.risk = limits` de açık politika değişikliğidir; yeni sürüm kaydeder.

## Güven sınırı

Bu yerel sanal sistemde SQLite dosyasına yazabilen veya Python çalıştırabilen
kullanıcı politikayı değiştirebilir. Bu, yetkisiz dosya müdahalesine karşı bir
kimlik doğrulama sistemi değildir. Gerçek para için bağımsız erişim kontrolü,
audit, canlı emir tasarımı ve ayrıca ekip onayı gerekir.

## Doğrulama

Özel testler: yeniden açma, politikası olmayan hesap, farklı/boş politikayla
açma, iki bağlantının yeni limitleri kullanması, işlemde sürüm kaydı, bozuk/ileri
şema, politika yazımının geri alınması ve eski şema göçü. Mevcut 60 test ile
birlikte 67 test geçti. Ek çalışmalar sonraki toplamı artırabilir.

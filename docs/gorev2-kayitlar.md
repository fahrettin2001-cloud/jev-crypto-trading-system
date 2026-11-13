# Görev 2 — SQLite kayıtları ve risk kontrolü taslağı

Uygulama PR #5 ile 13 Kasım 2026 tarihinde ana dala birleşti. Görev 1'in `Portfolio`,
`Position`, `Trade` ve `FeeSchedule` arayüzleri değiştirilmedi.

## Kullanım

Depo kökünde Python 3.10+ ile; dış paket veya servis gerekmez:

```python
from jev import SQLitePortfolio, RiskLimits

# 1000 USDT yalnızca değiştirilebilir örnek işlem üst limitidir;
# ekipçe kararlaştırılmış bir risk politikası değildir.
limits = RiskLimits(max_trade_notional="1000", allowed_symbols={"BTCUSDT"})
with SQLitePortfolio("paper.db", initial_cash="10000", risk=limits) as account:
    account.buy("BTCUSDT", "0.01", "50000")
    print(account.portfolio.cash)  # 9499.50000 (yeni hesapta)

with SQLitePortfolio("paper.db", risk=limits) as account:
    print(account.portfolio.positions["BTCUSDT"].quantity)  # 0.01
```

Örneği tekrar çalıştırmak aynı hesaba yeni alış ekler. `initial_cash`, `fees`
ve `quote` yalnızca yeni hesap oluştururken kullanılır; var olan hesapta kayıtlı
ayarlar korunur. Bir dosya bir hesap içerir. Bağlantıyı `with` veya `close()` ile
kapatın. `portfolio` bağımsız okuma kopyasıdır; kalıcı işlemler için doğrudan
`account.buy` / `account.sell` kullanın. Raporlama bu kopyanın mevcut çekirdek
metotlarıyla yapılır. Zaman verilirse saat dilimi içermeli; UTC'ye çevrilir.

## Tutarlılık

Her yazım `BEGIN IMMEDIATE` altında son hesabı okur, çekirdek işlemini uygular,
bakiye ve pozisyonları günceller, işlem geçmişine ekler ve birlikte commit eder.
Yazım/commit veya çekirdek hatasında rollback uygulanır. Paylaşılan canlı bir
portföy nesnesi tutulmadığından başarısız işlem bellekte bakiye değiştirmez.
Birden fazla bağlantı eski bakiye ile birbirinin işlemini ezmez; aynı bağlantıyı
farklı iş parçacıklarında kullanmayın. SQLite kilit/disk hataları çağırana iletilir.

Decimal tutarlar TEXT olarak saklanır; SQLite REAL dönüşümü kullanılmaz.
Hesap başlangıç bakiyesi, para birimi, maker/taker oranları, pozisyon miktarı ve
ortalama maliyet ile zamanlı işlem geçmişi yeniden yüklenir.

## Risk taslağı ve kapsam

`RiskLimits` kayıt katmanının her alış ve satışında çekirdekten önce çalışır:
boş sembol, sonlu/pozitif olmayan fiyat veya miktar reddedilir. İsteğe bağlı
sembol izin listesi ve komisyon hariç işlem tutarı üst limiti uygulanır.
Alıştan sonra komisyon dahil asgari nakit (`min_cash_reserve`) ve işlem fiyatıyla
ölçülen tek sembol pozisyon değeri (`max_position_notional`) sınırları da
isteğe bağlıdır. Bu iki kontrol satışlara uygulanmaz; işlem tutarı ve sembol
kontrolleri alış ve satışta sürer. Risk reddi hiçbir kayıt yazmadan rollback yapar.
Sayısal limit varsayılanı yoktur. Yetersiz nakit ve fazla satış çekirdekte reddedilir.
Risk politikası artık sürümlü olarak SQLite’ta tutulur; yeniden açma kayıtlı politikayı kullanır. Eski hesaplar için [göç yönergesini](RISK-KALICILIK-INCELEMESI.md) okuyun.
Doğrudan `Portfolio` kullanımı bu ek risk katmanını çalıştırmaz.

Bu ilk taslakta günlük zarar, tüm sembolleri kapsayan toplam pozisyon riski ve canlı emir
kontrolleri yoktur. Şifreleme, yedekleme, şema göçü ve birden fazla hesap desteği
bu değişikliğin kapsamı dışındadır. SQLite dosyaları yereldir, Git'e eklenmez.

## Doğrulama

```bash
python -m unittest discover -s tests -t . -v
python -m examples.demo
```

30 test geçti (19 mevcut, 11 yeni). Yeni testler yeniden açmayı, Decimal
hassasiyetini, maker komisyonunu, tam/kısmi satışı, yetersiz bakiye/varlığı,
geçersiz girdileri, risk reddini ve iki bağlantının güncel hesapla çalışmasını
kapsar. SQLite trigger ile bakiye güncellemesinden sonraki işlem kaydı yazımı
bilerek bozulur; bakiye, pozisyonlar ve geçmişin tamamen geri alındığı, yeniden
açıldığında da değişmediği ve sonraki işlemin çalıştığı doğrulanır.

## Genişletilmiş limit örneği

```python
limits = RiskLimits(
    max_trade_notional="1000",
    allowed_symbols={"BTCUSDT", "ETHUSDT"},
    min_cash_reserve="2000",
    max_position_notional="3000",
)
```

Bu tutarlar yalnızca örnektir. Nakit rezerve eşitse ve pozisyon değeri üst
limite eşitse alış kabul edilir. Tek sembol limiti, o semboldeki eski ve yeni
miktarın toplamını son işlem fiyatıyla değerler; ortalama maliyeti kullanmaz.
Piyasa hareketlerini sürekli izlemez ve farklı sembolleri birlikte sınırlamaz.
Politika yeni hesapta risk=limits ile kaydedilir; yeniden açılırken kayıtlı sürüm kullanılır.

Genişletme sonrası 39 test geçti: önceki 30 teste ek olarak rezerv sınırı,
komisyonun rezerve etkisi, birikimli pozisyon sınırı, yeni fiyatla değerleme,
sembol bazında uygulama, limit dışındayken pozisyon azaltan satış, yeniden açma,
geçersiz limitler ve sayısal taşma senaryoları doğrulandı.

## Fiyat güncelliği

İsteğe bağlı `max_price_age`, alış ve satış için fiyatın gözlem zamanını zorunlu
kılar. Limit verilmedikçe mevcut çevrimdışı kullanım değişmez. Aşağıdaki 30 saniye
sadece örnektir; ekibin kabul ettiği bir politika değildir:

```python
from datetime import datetime, timedelta, timezone
from jev import SQLitePortfolio, RiskLimits

limits = RiskLimits(max_price_age=timedelta(seconds=30))
with SQLitePortfolio("paper.db", initial_cash="10000", risk=limits) as account:
    # Gerçek veri entegrasyonunda bu zaman fiyat kaynağından gelmelidir.
    observed_at = datetime.now(timezone.utc)  # yalnızca çevrimdışı örnek
    account.buy("BTCUSDT", "0.01", "50000", price_observed_at=observed_at)
```

Kontrol `BEGIN IMMEDIATE` kilidi alınıp hesap yüklendikten sonra yapılır;
kilit beklerken eskiyen fiyat da reddedilir. Eksik, saat dilimsiz, gelecekteki
ve limitten daha eski gözlem zamanları `RiskError` üretir. Tam yaş sınırındaki
fiyat kabul edilir. Eksik/geçersiz fiyat tutarı mevcut sayısal kontrollerle reddedilir.
`timestamp` işlem kaydı zamanıdır; fiyat gözlem zamanı yerine kullanılamaz ve
kontrol saatini değiştirmez. Saat dilimleri UTC'ye çevrilerek karşılaştırılır.

Varsayılan kontrol saati UTC sistem saatidir. Deterministik test veya çevrimdışı
geçmiş veri simülasyonunda `SQLitePortfolio(..., clock=...)` ile saat sağlayıcı
verilebilir; bu sağlayıcı güvenilir uygulama yapılandırması olmalıdır. Ajan veya
harici fiyat içeriği kontrol saatini belirlememelidir. Tarihsel simülasyonda saat
ilgili simülasyon anını döndürmelidir; güncellik kontrolü için işlem `timestamp`ini
eskiletmek yeterli değildir.

Politika yeniden açılışta SQLite’tan yüklenir. Bu katman bir veri kaynağına
bağlanmaz; gözlem zamanının kaynaktaki doğruluğunu veya fiyatın gerçek piyasa fiyatı
olduğunu doğrulamaz. Gözlem zamanı bu sürümde veritabanına ayrıca kaydedilmez.
Fiyat hatasında satış için de geçerli bir fiyat gerekir; nakit/pozisyon üst limitleri
nedeniyle satışa tanınan istisna güncellik kontrolünü kaldırmaz.

Güncellik geliştirmesi sonrası 52 test geçti (39 mevcut, 13 yeni): güncel ve tam
sınırdaki fiyat, eski/gelecek/eksik zaman, saat dilimi, işlem tarihiyle aşma denemesi,
satış, yeniden açma, kilit sonrasında eskime, hatalı saat, varsayılan saat, önceki
çevrimdışı kullanım ve geçersiz yaş limitleri kapsanır.

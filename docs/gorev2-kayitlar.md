# Görev 2 — SQLite kayıtları ve risk kontrolü taslağı

Yerel uygulama tamamlandı, ekip incelemesi bekliyor. Görev 1'in `Portfolio`,
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
Sayısal limit varsayılanı yoktur. Yetersiz nakit ve fazla satış çekirdekte reddedilir.
Risk ayarları dosyaya kaydedilmez; her açılışta açıkça verilmelidir.
Doğrudan `Portfolio` kullanımı bu ek risk katmanını çalıştırmaz.

Bu ilk taslakta günlük zarar, fiyat güncelliği, toplam pozisyon riski ve canlı emir
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

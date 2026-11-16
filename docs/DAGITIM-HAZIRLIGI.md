# Hostinger dağıtımı için hazırlık — henüz dağıtılmadı

Hedef Hostinger ürününün Python/süreç desteği, VPS erişimi, kullanıcı, işletim
sistemi ve alan adı bilinmiyor. Bu yüzden sunucuya bağlanılmadı, servis kurulmadı.
`deploy/jev-panel.service.example`, systemd kullanan Linux VPS için incelenecek
örnektir; paylaşımlı web hosting üzerinde çalıştığı varsayılmaz.

Beklenen yerleşim: `/opt/jev` kodu ve sanal ortamı, `/var/lib/jev` hesap dosyası,
`jev` ayrı servis kullanıcısı. `python -m pip install .` şifreleme bağımlılığını
kurar. Hesap ve politika, terminal arayüzüyle dağıtımdan önce hazırlanmalı veya
şifreli yedekten yeni dosyaya geri yüklenmelidir. Yedek anahtarı Git'e konulmaz;
ayrı sır yöneticisinde korunur.

Örnek servis paneli sadece 127.0.0.1:8765 üzerinde açar. Kullanıcı kendi
bilgisayarından `ssh -L 8765:127.0.0.1:8765 kullanici@sunucu` ile bağlanabilir.
Panel salt okunurdur; internetten doğrudan yayın veya kullanıcı oturumu sistemi
bu sürümde hazırlanmadı. Kamusal web yayını istenirse kimlik doğrulama, HTTPS ve
uygun sunucu kurulumu ayrıca tasarlanmalıdır.

Hedef bilgisi geldiğinde: Python sürümü ve kaynakları kontrol et, bağımlılıkları
kur, geçici hesapta testleri çalıştır, şifreli yedek/geri yükleme dene, örnek servis
adımlarını gerçek dizinlerle doğrula. Son adım gerçek sunucuya dağıtımdır; yalnızca
bu dosyanın bulunması dağıtımın çalıştığı anlamına gelmez.

Gerçek borsa anahtarı veya canlı emir yolu eklenmedi. Bunlar önceki proje
kurallarındaki ayrı test ve ekip değerlendirmesi aşamasında kalır.

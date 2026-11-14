"""Jev bağlantısı için tek seferlik, sentetik ve işlem açmayan örnek."""
import os
import sys


def main():
    if not os.environ.get("TYPESAFE_API_KEY"):
        print("TYPESAFE_API_KEY ayarlanmamış; çağrı yapılmadı.", file=sys.stderr)
        return 1
    try:
        from typesafe_sdk import Noul, TypeSafeClient
    except ImportError:
        print("TypeSafe SDK kurulu değil: python -m pip install typesafe-sdk", file=sys.stderr)
        return 1

    # Gerçek hesap, haber veya piyasa verisi gönderilmez.
    state = "Sentetik örnek: BTCUSDT fiyatı 100 birimden 105 birime yükseldi."
    try:
        with TypeSafeClient(model="jev-latest") as client:
            response = client.system_one(
                state=state,
                questions={
                    "price_increased": Noul(
                        instructions="Does the example say the price increased?"
                    )
                },
            )
        print("Fiyat artışı ifadesi için model olasılığı:", response.nouls["price_increased"].noul)
    except Exception:
        # Kimlik bilgileri ya da istek ayrıntıları konsola yazdırılmaz.
        print("Jev çağrısı başarısız; API erişimini ve krediyi kontrol edin.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

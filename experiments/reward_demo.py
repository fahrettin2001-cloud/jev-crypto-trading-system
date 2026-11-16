"""Yalnızca sentetik verilerle ödül hesabı; işlem veya model eğitimi yapmaz."""
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name}: sayı gerekli")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"{name}: geçerli sayı gerekli") from None
    if not number.is_finite():
        raise ValueError(f"{name}: sonlu sayı gerekli")
    return number


def reward_record(previous_equity, current_equity, previous_peak, *,
                  period_fees=0, drawdown_weight=0):
    """Aynı para birimindeki komisyon dahil net portföy değerlerinden skor üret.

    Para yatırma/çekme içermeyen ardışık, aynı kapsamlı değerlemeler bekler.
    period_fees yalnızca rapor içindir; değerden yeniden düşülmez.
    drawdown_weight açıkça ayarlanmadıkça risk cezası sıfırdır.
    """
    prev = _number(previous_equity, "previous_equity")
    curr = _number(current_equity, "current_equity")
    peak = _number(previous_peak, "previous_peak")
    fees = _number(period_fees, "period_fees")
    weight = _number(drawdown_weight, "drawdown_weight")
    if prev <= 0 or curr < 0 or peak < prev or fees < 0 or weight < 0:
        raise ValueError("Değerler veya önceki tepe geçersiz")
    old_drawdown = (peak - prev) / peak
    new_peak = max(peak, curr)
    new_drawdown = (new_peak - curr) / new_peak
    net_change = curr - prev
    net_return = net_change / prev
    risk_penalty = weight * max(Decimal(0), new_drawdown - old_drawdown)
    return {
        "previous_equity": str(prev), "current_equity": str(curr),
        "previous_peak": str(peak), "new_peak": str(new_peak),
        "period_fees_included": str(fees), "net_change": str(net_change),
        "net_return": str(net_return), "previous_drawdown": str(old_drawdown),
        "current_drawdown": str(new_drawdown), "drawdown_weight": str(weight),
        "risk_penalty": str(risk_penalty), "reward": str(net_return - risk_penalty),
    }


def append_record(path, record):
    """Açıkça verilen yerel dosyaya tek JSON satırı ekler; ağ kullanmaz."""
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


if __name__ == "__main__":
    example = reward_record("500", "502", "500", period_fees="0.2")
    print("Sentetik örnek: sanal portföy değeri 500 → 502")
    print("Ücretler değere dahildir; bir kez daha çıkarılmaz.")
    print(f"Net değişim: {example['net_change']}; ödül: {example['reward']}")
    print("Bu bir öğrenme adımı veya piyasa performansı değildir.")

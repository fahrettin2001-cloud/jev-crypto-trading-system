#!/usr/bin/env bash
# Canlı bot klasörüne dokunmadan, geçici ayrı hesapta kurtarma doğrulaması.
set -euo pipefail
cd "$(dirname "$0")/.."
"${JEV_PYTHON:-python3}" - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from jev import SQLitePortfolio, RiskLimits, RiskError
from jev.backup import create_key, encrypted_backup, restore_backup

with TemporaryDirectory(prefix='jev-recovery-check-') as folder:
    root = Path(folder)
    source, restored = root/'source.db', root/'restored.db'
    key, backup = root/'key.jevkey', root/'snapshot.jevbackup'
    create_key(key)
    with SQLitePortfolio(source,initial_cash=1000,risk=RiskLimits(max_trade_notional=50)) as account:
        account.buy('BTCUSDT','0.0004',100000)
        expected = account.portfolio
        encrypted_backup(account,backup,key)
    restore_backup(backup,restored,key)
    with SQLitePortfolio.open(restored) as account:
        assert account.portfolio == expected, 'Hesap geri yüklemesi farklı'
        assert account.policy_status()[0] == 1, 'Politika sürümü farklı'
        try:
            account.buy('BTCUSDT','0.001',100000)
        except RiskError:
            pass
        else:
            raise AssertionError('Yeniden açılmış hesap risk limitini korumadı')
        account.sell('BTCUSDT','0.0004',150000)
        assert account.portfolio.positions == {}, 'Pozisyon satılamadı'
print('OK: ayrı sanal hesapta şifreli yedek, geri yükleme, risk kalıcılığı ve satış doğrulandı.')
PY

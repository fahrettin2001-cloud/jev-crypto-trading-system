$ErrorActionPreference = 'Stop'
$repo = Join-Path (Split-Path $PSScriptRoot -Parent) 'jev-crypto-trading-system'
$notes = 'notlar/paylasilan'
$log = Join-Path $PSScriptRoot 'yedekleme.log'
$git = 'C:\Program Files\Git\cmd\git.exe'

function Log([string]$message) {
    Add-Content -LiteralPath $log -Encoding UTF8 -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $message)
}
function Git([string[]]$arguments) {
    $ErrorActionPreference = 'Continue'
    $output = & $git @arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw ('Git komutu basarisiz: ' + $arguments[0]) }
    return $output
}

try {
    Set-Location -LiteralPath $repo
    if ((Git @('branch', '--show-current')) -ne 'main') { throw 'Ana dalda degil; islem durduruldu.' }
    $remote = Git @('remote', 'get-url', 'origin')
    if ($remote -notin @('https://github.com/fahrettin2001-cloud/jev-crypto-trading-system.git', 'https://github.com/fahrettin2001-cloud/jev-crypto-trading-system')) { throw 'Beklenen GitHub deposu bulunamadi.' }
    $staged = @(Git @('diff', '--cached', '--name-only'))
    if ($staged.Count -gt 0) { throw 'Onceden stage edilmis degisiklik var; islem durduruldu.' }
    $env:GIT_TERMINAL_PROMPT = '0'
    $env:GCM_INTERACTIVE = 'Never'
    Git @('fetch', 'origin', 'main') | Out-Null
    $local = Git @('rev-parse', 'HEAD')
    $upstream = Git @('rev-parse', 'refs/remotes/origin/main')
    if ($local -ne $upstream) {
        Git @('merge-base', '--is-ancestor', 'HEAD', 'refs/remotes/origin/main') | Out-Null
        Git @('merge', '--ff-only', 'refs/remotes/origin/main') | Out-Null
    }
    $changed = @(Git @('ls-files', '--modified', '--deleted', '--others', '--exclude-standard', '--', $notes))
    if ($changed.Count -eq 0) { Log 'Degisiklik yok; yedekleme gerekmiyor.'; exit 0 }
    foreach ($path in $changed) {
        if (-not $path.EndsWith('.md', [StringComparison]::OrdinalIgnoreCase)) { throw 'Paylasilan klasorde Markdown disi degisiklik var; islem durduruldu.' }
        if (Test-Path -LiteralPath $path) {
            $item = Get-Item -LiteralPath $path -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Baglanti dosyasi algilandi; islem durduruldu.' }
            $body = Get-Content -LiteralPath $path -Raw -Encoding UTF8
            if ($body -match '(?i)(-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|(?:api[_ -]?key|secret[_ -]?key|password|sifre)\s*[:=]\s*["'']?[^\s"'']{8,})') { throw 'Olası gizli bilgi algilandi; islem durduruldu.' }
        }
    }
    Git @('add', '-A', '--', $notes) | Out-Null
    $staged = @(Git @('diff', '--cached', '--name-only'))
    if ($staged.Count -eq 0) { Log 'Commit edilecek degisiklik yok.'; exit 0 }
    Git @('-c', 'user.name=fahrettin2001-cloud', '-c', 'user.email=287992302+fahrettin2001-cloud@users.noreply.github.com', 'commit', '-m', 'docs: paylasilan notlari yedekle') | Out-Null
    Git @('push', 'origin', 'main') | Out-Null
    Log ('Basarili: ' + (Git @('rev-parse', '--short', 'HEAD')))
} catch {
    Log ('HATA: ' + $_.Exception.Message)
    exit 1
}


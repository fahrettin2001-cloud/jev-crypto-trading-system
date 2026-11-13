$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path $PSScriptRoot 'yedekle.ps1'
$taskName = 'Jev-Not-Yedekleme'

Write-Host 'Once yedekleme deneniyor...'
& powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $scriptPath
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Deneme basarisiz. Gorev olusturulmadi. Son kayit:'
    Get-Content -LiteralPath (Join-Path $PSScriptRoot 'yedekleme.log') -Tail 3
    exit 1
}
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Write-Host 'Bu isimde bir gorev zaten var; uzerine yazilmadi.'
    exit 1
}
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $scriptPath + '"')
$trigger = New-ScheduledTaskTrigger -Daily -At '23:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Jev paylasilan Markdown notlarini gunluk yedekler' | Out-Null
Write-Host 'Gorev olusturuldu. Son kayit:'
Get-Content -LiteralPath (Join-Path $PSScriptRoot 'yedekleme.log') -Tail 3


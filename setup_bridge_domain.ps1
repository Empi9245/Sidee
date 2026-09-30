# Explicit local routing repair for the owner's passive collector. No TV commands.
param([Parameter(Mandatory=$true)][string]$ExpectedHostsSha256)
$ErrorActionPreference = 'Stop'
$bridgeWorkspace = $PSScriptRoot
$bridgeStatusPath = Join-Path $bridgeWorkspace 'reports\bridge-domain-setup.json'
$bridgeResult = @{ target = 'vidaahub.com'; previousIp = '192.168.1.8'; currentIp = '192.168.1.5'; changed = $false; success = $false }
try {
    $bridgeHostsPath = Join-Path $env:WINDIR 'System32\drivers\etc\hosts'
    if ((Get-FileHash -LiteralPath $bridgeHostsPath -Algorithm SHA256).Hash -ne $ExpectedHostsSha256) {
        throw 'Hosts changed since preparation; no change made.'
    }
    $bridgeBefore = [IO.File]::ReadAllBytes($bridgeHostsPath)
    $bridgeEncoding = [Text.Encoding]::GetEncoding(28591)
    $bridgeText = $bridgeEncoding.GetString($bridgeBefore)
    $bridgePattern = '(?m)^192\.168\.1\.8(?=[\t ]+vidaahub\.com(?:[\t ]|\r?$))'
    if ([regex]::Matches($bridgeText, $bridgePattern).Count -ne 1) {
        throw 'Expected single stale vidaahub mapping missing; no change made.'
    }
    $bridgeBackup = Join-Path $bridgeWorkspace ('reports\bridge-domain-hosts-before-admin-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bin')
    [IO.File]::WriteAllBytes($bridgeBackup, $bridgeBefore)
    $bridgeResult.backup = $bridgeBackup
    $bridgeAfter = [regex]::Replace($bridgeText, $bridgePattern, '192.168.1.5')
    [IO.File]::WriteAllBytes($bridgeHostsPath, $bridgeEncoding.GetBytes($bridgeAfter))
    $bridgeResult.changed = $true
    $bridgeResult.beforeSha256 = $ExpectedHostsSha256
    $bridgeResult.afterSha256 = (Get-FileHash -LiteralPath $bridgeHostsPath -Algorithm SHA256).Hash
    Clear-DnsClientCache
    $bridgeResult.success = $true
} catch {
    $bridgeResult.error = $_.Exception.Message
} finally {
    $bridgeResult.finishedAt = [DateTime]::UtcNow.ToString('o')
    $bridgeResult | ConvertTo-Json | Set-Content -LiteralPath $bridgeStatusPath -Encoding UTF8
}

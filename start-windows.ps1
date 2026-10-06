#Requires -Version 5.1
param([switch]$PrepareOnly)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

$sideeRoot = $PSScriptRoot
$sideeRuntimeRoot = Join-Path $sideeRoot '.runtime'
$sideePythonVersion = '3.13.16'
$sideePackageVersion = '2.1.0'
# Published SHA-256 checksums: https://www.python.org/downloads/release/python-31316/
$sideePythonHashes = @{
    amd64 = '97dae5274cc54867065e8d5a3226e48c35017ed332a0fdb0e27d5b5821961297'
    win32 = '0a3b162281b0a8e4d95d748e40ec2db9927086c7ec4231a5c8d29f91a1c2ba89'
    arm64 = '790d097697a2020477549a6764d89d22194c88d6e42caebcb2db63791e004c94'
}
$sideePackageUrl = 'https://files.pythonhosted.org/packages/c4/cb/00451c3cf31790287768bb12c6bec834f5d292eaf3022afc88e14b8afc94/paho_mqtt-2.1.0-py3-none-any.whl'
$sideePackageHash = '6db9ba9b34ed5bc6b6e3812718c7e06e2fd7444540df2455d2c51bd58808feee'

function Get-SideeFileHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '')
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

function Remove-SideeSetupPath([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path)
    $allowedRoot = [IO.Path]::GetFullPath($sideeRuntimeRoot).TrimEnd('\') + '\'
    if (-not $fullPath.StartsWith($allowedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Setup cleanup is outside the local runtime folder.'
    }
    if (Test-Path -LiteralPath $fullPath) {
        Remove-Item -LiteralPath $fullPath -Recurse -Force
    }
}

function Get-SideeDownload([string]$Url, [string]$Hash, [string]$Name) {
    $cache = Join-Path $sideeRuntimeRoot 'downloads'
    New-Item -ItemType Directory -Path $cache -Force | Out-Null
    $destination = Join-Path $cache $Name
    if ((Test-Path -LiteralPath $destination) -and
        ((Get-SideeFileHash $destination) -eq $Hash)) {
        return $destination
    }
    $partial = Join-Path $cache ([Guid]::NewGuid().ToString('N') + '.part')
    try {
        Invoke-WebRequest -Uri $Url -OutFile $partial -UseBasicParsing -TimeoutSec 90
        if ((Get-SideeFileHash $partial) -ne $Hash) {
            throw 'A setup download failed its integrity check. Please try again.'
        }
        Move-Item -LiteralPath $partial -Destination $destination -Force
    } finally {
        Remove-SideeSetupPath $partial
    }
    return $destination
}

function Expand-SideePackage([string]$Archive, [string]$Destination, [string]$ExpectedFile) {
    $staging = Join-Path $sideeRuntimeRoot ('setup-' + [Guid]::NewGuid().ToString('N'))
    try {
        [IO.Compression.ZipFile]::ExtractToDirectory($Archive, $staging)
        if (-not (Test-Path -LiteralPath (Join-Path $staging $ExpectedFile))) {
            throw 'The setup package is incomplete. Please try again.'
        }
        Remove-SideeSetupPath $Destination
        $parent = Split-Path -Parent $Destination
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        Move-Item -LiteralPath $staging -Destination $Destination
    } finally {
        Remove-SideeSetupPath $staging
    }
}

$sideeSetupLock = $null
try {
    Write-Host 'Sidee' -ForegroundColor Yellow
    if (-not (Test-Path -LiteralPath (Join-Path $sideeRoot 'sidee.py'))) {
        throw 'Extract the entire downloaded ZIP into a folder before opening start-windows.bat.'
    }
    $machine = $env:PROCESSOR_ARCHITEW6432
    if (-not $machine) { $machine = $env:PROCESSOR_ARCHITECTURE }
    $architecture = switch ($machine.ToUpperInvariant()) {
        'AMD64' { 'amd64' }
        'ARM64' { 'arm64' }
        'X86' { 'win32' }
        default { throw 'This computer architecture is not supported.' }
    }
    New-Item -ItemType Directory -Path $sideeRuntimeRoot -Force | Out-Null
    try {
        $sideeSetupLock = [IO.File]::Open((Join-Path $sideeRuntimeRoot 'setup.lock'),
            [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    } catch {
        throw 'Sidee is already preparing this folder. Wait for its other window to finish.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $pythonDirectory = Join-Path $sideeRuntimeRoot "python-$sideePythonVersion-$architecture"
    $pythonExecutable = Join-Path $pythonDirectory 'python.exe'
    $packageDirectory = Join-Path $sideeRuntimeRoot "packages\paho-mqtt-$sideePackageVersion"
    $packageReady = Join-Path $packageDirectory 'paho\mqtt\client.py'

    if (-not (Test-Path -LiteralPath $pythonExecutable)) {
        Write-Host 'First launch: preparing the app. Internet access is needed once.'
        Write-Host 'Downloading the official Python runtime...'
        $pythonArchiveName = "python-$sideePythonVersion-embed-$architecture.zip"
        $archive = Get-SideeDownload "https://www.python.org/ftp/python/$sideePythonVersion/$pythonArchiveName" `
            $sideePythonHashes[$architecture] $pythonArchiveName
        Expand-SideePackage $archive $pythonDirectory 'python.exe'
    }
    if (-not (Test-Path -LiteralPath $packageReady)) {
        Write-Host 'Preparing the TV connection library...'
        $archive = Get-SideeDownload $sideePackageUrl $sideePackageHash 'paho-mqtt-2.1.0.whl'
        Expand-SideePackage $archive $packageDirectory 'paho\mqtt\client.py'
    }
    # Relative paths keep this portable even if the extracted folder is moved.
    $paths = "python313.zip`r`n.`r`n..\..`r`n..\packages\paho-mqtt-$sideePackageVersion`r`n"
    [IO.File]::WriteAllText((Join-Path $pythonDirectory 'python313._pth'), $paths,
        [Text.Encoding]::ASCII)
    & $pythonExecutable -c "from core import client, webui; client._load_client_pem_key()"
    if ($LASTEXITCODE -ne 0) {
        throw 'The app could not finish setup. Extract the complete project into a writable folder and try again.'
    }
    $sideeSetupLock.Dispose()
    $sideeSetupLock = $null
    if ($PrepareOnly) {
        Write-Host 'Setup complete. The dashboard is ready to open.'
        exit 0
    }
    Write-Host 'Opening your dashboard. Keep this window open while using it.'
    & $pythonExecutable -u (Join-Path $sideeRoot 'sidee.py')
    exit $LASTEXITCODE
} catch {
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Check your Internet connection if this is the first launch, then open start-windows.bat again.'
    exit 1
} finally {
    if ($sideeSetupLock) { $sideeSetupLock.Dispose() }
}

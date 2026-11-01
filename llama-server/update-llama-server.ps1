# ======================= CONFIG (edit only this block) =======================
$Name        = "llama.cpp"                         # label + state-file name
$Repo        = "ggml-org/llama.cpp"    # owner/repo
$InstallDir  = $PSScriptRoot                    # where files are extracted
$TagRegex    = '^b\d+$'                         # only consider tags matching this
$MainRegex   = '^llama-.*-bin-win-cuda-(?<cuda>\d+\.\d+)-x64\.zip$'
$CudartRegex = '^cudart-llama-bin-win-cuda-{cuda}-x64\.zip$'   # '' = no runtime package
                                                # {cuda} is replaced by the (?<cuda>...) group captured from $MainRegex
$CudartFallbackToOlder = $true                  # take cudart from an older release if the chosen one lacks it
$PerPage     = 50
$GitHubToken = $env:GITHUB_TOKEN                # optional, avoids API rate limits

# --- Presets (copy over the values above) ---
# llama.cpp:
#   $Name="llama.cpp"; $Repo="ggml-org/llama.cpp"; $TagRegex='.*'
#   $MainRegex='^llama-.*-bin-win-cuda-(?<cuda>\d+\.\d+)-x64\.zip$'
#   $CudartRegex='^cudart-llama-bin-win-cuda-{cuda}-x64\.zip$'; $CudartFallbackToOlder=$false
# audio.cpp / prismML: open the releases page, copy a Windows zip name,
#   and write a regex for it (use (?<cuda>...) only if the version is in the name).
# =============================================================================

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13

$Slug          = ($Name -replace '[^\w\-]', '_')
$VerFile       = Join-Path $InstallDir ".$Slug-version"
$CudartVerFile = Join-Path $InstallDir ".$Slug-cudart-version"
$TempZip       = Join-Path $env:TEMP "$Slug-main.zip"
$TempCudart    = Join-Path $env:TEMP "$Slug-cudart.zip"
$UA            = "$Slug-updater/1.0"
$Headers       = @{ "User-Agent" = $UA; "Accept" = "application/vnd.github+json" }
if ($GitHubToken) { $Headers["Authorization"] = "Bearer $GitHubToken" }

if (-not (Test-Path $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir | Out-Null }

function Expand-ZipFlat {
    param([Parameter(Mandatory)][string]$ZipPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        foreach ($Entry in $Zip.Entries) {
            if ($Entry.FullName.EndsWith("/") -or [string]::IsNullOrEmpty($Entry.Name)) { continue }
            $Destination = Join-Path $InstallDir $Entry.Name
            $In  = $Entry.Open()
            $Out = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
            try { $In.CopyTo($Out) } finally { $Out.Dispose(); $In.Dispose() }
        }
    } finally { $Zip.Dispose() }
}

function Download-File {
    param([Parameter(Mandatory)][string]$Url, [Parameter(Mandatory)][string]$OutPath)
    if (Test-Path $OutPath) { Remove-Item $OutPath -Force }
    $Client = [System.Net.WebClient]::new()
    try {
        $Client.Headers.Add("User-Agent", $UA)
        Write-Host "   Downloading..." -ForegroundColor Gray
        $Client.DownloadFile($Url, $OutPath)
    } finally { $Client.Dispose() }
}

Write-Host "[1/4] Looking for the latest $Name Windows release..." -ForegroundColor Cyan
try {
    $Releases = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases?per_page=$PerPage" -Headers $Headers
} catch {
    Write-Error "Failed to contact GitHub's releases API: $_"
    exit 1
}

$Release = $null; $MainAsset = $null; $CudaVer = $null
foreach ($R in $Releases) {
    if ($R.draft -or $R.prerelease -and $false) { continue }
    if ($R.tag_name -notmatch $TagRegex) { continue }
    $A = $R.assets | Where-Object { $_.name -match $MainRegex } | Select-Object -First 1
    if ($A) {
        $null = $A.name -match $MainRegex
        if ($Matches.ContainsKey('cuda')) { $CudaVer = $Matches['cuda'] }
        $Release = $R; $MainAsset = $A
        break
    }
}

if (-not $Release) {
    Write-Error "No release (last $($Releases.Count) checked) has an asset matching: $MainRegex"
    Write-Host "Recent releases and their assets:" -ForegroundColor Yellow
    $Releases | Select-Object -First 5 | ForEach-Object {
        Write-Host "  $($_.tag_name)" -ForegroundColor Yellow
        $_.assets | ForEach-Object { Write-Host "      $($_.name)" -ForegroundColor DarkGray }
    }
    exit 1
}

$Tag = $Release.tag_name
Write-Host "   Using release: $Tag" -ForegroundColor Green
if ($CudaVer) { Write-Host "   CUDA version : $CudaVer" -ForegroundColor Green }

Write-Host "[2/4] Locating matching assets..." -ForegroundColor Cyan
$CudartAsset = $null
if ($CudartRegex) {
    $Pattern = if ($CudaVer) { $CudartRegex.Replace('{cuda}', [regex]::Escape($CudaVer)) } else { $CudartRegex }
    $CudartAsset = $Release.assets | Where-Object { $_.name -match $Pattern } | Select-Object -First 1
    if (-not $CudartAsset -and $CudartFallbackToOlder) {
        foreach ($R in $Releases) {
            $CudartAsset = $R.assets | Where-Object { $_.name -match $Pattern } | Select-Object -First 1
            if ($CudartAsset) { Write-Host "   Cudart taken from older release $($R.tag_name)" -ForegroundColor Yellow; break }
        }
    }
}
Write-Host "   Main  : $($MainAsset.name) ($([math]::Round($MainAsset.size / 1MB, 1)) MB)" -ForegroundColor Green
if ($CudartAsset) {
    Write-Host "   Cudart: $($CudartAsset.name) ($([math]::Round($CudartAsset.size / 1MB, 1)) MB)" -ForegroundColor Green
} else {
    Write-Host "   Cudart: none (skipping)." -ForegroundColor Yellow
}

Write-Host "[3/4] Main binaries..." -ForegroundColor Cyan
$Installed = if (Test-Path $VerFile) { (Get-Content $VerFile -Raw).Trim() } else { "" }
if ($Installed -eq $Tag) {
    Write-Host "   Already on $Tag; skipping." -ForegroundColor Green
} else {
    Download-File -Url $MainAsset.browser_download_url -OutPath $TempZip
    try { Expand-ZipFlat -ZipPath $TempZip } finally { if (Test-Path $TempZip) { Remove-Item $TempZip -Force } }
    Set-Content -Path $VerFile -Value $Tag -NoNewline
    Write-Host "   Installed $Tag." -ForegroundColor Green
}

Write-Host "[4/4] CUDA runtime..." -ForegroundColor Cyan
if ($CudartAsset) {
    $NewId = "$($CudartAsset.name)|$($CudartAsset.size)"
    $OldId = if (Test-Path $CudartVerFile) { (Get-Content $CudartVerFile -Raw).Trim() } else { "" }
    if ($OldId -eq $NewId) {
        Write-Host "   Runtime already installed; skipping." -ForegroundColor Green
    } else {
        Download-File -Url $CudartAsset.browser_download_url -OutPath $TempCudart
        try { Expand-ZipFlat -ZipPath $TempCudart } finally { if (Test-Path $TempCudart) { Remove-Item $TempCudart -Force } }
        Set-Content -Path $CudartVerFile -Value $NewId -NoNewline
        Write-Host "   Runtime updated." -ForegroundColor Green
    }
} else {
    Write-Host "   Nothing to do." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done! $Name at $Tag -> $InstallDir" -ForegroundColor Green
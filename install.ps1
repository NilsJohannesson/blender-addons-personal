param(
    [string]$BlenderVersion = "5.2"
)

$ErrorActionPreference = "Stop"
$RepoPath = $PSScriptRoot
$BlenderExtensionRepoPath = Join-Path $env:APPDATA "Blender Foundation\Blender\$BlenderVersion\extensions\user_default"

if (-not (Test-Path $BlenderExtensionRepoPath)) {
    New-Item -ItemType Directory -Path $BlenderExtensionRepoPath -Force | Out-Null
}

Write-Host "Using Blender $BlenderVersion local extension repository: $BlenderExtensionRepoPath"

$extensionSource = Join-Path $RepoPath "addons\render_spine"
$extensionTarget = Join-Path $BlenderExtensionRepoPath "render_spine"

if (-not (Test-Path $extensionSource)) {
    Write-Error "Extension package not found at $extensionSource."
}

if (Test-Path $extensionTarget) {
    $item = Get-Item $extensionTarget -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        Write-Host "  [skip] render_spine -- junction already exists"
    } else {
        Write-Warning "  [skip] render_spine -- a real folder already exists at $extensionTarget"
    }
} else {
    cmd /c mklink /J "`"$extensionTarget`"" "`"$extensionSource`""
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [link] render_spine"
    } else {
        Write-Warning "  [fail] render_spine -- mklink returned exit code $LASTEXITCODE"
    }
}

Write-Host "Done. Enable RenderSpine in Blender (Get Extensions / Add-ons), then reload scripts."

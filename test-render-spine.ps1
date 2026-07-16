param(
    [string]$BlenderPath,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$extensionRoot = Join-Path $repoRoot "addons\render_spine"
$testsRoot = Join-Path $repoRoot "tests\render_spine"
$distRoot = Join-Path $repoRoot "dist"

if (-not $BlenderPath) {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Blender Foundation\Blender 5.2\blender.exe"),
        (Join-Path $env:ProgramFiles "Blender Foundation\blender-5.2.0-beta+v52.4481d59ccf4e-windows.amd64-release\blender.exe")
    )
    $BlenderPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $BlenderPath -or -not (Test-Path $BlenderPath)) {
    throw "Blender 5.2 executable not found. Pass -BlenderPath explicitly."
}

if (-not (Test-Path $extensionRoot)) {
    throw "Extension source not found: $extensionRoot"
}

$version = & $BlenderPath --version | Select-Object -First 1
if ($version -notmatch "Blender 5\.2") {
    throw "Tests require Blender 5.2; found: $version"
}

Write-Host "[validate] $extensionRoot"
& $BlenderPath --factory-startup --command extension validate $extensionRoot
if ($LASTEXITCODE -ne 0) {
    throw "Extension validation failed."
}

$tests = Get-ChildItem -Path $testsRoot -Filter "test_*.py" -File |
    Sort-Object Name
if (-not $tests) {
    throw "No tests found under $testsRoot"
}

foreach ($test in $tests) {
    Write-Host "[test] $($test.Name)"
    $output = & $BlenderPath --factory-startup --background --python $test.FullName -- --extension-root $extensionRoot 2>&1
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    $sentinel = "RSP_TEST_PASS: $($test.BaseName -replace '^test_', '')"
    if ($exitCode -ne 0 -or ($output -join "`n") -notmatch [regex]::Escape($sentinel)) {
        throw "Test failed: $($test.Name)"
    }
}

if (-not $SkipBuild) {
    if (-not (Test-Path $distRoot)) {
        New-Item -ItemType Directory -Path $distRoot | Out-Null
    }
    $packagePath = Join-Path $distRoot "render_spine-1.0.0.zip"
    Write-Host "[build] $packagePath"
    & $BlenderPath --factory-startup --command extension build --source-dir $extensionRoot --output-filepath $packagePath
    if ($LASTEXITCODE -ne 0) {
        throw "Extension build failed."
    }
    Write-Host "[validate package] $packagePath"
    & $BlenderPath --factory-startup --command extension validate $packagePath
    if ($LASTEXITCODE -ne 0) {
        throw "Built extension validation failed."
    }
}

Write-Host "RenderSpine 1.0 verification passed."

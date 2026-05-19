$ErrorActionPreference = "Stop"

$UvInstallUrl = if ($env:UV_INSTALL_URL) { $env:UV_INSTALL_URL } else { "https://astral.sh/uv/install.ps1" }
$WorkspaceMcpPython = if ($env:WORKSPACE_MCP_PYTHON) { $env:WORKSPACE_MCP_PYTHON } else { "3.13" }
$WorkspaceMcpSource = if ($env:WORKSPACE_MCP_SOURCE) { $env:WORKSPACE_MCP_SOURCE } else { "https://github.com/OpenBB-finance/workspace-mcp/archive/refs/heads/main.zip" }
$WorkspaceMcpArgs = $args

function Write-Info {
    param([string] $Message)
    Write-Host $Message
}

function Test-Uv {
    $command = Get-Command uv -ErrorAction SilentlyContinue
    return $null -ne $command
}

function Add-UvInstallDirsToPath {
    $candidateDirs = @()

    if ($env:USERPROFILE) {
        $candidateDirs += Join-Path $env:USERPROFILE ".local\bin"
        $candidateDirs += Join-Path $env:USERPROFILE ".cargo\bin"
    }

    if ($env:LOCALAPPDATA) {
        $candidateDirs += Join-Path $env:LOCALAPPDATA "Programs\uv"
    }

    foreach ($dir in $candidateDirs) {
        if ((Test-Path $dir) -and (($env:PATH -split ";") -notcontains $dir)) {
            $env:PATH = "$dir;$env:PATH"
        }
    }
}

if (-not (Test-Uv)) {
    Write-Info "uv was not found; installing uv..."
    Invoke-RestMethod -Uri $UvInstallUrl | Invoke-Expression
    Add-UvInstallDirsToPath
}

if (-not (Test-Uv)) {
    throw "uv was installed, but it is not available on PATH yet. Restart PowerShell or add the uv install directory to PATH, then rerun this command."
}

$uvArgs = @(
    "tool",
    "run",
    "--python",
    $WorkspaceMcpPython,
    "--from",
    $WorkspaceMcpSource,
    "workspace-mcp"
) + $WorkspaceMcpArgs

& uv @uvArgs
exit $LASTEXITCODE

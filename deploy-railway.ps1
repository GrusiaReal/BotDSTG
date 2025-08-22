<# 
.SYNOPSIS
  Deploy to Railway with a provided token (no browser login needed).

.EXAMPLE
  .\deploy-railway.ps1 -Token "9485431c-82f7-4fcf-8dbd-199d85da6feb" -Service "api" -Environment "production"

.PARAMETERS
  -Token        Railway account API token (will be used only for this process unless -Persist).
  -Service      Railway service name to deploy (optional).
  -Environment  Railway environment name (optional).
  -ProjectPath  Path to project (default: current dir).
  -Persist      Also save RAILWAY_TOKEN to user env (permanent) using setx.
  -Verbose      Show extra info.
#>

param(
  [Parameter(Mandatory = $true)]
  [string]$Token,

  [Parameter(Mandatory = $false)]
  [string]$Service,

  [Parameter(Mandatory = $false)]
  [string]$Environment,

  [Parameter(Mandatory = $false)]
  [string]$ProjectPath = (Get-Location).Path,

  [switch]$Persist
)

$ErrorActionPreference = "Stop"

function Mask-Token([string]$t) {
  if ([string]::IsNullOrWhiteSpace($t)) { return "" }
  if ($t.Length -le 8) { return "****" }
  return ($t.Substring(0,4) + "…" + $t.Substring($t.Length-4,4))
}

Write-Host "==> Using token: $(Mask-Token $Token)"

# 1) Set env var for *this* PowerShell session + child processes
$env:RAILWAY_TOKEN = $Token

# 2) Optionally persist to user environment (requires new shell to take effect)
if ($Persist) {
  Write-Host "==> Persisting RAILWAY_TOKEN to user environment..."
  setx RAILWAY_TOKEN $Token | Out-Null
  Write-Host "    Saved. Open a new terminal to inherit it."
}

# 3) Find Railway CLI
function Get-RailwayCmd {
  $candidates = @(
    (Get-Command "railway.exe" -ErrorAction SilentlyContinue)?.Source,
    (Get-Command "railway" -ErrorAction SilentlyContinue)?.Source
  ) | Where-Object { $_ -ne $null } | Select-Object -First 1

  if ($null -ne $candidates) { return $candidates }

  # Fallback to npx (requires Node.js)
  try {
    $null = Get-Command "npx" -ErrorAction Stop
    return "npx railway"
  } catch {
    throw "Railway CLI not found. Install it first (e.g. 'npm i -g @railway/cli' or download railway.exe)."
  }
}

$railway = Get-RailwayCmd
Write-Host "==> Railway CLI: $railway"

# 4) Show whoami (sanity check)
Write-Host "==> Checking account (railway whoami)..."
$whoami = & $railway whoami 2>&1
Write-Host $whoami

# 5) Build deploy command
$cmd = @("up")
if ($Service)     { $cmd += @("--service", $Service) }
if ($Environment) { $cmd += @("--environment", $Environment) }

# 6) Run from project path
if (-not (Test-Path $ProjectPath)) {
  throw "ProjectPath not found: $ProjectPath"
}
Push-Location $ProjectPath
try {
  Write-Host "==> Running: railway $($cmd -join ' ')"
  & $railway @cmd
  $exit = $LASTEXITCODE
  if ($exit -ne 0 -and $exit -ne $null) {
    throw "Railway deploy failed with exit code $exit"
  }
  Write-Host "✅ Deploy finished."
}
finally {
  Pop-Location
}

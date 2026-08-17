# 1c-project-init v1.0 - Initialize or enrich a 1C project from AI workspace
param(
    [Parameter(Mandatory)]
    [string]$TargetPath,

    [ValidateSet("new", "enrich", "auto")]
    [string]$Mode = "auto"
)

$ErrorActionPreference = "Stop"
$WorkspacePath = "$PSScriptRoot\..\..\..\.."  # scripts/ -> 1c-project-init/ -> skills/ -> .claude/ -> workspace root
$WorkspacePath = (Resolve-Path $WorkspacePath).Path

$SkillsSrc = Join-Path $WorkspacePath ".claude\skills"
$DocsSrc   = Join-Path $WorkspacePath ".claude\docs"
$SkillsDst = Join-Path $TargetPath ".claude\skills"
$DocsDst   = Join-Path $TargetPath ".claude\docs"

# Auto-detect mode
if ($Mode -eq "auto") {
    $Mode = if (Test-Path $SkillsDst) { "enrich" } else { "new" }
}

Write-Host "Mode: $Mode" -ForegroundColor Cyan
Write-Host "Source: $WorkspacePath" -ForegroundColor Gray
Write-Host "Target: $TargetPath" -ForegroundColor Gray
Write-Host ""

$created = @()
$updated = @()
$skipped = @()

# ── Helper ──────────────────────────────────────────────────────────────────

function Copy-IfNewer {
    param([string]$Src, [string]$Dst, [string]$Label)
    if (-not (Test-Path $Dst)) {
        $null = New-Item -ItemType File -Path $Dst -Force
        Copy-Item -Path $Src -Destination $Dst -Force
        $script:created += $Label
    } else {
        $srcHash = (Get-FileHash $Src -Algorithm MD5).Hash
        $dstHash = (Get-FileHash $Dst -Algorithm MD5).Hash
        if ($srcHash -ne $dstHash) {
            Copy-Item -Path $Src -Destination $Dst -Force
            $script:updated += $Label
        } else {
            $script:skipped += $Label
        }
    }
}

# ── Skills ───────────────────────────────────────────────────────────────────

Write-Host "Syncing skills..." -ForegroundColor Yellow
$null = New-Item -ItemType Directory -Path $SkillsDst -Force

Get-ChildItem -Path $SkillsSrc -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($SkillsSrc.Length + 1)
    # Skip the init skill itself to avoid self-copy issues
    if ($rel -like "1c-project-init*") { return }
    $dst = Join-Path $SkillsDst $rel
    $null = New-Item -ItemType Directory -Path (Split-Path $dst) -Force
    Copy-IfNewer -Src $_.FullName -Dst $dst -Label "skills/$rel"
}

# ── Docs (always overwrite - platform specs are source-of-truth) ─────────────

Write-Host "Syncing docs..." -ForegroundColor Yellow
$null = New-Item -ItemType Directory -Path $DocsDst -Force

Get-ChildItem -Path $DocsSrc -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($DocsSrc.Length + 1)
    $dst = Join-Path $DocsDst $rel
    $null = New-Item -ItemType Directory -Path (Split-Path $dst) -Force
    Copy-Item -Path $_.FullName -Destination $dst -Force
    $script:updated += "docs/$rel"
}

# ── New project scaffold ──────────────────────────────────────────────────────

if ($Mode -eq "new") {
    Write-Host "Creating project scaffold..." -ForegroundColor Yellow

    $dirs = @(
        "src",
        "openspec\changes",
        "openspec\specs",
        "openspec\archive",
        "docs",
        "presentations",
        "playwright-screenshots"
    )
    foreach ($d in $dirs) {
        $path = Join-Path $TargetPath $d
        if (-not (Test-Path $path)) {
            $null = New-Item -ItemType Directory -Path $path -Force
            $created += "dir: $d"
        }
    }

    # playwright-screenshots/.gitkeep
    $gitkeep = Join-Path $TargetPath "playwright-screenshots\.gitkeep"
    if (-not (Test-Path $gitkeep)) {
        $null = New-Item -ItemType File -Path $gitkeep -Force
        $created += "playwright-screenshots/.gitkeep"
    }

    # .gitignore - add playwright screenshots entries
    $gitignorePath = Join-Path $TargetPath ".gitignore"
    $pwEntry = "playwright-screenshots/*.png"
    if (Test-Path $gitignorePath) {
        $content = Get-Content $gitignorePath -Raw -Encoding UTF8
        if ($content -notlike "*playwright-screenshots*") {
            Add-Content -Path $gitignorePath -Value "`n# Playwright screenshots (auto-generated)`nplaywright-screenshots/*.png`nplaywright-screenshots/*.jpg`nplaywright-screenshots/*.jpeg`n" -Encoding UTF8
            $updated += ".gitignore (playwright-screenshots)"
        }
    } else {
        "# Playwright screenshots (auto-generated)`nplaywright-screenshots/*.png`nplaywright-screenshots/*.jpg`nplaywright-screenshots/*.jpeg`n" | Set-Content -Path $gitignorePath -Encoding UTF8
        $created += ".gitignore"
    }

    # openspec/project.md placeholder
    $projectMd = Join-Path $TargetPath "openspec\project.md"
    if (-not (Test-Path $projectMd)) {
        "# Project Context`n`n<!-- AI: fill this with project goals, conventions, architecture -->`n" | Set-Content -Path $projectMd -Encoding UTF8
        $created += "openspec/project.md"
    }
}

# ── 1c-creds.json (central credentials file, created once per machine) ───────

Write-Host "Checking 1c-creds.json..." -ForegroundColor Yellow
$CredsFile = Join-Path $env:USERPROFILE ".claude\1c-creds.json"
if (-not (Test-Path $CredsFile)) {
    $null = New-Item -ItemType Directory -Path (Split-Path $CredsFile) -Force
    @'
{
  "_note": "Credentials for mcp-1c-bridge.py. Keyed by base URL (without /hs/ai). Not committed anywhere.",
  "http://YOUR_EDT_SERVER/KAF": {"user": "r.safiulin", "password": "FILL_ME"},
  "default":                  {"user": "r.safiulin", "password": "FILL_ME"}
}
'@ | Set-Content -Path $CredsFile -Encoding UTF8
    $created += "~/.claude/1c-creds.json (FILL IN PASSWORDS)"
    Write-Host "  + Created ~/.claude/1c-creds.json - fill in passwords!" -ForegroundColor Yellow
} else {
    Write-Host "  ~/.claude/1c-creds.json already exists" -ForegroundColor Gray
}

# ── .claude/settings.json ────────────────────────────────────────────────────

$settingsPath = Join-Path $TargetPath ".claude\settings.json"
if (-not (Test-Path $settingsPath)) {
    $null = New-Item -ItemType Directory -Path (Split-Path $settingsPath) -Force
    @'
{
  "permissions": {
    "allow": [
      "Bash(git *)",
      "Bash(powershell *)",
      "mcp__rlm-toolkit__*"
    ]
  }
}
'@ | Set-Content -Path $settingsPath -Encoding UTF8
    $created += ".claude/settings.json"
}

# ── Gitea remote setup ────────────────────────────────────────────────────────

$GiteaUrl   = "http://YOUR_SERVER:3000"
$GiteaToken = if ($env:GITEA_TOKEN) { $env:GITEA_TOKEN } else { (Get-Content "$env:USERPROFILE\.claude\private\credentials.md" -Raw) -match 'GITEA_TOKEN:\s*`([^`]+)`' | Out-Null; $Matches[1] }
$ProjectName = Split-Path $TargetPath -Leaf

Write-Host "Setting up Gitea remote..." -ForegroundColor Yellow

if (Test-Path (Join-Path $TargetPath ".git")) {
    $remotes = & git -C $TargetPath remote 2>$null
    if ($remotes -notcontains "gitea") {
        # Create repo in Gitea if not exists
        $body = @{ name = $ProjectName; private = $true; auto_init = $false } | ConvertTo-Json
        try {
            $null = Invoke-RestMethod -Method Post -Uri "$GiteaUrl/api/v1/user/repos" `
                -Headers @{ Authorization = "token $GiteaToken"; "Content-Type" = "application/json" } `
                -Body $body -ErrorAction SilentlyContinue
        } catch {}

        $remoteUrl = "http://admin:admin123@YOUR_SERVER:3000/admin/$ProjectName.git"
        & git -C $TargetPath remote add gitea $remoteUrl 2>$null
        $created += "git remote: gitea"
        Write-Host "  + Added gitea remote: $remoteUrl" -ForegroundColor Green
    } else {
        Write-Host "  gitea remote already exists" -ForegroundColor Gray
    }
} else {
    Write-Host "  Not a git repo, skipping gitea remote" -ForegroundColor Gray
}

# ── bsl-lsp-bridge ────────────────────────────────────────────────────────────

Write-Host "Checking bsl-lsp-bridge..." -ForegroundColor Yellow
$containerName = "mcp-lsp-$ProjectName"
$containerRunning = ssh root@YOUR_SERVER "docker ps -q --filter name=$containerName" 2>$null
if (-not $containerRunning) {
    ssh root@YOUR_SERVER "bash /opt/start-bsl-lsp.sh $ProjectName $ProjectName/src" 2>$null
    $created += "bsl-lsp-bridge: $containerName"
    Write-Host "  + Started container: $containerName" -ForegroundColor Green
} else {
    Write-Host "  $containerName already running" -ForegroundColor Gray
}

# ── Extension: Load XML -> DB + Build CFE ─────────────────────────────────────

$v8ProjectFile = Join-Path $TargetPath ".v8-project.json"
if (Test-Path $v8ProjectFile) {
    try {
        $v8Proj = Get-Content $v8ProjectFile -Encoding UTF8 | ConvertFrom-Json

        $v8Bin = if ($v8Proj.v8path) { $v8Proj.v8path } else {
            $exe = Get-ChildItem "C:\Program Files\1cv8\*\bin\1cv8.exe" -ErrorAction SilentlyContinue |
                   Sort-Object -Descending | Select-Object -First 1
            if ($exe) { $exe.Directory.FullName } else { $null }
        }

        if ($v8Bin) {
            $v8Exe = Join-Path $v8Bin "1cv8.exe"
            $dbs   = if ($v8Proj.databases) { $v8Proj.databases } else { @() }

            foreach ($db in $dbs) {
                if (-not $db.extensionName -or -not $db.configSrc) { continue }

                $extName   = $db.extensionName
                $configSrc = $db.configSrc
                $distDir   = Join-Path $TargetPath "dist"
                $cfeFile   = Join-Path $distDir "$extName.cfe"

                # Connection args
                $connArgs = if ($db.server) { "/S`"$($db.server)/$($db.ref)`"" }
                            elseif ($db.path) { "/F`"$($db.path)`"" }
                            else { $null }
                if (-not $connArgs) { continue }

                $authArgs = ""
                if ($db.user)     { $authArgs += " /N`"$($db.user)`"" }
                if ($db.password) { $authArgs += " /P`"$($db.password)`"" }

                $logFile = [System.IO.Path]::GetTempFileName()

                Write-Host "  Loading XML -> $extName @ $($db.ref)..." -ForegroundColor Cyan
                $loadArgs = "DESIGNER $connArgs$authArgs /LoadConfigFromFiles `"$configSrc`" -Format Hierarchical -Extension `"$extName`" /UpdateDBCfg /Out `"$logFile`" /DisableStartupDialogs"
                $p = Start-Process -FilePath $v8Exe -ArgumentList $loadArgs -Wait -PassThru -NoNewWindow
                if ($p.ExitCode -eq 0) {
                    $script:created += "extension loaded: $extName"
                    Write-Host "  OK Loaded and applied" -ForegroundColor Green

                    $null = New-Item -ItemType Directory -Path $distDir -Force
                    Write-Host "  Building CFE -> dist/$extName.cfe..." -ForegroundColor Cyan
                    $dumpArgs = "DESIGNER $connArgs$authArgs /DumpCfg `"$cfeFile`" -Extension `"$extName`" /Out `"$logFile`" /DisableStartupDialogs"
                    $p2 = Start-Process -FilePath $v8Exe -ArgumentList $dumpArgs -Wait -PassThru -NoNewWindow
                    if ($p2.ExitCode -eq 0) {
                        $script:created += "dist/$extName.cfe"
                        Write-Host "  OK CFE saved: dist/$extName.cfe" -ForegroundColor Green
                    } else {
                        Write-Host "  FAIL CFE dump failed (exit $($p2.ExitCode))" -ForegroundColor Red
                        if (Test-Path $logFile) { Get-Content $logFile -Encoding UTF8 | Select-Object -Last 5 }
                    }
                } else {
                    Write-Host "  FAIL Load failed (exit $($p.ExitCode))" -ForegroundColor Red
                    if (Test-Path $logFile) { Get-Content $logFile -Encoding UTF8 | Select-Object -Last 5 }
                }
                Remove-Item $logFile -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-Host "  1cv8.exe not found, skipping extension deploy" -ForegroundColor Gray
        }
    } catch {
        Write-Host "  Warning: .v8-project.json processing failed: $_" -ForegroundColor Yellow
    }
}

# ── Summary ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "=== DONE ===" -ForegroundColor Green
Write-Host "Mode: $Mode | Target: $TargetPath"
Write-Host ""

if ($created.Count -gt 0) {
    Write-Host "Created ($($created.Count)):" -ForegroundColor Green
    $created | Select-Object -First 20 | ForEach-Object { Write-Host "  + $_" }
    if ($created.Count -gt 20) { Write-Host "  ... and $($created.Count - 20) more" }
}
if ($updated.Count -gt 0) {
    Write-Host "Updated ($($updated.Count)):" -ForegroundColor Yellow
    $updated | Where-Object { $_ -notlike "docs/*" } | Select-Object -First 10 | ForEach-Object { Write-Host "  ~ $_" }
    $docsCount = ($updated | Where-Object { $_ -like "docs/*" }).Count
    if ($docsCount -gt 0) { Write-Host "  ~ docs: $docsCount files refreshed" }
}
if ($skipped.Count -gt 0) {
    Write-Host "Unchanged: $($skipped.Count) skills" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Next steps for AI: generate CLAUDE.md, .mcp.json, .v8-project.json" -ForegroundColor Cyan

# pylint: disable=unused-import
# E:\pyProject\alpha_v6\run_llms.ps1
# ==========================================
# AUTOMATIC EXECUTION POLICY ADJUSTMENT
# ==========================================
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force

# ==========================================
# VIRTUAL ENVIRONMENT ACTIVATION
# ==========================================
$VenvPath = "d:\myBot\.venv312\Scripts\Activate.ps1"
if (Test-Path $VenvPath) {
    Write-Host "Activating Python Virtual Environment..." -ForegroundColor Green
    . $VenvPath
} else {
    Write-Host "Warning: Virtual environment not found at $VenvPath" -ForegroundColor Yellow
}

# ==========================================
# GLOBAL CONFIGURATION
# ==========================================
$Repo = "ggerganov/llama.cpp"
$LlamaCmd = "D:\Downloads\llama-b9849\llama-server.exe"
$ModelDir = "D:\GGUF"
$Port = 8080
$HostUrl = "http://127.0.0.1:$Port"

# Define ordered model configurations with custom metadata and optional draft paths
$CoderModels = [ordered]@{
    "ornith-1.0-35b-Q4_K_M"                   = @{ File = "ornith-1.0-35b-Q4_K_M.gguf"; Thinking = $true; Effort = "high"; Web = $true }
    "Qwen3-Coder-30B-A3B-Instruct-UD-Q3_K_XL"  = @{ File = "Qwen3-Coder-30B-A3B-Instruct-UD-Q3_K_XL.gguf"; Thinking = $true; Effort = "high"; Web = $true }
    "Qwen2.5-Coder-14B-Instruct-Q4_K_M"    = @{ File = "Qwen2.5-Coder-14B-Instruct-Q4_K_M.gguf"; Thinking = $false; Effort = "none"; Web = $false }
    "Gemma-4-12B-it (Speculative MTP Co-Run)" = @{ File = "gemma-4-12b-it-Q4_K_M.gguf"; DraftFile = "gemma-4-12B-it-BF16-MTP.gguf"; Thinking = $true; Effort = "high"; Web = $false }
    "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M" = @{ File = "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf"; Thinking = $false; Effort = "none"; Web = $false }
}

$GeneralModels = [ordered]@{
    "gpt-oss-20b-Q4_K_M"                     = @{ File = "gpt-oss-20b-Q4_K_M.gguf"; Thinking = $false; Effort = "none"; Web = $true }
    "ornith-1.0-35b-Q4_K_M"                   = @{ File = "ornith-1.0-35b-Q4_K_M.gguf"; Thinking = $true; Effort = "high"; Web = $true }
    "Gemma-4-12B-it (Speculative MTP Co-Run)" = @{ File = "gemma-4-12b-it-Q4_K_M.gguf"; DraftFile = "gemma-4-12B-it-BF16-MTP.gguf"; Thinking = $true; Effort = "high"; Web = $false }
}

# ==========================================
# STEP 1: CHECK & UPDATE LLAMA.CPP
# ==========================================
Write-Host "Checking for llama.cpp updates..." -ForegroundColor Cyan

if (Test-Path $LlamaCmd) {
    $LocalVersionInfo = & $LlamaCmd --version 2>&1 | Out-String
    if ($LocalVersionInfo -match "build (\d+)") { $LocalBuild = [int]$Matches[1] } else { $LocalBuild = 0 }
} else {
    $LocalBuild = 0
    Write-Host "llama-server.exe not found at $LlamaCmd." -ForegroundColor Red
    Exit
}

try {
    $Uri = "https://api.github.com/repos/$Repo/releases/latest"
    $LatestRelease = Invoke-RestMethod -Uri $Uri -UseBasicParsing
    if ($LatestRelease.tag_name -match "b(\d+)") { $RemoteBuild = [int]$Matches[1] } else { $RemoteBuild = 0 }

    if ($RemoteBuild -gt $LocalBuild) {
        Write-Host "A new version is available! (Local: b$LocalBuild -> Remote: b$RemoteBuild)" -ForegroundColor Magenta
        $Choice = Read-Host "Would you like to upgrade llama.cpp right now? (Y/N)"
        if ($Choice -eq 'Y' -or $Choice -eq 'y') {
            Start-Process $LatestRelease.html_url
            Read-Host "Press ENTER after extracting the update to continue"
        }
    } else {
        Write-Host "llama.cpp is up to date (Build b$LocalBuild)." -ForegroundColor Green
    }
} catch {
    Write-Host "Could not check for updates. Skipping..." -ForegroundColor Yellow
}

Write-Host "`n--------------------------------------------------`n"

# ==========================================
# STEP 2: CHOOSE MODEL POOL, SELECTION, & CONTEXT SIZE
# ==========================================
Write-Host "Select the purpose of the model you want to run:" -ForegroundColor Cyan
Write-Host "1) Coder Models"
Write-Host "2) General Purpose Models"
$PoolChoice = Read-Host "Enter choice (1 or 2)"

$SelectedPool = if ($PoolChoice -eq "1") { $CoderModels } else { $GeneralModels }
$PoolName = if ($PoolChoice -eq "1") { "Coder" } else { "General Purpose" }

Write-Host "`nAvailable $PoolName Models:" -ForegroundColor Cyan
$MenuMapping = @{}
$Index = 1

foreach ($Key in $SelectedPool.Keys) {
    Write-Host "$Index) $Key"
    $MenuMapping.Add($Index, $SelectedPool[$Key])
    $Index++
}

$ModelChoice = Read-Host "`nSelect a model number to run"
$Selection = $MenuMapping[[int]$ModelChoice]

if (-not $Selection) {
    Write-Host "Invalid selection. Exiting." -ForegroundColor Red
    Exit
}

$SelectedModelFile = $Selection.File
$FullModelPath = Join-Path $ModelDir $SelectedModelFile

if (-not (Test-Path $FullModelPath)) {
    Write-Host "Error: Target model file not found at $FullModelPath" -ForegroundColor Red
    Exit
}

# --- DYNAMIC CONTEXT WINDOW ENTRY ---
$ContextInput = Read-Host "`nEnter context window size (Default: 262144)"
$ContextSize = if ([string]::IsNullOrWhiteSpace($ContextInput)) { "262144" } else { $ContextInput.Trim() }

# ==========================================
# STEP 3: LAUNCH OPENAI-COMPATIBLE SERVER (BACKGROUND)
# ==========================================
$ModelNameWithoutExt = [System.IO.Path]::GetFileNameWithoutExtension($SelectedModelFile)
$host.UI.RawUI.WindowTitle = "llama-server:8080 | $ModelNameWithoutExt (Ctx: $ContextSize)"

# Build base parameters with dynamic context window size, Flash Attention, and Q8 KV-quantization
$ServerArgs = @(
    "-m", "$FullModelPath",
    "-c", "$ContextSize",
    "--port", "$Port",
    "--host", "127.0.0.1",
    "-np", "1",
    "-fa", "on",               # Force Flash Attention
    "-ctk", "q8_0",            # Quantize Key cache to 8-bit
    "-ctv", "q8_0"             # Quantize Value cache to 8-bit
)

# Append speculative flags if draft assistant is selected
if ($Selection.DraftFile) {
    $FullDraftPath = Join-Path $ModelDir $Selection.DraftFile
    if (Test-Path $FullDraftPath) {
        Write-Host "Configuring Speculative Decoding with Draft Assistant: $($Selection.DraftFile)" -ForegroundColor Magenta
        $ServerArgs += @(
            "--spec-type", "draft-mtp",
            "-md", "$FullDraftPath",
            "-fit", "off"
        )
    }
}

Write-Host "`n[Starting server on port $Port for model: $ModelNameWithoutExt with Context: $ContextSize]" -ForegroundColor Green
$ServerProcess = Start-Process -FilePath $LlamaCmd -ArgumentList $ServerArgs -NoNewWindow -PassThru

# ==========================================
# STEP 4: HEALTH CHECK VERIFICATION & CRASH RECOVERY
# ==========================================
Write-Host "Waiting for server to report healthy at http://127.0.0.1:$Port..." -ForegroundColor Yellow
$MaxRetries = 15
$Healthy = $false

for ($i = 1; $i -le $MaxRetries; $i++) {
    try {
        $Response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($Response.StatusCode -eq 200 -or $Response.Content -match '"status":\s*"ok"') {
            $Healthy = $true
            break
        }
    } catch {
        # Check if the process died prematurely due to the upstream MTP vector bug
        if ($ServerProcess.HasExited) {
            Write-Host "[!] The server process terminated unexpectedly." -ForegroundColor Red
            break
        }
    }
    Start-Sleep -Seconds 2
}

# Fallback sequence if speculative decoding failed to load
if (-not $Healthy) {
    if ($Selection.DraftFile) {
        Write-Host "`n[!] Detected llama.cpp upstream MTP loader bug ('invalid vector subscript')." -ForegroundColor Yellow
        Write-Host "Falling back to standalone execution mode (without Draft Assistant)..." -ForegroundColor Cyan

        # Strip draft options out and form a clean standalone execution parameter stack
        $ServerArgs = @("-m", "$FullModelPath", "-c", "$ContextSize", "--port", "$Port", "--host", "127.0.0.1", "-np", "1", "-fa", "on", "-ctk", "q8_0", "-ctv", "q8_0")
        $ServerProcess = Start-Process -FilePath $LlamaCmd -ArgumentList $ServerArgs -NoNewWindow -PassThru

        for ($i = 1; $i -le $MaxRetries; $i++) {
            try {
                $Response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                if ($Response.StatusCode -eq 200) { $Healthy = $true; break }
            } catch {}
            Start-Sleep -Seconds 2
        }
    }

    if (-not $Healthy) {
        Write-Host "`nError: Server failed to initialize on port $Port." -ForegroundColor Red
        if ($ServerProcess -and -not $ServerProcess.HasExited) {
            Stop-Process -Id $ServerProcess.Id -Force
        }
        Exit
    }
}

Write-Host "`nServer is running and healthy on Port $Port!" -ForegroundColor Green

# ==========================================
# STEP 5: AUTOMATIC CLIENT CONFIGURATION DYNAMICS
# ==========================================
Write-Host "`nUpdating IDE/Client Configurations..." -ForegroundColor Cyan

# A) Dynamic DeepCode Integration
$DeepCodePath = "C:\Users\javad\.deepcode"
if (-not (Test-Path $DeepCodePath)) { New-Item -ItemType Directory -Path $DeepCodePath -Force | Out-Null }

$DeepCodeConfig = @{
    "env" = @{
        "MODEL"    = $ModelNameWithoutExt
        "BASE_URL" = "http://localhost:8080/v1"
        "API_KEY"  = "Dummy"
        "LLM_CONTEXT_WINDOW"     = "262144"  # Forced fallback constraint variables
        "CONTEXT_LENGTH"         = "262144"
        "MAX_TOKENS"             = "262144"
    }
    "thinkingEnabled" = $Selection.Thinking
    "reasoningEffort" = $Selection.Effort
    "webSearchTool"   = $Selection.Web
    "model"           = $ModelNameWithoutExt
    "maxTokens"       = "262144"
    "contextWindow"     = "262144"           # Base root level parameter override
    "maxContextTokens"  = "262144"           # Extension specific override key
    "overrideModelMax"  = $true
} | ConvertTo-Json -Depth 10

Set-Content -Path (Join-Path $DeepCodePath "settings.json") -Value $DeepCodeConfig -Force
Write-Host " -> Bespoke DeepCode settings.json written for: $ModelNameWithoutExt" -ForegroundColor Gray

# B) Aider Environment Runtime Flags
$AiderEnvPath = Join-Path (Split-Path $MyInvocation.MyCommand.Path) ".aider.env"
$AiderConfigText = @"
OPENAI_API_BASE=http://localhost:8080/v1
OPENAI_API_KEY=Dummy
AIDER_MODEL=openai/$ModelNameWithoutExt
"@
Set-Content -Path $AiderEnvPath -Value $AiderConfigText -Force
Write-Host " -> Aider configuration exported locally to .aider.env" -ForegroundColor Gray

# ==========================================
# STEP 6: AUTOMATICALLY LAUNCH DEEPCODE CLIENT
# ==========================================
Write-Host "`nLaunching DeepCode Client..." -ForegroundColor Green
# Fires up deepcode asynchronously so it doesn't block log output streaming below
Start-Process -FilePath "deepcode"

# ==========================================
# STEP 7: DISPLAY CONNECTION INFO & BROWSE
# ==========================================
Write-Host "`n===============================================" -ForegroundColor Green
Write-Host "SERVER BASE ENDPOINT     : http://localhost:8080/v1" -ForegroundColor Green
Write-Host "TARGET MODEL IDENTIFIER  : $ModelNameWithoutExt" -ForegroundColor Green
Write-Host "CONTEXT WINDOW SIZE      : $ContextSize" -ForegroundColor Green
if ($Selection.DraftFile) {
Write-Host "ASSISTANT DRAFTER MODEL  : $($Selection.DraftFile)" -ForegroundColor Magenta
}
Write-Host "DeepCode Features Status : Thinking=$($Selection.Thinking), Effort=$($Selection.Effort), Web=$($Selection.Web)" -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Green

$OpenBrowser = Read-Host "`nWould you like to open the browser to inspect active endpoints? (Y/N)"
if ($OpenBrowser -eq 'Y' -or $OpenBrowser -eq 'y') {
    Start-Process "http://localhost:8080/v1/models"
}

# Stream engine activity logs and handle process cleanup
Write-Host "`nStreaming engine activity logs. Press Ctrl+C to terminate server and exit.`n" -ForegroundColor Yellow
try {
    $ServerProcess | Wait-Process
} catch {
    # Exit caught
} finally {
    if (-not $ServerProcess.HasExited) {
        Write-Host "`nStopping background engine process running on port 8080..." -ForegroundColor Yellow
        Stop-Process -Id $ServerProcess.Id -Force
    }
}

# PowerShell Script to create a portable distribution package
# Usage: .\portable_setup.ps1

$OutputEncoding = [System.Text.Encoding]::UTF8

# 1. Configuration
$ProjectDir = Get-Location
$DistDir = Join-Path $ProjectDir "Data_Flow_Dist"
$PythonVersion = "3.10.11"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$ZipFile = Join-Path $DistDir "python_embed.zip"
$BinDir = Join-Path $DistDir "bin"

Write-Host ">>> Preparing portable package..." -ForegroundColor Cyan

# 2. Cleanup and Create Directory Structure
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
New-Item -ItemType Directory -Path $DistDir
New-Item -ItemType Directory -Path $BinDir

# 3. Download and Extract Embeddable Python
Write-Host ">>> Downloading Python $PythonVersion..." -ForegroundColor Yellow
Invoke-WebRequest -Uri $PythonUrl -OutFile $ZipFile
Expand-Archive -Path $ZipFile -DestinationPath $BinDir
Remove-Item $ZipFile

# 4. Configure Python Runtime Environment
Write-Host ">>> Configuring environment..." -ForegroundColor Yellow
$PthFile = Get-ChildItem -Path $BinDir -Filter "*._pth" | Select-Object -First 1
if ($PthFile) {
    # Uncomment 'import site' to allow loading installed libraries
    (Get-Content $PthFile.FullName) -replace "#import site", "import site" | Set-Content $PthFile.FullName
}

# 5. Install pip
Write-Host ">>> Installing pip..." -ForegroundColor Yellow
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile (Join-Path $DistDir "get-pip.py")
& "$BinDir\python.exe" (Join-Path $DistDir "get-pip.py")
Remove-Item (Join-Path $DistDir "get-pip.py")

# 6. Install Project Dependencies
Write-Host ">>> Installing dependencies (using AliCloud mirror)..." -ForegroundColor Yellow
$MirrorUrl = "https://mirrors.aliyun.com/pypi/simple/"
& "$BinDir\python.exe" -m pip install --no-cache-dir -i $MirrorUrl -r (Join-Path $ProjectDir "requirements.txt")
& "$BinDir\python.exe" -m pip install --no-cache-dir -i $MirrorUrl langchain-openai

# 7. Copy Project Source Files
Write-Host ">>> Syncing project source..." -ForegroundColor Yellow
# Exclude sensitive files, environment settings, and heavy folders
$ExcludeList = @(
    "Data_Flow_Dist", ".git", ".vscode", "__pycache__", "tests", 
    ".streamlit", "portable_setup.ps1", ".gemini", ".agent",
    ".env", ".env.local", "*.pyc", ".python-version", ".ipynb_checkpoints"
)
Get-ChildItem -Path $ProjectDir | Where-Object { $ExcludeList -notcontains $_.Name } | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $DistDir -Recurse -Force
}

# 8. Create Standalone Streamlit Config
New-Item -ItemType Directory -Path (Join-Path $DistDir ".streamlit")
@'
[theme]
base="light"
primaryColor="#1a73e8"

[browser]
gatherUsageStats = false

[server]
headless = true
'@ | Out-File (Join-Path $DistDir ".streamlit\config.toml") -Encoding utf8

Write-Host "`n>>> SUCCESS! Portable package created at: $DistDir" -ForegroundColor Green
Write-Host ">>> You can now zip this folder and share it with others." -ForegroundColor Green

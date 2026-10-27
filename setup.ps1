# Codex の設定と作業フォルダを、このPCに置く。
#   home\.codex\AGENTS.md    → %USERPROFILE%\.codex\AGENTS.md
#   home\.agents\skills\*    → %USERPROFILE%\.agents\skills\*   （同名ファイルは新しい版で置き換える。いらすとやの索引は残す）
#   dev\*                    → C:\dev\*                        （すでにあるファイルには触らない）
#   Python・VS Code・Git・pymupdf・pillow を winget と pip で入れる（入っていれば飛ばす）
#   VS Code を日本語化し、デスクトップに C:\dev\卒論 を開くショートカット「卒論」を置く
# 何度実行してもよい。本人のファイルは上書きしない。
param([string]$DevRoot = 'C:\dev', [string]$HomeRoot = $env:USERPROFILE, [switch]$SkipInstall, [string]$ShortcutDir = [Environment]::GetFolderPath('Desktop'))
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path (Join-Path $here 'home'))) {
    Write-Host 'ZIPを「すべて展開」してから、展開したフォルダの中の setup.cmd を実行してください。' -ForegroundColor Red
    exit 1
}

$script:added = 0; $script:updated = 0; $script:kept = @()

function Copy-Tree([string]$src, [string]$dst, [bool]$update, [string[]]$keepNames = @()) {
    $src = (Resolve-Path -LiteralPath $src).Path
    Get-ChildItem -LiteralPath $src -Recurse -Directory -Force | ForEach-Object {
        New-Item -ItemType Directory -Force -Path (Join-Path $dst $_.FullName.Substring($src.Length)) | Out-Null
    }
    Get-ChildItem -LiteralPath $src -Recurse -File -Force | ForEach-Object {
        $to = Join-Path $dst $_.FullName.Substring($src.Length)
        New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
        if (Test-Path -LiteralPath $to) {
            if (-not $update -or $keepNames -contains $_.Name) { return }
            if ((Get-FileHash -LiteralPath $to).Hash -eq (Get-FileHash -LiteralPath $_.FullName).Hash) { return }
            Copy-Item -LiteralPath $_.FullName -Destination $to -Force
            $script:updated++
        } else {
            Copy-Item -LiteralPath $_.FullName -Destination $to
            $script:added++
        }
    }
}

# 1. Codex 全体の決まり。本人がすでに書いたものがあれば残し、隣に置く
$codexDir = Join-Path $HomeRoot '.codex'
New-Item -ItemType Directory -Force -Path $codexDir | Out-Null
$agentsSrc = Join-Path $here 'home\.codex\AGENTS.md'
$agentsDst = Join-Path $codexDir 'AGENTS.md'
if (-not (Test-Path -LiteralPath $agentsDst)) {
    Copy-Item -LiteralPath $agentsSrc -Destination $agentsDst; $script:added++
} elseif ((Get-FileHash -LiteralPath $agentsDst).Hash -ne (Get-FileHash -LiteralPath $agentsSrc).Hash) {
    $side = Join-Path $codexDir 'AGENTS.セットの版.md'
    Copy-Item -LiteralPath $agentsSrc -Destination $side -Force
    $script:kept += "$agentsDst （すでにあったので残した。セットの版は $side）"
}

# 2. スキル
Copy-Tree (Join-Path $here 'home\.agents\skills') (Join-Path $HomeRoot '.agents\skills') $true @('_索引.tsv')

# 3. 作業フォルダ。論文とレジュメの置き場は空のフォルダとして作る
Copy-Tree (Join-Path $here 'dev') $DevRoot $false
foreach ($d in @('論文', 'レジュメ')) { New-Item -ItemType Directory -Force -Path (Join-Path $DevRoot "卒論\$d") | Out-Null }

Write-Host ''
Write-Host "置いたファイル: 新規 $script:added 件、更新 $script:updated 件" -ForegroundColor Green
foreach ($k in $script:kept) { Write-Host "注意: $k" -ForegroundColor Yellow }

# 4. ソフトを入れる。すでに入っているものは飛ばす
#    winget と python は stderr に進み具合を書くので、ここからは止めずに続ける
$ErrorActionPreference = 'Continue'
#    Python と VS Code はユーザー単位で入れる（管理者の許可は要らない）
#    Git はPC全体に入れるので、Windows の許可の画面が出る
function Update-PathFromRegistry {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Find-Python {
    # WindowsApps の python.exe はストアへの案内で、本物ではない
    Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike '*WindowsApps*' } |
        Select-Object -First 1 -ExpandProperty Source
}
$apps = @(
    @{ Name = 'Python 3.13'; Id = 'Python.Python.3.13';         Scope = 'user'; Test = { [bool](Find-Python) } },
    @{ Name = 'VS Code';     Id = 'Microsoft.VisualStudioCode'; Scope = 'user'; Test = { [bool](Get-Command code -ErrorAction SilentlyContinue) } },
    @{ Name = 'Git';         Id = 'Git.Git';                    Scope = '';     Test = { [bool](Get-Command git -ErrorAction SilentlyContinue) } }
)
Write-Host ''
Write-Host 'ソフト:'
$failed = @()
$winget = Get-Command winget -ErrorAction SilentlyContinue
foreach ($a in $apps) {
    if (& $a.Test) { Write-Host "  入っている  $($a.Name)"; continue }
    if ($SkipInstall) { Write-Host "  入っていない  $($a.Name)（-SkipInstall のため入れない）" -ForegroundColor DarkGray; continue }
    if (-not $winget) { Write-Host "  入れられない  $($a.Name)（winget が無い）" -ForegroundColor Red; $failed += $a.Name; continue }
    Write-Host "  入れる  $($a.Name) ..." -ForegroundColor Cyan
    $wargs = @('install', '-e', '--id', $a.Id, '--silent', '--accept-package-agreements', '--accept-source-agreements')
    if ($a.Scope) { $wargs += @('--scope', $a.Scope) }
    & $winget.Source @wargs | Out-Host
    Update-PathFromRegistry
    if (& $a.Test) { Write-Host "  入れた  $($a.Name)" -ForegroundColor Green }
    else { Write-Host "  入らなかった  $($a.Name)" -ForegroundColor Red; $failed += $a.Name }
}

# VS Code の日本語化
$codeCmd = Get-Command code -ErrorAction SilentlyContinue
if ($codeCmd) {
    $ext = 'ms-ceintl.vscode-language-pack-ja'
    $have = @(& $codeCmd.Source --list-extensions 2>$null) | ForEach-Object { $_.ToLower() }
    if ($have -contains $ext) { Write-Host '  入っている  VS Code の日本語化' }
    elseif ($SkipInstall) { Write-Host '  入っていない  VS Code の日本語化（-SkipInstall のため入れない）' -ForegroundColor DarkGray }
    else {
        Write-Host '  入れる  VS Code の日本語化 ...' -ForegroundColor Cyan
        & $codeCmd.Source --install-extension $ext --force 2>$null | Out-Null
        $now = @(& $codeCmd.Source --list-extensions 2>$null) | ForEach-Object { $_.ToLower() }
        if ($now -contains $ext) { Write-Host '  入れた  VS Code の日本語化' -ForegroundColor Green }
        else { Write-Host '  入らなかった  VS Code の日本語化' -ForegroundColor Red; $failed += 'VS Code の日本語化' }
    }
}

# デスクトップに、C:\dev\卒論 のフォルダを開くショートカットを置く
$lnk = Join-Path $ShortcutDir '卒論.lnk'
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$sc.TargetPath = Join-Path $DevRoot '卒論'
$sc.Save()
Write-Host '  置いた  デスクトップのショートカット「卒論」'

# Python のライブラリ。論文PDFの読み取り（pymupdf）と画像の縮小（pillow）
$py = Find-Python
if ($py) {
    & $py -c "import fitz, PIL" 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Host '  入っている  pymupdf, pillow' }
    elseif ($SkipInstall) { Write-Host '  入っていない  pymupdf, pillow（-SkipInstall のため入れない）' -ForegroundColor DarkGray }
    else {
        Write-Host '  入れる  pymupdf, pillow ...' -ForegroundColor Cyan
        & $py -m pip install --quiet --disable-pip-version-check pymupdf pillow | Out-Host
        & $py -c "import fitz, PIL" 2>$null
        if ($LASTEXITCODE -eq 0) { Write-Host '  入れた  pymupdf, pillow' -ForegroundColor Green }
        else { Write-Host '  入らなかった  pymupdf, pillow' -ForegroundColor Red; $failed += 'pymupdf, pillow' }
    }
}

# スライドのPDF化に使うブラウザ。Edge は Windows に最初から入っている
$browser = (Test-Path "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe") -or (Test-Path "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe")
if ($browser) { Write-Host '  入っている  Chrome か Edge' } else { Write-Host '  見つからない  Chrome か Edge' -ForegroundColor Red; $failed += 'Chrome か Edge' }

Write-Host ''
if ($failed.Count) {
    Write-Host "入らなかったもの: $($failed -join '、')。ネットにつながっているか確かめて、setup.cmd をもう一度実行する。" -ForegroundColor Red
}
Write-Host '終わりました。Codex を開き直すと、新しい決まりとスキルが読まれます。'

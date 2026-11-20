# Макс Движ — установка контент-фабрики на Windows (без прав администратора).
# Запуск в PowerShell:  irm https://raw.githubusercontent.com/createparadise/maks-dvizh-assets/main/factory/setup.ps1 | iex
# Повторный запуск безопасен: обновляет скрипты, ключи и задачи, config.json не затирает.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Say($t) { Write-Host ''; Write-Host ">>> $t" -ForegroundColor Cyan }
function Ok($t)  { Write-Host "    OK  $t" -ForegroundColor Green }
function Warn($t){ Write-Host "    !!  $t" -ForegroundColor Yellow }

$root = Join-Path $env:USERPROFILE 'ai\neuroblog\factory'
New-Item -ItemType Directory -Force -Path $root | Out-Null

# 1. Скрипты фабрики
Say '1/6 Скачиваю фабрику с GitHub'
$zip = Join-Path $env:TEMP 'maks-dvizh.zip'
$src = Join-Path $env:TEMP 'maks-dvizh-src'
Invoke-WebRequest 'https://codeload.github.com/createparadise/maks-dvizh-assets/zip/refs/heads/main' -OutFile $zip -UseBasicParsing
if (Test-Path $src) { Remove-Item $src -Recurse -Force }
Expand-Archive $zip -DestinationPath $src -Force
Copy-Item (Join-Path $src 'maks-dvizh-assets-main\factory\*') $root -Recurse -Force
Ok "папка $root"

# 2. Python
Say '2/6 Проверяю Python'
$py = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
if (-not (Test-Path $py)) {
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { $py = $cmd.Source } else { throw 'Python не найден. Поставь Python 3.12 с python.org и запусти установку ещё раз.' }
}
$pyw = Join-Path (Split-Path $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py }
Ok (& $py --version)

# 3. Ключи (хранятся только на этом компьютере, в config.json)
Say '3/6 Ключи'
$cfgPath = Join-Path $root 'config.json'
if (-not (Test-Path $cfgPath)) { Copy-Item (Join-Path $root 'config.example.json') $cfgPath }
$cfg = [IO.File]::ReadAllText($cfgPath, $utf8).TrimStart([char]0xFEFF) | ConvertFrom-Json
foreach ($p in 'llmmart_key', 'vk_group_token') {
  if (-not ($cfg.PSObject.Properties.Name -contains $p)) { $cfg | Add-Member -NotePropertyName $p -NotePropertyValue '' }
}
if (-not $cfg.llmmart_key) {
  $k = Read-Host 'Вставь ключ LLM Mart (sk-router-...) и нажми Enter'
  if ($k) { $cfg.llmmart_key = $k.Trim() }
}
if (-not $cfg.vk_group_token) {
  $t = Read-Host 'Вставь ключ группы ВК (vk1.a...) и нажми Enter. Нет ключа — просто Enter'
  if ($t) { $cfg.vk_group_token = $t.Trim() }
}
[IO.File]::WriteAllText($cfgPath, ($cfg | ConvertTo-Json -Depth 6), $utf8)
if ($cfg.llmmart_key) { Ok 'ключ LLM Mart сохранён' } else { Warn 'нет ключа LLM Mart — картинки и посты не заработают' }
if ($cfg.vk_group_token) { Ok 'ключ группы ВК сохранён' } else { Warn 'нет ключа ВК — автопостинг и бот ТЕЛО включатся после повторного запуска с ключом' }

# 4. Расписание Windows (от имени текущего пользователя)
Say '4/6 Ставлю задачи в Планировщик Windows'
Push-Location $root
& cmd.exe /c 'echo.|install_tasks.bat'
Pop-Location
foreach ($n in 'MaksDvizh-Weekly', 'MaksDvizh-DailyImage', 'MaksDvizh-TELO') {
  & schtasks.exe /Query /TN $n 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Ok $n } else { Warn "$n не создана" }
}

# 5. Cua Driver — агент сам кликает мышкой (подключается к Cline)
Say '5/6 Ставлю Cua Driver'
function Find-Cua {
  foreach ($c in (Join-Path $env:LOCALAPPDATA 'Programs\Cua\cua-driver\bin\cua-driver.exe'),
                 (Join-Path $env:LOCALAPPDATA 'Programs\trycua\cua-driver-rs\bin\cua-driver.exe')) {
    if (Test-Path $c) { return $c }
  }
  return $null
}
$cua = Find-Cua
if (-not $cua) {
  # Прямо с GitHub Releases: cua.ai из РФ может не открываться
  $bin = Join-Path $env:LOCALAPPDATA 'Programs\Cua\cua-driver\bin'
  New-Item -ItemType Directory -Force -Path $bin | Out-Null
  $czip = Join-Path $env:TEMP 'cua-driver-win.zip'
  $url = 'https://github.com/trycua/cua/releases/download/cua-driver-rs-v0.55.0/cua-driver-rs-0.55.0-windows-x86_64-binary.zip'
  Write-Host '    качаю Cua Driver с GitHub (33 МБ)...'
  try {
    Invoke-WebRequest $url -OutFile $czip -UseBasicParsing -TimeoutSec 900
    Expand-Archive $czip -DestinationPath $bin -Force
  } catch { Warn $_.Exception.Message }
  $cua = Find-Cua
}
if ($cua) {
  $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  $v = (& $cua --help 2>&1 | Select-Object -First 1 | Out-String).Trim()
  $code = $LASTEXITCODE
  $ErrorActionPreference = $old
  if ($code -eq -1073741795 -or $code -eq -1073741515 -or $code -eq -1073740791) {
    Warn "Cua Driver не запускается на этом процессоре или без библиотек (код $code)"; $cua = $null
  } else { Ok "Cua Driver отвечает: $v" }
}
if ($cua) {
  Ok "Cua Driver: $cua"
  $mcp = Join-Path $env:APPDATA 'Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json'
  New-Item -ItemType Directory -Force -Path (Split-Path $mcp) | Out-Null
  if (Test-Path $mcp) {
    $obj = [IO.File]::ReadAllText($mcp, $utf8).TrimStart([char]0xFEFF) | ConvertFrom-Json
  } else {
    $obj = [pscustomobject]@{}
  }
  if (-not ($obj.PSObject.Properties.Name -contains 'mcpServers')) { $obj | Add-Member -NotePropertyName mcpServers -NotePropertyValue ([pscustomobject]@{}) }
  $srv = [pscustomobject]@{ command = $cua; args = @('mcp'); disabled = $false; autoApprove = @(); timeout = 120; type = 'stdio' }
  $obj.mcpServers | Add-Member -NotePropertyName 'cua-driver' -NotePropertyValue $srv -Force
  [IO.File]::WriteAllText($mcp, ($obj | ConvertTo-Json -Depth 10), $utf8)
  Ok 'Cua Driver подключён к Cline (перезапусти VS Code)'
} else {
  Warn 'Cua Driver не установился — фабрика работает и без него'
}

# 6. Проверка: картинка к посту дня 2 откроется на экране
Say '6/6 Тест: рисую первую картинку для группы'
if ($cfg.llmmart_key) {
  Push-Location $root
  $env:PYTHONUTF8 = '1'
  New-Item -ItemType Directory -Force -Path (Join-Path $root 'images') | Out-Null
  & $py gen_image.py --text 'Мужчина 35 лет в футболке делает разминку для спины рядом с рабочим столом дома, утренний свет из окна, живое фото, без текста' --out (Join-Path $root 'images\test-first.png')
  Pop-Location
  $img = Get-ChildItem (Join-Path $root 'images') -Filter *.png -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($img) { Ok $img.FullName; Start-Process $img.FullName } else { Warn 'картинка не появилась — смотри текст выше' }
}

Write-Host ''
Write-Host 'ГОТОВО. Фабрика: ' -NoNewline; Write-Host $root -ForegroundColor Green
Write-Host 'Каждый пн 09:00 — 7 постов в отложенные ВК; каждый день 08:00 — картинка; каждые 10 минут — ответ на ТЕЛО.'

# Creates a Windows Desktop shortcut for one-click automatic launch of JARVIS
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path -Path $DesktopPath -ChildPath "J.A.R.V.I.S..lnk"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$TargetExe = Join-Path -Path $ProjectDir -ChildPath ".venv\Scripts\pythonw.exe"
$IconPath = Join-Path -Path $ProjectDir -ChildPath "assets\branding\jarvis_logo.png"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetExe
$Shortcut.Arguments = "-m jarvis.main"
$Shortcut.WorkingDirectory = $ProjectDir
$Shortcut.Description = "JARVIS Personal AI Desktop Assistant"
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath,0"
}
$Shortcut.Save()

Write-Host "Created Desktop shortcut at: $ShortcutPath"

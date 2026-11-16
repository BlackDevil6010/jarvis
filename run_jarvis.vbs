Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
ScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir
WshShell.Run """" & ScriptDir & "\.venv\Scripts\pythonw.exe"" -m jarvis.main", 0, False
Set WshShell = Nothing
Set fso = Nothing

Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
shell.CurrentDirectory = fs.GetParentFolderName(WScript.ScriptFullName)
shell.Run "pythonw """ & shell.CurrentDirectory & "\jojo_desktop.py"" --start-core", 0, False

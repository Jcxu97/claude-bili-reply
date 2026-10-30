' Start a command with no console window. Args: program and its arguments.
Dim a, i, cmd
Set a = WScript.Arguments
For i = 0 To a.Count - 1
  cmd = cmd & " """ & a(i) & """"
Next
WScript.Quit CreateObject("WScript.Shell").Run(Mid(cmd, 2), 0, True)

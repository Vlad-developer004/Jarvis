@echo off
cd /d "C:\Users\tanja\OneDrive\Desktop\projects\Jarvis"
"C:\Users\tanja\AppData\Local\Programs\Inno Setup 6\ISCC.exe" jarvis_installer.iss
echo ISCC_EXIT=%ERRORLEVEL%

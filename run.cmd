@echo off
rem Starts the app. This exists so nobody has to type the PowerShell incantation.
rem
rem Windows blocks unsigned scripts by default, so run.ps1 has to be launched
rem with -ExecutionPolicy Bypass. Asking a first time user to paste
rem "powershell -ExecutionPolicy Bypass -File .\run.ps1" is the most alarming
rem thing on the whole setup page, and it is alarming for a reason that has
rem nothing to do with this project. The flag lives here instead, so the
rem documented command is ".\run.cmd" and double clicking this file also works.
rem
rem run.ps1 still runs directly for anyone who prefers it.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*

rem Double clicking opens a window that would close the instant anything failed,
rem taking the error with it. Hold it open so the message can be read.
if errorlevel 1 pause

@echo off
title JoJo AGI - Universal Remote Access Tunnel
chcp 65001 >nul
cls
echo ==============================================================
echo 🌐 JoJo AGI - Universal Remote Access Tunnel
echo (Phone aur Laptop ko alag-alag network / 4G par connect karein)
echo ==============================================================
echo.
echo 🚀 Generating free secure public HTTPS URL for JoJo Core (port 8000)...
echo 👉 Copy the HTTPS URL shown below and open on your mobile:
echo.
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run
echo.
echo Tunnel closed.
pause

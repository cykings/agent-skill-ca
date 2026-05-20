@echo off
chcp 65001 > nul
cd /d %~dp0
echo ============================================
echo  tg-ca-bot 启动中...
echo  Ctrl+C 退出
echo ============================================
python bot.py
pause

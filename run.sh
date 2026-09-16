#!/data/data/com.termux/files/usr/bin/bash
cd ~/Haedrstorebot
pkill -f "python bot.py" 2>/dev/null
sleep 2
nohup python bot.py > bot.log 2>&1 &
sleep 3
if ps aux | grep -q "[p]ython bot.py"; then
    echo "البوت يعمل في الخلفية"
    echo "السجل: ~/Haedrstorebot/bot.log"
else
    echo "فشل تشغيل البوت"
    tail -20 bot.log
fi

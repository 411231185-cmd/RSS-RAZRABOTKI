@echo off
chcp 65001 >nul
echo 🚀 Начинаем преобразование...

cd /d "C:\GitHub-Repositories\RUS-tanko-Sbyt-Agreements\"

echo 1️⃣ СОЗДАЁМ PPTX...
pandoc "Prezentacija_Zvezdochka (1).md" -t pptx -o "Prezentacija_Zvezdochka (1).pptx"
echo ✅ PPTX готов

echo 2️⃣ СОЗДАЁМ PDF...
pandoc "Prezentacija_Zvezdochka (1).md" -t pdf -o "Prezentacija_Zvezdochka (1).pdf"
echo ✅ PDF готов

echo 3️⃣ СОЗДАЁМ HTML...
pandoc "Prezentacija_Zvezdochka (1).md" -t revealjs --standalone -o "Prezentacija_Zvezdochka (1).html"
echo ✅ HTML готов

echo.
echo 🎉 ВСЕ ФАЙЛЫ СОЗДАНЫ!
pause

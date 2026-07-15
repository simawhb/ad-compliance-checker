@echo off
REM 驷马报考 每日数据采集
REM 由 Windows 任务计划程序触发，不依赖 Hermes 是否运行
cd /d D:\WorkBuddy\gaokao-database

echo [%date% %time%] 驷马报考 每日采集开始

REM 1. 数据采集
python src/scripts/daily_run.py
if errorlevel 1 echo [ERROR] daily_run.py 失败

REM 2. 数据入库
python src/scripts/import_to_sqlite.py
if errorlevel 1 echo [ERROR] import_to_sqlite.py 失败

REM 3. 学校关联修复
python src/scripts/fix_forum_school_ids.py
if errorlevel 1 echo [ERROR] fix_forum_school_ids.py 失败

echo [%date% %time%] 驷马报考 每日采集完成

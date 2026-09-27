@echo off
REM Build the MCB120L Excel Grader GUI into a standalone Windows app.
REM Run this from the repo root. Use Python 3.11, 3.12, or 3.13 (not 3.14).

echo Installing the package and build tools...
pip install -e . || goto :err
pip install pyinstaller || goto :err

echo.
echo Building the executable...
pyinstaller ^
  --name MCB120L_Grader ^
  --noconfirm ^
  --windowed ^
  --paths src ^
  --add-data "src/excel_grader;excel_grader" ^
  --collect-all polars ^
  --collect-all fastexcel ^
  --collect-submodules openpyxl ^
  --hidden-import excel_grader ^
  --hidden-import excel_grader.configs ^
  --hidden-import excel_grader.process_config ^
  --hidden-import excel_grader.utils ^
  --hidden-import excel_grader.gui ^
  --hidden-import excel_grader.gui.app ^
  --hidden-import excel_grader.gui.grader_api ^
  --hidden-import excel_grader.gui.lab_presets ^
  run_gui.py || goto :err

echo.
echo Done. The app is in dist\MCB120L_Grader\
echo Zip that whole folder to share it. The .exe needs the _internal folder next to it.
goto :eof

:err
echo.
echo Build failed. Use Python 3.11, 3.12, or 3.13 (not 3.14), and make sure
echo pip installed the dependencies without errors.
exit /b 1

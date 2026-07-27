#!/usr/bin/env bash
set -e
pip install -e .
pip install pyinstaller
pyinstaller \
  --name MCB120L_Grader \
  --noconfirm \
  --windowed \
  --paths src \
  --add-data "src/excel_grader:excel_grader" \
  --collect-all polars \
  --collect-all fastexcel \
  --collect-submodules openpyxl \
  --hidden-import excel_grader \
  --hidden-import excel_grader.configs \
  --hidden-import excel_grader.process_config \
  --hidden-import excel_grader.utils \
  --hidden-import excel_grader.gui \
  --hidden-import excel_grader.gui.app \
  --hidden-import excel_grader.gui.grader_api \
  --hidden-import excel_grader.gui.lab_presets \
  run_gui.py

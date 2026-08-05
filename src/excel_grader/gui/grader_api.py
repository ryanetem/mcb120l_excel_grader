from __future__ import annotations

import contextlib
import importlib
import io
import re
import traceback
from pathlib import Path

import polars as pl
import polars.selectors as cs

import builtins as _builtins
import typing as _typing
_builtins.Optional = _typing.Optional

from .. import configs as _configs_mod
from .. import process_config as _process_config_mod
from .. import utils as _utils


def grade_file(
    xlsx_path,
    *,
    operation_configs,
    stock_configs,
    dilution_configs,
    pka_configs,
    standard_configs,
    assay_configs,
    bglb_configs,
    hh_configs,
    multiplier_configs,
    separator="_",
):
    xlsx_path = Path(xlsx_path)

    _inject_configs(
        operation_configs=operation_configs,
        stock_configs=stock_configs,
        dilution_configs=dilution_configs,
        pka_configs=pka_configs,
        standard_configs=standard_configs,
        assay_configs=assay_configs,
        bglb_configs=bglb_configs,
        hh_configs=hh_configs,
        multiplier_configs=multiplier_configs,
    )

    buf = io.StringIO()
    success = True
    err = ""

    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            _run_one_file(xlsx_path, separator=separator)
        except Exception as e:  # noqa: BLE001
            success = False
            err = f"{type(e).__name__}: {e}"
            traceback.print_exc()

    return {
        "success": success,
        "output": buf.getvalue(),
        "error": err,
        "file": str(xlsx_path),
    }


def _inject_configs(
    *,
    operation_configs,
    stock_configs,
    dilution_configs,
    pka_configs,
    standard_configs,
    assay_configs,
    bglb_configs,
    hh_configs,
    multiplier_configs,
):
    _configs_mod.OPERATION_CONFIGS = operation_configs
    _configs_mod.STOCK_CONFIGS = stock_configs
    _configs_mod.DILUTION_CONFIGS = dilution_configs
    _configs_mod.PKA_CONFIGS = pka_configs
    _configs_mod.STANDARD_CONFIGS = standard_configs
    _configs_mod.ASSAY_CONFIGS = assay_configs
    _configs_mod.BGLB_CONFIGS = bglb_configs
    _configs_mod.HH_CONFIGS = hh_configs
    _configs_mod.MULTIPLIER_CONFIGS = multiplier_configs

    importlib.reload(_process_config_mod)


def _run_one_file(xlsx_path, *, separator):
    process_operation = _process_config_mod.process_operation

    print("-" * 80)
    print(f"\nLoaded: {xlsx_path}")

    df = pl.read_excel(xlsx_path)
    df = df.rename({col: col.lower() for col in df.columns})
    df = df.rename({col: re.sub(r"_\(.*\)", "", col) for col in df.columns})

    print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns")

    column_groups = _utils.group_columns_by_first_then_second(df, separator=separator)
    print(column_groups)

    print("\n" + "=" * 80)
    print("EXECUTING VERIFICATION PIPELINE")
    print("=" * 80)

    operation_configs = _configs_mod.OPERATION_CONFIGS

    for i, (parent_group, child_groups) in enumerate(column_groups.items()):
        print(f"\n--- Step {i}: {parent_group} ---\n")

        parent_config = next(
            (cfg for key, cfg in operation_configs.items() if key == parent_group),
            None,
        )
        if parent_config:
            print(
                f"Matched operation '{parent_config['operation']}' "
                f"on parent group '{parent_group}'"
            )
            df = process_operation(
                parent_config, parent_group, df, column_groups, str(xlsx_path)
            )
            continue

        processed_any_child = False
        for j, (child_group, _columns) in enumerate(child_groups.items()):
            child_config = next(
                (cfg for key, cfg in operation_configs.items() if key == child_group),
                None,
            )
            if child_config:
                print(
                    f"  Inner loop {j}: Matched operation "
                    f"'{child_config['operation']}' on child group '{child_group}'"
                )
                df = process_operation(
                    child_config, parent_group, df, child_groups, str(xlsx_path)
                )
                processed_any_child = True

        if not processed_any_child:
            print(df.select(cs.starts_with(parent_group)))

    print("\n" + "-" * 80)


def grade_folder(
    input_dir,
    output_dir,
    *,
    operation_configs,
    stock_configs,
    dilution_configs,
    pka_configs,
    standard_configs,
    assay_configs,
    bglb_configs,
    hh_configs,
    multiplier_configs,
    output_basename="results",
    section="",
    file_match=None,
    progress_cb=None,
):
    EXTS = {".xls", ".xlsx", ".xlsm", ".xlsb", ".xltx"}
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in EXTS
        and not p.name.startswith("~$")
        and not p.name.startswith("._")
    )

    if file_match:
        tokens = [t.lower() for t in file_match]
        files = [f for f in files if any(t in f.name.lower() for t in tokens)]

    results = []

    for i, f in enumerate(files, start=1):
        result = grade_file(
            f,
            operation_configs=operation_configs,
            stock_configs=stock_configs,
            dilution_configs=dilution_configs,
            pka_configs=pka_configs,
            standard_configs=standard_configs,
            assay_configs=assay_configs,
            bglb_configs=bglb_configs,
            hh_configs=hh_configs,
            multiplier_configs=multiplier_configs,
        )
        results.append(result)

        try:
            rel = f.relative_to(input_dir)
        except ValueError:
            rel = Path(f.name)
        result["_rel"] = rel.as_posix()

        if progress_cb:
            progress_cb(i, len(files), f.name, result)

    suffix = f"_{section}" if section else ""
    results_filename = f"{output_basename}results{suffix}.txt"
    summary_filename = f"{output_basename}summary{suffix}.csv"

    combined_path = output_dir / results_filename
    sep = "-" * 80
    chunks = []
    for r in results:
        chunks.append(sep)
        chunks.append("")
        chunks.append(f"File: {r['_rel']}")
        chunks.append(f"Status: {'OK' if r['success'] else 'ERROR'}")
        if r["error"]:
            chunks.append(f"Error: {r['error']}")
        chunks.append("")
        chunks.append(r["output"].rstrip("\n"))
        chunks.append("")
    chunks.append(sep)
    combined_path.write_text("\n".join(chunks), encoding="utf-8")

    summary_lines = ["submission_folder,filename,status,error"]
    for r in results:
        rel = Path(r["_rel"])
        folder = rel.parent.as_posix() if rel.parent != Path(".") else "."
        name = rel.name
        status = "OK" if r["success"] else "ERROR"
        err = (r["error"] or "").replace("\n", " ").replace(",", ";")
        summary_lines.append(f"{folder},{name},{status},{err}")
    (output_dir / summary_filename).write_text(
        "\n".join(summary_lines), encoding="utf-8"
    )

    return results

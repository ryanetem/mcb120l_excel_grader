#! /usr/bin/env python

import polars as pl
import numpy as np
import polars.selectors as cs
import argparse
import re
import sys
from collections import defaultdict
from typing import Dict, List, Tuple, Union
from pathlib import Path
from glob import glob
import logging

from . import utils
from .process_config import verify_calculated_columns_generic, report_mismatches, get_verification_columns, process_operation
from .configs import OPERATION_CONFIGS

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("check_hw_errors.log"),
        logging.StreamHandler(sys.stderr),
    ],
)

def main():
    p = argparse.ArgumentParser(description='Verify Excel calculations using column groups')
    p.add_argument('input', nargs='+', type=utils.path_exists, help='Input Excel file(s)')
    p.add_argument('--output', default=None, help='Output Excel file (optional)')
    p.add_argument('--separator', default='_', help='Column name separator (default: _)')
    args = p.parse_args()

    excel_files = utils.collect_excels(args.input)

    for excel_file in excel_files:

        print("-"*80)
        print(f"\nLoaded: {excel_file}")

        try:
            df = pl.read_excel(excel_file,   # schema_overrides={"Dilution_factor_unknown_1-2": pl.Float64}
            )
            # We could set a row limit with df = df.head(n=8)
            df = df.rename({col: col.lower() for col in df.columns})
            df = df.rename({col: re.sub(r"_\(.*\)", '', col) for col in df.columns})
        except Exception as e:
            logging.error(f"\n{excel_file}: failed to read Excel file — {e}\n")
            continue

        print(f"Shape: {df.shape[0]} rows × {df.shape[1]} columns")

        # Group columns into nested dict
        column_groups = utils.group_columns_by_first_then_second(df, separator=args.separator)
        print(column_groups)

        print("\n" + "="*80)
        print("EXECUTING VERIFICATION PIPELINE")
        print("="*80)

        for i, (parent_group, child_groups) in enumerate(column_groups.items()):
            print(f"\n--- Step {i}: {parent_group} ---\n")

            # A. Check Parent Group First
            parent_config = next((config for key, config in OPERATION_CONFIGS.items() if key in parent_group), None)

            if parent_config:
                print(f"Matched operation '{parent_config['operation']}' on parent group '{parent_group}'")
                df = process_operation(parent_config, parent_group, df, column_groups, excel_file)
                continue  # Move to the next parent_group since we handled it at the top level

            # B. If Parent didn't match, check Child Groups
            processed_any_child = False

            for j, (child_group, columns) in enumerate(child_groups.items()):
                child_config = next((config for key, config in OPERATION_CONFIGS.items() if key in child_group), None)

                if child_config:
                    print(f"  Inner loop {j}: Matched operation '{child_config['operation']}' on child group '{child_group}'")
                    # Note: target_group is still parent_group based on your original logic
                    df = process_operation(child_config, parent_group, df, child_groups, excel_file)
                    processed_any_child = True
            
            # C. Fallback: If neither the parent nor any children matched our configs
            if not processed_any_child:
                print(df.select(cs.starts_with(parent_group)))

        print("\n" + "-"*80)

if __name__ == '__main__':
    main()

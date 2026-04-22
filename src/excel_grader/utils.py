#! /usr/bin/env python

import polars as pl
from collections import defaultdict
from typing import Dict, List
import re
from pathlib import Path
import argparse
from glob import glob

EXCEL_EXTS = {".xls", ".xlsx", ".xlsm", ".xlsb", ".xltx"}

def is_close(a, b, atol=1e-6, rtol=1e-5):
    return (a - b).abs() <= (atol + rtol * a.abs())

def group_columns_by_first_then_second(df: pl.DataFrame, separator: str = '_') -> Dict[str, Dict[str, List[str]]]:
    """
    Group columns first by their prefix, then by the 'middle' string (ignoring numeric ranges).
    
    Args:
        df: Polars DataFrame
        separator: Character that separates prefix from rest of column name
        
    Returns:
        Nested Dictionary mapping prefix -> middle_string -> list of column names
    """
    groups = defaultdict(lambda: defaultdict(list))
    
    for col in df.columns:
        parts = col.split(separator)
        if not parts:
            continue
 
        first = parts[0].lower()
        second = parts[1].lower()
        rest_of_col = col[len(first) + len(separator):]
 
        # 3. Use Regex to separate the middle text from the numeric ranges
        # - Group 1: Captures everything up to the number (Middle string)
        # - Group 2: Captures the number or range (e.g., '1', '1-3', '4-6')
        match = re.search(r'(.*?)(?:_)?(\d+(?:-\d+)?)', rest_of_col)

        if match:
            # Strip trailing separators (e.g., "dilution-factor_" becomes "dilution-factor")
            middle = match.group(1).strip(separator)
        else:
            # If no numbers/ranges are found, the entire remaining string is the middle
            middle = rest_of_col.strip(separator)

        # Edge case: fallback if there is no middle string
        if not middle:
            middle = "base"

        # 4. Group the data
        groups[first][second].append(col)
        
    # Convert nested defaultdicts back to standard dictionaries for a clean output
    return {k: dict(v) for k, v in groups.items()}

def path_exists(path: str) -> Path:
    p = Path(path)
    if not p.exists():
        raise argparse.ArgumentTypeError(f"{path} does not exist")
    return p

def collect_excels(paths: list[Path]) -> list[Path]:
    files: list[Path] = []

    for p in paths:
        matches = list(map(Path, glob(str(p))))
        if matches:
            for m in matches:
                if m.is_dir():
                    files.extend(
                        f for f in m.iterdir()
                        if f.suffix.lower() in EXCEL_EXTS
                    )
                else:
                    files.append(m)
        elif p.is_dir():
            files.extend(
                f for f in p.iterdir()
                if f.suffix.lower() in EXCEL_EXTS
            )
        else:
            files.append(p)

    excel_files = [
        f for f in files
        if f.exists() and f.suffix.lower() in EXCEL_EXTS
    ]

    if not excel_files:
        raise SystemExit("❌ No Excel files found")

    return sorted(set(excel_files))

def process_operation(config, target_group, df, column_groups, excel_file):
    """Executes the verification, formatting, and printing for a given configuration."""
    try:
        kwargs = {
            'df': df,
            'source_group': config['source_group'],
            'target_group': config['target_group'],
            'column_groups': column_groups,
            'operation': config['operation']
        }
 
        if 'dilution_col' in config:
            kwargs['dilution_col'] = config['dilution_col']

        df = verify_calculated_columns_generic(**kwargs)
        report_mismatches(df, target_group, column_groups)
        relevant_cols = get_verification_columns(df, target_group)

        with pl.Config() as cfg:
            if config['operation'] in ('concentration','graph'):
                cfg.set_tbl_rows(-1)
                cfg.set_tbl_cols(-1)
                if config['operation'] == 'graph':
                    cfg.set_tbl_width_chars(100)
                    cfg.set_fmt_str_lengths(100)
                    cfg.set_fmt_table_cell_list_len(-1)

            print(df.select(relevant_cols))

    except Exception as e:
        logging.error(f"\n{excel_file} | {config['error_msg']}: {e}", exc_info=True)

    return df

def find_related_columns(df, split_and_search_headers, context_term, ignore_list=None):
    """
    Finds sister columns that contain both a significant element of the target column 
    and the context term, ensuring none of the found columns are in the ignore_list.
    
    Returns:
        dict: A mapping of {target_col: discovered_sister_col}
    """
    # Safe handling of mutable default arguments
    if ignore_list is None:
        ignore_list = ['match', 'diff', 'calculated']

    related_cols = {}

    for target_col in split_and_search_headers:
        # 1. Get keywords and filter out tiny words (like 'of', 'in') immediately
        col_keywords = [kw for kw in target_col.split('_') if len(kw) > 2]
        print(col_keywords)
        # 2. Find matching columns in the dataframe
        matches = [
            c for c in df.columns 
            if context_term in c                                    # Must contain context (e.g., 'stock')
            and any(keyword in c for keyword in col_keywords)       # Must contain at least one keyword
            and not any(bad in c for bad in ignore_list)            # Strict ignore
        ]

        # 3. Handle the "Break" logic
        if not matches:
            raise ValueError(
                f"❌ Column Discovery Break: Could not find a related column containing '{context_term}' "
                f"using keywords {col_keywords}.\n"
                f"Target Column: {target_col}\n"
                f"Search excluded: {ignore_list}"
            )

        # 4. Store the discovered mapping (grabbing the first match)
        related_cols[target_col] = matches

    return related_cols

def find_related_term(df, headers_to_split, context_term, ignore_list=None):
    """
    Finds the sister column to a term in the header and the context term while
    also ignoring any terms in the ignore list.

    Returns:
        list: A list of matching terms
    """
    if ignore_list is None:
        ignore_list = ['match', 'diff', 'calculated']

    related_terms =[]
    for target_col in headers_to_split:
        col_keywords = [kw for kw in target_col.split('_') if len(kw) > 2]
        print(col_keywords)

        matches = [
                term 
                for c in df.columns
                if context_term in c
                and not any(bad_word in c for bad_word in ignore_list)
                for term in c.split('_')
                if term in col_keywords
                ]

        if not matches:
            raise ValueError(
                f"❌ Column Discovery Break: Could not find a related column containing '{context_term}' "
                f"using keywords {col_keywords}.\n"
                f"Target Column List: {target_col}\n"
                f"Search excluded: {ignore_list}"
                )

        related_terms.extend(matches)
    return list(set(related_terms))

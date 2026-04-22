#! /usr/bin/env python

import polars as pl
import numpy as np
import polars.selectors as cs

import sys
import re
from collections import defaultdict
from typing import Dict, List, Tuple, Union
import logging

from .configs import STOCK_CONFIGS, DILUTION_CONFIGS, PKA_CONFIGS
from . import utils
from .utils import is_close

def verify_calculated_columns_generic(df: pl.DataFrame, 
                                     source_group: Union[str, List[str]],
                                     target_group: str,
                                     column_groups: Dict[str, List[str]],
                                     operation: str = 'mean',
                                     numerator: float = None,
                                     dilution_col: str = None,
                                     set_y_int_to_0: bool = False,
                                     ) -> pl.DataFrame:
    """
    Verify calculated columns using column groups.

    Args:
        df: Polars DataFrame
        source_group: Name of source column group (e.g., "raw")
        target_group: Name of target column group (e.g., "average")
        column_groups: Dictionary of column groups
        operation: Operation to perform ('mean', 'sum', 'product', 'division', 'blank_correction')
        numerator: Value for division operation
        dilution_col: Column name for blank correction (required when operation='blank_correction')
    
    Returns:
        DataFrame with added calculated, difference, and match columns
    """
    if operation == 'division' and numerator is None:
        print("⚠️ Select numerator (Starting working concentration value)")
        return df
    
    if (operation == 'blank_correction' and dilution_col is None or
       operation == 'verify_working' and dilution_col is None):
        print("⚠️ dilution_col is required for blank_correction operation")
        return df

    print(f"\n{'='*80}")
    print(f"Verifying: {source_group} -> {target_group}")
    if operation == 'blank_correction':
        print(f"Operation: Blank Correction using {dilution_col}")
    else:
        print(f"Operation: {operation}")
    print(f"{'='*80}")

    if operation == 'divide_columns':
        if not isinstance(source_group, list) or len(source_group) != 2:
            raise ValueError("For 'divide_columns', source_group must be a list: ['numerator_group', 'denominator_group']")

        num_cols = column_groups.get(source_group[0], [])
        den_cols = column_groups.get(source_group[1], [])
        target_cols = column_groups.get(target_group, [])

        out_exprs = []

        for num_col, den_col, target_col in zip(num_cols, den_cols, target_cols):
            calc_col = f"calculated_{target_col}"
            diff_col = f"diff_{target_col}"
            match_col = f"match_{target_col}"
            calc_expr = None


            raw_calc =  pl.col(num_col) / pl.col(den_col)
            calc_expr = (
                        pl.when(raw_calc.is_infinite() | raw_calc.is_nan())
                        .then(None)
                        .otherwise(raw_calc)
                        )

            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - pl.col(target_col)).alias(diff_col),
                ((calc_expr - pl.col(target_col)).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    source_cols = column_groups.get(source_group, [])
    target_cols = column_groups.get(target_group, [])

    # Helper logic to dynamically extract lists from dictionaries
    if isinstance(source_cols, dict):
        # Extracts all values (which are lists) and flattens them into a single list
        source_cols = [col for sublist in source_cols.values() for col in sublist]

    if isinstance(target_cols, dict):
        target_cols = [col for sublist in target_cols.values() for col in sublist]

    if not source_cols:
        print(f"⚠️  No columns found for source group '{source_group}'")
        try:
            # this function should not return the full column name but the string that binds them together!!!
            print('rel col:', target_cols)
            print(utils.find_related_term(df, target_cols, source_group))
            related_terms = utils.find_related_term(df, target_cols, source_group)
            related_cols =  utils.find_related_columns(df, target_cols, source_group)
            print(related_cols, related_terms)
            for col in related_cols.values():
                source_cols.extend(col)
            source_cols = list(set(source_cols))
            print('\n',source_cols, related_terms, '\n')
        except:
            return df

    if not target_cols:
        print(f"⚠️  No columns found for target group '{target_group}'")
        print(utils.find_related_column(df, target_cols, target_group))
 
        return df

    print(f"Source columns ({len(source_cols)}): {source_cols}")
    print(f"Target columns ({len(target_cols)}): {target_cols}")

    if operation == 'verify_hh_ph':
        assert len(PKA_CONFIGS) < 2

        for key, value in PKA_CONFIGS.items():
            pka_name = key
            pka_value = value

        print("pKa for", pka_name, "is", pka_value)
 
        pka_col = next((c for c in target_cols if "pka" in c), None)

        if pka_col is None:
            print("⚠️ Student pKa value not found.")

        if pka_col:
            invalid_mask = df.filter(
                pl.col(pka_col).cast(pl.Float64, strict=False).is_null() & 
                pl.col(pka_col).is_not_null()
            )

            if not invalid_mask.is_empty():
                bad_values = invalid_mask[pka_col].unique().to_list()
                raise TypeError(
                    f"❌ Data Type Break: Column '{pka_col}' contains non-numeric data: {bad_values}. "
                    f"Fix the source data before proceeding."
                )

            try:
                raw_val = df.select(pl.col(pka_col).drop_nulls()).item(0, 0)
            except IndexError:
                raise ValueError(f"❌ Data Break: Column '{pka_col}' is completely empty.")

            if raw_val not in PKA_CONFIGS.values():
                raise ValueError(
                    f"❌ Value Mismatch: Student entered {raw_val}, "
                    f"but expected one of {PKA_CONFIGS}."
                )

            print(f"✅ pKa verified successfully: {raw_val}")

        out_exprs = []
        for col in target_cols:
            if 'pka' in col:
                continue
            related_term = utils.find_related_term(df, [col], source_group)
            related_term = str(related_term[0])
            calc_col = f"calculated_{col}"
            diff_col = f"diff_{col}"
            match_col = f"match_{col}"
            calc_expr = None

            t_expr = pl.col(col)#.cast(pl.Float64, strict=False)
            s_expr = pl.col(f"graph_slope_{related_term}")
            den_col = pl.col(dilution_col)

            den_expr = ( 1 - (s_expr / den_col) )
            hh_eq = pka_value + (np.log10((s_expr / den_col)/(den_expr)))

            calc_expr = (
                    pl.when(den_expr <= 0)
                    .then(0.0)
                    .when(hh_eq.is_infinite())
                    .then(0.0)
                    .when(den_col.is_null())
                    .then(None)
                    .otherwise(
                        hh_eq
                        )
                    )

            if calc_expr is None:
                continue

            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - t_expr).alias(diff_col),
                ((calc_expr - t_expr).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    if operation == 'verify_dilution_factor':
        # 1. Find the column
        fact_col = next((c for c in source_cols if "dilution" in c), None)
        if fact_col is None:
            print("⚠️ Dilution Factor column not found.")
            return df
 
        verification = df.select([
            pl.col(fact_col).alias("raw_value")
        ]).with_columns([
            # Attempt to cast to float (non-numerics become null)
            pl.col("raw_value").cast(pl.Float64, strict=False).alias("parsed_float")
        ]).with_columns([
            # Check if the parsed float exists in your allowed list
            pl.col("parsed_float").is_in(DILUTION_CONFIGS).alias("is_valid")
        ])
    
        # 3. Identify failures
        invalid_rows = verification.filter(pl.col("is_valid") == False)
    
        if invalid_rows.height == 0:
            print(f"✅ {fact_col}: All rows verified successfully!")
        else:
            print(f"❌ {fact_col}: Found {invalid_rows.height} invalid entries.")
            
            # 4. Detailed reporting (limited to first 5 errors to avoid spamming the console)
            for row in invalid_rows.head(5).iter_rows(named=True):
                raw = row['raw_value']
                parsed = row['parsed_float']
                
                if parsed is None:
                    print(f"  - Invalid format: '{raw}' is not a number.")
                else:
                    print(f"  - Mismatch: {parsed} is not in expected {DILUTION_CONFIGS}")
            
            if invalid_rows.height > 5:
                print(f"  ... and {invalid_rows.height - 5} more issues.")
    
        return df

    if operation == 'verify_working':
        stock_col = next((c for c in source_cols if "stock" in c), None)
        if stock_col is None:
            print("⚠️  Stock columns not found in dataframe.")
            return df
        stock_series = df.select(pl.col(stock_col).drop_nulls()).to_series()

        if stock_series.is_empty():
            raise ValueError(f"❌ Data Break: Column '{stock_col}' is completely empty.")

        raw_stock = stock_series[0]
        print(raw_stock)
        try:
            scalar_stock = float(raw_stock)
        except (ValueError, TypeError):
            raise TypeError(f"❌ Data Type Break: '{stock_col}' contains '{raw_stock}', which is not a number.")

        out_exprs = []
        print(df.filter(pl.col(stock_col).is_not_null()))
        for col in target_cols:
            calc_col = f"calculated_{col}"
            diff_col = f"diff_{col}"
            match_col = f"match_{col}"
            calc_expr = None

            t_expr = pl.col(col)#.cast(pl.Float64, strict=False)
            den_col = pl.col(dilution_col)

            calc_expr = (
                    pl.when(den_col == 0)
                    .then(0.0)
                    .when(den_col.is_null())
                    .then(None)
                    .otherwise(scalar_stock / den_col)
                    )

            if calc_expr is None:
                continue

            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - t_expr).alias(diff_col),
                ((calc_expr - t_expr).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    if operation == 'verify_stock':
        color_col = next((c for c in source_cols if "chosen" in c), None)
        conc_col = next((c for c in source_cols if "concentration" in c), None)

        if color_col is None and conc_col is None:
            print(color_col, conc_col)
            print("⚠️  Stock columns not found in dataframe.")
            return df
        if color_col is None and conc_col:
            invalid_mask = df.filter(
                pl.col(conc_col).cast(pl.Float64, strict=False).is_null() & 
                pl.col(conc_col).is_not_null()
            )

            if not invalid_mask.is_empty():
                bad_values = invalid_mask[conc_col].unique().to_list()
                raise TypeError(
                    f"❌ Data Type Break: Column '{conc_col}' contains non-numeric data: {bad_values}. "
                    f"Fix the source data before proceeding."
                )

            try:
                raw_val = df.select(pl.col(conc_col).drop_nulls()).item(0, 0)
            except IndexError:
                raise ValueError(f"❌ Data Break: Column '{conc_col}' is completely empty.")

            if raw_val not in STOCK_CONFIGS:
                raise ValueError(
                    f"❌ Value Mismatch: Student entered {raw_val}, "
                    f"but expected one of {STOCK_CONFIGS}."
                )

            print(f"✅ Stock verified successfully: {raw_val}")
            return df
            valid_data = df.filter(
                pl.col(conc_col)
                .cast(pl.Float32, strict=False)
                .is_in(STOCK_CONFIGS)
                )
            if valid_data.height == 0:
                print("\n⚠️  No valid concentration found in the student's submission.")
                return df
 
            raw_conc = valid_data[conc_col][0]
            expected_conc = STOCK_CONFIGS
        
            try:
                student_conc = float(raw_conc)
        
                if student_conc in expected_conc:
                    print(f"\n✅ {conc_col}: Correct! ({student_conc}%)")
                else:
                    print(f"\n❌ {conc_col}: Mismatch. Student entered {student_conc}%, expected {expected_conc}%")
                    
            except (ValueError, TypeError):
                print(f"\n⚠️ {conc_col}: Invalid format. Student entered '{raw_conc}', expected a number.")
            return df


        # Filter out nulls and instructor notes by checking if the lowercased string is in our dict keys
        valid_data = df.filter(
            pl.col(color_col)
            .cast(pl.Utf8)
            .str.strip_chars()
            .str.to_lowercase()
            .is_in(STOCK_CONFIGS.keys())
        )

        if valid_data.height == 0:
            print("⚠️  No valid known color found in the student's submission.")
            return df
    
        # Extract the values
        chosen_color = valid_data[color_col][0].lower().strip()
        raw_conc = valid_data[conc_col][0]
    
        try:
            student_conc = float(raw_conc)
            expected_conc = STOCK_CONFIGS[chosen_color]
    
            if student_conc == expected_conc:
                print(f"\n✓ {conc_col}: Correct! ({student_conc}% for {chosen_color.capitalize()})")
            else:
                print(f"\n⚠️ {conc_col}: Mismatch. Student entered {student_conc}%, expected {expected_conc}% for {chosen_color.capitalize()}")
                
        except (ValueError, TypeError):
            print(f"\n⚠️ {conc_col}: Invalid format. Student entered '{raw_conc}', expected a number.")
        return df

    if operation == 'enzyme':
        # extract from the sources
        vmax_col = next((c for c in source_cols if "vmax" in c), None)

        #extract from only the target cols
        stock_col = next((c for c in target_cols if "stock-concentration" in c), None)
        dilut_col = next((c for c in target_cols if "dilution-factor" in c), None)
        vol_col = next((c for c in target_cols if "volume-in-assay" in c), None)
        mass_col = next((c for c in target_cols if "mass-in-assay" in c), None)
        spec_activity_col = next((c for c in target_cols if "specific-activity" in c), None)

        cols_to_change = [
            vmax_col, stock_col, dilut_col,
            vol_col, mass_col, spec_activity_col
        ]

        numeric_cols = [
            c for c in cols_to_change
            if c is not None
        ]

        df = df.with_columns([
            pl.col(c).cast(pl.Float64, strict=False) for c in numeric_cols
        ])

        tar_cols = (
            df.select(
                cs.starts_with(target_group)
                & ~cs.matches("units|equation|calculation|calcultion") # dont match these columns
            )
            .columns
        )

        out_exprs = []

        for col in tar_cols:
            calc_col = f"calculated_{col}"
            diff_col = f"diff_{col}"
            match_col = f"match_{col}"
            calc_expr = None

            t_expr = pl.col(col).cast(pl.Float64, strict=False)
            if ("mass-in-assay" in col):
                calc_expr = (( pl.col(stock_col) / pl.col(dilut_col) ) * pl.col(vol_col))
            elif "specific-activity" in col:
                calc_expr = ( pl.col(vmax_col) / pl.col(mass_col))

            if calc_expr is None:
                continue
            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - t_expr).alias(diff_col),
                ((calc_expr - t_expr).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    if operation == 'kcat':
        # extract from the sources
        spec_activity_col = next((c for c in source_cols if "specific-activity" in c), None)
        mol_weight_col = next((c for c in source_cols if "molecular-weight" in c), None)

        #extract from only the target cols
        kcat_col = next((c for c in target_cols if "kcat" in c), None)

        cols_to_change = [
            spec_activity_col, mol_weight_col, kcat_col
        ]

        numeric_cols = [
            c for c in cols_to_change
            if c is not None
        ]

        df = df.with_columns([
            pl.col(c).cast(pl.Float64, strict=False) for c in numeric_cols
        ])

        tar_cols = (
            df.select(
                cs.starts_with(target_group)
                & ~cs.matches("units|equation|calculation|calcultion") # dont match these columns
            )
            .columns
        )

        out_exprs = []

        for col in tar_cols:
            calc_col = f"calculated_{col}"
            diff_col = f"diff_{col}"
            match_col = f"match_{col}"
            calc_expr = None

            t_expr = pl.col(col).cast(pl.Float64, strict=False)
            if ("kcat" in col):
                calc_expr = (( pl.col(spec_activity_col) * pl.col(mol_weight_col) ) / 1000)

            if calc_expr is None:
                continue
            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - t_expr).alias(diff_col),
                ((calc_expr - t_expr).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)



    if operation == 'custom_conc':
        conc_col = next((c for c in source_cols if "concentration" in c), None)

        out_exprs = []
        for target_col in target_cols:
            if "concentration" not in target_col:
                continue
            
            calc_col = f"calculated_{target_col}"
            diff_col = f"diff_{target_col}"
            match_col = f"match_{target_col}"

            denom = 3.0

            c_expr = pl.col(conc_col).cast(pl.Float64, strict=False)
            t_expr = pl.col(target_col).cast(pl.Float64, strict=False)

            raw_calc = (
                pl.when(pl.int_range(pl.len()) == 0)
                .then(75)  # First row gets the starting working conc
                .when(pl.int_range(pl.len()) == (pl.len() - 1))
                .then(0.0) # Last row gets forced to 0 for the blank
                # shift up 1, grab that value, and divide by 3 with the lowest value being 0
                .otherwise(c_expr.shift(1).clip(lower_bound=0) / denom)
            )

            calc_expr = (
                pl.when(raw_calc.is_infinite() | raw_calc.is_nan())
                .then(None)
                .otherwise(raw_calc)
            )

            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - t_expr).alias(diff_col),
                ((calc_expr - t_expr).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    if operation == 'temp_norm':
        if dilution_col not in df.columns:
            print(f"⚠️  Temperature (dilution) column '{dilution_col}' not found!")
            return df

        print(f"Temperature (dilution) column: {dilution_col}")

        #extract from only the source cols
        avg_col = next((c for c in source_cols if "average" in c), None)
 
        out_exprs = []

        for target_col in target_cols:
            if "normalized" not in target_col:
                continue
            calc_col = f"calculated_{target_col}"
            diff_col = f"diff_{target_col}"
            match_col = f"match_{target_col}"
            calc_expr = None

            a_expr = pl.col(avg_col).cast(pl.Float64, strict=False)
            t_expr = pl.col(target_col).cast(pl.Float64, strict=False)
            temp_expr = pl.col(dilution_col).cast(pl.Float64, strict=False)
            min_temp = temp_expr.min()
            denom_expr = (
                a_expr
                .filter(temp_expr == min_temp)
                .max()
                .clip(lower_bound=0)
            )
            raw_calc = a_expr.clip(lower_bound=0) / denom_expr

            calc_expr = (
                pl.when(raw_calc.is_infinite() | raw_calc.is_nan())
                .then(None)
                .otherwise(raw_calc)
            )

            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - t_expr).alias(diff_col),
                ((calc_expr - t_expr).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    if operation == "yield":
        if dilution_col not in df.columns:
            print(f"⚠️  Dilution column '{dilution_col}' not found!")
            return df

        print(f"Dilution column: {dilution_col}")

        # extract from the full df
        frac_col = next((c for c in df.columns if "fraction" in c and "volume" not in c), "fraction")
        frac_vol_col = next((c for c in df.columns if "fraction_volume" in c), None)

        #extract from only the source cols
        quant_col = next((c for c in source_cols if "quant" in c), None)
        loaded_vol_col = next((c for c in source_cols if "volume-loaded" in c), None)
        total_yield_col = next((c for c in source_cols if "total-yield" in c), None)
        frac_activity_col = next((c for c in source_cols if "activity-per-ml" in c), None)
        total_activity_col = next((c for c in source_cols if "total-activity" in c), None)
        perc_activity_col = next((c for c in source_cols if "activity-%-yield" in c), None)
        conc_col = next((c for c in source_cols if "concentration" in c), None)
        total_prot_col = next((c for c in source_cols if "total-protein" in c), None)
        specific_activity_col = next((c for c in source_cols if "fraction" in c), None)

        cols_to_change = [
            frac_vol_col, quant_col, loaded_vol_col, total_yield_col, 
            frac_activity_col, total_activity_col, perc_activity_col,
            conc_col, total_prot_col, specific_activity_col
        ]

        numeric_cols = [
            c for c in cols_to_change
            if c is not None
        ]

        df = df.with_columns([
            pl.col(c).cast(pl.Float64, strict=False) for c in numeric_cols
        ])

        tar_cols = (
            df.select(
                cs.starts_with(target_group)
                & ~cs.matches("units|equation|calculation|calcultion") # dont match these columns
            )
            .columns
        )

        out_exprs = []

        for col in tar_cols:
            calc_col = f"calculated_{col}"
            diff_col = f"diff_{col}"
            match_col = f"match_{col}"
            calc_expr = None

            if ("volume-loaded" in col):
                allowed_volumes = [2, 8, 0]
                print(f"\n    Searching for values of {allowed_volumes}")
                # Create a boolean validation column
                valid_volume_expr = (
                    pl.col(loaded_vol_col)
                    .round(3)
                    .is_in(allowed_volumes)
                #    .alias("is_valid_volume_loaded")
                )

                # Add it to the list of expressions to be executed at the end
                calc_expr = (valid_volume_expr)
                calc_expr = (
                    pl.when(pl.col(loaded_vol_col).round(3).is_in(allowed_volumes))
                    .then(pl.col(loaded_vol_col))
                    .otherwise(pl.lit(None))
                )
            elif "total-yield" in col and dilution_col:
                calc_expr = (( pl.col(quant_col) / pl.col(loaded_vol_col) ) * pl.col(dilution_col))

            elif "total-activity" in col and dilution_col:
                calc_expr = ( pl.col(frac_activity_col) * pl.col(dilution_col))

            elif "total-protein" in col and dilution_col:
                calc_expr = ( pl.col(conc_col) * pl.col(dilution_col))


            elif "protein-%-yield" in col and dilution_col:
                frac_col = pl.col(frac_col)

                # expecting WT or MUT
                strain_group = frac_col.str.split("_").list.last()

                denom_expr = (
                    pl.col(total_yield_col)
                    .filter(frac_col.str.contains("(?i)Crude_lysate")) # (?i) makes it case-insensitive
                    .first()
                    .over(strain_group)
                )
                tot_y_expr = pl.col(total_yield_col).cast(pl.Float64, strict=False)
                raw_calc = (tot_y_expr.clip(lower_bound=0) /denom_expr) * 100
                calc_expr = (
                        pl.when(raw_calc.is_infinite() | raw_calc.is_nan())
                        .then(None)
                        .otherwise(raw_calc)
                        )
            elif "activity-%-yield" in col and dilution_col:
                frac_col = pl.col(frac_col)

                # expecting WT or MUT
                strain_group = frac_col.str.split("_").list.last()

                denom_expr = (
                    pl.col(total_activity_col)
                    .filter(frac_col.str.contains("(?i)Crude_lysate")) # (?i) makes it case-insensitive
                    .first()
                    .over(strain_group)
                )
                tot_a_expr = pl.col(total_activity_col).cast(pl.Float64, strict=False)
                raw_calc = (tot_a_expr.clip(lower_bound=0) / denom_expr) * 100

                calc_expr = (
                    pl.when(raw_calc.is_infinite() | raw_calc.is_nan())
                    .then(None)
                    .otherwise(raw_calc)
                )
            elif "purification" in col and dilution_col:
                frac_col = pl.col(frac_col)

                # expecting WT or MUT
                strain_group = frac_col.str.split("_").list.last()

                denom_expr = (
                    pl.col(specific_activity_col)
                    .filter(frac_col.str.contains("(?i)Crude_lysate")) # (?i) makes it case-insensitive
                    .first()
                    .over(strain_group)
                )
                spec_act_expr = pl.col(specific_activity_col).cast(pl.Float64, strict=False)
                raw_calc = spec_act_expr.clip(lower_bound=0) / denom_expr
                calc_expr = (
                        pl.when(raw_calc.is_infinite() | raw_calc.is_nan())
                        .then(None)
                        .otherwise(raw_calc)
                        )


            if calc_expr is None:
                continue

            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - pl.col(col)).alias(diff_col),
                ((calc_expr - pl.col(col)).abs() < 1e-5).alias(match_col),
            ])

        return df.with_columns(out_exprs)

    if operation == "graph":
        if dilution_col not in df.columns:
            print(f"⚠️  Dilution column '{dilution_col}' not found!")
            return df
        print(f"Dilution column: {dilution_col}")

        # Accumulate Polars expressions to add to the DataFrame at the end
        calc_exprs = []
        compare_exprs = []

        # Assuming 'related_terms' is a list of the same length as 'source_cols'
        # Adjust the zip if related_term is extracted differently in your wider code
        for source_col in source_cols:
            plot_df = (
                df.with_columns(
                    pl.col(dilution_col).cast(pl.Float64, strict=False)
                )
                .select([
                    pl.col(dilution_col),
                    pl.col(source_col)
                ])
                .drop_nulls()
            )

            if plot_df.height == 0:
                print(f"⚠️  No valid data points for graph fit on {source_col}")
                continue

            x = plot_df[dilution_col].to_numpy()
            y = plot_df[source_col].to_numpy()

            # --- LINEAR FIT ---
            if any("slope" in t for t in target_cols) and any("intercept" in t for t in target_cols):
                if set_y_int_to_0:
                    # Zero-intercept least squares
                    slope = (x @ y) / (x @ x) if not np.all(x == 0) else np.nan
                    intercept = 0.0
                else:
                    # Free linear fit
                    slope, intercept = np.polyfit(x, y, 1)

                # Define the suffix based on whether related_term is provided
                matches = [word for word in source_col.split('_') if word in related_terms]
                related_term = matches[0] if matches else None
                suffix = f"_{related_term}" if related_term else ""

                # Define calculated column expressions
                calc_exprs.extend([
                    pl.lit(slope).alias(f"calculated_graph_slope{suffix}"),
                    pl.lit(intercept).alias(f"calculated_graph_y-intercept{suffix}"),
                ])

                # Slope Match/Diff
                target_slope = f"graph_slope{suffix}"
                if target_slope in df.columns:
                    compare_exprs.extend([
                        is_close(
                            pl.col(target_slope), 
                            pl.lit(slope) # use literal to avoid ColumnNotFoundError
                        ).alias(f"match_graph_slope{suffix}"),
                        (
                            pl.col(target_slope) - pl.lit(slope)
                        ).abs().alias(f"diff_graph_slope{suffix}")
                    ])

                # Intercept Match/Diff (matching the requested 'graph_y-int_')
                target_int = f"graph_y-int{suffix}"
                if target_int in df.columns:
                    compare_exprs.extend([
                        is_close(
                            pl.col(target_int), 
                            pl.lit(intercept)
                        ).alias(f"match_graph_intercept{suffix}"),
                        (
                            pl.col(target_int) - pl.lit(intercept)
                        ).abs().alias(f"diff_graph_intercept{suffix}")
                    ])

            # --- QUADRATIC FIT ---
            if any("coefficient" in t for t in target_cols): 
                # Free linear fit
                nonzero_a, nonzero_b, nonzero_c = np.polyfit(x, y, 2)

                no_constant = np.column_stack([x**2, x])   # no constant term
                (a, b), *_ = np.linalg.lstsq(no_constant, y, rcond=None)
                c = 0.0
                
                # Use the same suffix logic here
                matches = [word for word in source_col.split('_') if word in related_terms]
                related_term = matches[0] if matches else None
                suffix = f"_{related_term}" if related_term else ""

                calc_exprs.extend([
                    pl.lit(a).alias(f"calculated_graph_a_coeff{suffix}"),
                    pl.lit(b).alias(f"calculated_graph_b_coeff{suffix}"),
                    pl.lit(c).alias(f"calculated_graph_c_coeff{suffix}"),
                    pl.lit(nonzero_a).alias(f"calculated_graph_a_zero_coeff{suffix}"),
                    pl.lit(nonzero_b).alias(f"calculated_graph_b_zero_coeff{suffix}"),
                    pl.lit(nonzero_c).alias(f"calculated_graph_c_zero_coeff{suffix}"),
                ])

        # Apply all generated columns to the dataframe simultaneously 
        if calc_exprs:
            df = df.with_columns(calc_exprs)

        # Apply the comparisons in a second pass so calculated literals are correctly framed
        if compare_exprs:
            df = df.with_columns(compare_exprs)

    if operation == "validate":
        valid_mask = (
            pl.any_horizontal(
               cs.starts_with("valid")
                  .cast(pl.Utf8)
                  .str.to_lowercase()
                  .is_in(["valid", "yes", "y", "true", "1"])
            )
        )

        standard_col = next(c for c in source_cols if "standard" in c)
        unknown_col = next(c for c in source_cols if "unknown" in c)
        corrected_unknown = f"corrected_{unknown_col}"
        corrected_standard = f"corrected_{standard_col}"

        df_sorted = df.sort(dilution_col)
        r, ok = common_multiplier(df_sorted, dilution_col)
        if not ok:
            print("⚠️ Dilution factor check failed:")
            print(f"    - Ratio of {r}")
        else:
            print(f"Dilution factor of {r}")

        df = df.with_columns([
            pl.when(pl.col(dilution_col) != 1)
            .then(pl.col(unknown_col) / r)
            .otherwise(pl.col(unknown_col))
                .alias(corrected_unknown),
            #(pl.col(standard_col) * pl.col(dilution_col))
            #    .alias(corrected_standard),
        ])

        # Use a robust reference (median)
        ref = df.select(pl.col(corrected_unknown).median()).item()
        
        # Allow tolerance (e.g. ±20%)
        TOL = 0.20
        
        df = df.with_columns(
            (
                (pl.col(corrected_unknown) / ref)
                .is_between(1 - TOL, 1 + TOL)
            ).alias("valid_dilution_ratio")
        )
        
        # ⚠️ Warning only
        bad_ratio = df.filter(~pl.col("valid_dilution_ratio") & valid_mask)
        
        if bad_ratio.height > 0:
            print("⚠️ Dilution ratio check failed for some rows:")
            print(
                bad_ratio.select(
                    unknown_col,
                    dilution_col,
                    corrected_unknown
                )
            )

        std_min = (
            df
            .select(
                pl.col(standard_col).min(),
            )
            .item()
        )
        std_max = (
            df
            .select(
                pl.col(standard_col).max(),
            )
            .item()
        )
        print(f"The minimum corrected student value is {std_min} and the maximum of {std_max}")
        df = df.with_columns(
            pl.col(unknown_col)
            .is_between(std_min, std_max)
            .alias("valid_standard_range")
        )
        
        # ⚠️ Warning only
        out_of_bounds = df.filter(~pl.col("valid_standard_range") & valid_mask)
        
        if out_of_bounds.height > 0:
            print(
                f"⚠️ Unknown values outside standard range "
                f"[{std_min:.3g}, {std_max:.3g}]:"
            )
            print(out_of_bounds.select(unknown_col, standard_col))
       
        df = df.with_columns(
            pl.col(unknown_col)
            .is_between(std_min, std_max)
            .alias("valid_standard_range")
        )
        
        # ⚠️ Warning only
        out_of_bounds = df.filter(~pl.col("valid_standard_range") & valid_mask)
        
        if out_of_bounds.height > 0:
            print(
                f"⚠️ Unknown values outside standard range "
                f"[{std_min:.3g}, {std_max:.3g}]:"
            )
            print(out_of_bounds.select(unknown_col, standard_col))
        df = df.with_columns(
                pl.col(unknown_col).alias(f"valid_{unknown_col}")
                )
        return df

    if operation == "concentration_series":

        corrected_col = next((c for c in source_cols if "unknown" in c or
                              "dabs-per-minute" in c or
                              "mutant" in c), None)
        enzyme_col = next((c for c in source_cols if "enzyme_abs/min" in c), None)
        valid_col = next((c for c in source_cols if "valid" in c), None)

        cast_exprs = []

        if dilution_col:
            cast_exprs.append(pl.col(dilution_col).cast(pl.Float64, strict=False))
        if corrected_col:
            cast_exprs.append(pl.col(corrected_col).cast(pl.Float64, strict=False))
        if enzyme_col:
            cast_exprs.append(pl.col(enzyme_col).cast(pl.Float64, strict=False))

        df = df.with_columns(cast_exprs)

        if valid_col:
            valid_mask = (
                pl.any_horizontal(
                   cs.starts_with("valid_data")
                      .cast(pl.Utf8)
                      .str.strip_chars()
                      .str.to_lowercase()
                      .is_in(["valid", "yes", "y", "true", "1"])
                )
            )
        else:
            valid_mask = pl.lit(True)

        slope = None
        intercept = None
        a = None
        b = None
        c = None

        if any("slope" in c for c in df.columns):
            slope = df.select(pl.col("graph_slope").cast(pl.Float64, strict=False).first()).item()
            intercept = df.select(pl.col('graph_y-intercept').cast(pl.Float64, strict=False).first()).item()

        elif any(r"graph*coefficient" in c for c in df.columns):
            a = df.select(pl.col("graph_a_coefficient").cast(pl.Float64, strict=False).first()).item()
            b = df.select(pl.col("graph_b_coefficient").cast(pl.Float64, strict=False).first()).item()
            c = df.select(pl.col("graph_c_coefficient").cast(pl.Float64, strict=False).first()).item()

        elif (
            any("molar-extinction" in c for c in df.columns)
            and any("pka" in c for c in df.columns)
            and any("ph_buffer" in c for c in df.columns)
            ):
            molar_ext = df.select(pl.col("^molar-extinction.*$").cast(pl.Float64, strict=False).first()).item()
            pka = df.select(pl.col("^pka.*$").cast(pl.Float64, strict=False).first()).item()
            ph = df.select(pl.col("ph_buffer").cast(pl.Float64, strict=False).first()).item()
            path = df.select(pl.col('^path_length.*$').cast(pl.Float64, strict=False).first()).item()

        conc_cols = (
            df.select(
                cs.starts_with(target_group)
                & ~cs.matches("units|equation|calculation|calcultion")
            )
            .columns
        )

        out_exprs = []

        for col in conc_cols:
            calc_col = f"calculated_{col}"
            diff_col = f"diff_{col}"
            match_col = f"match_{col}"
            calc_expr = None

            if (("dilute" in col) and (slope or a)):
                if slope:
                    calc_expr = pl.col(corrected_col) / slope
                elif a is not None and b is not None:
                    y = pl.col(corrected_col)

                    A = pl.lit(a)
                    B = pl.lit(b)
                    C = pl.lit(c) - y

                    disc = B**2 - 4 * A * C

                    calc_expr = (
                        pl.when(disc < 0)
                          .then(None)
                          .otherwise((-B + disc.sqrt()) / (2 * A))
                    )
                    #  NOTE: I picked "+" for the "±" term of the quadratic formula since the "+" solutions correspond to the x-intercept values where the parabola is increasing, matching the positve slope of our BSA standard curve.

            elif "stock" in col and dilution_col:
                calc_expr = pl.col("concentration_dilute_(ug/ul)") * pl.col(dilution_col)

            elif "final_average" in col:
                calc_expr = pl.when(valid_mask).then(
                    pl.col("concentration_stock_(ug/ul)")
                ).mean()

            elif "pnp-per-minute" in col and slope:
                if enzyme_col:
                    calc_expr = ( pl.col(enzyme_col) - intercept ) / slope
                else:
                    calc_expr = ( pl.col(corrected_col) - intercept ) / slope

            elif "standard_pnp" in col and dilution_col:
                unit_expr = pl.col("concentration_pnp_untis?").drop_nulls().first()

                numerator_expr = (
                    pl.when(unit_expr.is_in(["mm", "mM"]))
                    .then(0.5)
                    .when(unit_expr.is_in([
                         "um", "uM",   # Standard 'u'
                         "µm", "µM",   # Micro sign (Alt+0181 / Option+M)
                         "μm", "μM"    # Greek letter mu
                     ]))
                    .then(500.0)
                    .otherwise(pl.lit(None))
                )

                calc_expr = (
                    pl.when(pl.col(dilution_col) == 0)
                    .then(0.0)
                    .otherwise(numerator_expr / pl.col(dilution_col))
                )

            elif "pnpo-" in col and molar_ext and pka:
                calc_expr = (pl.col(corrected_col) / (molar_ext * path))

            elif "pnpoh" in col:
                print(f"concentration_pnop- / 10 ** {ph} - {pka}")
                calc_expr = ( pl.col("concentration_pnpo-") / ( 10 ** (ph - pka) ))

            elif "pnp" in col and "per-minute" not in col and not dilution_col:
                # Safety check: only do this addition if both columns exist
                if "concentration_pnpo-" in df.columns and "concentration_pnpoh" in df.columns:
                    calc_expr = (pl.col("concentration_pnpo-") + pl.col("concentration_pnpoh"))

            if calc_expr is None:
                continue

            safe_col = pl.col(col).cast(pl.Float64, strict=False)   
            out_exprs.extend([
                calc_expr.alias(calc_col),
                (calc_expr - safe_col).alias(diff_col),
                ((calc_expr - safe_col).abs() < 1e-5).alias(match_col),
            ])
    
        return df.with_columns(out_exprs)        # For each target column, find corresponding source and apply blank correction
 
    if operation == 'blank_correction':
        if dilution_col not in df.columns:
            print(f"⚠️  Dilution column '{dilution_col}' not found!")
            return df
        print(f"Dilution column: {dilution_col}")

        # Add strict=False to cast to ignore student notes?
        neg_checks = df.select((pl.col(target_cols).cast(pl.Float64) < 0).any()).to_dicts()[0]
        bad_cols = [col for col, has_neg in neg_checks.items() if has_neg]
        if bad_cols:
            print(f"⚠️ Negative values detected in: {bad_cols}")

        df = df.with_columns(
            pl.col(dilution_col).cast(pl.Float64, strict=False)
        )
        
        dil = pl.col(dilution_col)
        blank_expr = (
            (dil.cast(pl.Float64, strict=False) == 0)
            |
            dil.is_null()
        )
        
        blank_rows = df.filter(blank_expr)
        n_blank = blank_rows.height
        
        if n_blank == 0:
            print("⚠️  No blank row found (dilution = 0, NULL, or blank text)")
            return df
        elif n_blank > 1:
            print("⚠️  Multiple blank rows found, using first one")
        
        blank_row = blank_rows.head(1)
        
        for target_col in target_cols:
            target_range = get_column_range_simple(target_col, target_group)
            #print("target",target_range)
            if target_range:
                t_middle, t_start, t_end = target_range
                
                matching_source = None
                no_enzyme_source = None
                standard_data_source = None
                
                # Scan all source columns to find matching standard, main source, and no-enzyme control
                for source_col in source_cols:
                    source_range = get_column_range_simple(source_col, source_group)
                    #print("source",source_range)
                    if source_range:
                        s_middle, s_start, s_end = source_range
                        
                        # Find the master standard_data column
                        if s_middle == 'standard_data':
                            standard_data_source = source_col
                            
                        # If the ranges match (e.g., the '1' and '3' match the target's range)
                        if s_start == t_start and s_end == t_end:
                            if s_middle == t_middle:
                                matching_source = source_col
                            if "no-" in s_middle or "no-enzyme" in s_middle:
                                no_enzyme_source = source_col
                #print(matching_source, no_enzyme_source)
                if matching_source:
                    calc_col_name = f'calculated_{target_col}'
                    diff_col_name = f'diff_{target_col}'
                    match_col_name = f'match_{target_col}'
                    
                    if "standard" in target_col.lower():
                        blank_source = standard_data_source if standard_data_source else matching_source
                        
                        blank_value = blank_row.select(
                            pl.col(blank_source).cast(pl.Float64, strict=False)
                        ).item()
                        
                        blank_value = 0.0 if blank_value is None else float(blank_value)
                        
                        print(f"\n  {target_col} <- {matching_source} (scalar) - {blank_value:.6f}")
                        
                        calc_expr = ( 
                            pl.col(matching_source).cast(pl.Float64, strict=False) - blank_value 
                        ).clip(lower_bound=0)
                        
                    elif "mutant" in target_col.lower() and no_enzyme_source:
                        print(f"\n  {target_col} <- {matching_source} - {no_enzyme_source} (full column subtraction)")
                        
                        calc_expr = ( 
                            pl.col(matching_source).cast(pl.Float64, strict=False) - 
                            pl.col(no_enzyme_source).cast(pl.Float64, strict=False) 
                        ).clip(lower_bound=0)
                        
                    else:
                        if no_enzyme_source:
                            calc_expr = (pl.col(matching_source).cast(pl.Float64, strict=False) - 
                                         pl.col(no_enzyme_source).cast(pl.Float64, strict=False)).clip(lower_bound=0)
                        else:
                            blank_source = standard_data_source if standard_data_source else matching_source
                            
                            blank_value = blank_row.select(
                                pl.col(blank_source).cast(pl.Float64, strict=False)
                            ).item()
                            
                            blank_value = 0.0 if blank_value is None else float(blank_value)
                            
                            print(f"\n  {target_col} <- {matching_source} (scalar) - {blank_value:.6f}")
                            
                            calc_expr = ( 
                                pl.col(matching_source).cast(pl.Float64, strict=False) - blank_value 
                            ).clip(lower_bound=0)
 
#                            calc_expr = (pl.col(matching_source).cast(pl.Float64, strict=False) - 0.0).clip(lower_bound=0)

                    df = df.with_columns([
                        calc_expr.alias(calc_col_name)
                    ])

                    t_expr = pl.col(target_col).cast(pl.Float64, strict=False)
                    df = df.with_columns([
                        (t_expr - pl.col(calc_col_name)).abs().alias(diff_col_name),
                        (t_expr - pl.col(calc_col_name)).abs().lt(1e-10).alias(match_col_name)
                    ])
        return df
    
    if operation == 'enzyme_units':

        # pnp renamed to standard_pnp currently earlier in script
        conc_col = (
            next((c for c in source_cols if "pnp-per-minute" in c), None) or 
            next((c for c in source_cols if "standard_pnp" in c), None)
        )
        volume_col = next((c for c in df.columns if "volume_assay" in c), None)

        cast_exprs = [
            pl.col(conc_col).cast(pl.Float64, strict=False)
        ]

        if volume_col:
            cast_exprs.append(pl.col(volume_col).cast(pl.Float64, strict=False))

        df = df.with_columns(cast_exprs)

        for target_col in target_cols:
            if re.search(r"equation|calculation", target_col):
                continue

            calc_col= f'calculated_{target_col}'
            diff_col= f'diff_{target_col}'
            match_col= f'match_{target_col}'
            
            print(f"\n  {target_col} <- {conc_col} * (1000 or 100000) * {volume_col} (full column multplicaiton)")

            out_exprs = []
            multipliers = [1000, 1000000]
            for i in multipliers:
                calc_expr = ( pl.col(conc_col) * i * pl.col(volume_col).first() ).clip(lower_bound=0)

                out_exprs.extend([
                    calc_expr.alias(f"{calc_col}_{i}"),
                    (calc_expr - pl.col(target_col)).alias(f"{diff_col}_{i}"),
                    ((calc_expr - pl.col(target_col)).abs() < 1e-5).alias(f"{match_col}_{i}"),
                ])
                
        return df.with_columns(out_exprs)        # For each target column, find corresponding source and apply blank correction

    if operation == 'mass':

        volume_col = next((c for c in source_cols if "enzyme-in-assay" in c), None)
        conc_col = next((c for c in df.columns if "concentration_enzyme_stock" in c), None)

        cast_exprs = []

        if dilution_col:
            cast_exprs.append(pl.col(dilution_col).cast(pl.Float64, strict=False))
        if volume_col:
            cast_exprs.append(pl.col(volume_col).cast(pl.Float64, strict=False))
        if conc_col:
            cast_exprs.append(pl.col(conc_col).cast(pl.Float64, strict=False))

        df = df.with_columns(cast_exprs)

        for target_col in target_cols:
            if re.search(r"units|equation|calculation", target_col):
                continue

            calc_col= f'calculated_{target_col}'
            diff_col= f'diff_{target_col}'
            match_col= f'match_{target_col}'
            
            print(f"\n  {target_col} <- {conc_col} * {volume_col} (full column multplicaiton)")

            out_exprs = []
            calc_expr = ( 
                        pl.when(pl.col(dilution_col).is_null() | (pl.col(dilution_col) == 0))
                          .then(0)
                          .otherwise( ((pl.col(conc_col).first() / dilution_col) * pl.col(volume_col).first() ).clip(lower_bound=0))
                    )

            out_exprs.extend([
                    calc_expr.alias(f"{calc_col}"),
                    (calc_expr - pl.col(target_col)).alias(f"{diff_col}"),
                    ((calc_expr - pl.col(target_col)).abs() < 1e-5).alias(f"{match_col}"),
                ])
                
        return df.with_columns(out_exprs)        # For each target column, find corresponding source and apply blank correction

    # Handle all other operations (mean, sum, product, division)
    for target_col in target_cols:
        # Extract the range from target column
        col_range = get_column_range_simple(target_col, target_group)
        if col_range:
            middle, start_idx, end_idx = col_range
            target_prefix = target_col.split('_')[0].lower()
            # Build list of source columns in this range
            cols_to_process = []
            for source_col in source_cols:
                if source_col == target_col:
                    continue
                source_range = get_column_range_simple(source_col, source_group)

                if source_range:
                    src_middle, src_start_idx, src_end_idx = source_range
                    if start_idx <= src_start_idx <= end_idx:
                        cols_to_process.append(source_col)
                else:
                    # Handle columns without range (e.g., "raw_1", "raw_2")
                    #match = re.search(rf'{re.escape(source_group)}_{middle}_(\d+)', source_col)
                    #if match:
                    #    src_idx = int(match.group(1))
                    #    if start_idx <= src_idx <= end_idx:
                    #        cols_to_process.append(source_col)
                    match = re.search(r'_(\d+)\s*$', source_col)
                    source_prefix = source_col.split('_')[0].lower()

                    if match and source_prefix == target_prefix:
                        src_idx = int(match.group(1))
                        if start_idx <= src_idx <= end_idx:
                            cols_to_process.append(source_col)
                            continue 

                    # Original fallback (kept safe for your older datasets)
                    fallback_match = re.search(rf'{re.escape(source_group)}_{middle}_(\d+)', source_col)
                    if fallback_match:
                        src_idx = int(fallback_match.group(1))
                        if start_idx <= src_idx <= end_idx:
                            cols_to_process.append(source_col)

            if cols_to_process:
                calc_col_name = f'calculated_{target_col}'
                diff_col_name = f'diff_{target_col}'
                match_col_name = f'match_{target_col}'

                print(f"\n  {target_col} <- {cols_to_process} (operation: {operation})")
                df = df.with_columns([
                    pl.col(c).cast(pl.Float64, strict=False) for c in cols_to_process
                ])
                # check negatives in source columns for this target
                numeric_cols = [
                    c for c in cols_to_process
                    if df.schema.get(c) and df.schema[c].is_numeric()
                ]

                if numeric_cols:
                    negs = (
                        df.select([
                            (pl.col(c) < 0).any().alias(c)
                            for c in numeric_cols
                        ])
                        .row(0)
                    )

                    bad = [c for c, has_neg in zip(numeric_cols, negs) if has_neg]

                    if bad:
                        print(
                            f"⚠️  Negative values detected for calculation of '{target_col}':\n"
                            + "\n".join(f"    - {c}" for c in bad)
                        )

                # Calculate based on operation
                if operation == 'mean':
                    mean_exprs = [
                        pl.col(c).clip(lower_bound=0) if c in numeric_cols else pl.col(c) 
                        for c in cols_to_process
                    ]
                    df = df.with_columns([
                        pl.concat_list(mean_exprs).list.mean().alias(calc_col_name)
                    ])
                   # df = df.with_columns([
                   #     pl.concat_list(cols_to_process)
                   #       .list.mean()
                   #       .alias(calc_col_name)
                   # ])
                elif operation == 'sum':
                    df = df.with_columns([
                        pl.concat_list(cols_to_process)
                          .list.sum()
                          .alias(calc_col_name)
                    ])
                elif operation == 'product':
                    df = df.with_columns([
                        pl.concat_list(cols_to_process).list.eval(pl.element().cumfold(lambda x, y: x * y, 1)).alias(calc_col_name)
                    ])
                elif operation == 'division':
                    denom_col = pl.col(cols_to_process[0]).cast(pl.Int64, strict=False)
                    if numerator:
                        numerator_series = df.select(numerator).cast(pl.Float64, strict=False).drop_nulls()
                    else:
                        numerator_series = df.filter(denom_col == 1).select(target_col)

                    unique_numerators = numerator_series.to_series().unique()
                    n_unique = len(unique_numerators)

                    if n_unique == 0:
                        print(f"⚠️  No numerator found in {target_col} where {cols_to_process[0]} == 1")
                        continue
                    elif n_unique > 1:
                        # There are multiple DIFFERENT values
                        print(f"⚠️  Conflicting numerators found in {target_col} where {cols_to_process[0]} == 1")
                        print(f"    Values found: {unique_numerators.to_list()}")
                        continue
                    
                    # If we pass the checks, n_unique is exactly 1.
                    # We can safely use .item() and cast to float.
                    numerator_value = float(unique_numerators.item())

                    print(f"\n  {target_col} <- {numerator} / {cols_to_process}")
                    df = df.with_columns([
                        pl.when(denom_col.is_null() | (denom_col == 0))
                          .then(0)
                          .otherwise(numerator_value / denom_col)
                          .alias(calc_col_name)
                    ])
                else:
                    print(f"⚠️  Unknown operation '{operation}'")
                    continue
                
#                # Add comparison columns
#                df = df.with_columns([
#                    (pl.col(target_col) - pl.col(calc_col_name)).abs().alias(diff_col_name),
#                    (pl.col(target_col) - pl.col(calc_col_name)).abs().lt(1e-10).alias(match_col_name)
#                ])
                target_expr = pl.col(target_col).cast(pl.Float64, strict=False)
                calc_expr = pl.col(calc_col_name).cast(pl.Float64, strict=False)

                # Add comparison columns
                df = df.with_columns([
                    (target_expr - calc_expr).abs().alias(diff_col_name),
                    (target_expr - calc_expr).abs().lt(1e-10).alias(match_col_name)
                ])
    return df



def get_column_range_simple(column_name: str, prefix: str = None) -> Optional[Union[Tuple[int, int], Tuple[str, int, int]]]:
    """
    Extract the numeric range from a column name, regardless of where the digits are embedded.
    """
    match = re.search(r'(\d+)-(\d+)', column_name)

    if not match:
        return None

    start = int(match.group(1))
    end = int(match.group(2))

    if prefix is None:
        return start, end

    leftover_text = column_name.replace(prefix, "").replace(match.group(0), "")

    middle = leftover_text.strip("_")

    return middle, start, end


def report_mismatches(df: pl.DataFrame, target_group: str, column_groups: dict):
    print(f"\n{'='*80}\nRESULTS: {target_group}\n{'='*80}")
    
    # Extract columns, flattening the list if it's a nested dictionary from previous steps
    target_cols = column_groups.get(target_group, [])
    print(target_cols)
    if isinstance(target_cols, dict):
        target_cols = [col for sublist in target_cols.values() for col in sublist]

    for target_col in target_cols:
        calc_col, diff_col = f'calculated_{target_col}', f'diff_{target_col}'

        if calc_col not in df.columns or target_col not in df.columns:
            continue

        # 1. Cast to float
        t_col = pl.col(target_col).cast(pl.Float64, strict=False)
        c_col = pl.col(calc_col).cast(pl.Float64, strict=False)

        # 2. Define Math (filling nulls with 0.0 temporarily to prevent math errors)
        math_diff = (t_col.fill_null(0.0) - c_col.fill_null(0.0)).abs()
        tolerance = 1e-3 + 1e-2 * t_col.fill_null(0.0).abs() # ATOL + RTOL * abs(target)

        # 3. Filter directly for mismatches (Target is NOT blank AND exceeds tolerance)
        mismatches = df.filter(t_col.is_not_null() & (math_diff > tolerance))

        # 4. Report
        if mismatches.height > 0:
            print(f"\n⚠️  {target_col}: {mismatches.height} LARGE mismatches")
            cols_to_show = [c for c in [target_col, calc_col, diff_col] if c in df.columns]
            print(mismatches.select(cols_to_show))
        else:
            print(f"\n✓  {target_col}: All values within tolerance")

    print("\nRESULTS complete\n")

def report_mismatches(df: pl.DataFrame, target_group: str, column_groups: dict):
    print(f"\n{'='*80}")
    print(f"RESULTS: {target_group}")
    print(f"{'='*80}")

    target_cols = column_groups.get(target_group, [])
    print(target_group, target_cols)
    RTOL = 1e-2
    ATOL = 1e-3

    targets = []
    if isinstance(target_cols, dict):
        for target_col in target_cols.values():
            targets.extend(target_col)
    else:
        targets = target_cols

    for target_col in targets:
        calc_col = f'calculated_{target_col}'
        diff_col = f'diff_{target_col}'

        if calc_col not in df.columns or target_col not in df.columns:
            continue
        t_expr = pl.col(target_col).cast(pl.Float64, strict=False)
        c_expr = pl.col(calc_col).cast(pl.Float64, strict=False)

        t_compare = t_expr.fill_null(0.0)
        c_compare = c_expr.fill_null(0.0)

        math_match = (t_compare - c_compare).abs() <= (ATOL + RTOL * t_compare.abs())
        student_blank = t_expr.is_null()

        close_expr = (math_match | student_blank).fill_null(False)
        mismatches = df.filter(~close_expr)

        if mismatches.height > 0:
            print(f"\n⚠️  {target_col}: {mismatches.height} LARGE mismatches")
            cols_to_show = [c for c in [target_col, calc_col, diff_col] if c in df.columns]
            print(mismatches.select(cols_to_show))
        else:
            print(f"\n✓  {target_col}: All values within tolerance")

    print("\nRESULTS complete\n")

def get_verification_columns(df, prefix='average_data_', source_prefix=None, include_source=True):
    """
    Get only the columns related to a specific verification.
    
    Returns:
        List of column names
    """
    cols = []
    
    # Add source columns if requested
    if include_source and source_prefix:
        cols.extend([col for col in df.columns if col.startswith(source_prefix)])
    
    # Add target columns
    cols.extend([col for col in df.columns if col.startswith(prefix)])
    
    # Add calculated columns
    cols.extend([col for col in df.columns if col.startswith(f'calculated_{prefix}')])
    
    # Add diff columns
    #cols.extend([col for col in df.columns if col.startswith(f'diff_{prefix}')])
    
    # Add match columns
    #cols.extend([col for col in df.columns if col.startswith(f'match_{prefix}')])
    
    # Remove duplicates while preserving order
    unique_cols = list(dict.fromkeys(cols))
    
    # Define the substrings we want to exclude
    exclude_terms = ['units', 'untis', 'equation', 'calculation']
    
    # Filter out any column that contains the excluded terms (case-insensitive)
    return [
        c for c in unique_cols 
        if not any(term in c.lower() for term in exclude_terms)
    ]

def process_operation(config, target_group, df, column_groups, excel_file):
    """Executes the verification, formatting, and printing for a given configuration."""
    try:
        kwargs = {
            'df': df,
            'source_group': config['source_group'],
            'target_group': config['target_group'],
            'column_groups': column_groups,
            'numerator': config.get('numerator'),
            'dilution_col': config.get('dilution_col'),
            'set_y_int_to_0': config.get('set_y_int_to_0'),
            'operation': config['operation'],
        }
        
        #if 'dilution_col' in config:
        #    kwargs['dilution_col'] = config['dilution_col']

        df = verify_calculated_columns_generic(**kwargs)
        report_mismatches(df, config['target_group'], column_groups)
        relevant_cols = get_verification_columns(df, f"{target_group}_{config['target_group']}") or get_verification_columns(df, target_group)

        with pl.Config() as cfg:
            if config['operation'] in ('concentration','graph'):
                cfg.set_tbl_rows(-1)
                cfg.set_tbl_cols(-1)
                if config['operation'] == 'graph':
                    cfg.set_tbl_width_chars(160)
                    cfg.set_fmt_str_lengths(160)
                    cfg.set_fmt_table_cell_list_len(-1)
            
            print(df.select(relevant_cols))
            
    except Exception as e:
        logging.error(f"\n{excel_file} | {config['error_msg']}: {e}", exc_info=True)
        
    return df

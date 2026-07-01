from __future__ import annotations


COLOR = {
    "name": "Color",
    "file_match": None,
    "runtime_params": [
        {"key": "stock_chosen", "label": "Stock chosen", "default": "",
         "kind": "text", "group": "Stock"},
        {"key": "stock_concentration", "label": "Stock concentration (%)",
         "default": "", "kind": "float", "group": "Stock"},
        {"key": "yint_1_3", "label": "Set y-intercept to 0 (1-3)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
        {"key": "yint_4_6", "label": "Set y-intercept to 0 (4-6)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
    ],
    "build_operation_configs": lambda p: {
        "stock": {
            "source_group": ["stock"],
            "target_group": ["stock"],
            "operation": ["verify_stock"],
            "error_msg": "stock verification failed",
        },
        "concentration": {
            "source_group": ["dilution-factor"],
            "target_group": ["concentration"],
            "operation": ["division"],
            "numerator": "stock_color_concentration",
            "error_msg": "concentration verification failed",
        },
        "average": {
            "source_group": ["raw"],
            "target_group": ["average"],
            "operation": ["mean"],
            "error_msg": "average verification failed",
        },
        "corrected": {
            "source_group": ["average"],
            "target_group": ["corrected"],
            "operation": ["blank_correction"],
            "dilution_col": "color_concentration_1-3",
            "error_msg": "corrected verification failed",
        },
        "graph": {
            "source_group": ["corrected"],
            "target_group": ["graph"],
            "operation": ["graph"],
            "dilution_col": "color_concentration_1-3",
            "set_y_int_to_0": p["yint_1_3"],
            "error_msg": "Graph verification failed",
        },
    },
    "build_stock_configs": lambda p: {
        "chosen": p["stock_chosen"],
        p["stock_chosen"]: p["stock_concentration"],
    },
    "build_dilution_configs": lambda p: set(),
    "build_pka_configs": lambda p: {},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {},
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {},
    "build_multiplier_configs": lambda p: {},
}


BUFFER = {
    "name": "Buffer",
    "file_match": None,
    "runtime_params": [
        {"key": "stock_concentration", "label": "pNP stock (mM)",
         "default": "", "kind": "float", "group": "Stock"},
        {"key": "dilution_factors", "label": "Dilution factor",
         "default": "", "kind": "int_list", "group": "Dilution"},
        {"key": "yint_naoh", "label": "Set y-intercept to 0 (NaOH)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
        {"key": "yint_acetate", "label": "Set y-intercept to 0 (Acetate)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
        {"key": "yint_phosphate", "label": "Set y-intercept to 0 (Phosphate)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
        {"key": "yint_tris", "label": "Set y-intercept to 0 (Tris)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
    ],
    "build_operation_configs": lambda p: {
        "stock-concentration": {
            "source_group": ["stock-concentration"],
            "target_group": ["stock-concentration"],
            "operation": ["verify_stock"],
            "error_msg": "stock verification failed",
        },
        "dilution": {
            "source_group": ["dilution"],
            "target_group": ["dilution"],
            "operation": ["verify_dilution_factor"],
            "error_msg": "dilution verification failed",
        },
        "concentration": {
            "source_group": ["stock-concentration"],
            "target_group": ["diluted-concentration"],
            "operation": ["verify_working"],
            "dilution_col": "pnp_dilution_factor",
            "error_msg": "Working stock verification failed",
        },
        "average": {
            "source_group": ["raw"],
            "target_group": ["average"],
            "operation": ["mean"],
            "error_msg": "average verification failed",
        },
        "corrected": {
            "source_group": ["average"],
            "target_group": ["corrected"],
            "operation": ["blank_correction"],
            "dilution_col": "pnp_diluted-concentration",
            "error_msg": "corrected verification failed",
        },
        "graph": {
            "source_group": ["corrected"],
            "target_group": ["graph"],
            "operation": ["graph"],
            "dilution_col": "pnp_diluted-concentration",
            "set_y_int_to_0": p["yint_naoh"],
            "error_msg": "Graph verification failed",
        },
        "hh": {
            "source_group": ["graph"],
            "target_group": ["hh"],
            "operation": ["verify_hh_ph"],
            "dilution_col": "graph_slope_naoh",
            "error_msg": "Henderson-Hasselbalch verification failed",
        },
    },
    "build_stock_configs": lambda p: {p["stock_concentration"]},
    "build_dilution_configs": lambda p: set(p["dilution_factors"]),
    "build_pka_configs": lambda p: {"pnp": 7.15},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {},
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {},
    "build_multiplier_configs": lambda p: {},
}


A280 = {
    "name": "A280",
    "file_match": ["a280"],
    "runtime_params": [
        {"key": "yint", "label": "Set y-intercept to 0",
         "default": True, "kind": "bool_yint", "group": "Graph"},
        {"key": "dilution_factors", "label": "Dilution factor",
         "default": "", "kind": "int_list", "group": "Unknown"},
    ],
    "build_operation_configs": lambda p: {
        "standard": {
            "source_group": ["standard", "raw", "average"],
            "target_group": ["standard", "average", "corrected"],
            "operation": ["verify_standard", "mean", "blank_correction"],
            "dilution_col": "standard_concentration",
            "error_msg": "standard verification failed",
        },
        "graph": {
            "source_group": ["corrected"],
            "target_group": ["graph"],
            "operation": ["graph"],
            "dilution_col": "standard_concentration",
            "source_target": "standard",
            "set_y_int_to_0": p["yint"],
            "error_msg": "Graph verification failed",
        },
        "unknown": {
            "source_group": ["dilution-factor", "raw", "average", "corrected"],
            "target_group": ["dilution-factor", "average", "corrected", "valid"],
            "operation": ["verify_dilution_factor", "mean",
                          "blank_correction", "verify_a280_validation"],
            "dilution_col": "standard_concentration",
            "validation_ratio": "unknown_dilution-factor",
            "source_target": "standard",
            "error_msg": "Unknown verification failed",
        },
        "concentration": {
            "source_group": ["unknown"],
            "target_group": ["concentration"],
            "operation": ["concentration_series"],
            "dilution_col": "unknown_dilution-factor",
            "source_target": "unknown",
            "error_msg": "concentration verification failed",
        },
    },
    "build_stock_configs": lambda p: set(),
    "build_dilution_configs": lambda p: set(p["dilution_factors"]),
    "build_pka_configs": lambda p: {},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {},
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {},
    "build_multiplier_configs": lambda p: {},
}


BRADFORD = {
    "name": "Bradford",
    "file_match": ["bradford"],
    "runtime_params": [
        {"key": "yint", "label": "Set y-intercept to 0 (constant c)",
         "default": True, "kind": "bool_yint", "group": "Graph"},
    ],
    "build_operation_configs": lambda p: {
        "standard": {
            "source_group": ["raw", "average"],
            "target_group": ["average", "corrected"],
            "operation": ["mean", "blank_correction"],
            "dilution_col": "standard_concentration",
            "error_msg": "standard verification failed",
        },
        "graph": {
            "source_group": ["corrected"],
            "target_group": ["graph"],
            "operation": ["graph"],
            "dilution_col": "standard_concentration",
            "source_target": "standard",
            "set_y_int_to_0": p["yint"],
            "error_msg": "Graph verification failed",
        },
        "unknown": {
            "source_group": ["dilution-factor", "raw", "average", "corrected"],
            "target_group": ["dilution-factor", "average", "corrected", "valid"],
            "operation": ["verify_int_type", "mean",
                          "blank_correction", "verify_bradford_validation"],
            "dilution_col": "standard_concentration",
            "source_target": "standard",
            "error_msg": "Unknown verification failed",
        },
        "concentration": {
            "source_group": ["unknown"],
            "target_group": ["concentration"],
            "operation": ["concentration_series"],
            "dilution_col": "unknown_dilution-factor",
            "source_target": "unknown",
            "error_msg": "concentration verification failed",
        },
    },
    "build_stock_configs": lambda p: set(),
    "build_dilution_configs": lambda p: set(),
    "build_pka_configs": lambda p: {},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {},
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {},
    "build_multiplier_configs": lambda p: {},
}


OPTIMAL_PH = {
    "name": "Optimal pH",
    "file_match": ["optimal"],
    "runtime_params": [
        {"key": "stock_concentration", "label": "pNP stock (mM)",
         "default": "", "kind": "float", "group": "Stock"},
        {"key": "dilution_factors", "label": "Dilution factor",
         "default": "", "kind": "int_list", "group": "Dilution"},
        {"key": "yint", "label": "Set y-intercept to 0",
         "default": True, "kind": "bool_yint", "group": "Graph"},
        {"key": "assay_time", "label": "Assay time (min)",
         "default": "", "kind": "float", "group": "Assay"},
        {"key": "assay_volume", "label": "Assay volume (L)",
         "default": "", "kind": "float", "group": "Assay"},
    ],
    "build_operation_configs": lambda p: {
        "pnp": {
            "source_group": ["stock-concentration", "dilution-factor",
                             "stock-concentration"],
            "target_group": ["stock-concentration", "dilution-factor",
                             "diluted-concentration"],
            "operation": ["verify_stock", "verify_dilution_factor",
                          "verify_working"],
            "dilution_col": "pnp_dilution-factor",
            "error_msg": "pNP verification failed",
        },
        "standard": {
            "source_group": ["average"],
            "target_group": ["corrected"],
            "operation": ["blank_correction"],
            "dilution_col": "pnp_diluted-concentration",
            "error_msg": "standard verification failed",
        },
        "graph": {
            "source_group": ["corrected"],
            "target_group": ["graph"],
            "operation": ["graph"],
            "dilution_col": "pnp_diluted-concentration",
            "source_target": "standard",
            "set_y_int_to_0": p["yint"],
            "error_msg": "Graph verification failed",
        },
        "enzyme": {
            "source_group": ["average", "corrected"],
            "target_group": ["corrected", "normalized"],
            "operation": ["blank_correction", "divide_by_time"],
            "dilution_col": "pnp_diluted-concentration",
            "numerator": "enzyme_corrected_abs_1-3",
            "denominator": p["assay_time"],
            "error_msg": "Enzyme verification failed",
        },
        "concentration": {
            "source_group": ["enzyme"],
            "target_group": ["concentration"],
            "operation": ["concentration_series"],
            "error_msg": "concentration verification failed",
        },
        "assay": {
            "source_group": ["concentration", "initial-velocity"],
            "target_group": ["initial-velocity", "optimal-ph"],
            "operation": ["verify_assay", "verify_greatest"],
            "dilution_col": "assay_ph",
            "error_msg": "Assay verification failed",
        },
    },
    "build_stock_configs": lambda p: {p["stock_concentration"]},
    "build_dilution_configs": lambda p: set(p["dilution_factors"]),
    "build_pka_configs": lambda p: {},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {
        "time": p["assay_time"],
        "volume": p["assay_volume"],
        "magnitude": 1000,
    },
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {},
    "build_multiplier_configs": lambda p: {},
}


SPECIFIC_ACTIVITY = {
    "name": "Specific Activity",
    "file_match": ["specific"],
    "runtime_params": [
        {"key": "stock_concentration", "label": "BglB stock (mg/mL)",
         "default": "", "kind": "float", "group": "Stock"},
        {"key": "volume_in_assay", "label": "Volume in assay (mL)",
         "default": "", "kind": "float", "group": "Stock"},
        {"key": "molar_coefficient",
         "label": "Molar extinction coefficient (/Mcm)",
         "default": "", "kind": "float", "group": "Assay"},
        {"key": "pathlength", "label": "Pathlength (cm)",
         "default": "", "kind": "float", "group": "Assay"},
        {"key": "assay_volume", "label": "Assay volume (L)",
         "default": "", "kind": "float", "group": "Assay"},
        {"key": "pka", "label": "pKa", "default": "",
         "kind": "float", "group": "Henderson-Hasselbalch"},
        {"key": "ph_assay", "label": "Assay pH", "default": "",
         "kind": "float", "group": "Henderson-Hasselbalch"},
    ],
    "build_operation_configs": lambda p: {
        "bglb": {
            "source_group": ["stock-concentration", "dilution-factor",
                             "stock-concentration", "diluted-concentration"],
            "target_group": ["stock-concentration", "dilution-factor",
                             "diluted-concentration", "mass"],
            "operation": ["verify_stock", "verify_dilution_factor",
                          "verify_working", "simple_multiply"],
            "dilution_col": "bglb_dilution-factor",
            "multiplier": p["volume_in_assay"],
            "error_msg": "BGLB standard verification failed",
        },
        "enzyme": {
            "source_group": ["raw", "average"],
            "target_group": ["average", "corrected"],
            "operation": ["mean", "blank_correction"],
            "dilution_col": "bglb_diluted-concentration",
            "error_msg": "Enzyme verification failed",
        },
        "assay": {
            "source_group": ["concentration"],
            "target_group": ["initial-velocity"],
            "operation": ["verify_assay"],
            "error_msg": "Assay verification failed",
        },
        "hh": {
            "source_group": ["hh"],
            "target_group": ["hh"],
            "operation": ["verify_hh"],
            "error_msg": "HH verification failed",
        },
        "concentration": {
            "source_group": ["corrected", "pnpo-", "pnpoh"],
            "target_group": ["pnpo-", "pnpoh", "pnp"],
            "operation": ["concentration_series", "concentration_series",
                          "concentration_series"],
            "source_target": "enzyme",
            "error_msg": "concentration verification failed",
        },
    },
    "build_stock_configs": lambda p: {p["stock_concentration"]},
    "build_dilution_configs": lambda p: set(),
    "build_pka_configs": lambda p: {},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {
        "molar-coefficient": p["molar_coefficient"],
        "pathlength": p["pathlength"],
        "volume": p["assay_volume"],
        "magnitude": 1000000,
    },
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {
        "pka": p["pka"],
        "ph_assay": p["ph_assay"],
    },
    "build_multiplier_configs": lambda p: {
        "volume": p["volume_in_assay"],
    },
}


PURIFICATION = {
    "name": "Purification",
    "file_match": None,
    "runtime_params": [],
    "build_operation_configs": lambda p: {
        "fraction": {
            "source_group": ["specific-activity"],
            "target_group": ["specific-activity"],
            "numerator": "kinetics_total-activity",
            "denominator": "bradford_total_protein",
            "operation": ["divide_columns"],
            "error_msg": "Fraction verification failed",
        },
        "coomassie": {
            "source_group": ["coomassie"],
            "target_group": ["coomassie"],
            "dilution_col": "fraction_volume",
            "operation": ["verify_coomassie_yield"],
            "error_msg": "Coomassie yield verification failed",
        },
        "kinetics": {
            "source_group": ["kinetics"],
            "target_group": ["kinetics"],
            "dilution_col": "fraction_volume",
            "operation": ["verify_kinetics_yield"],
            "error_msg": "Kinetics yield verification failed",
        },
        "bradford": {
            "source_group": ["concentration"],
            "target_group": ["total"],
            "multiplier": "fraction_volume",
            "operation": ["multiply_columns"],
            "error_msg": "Bradford verification failed",
        },
        "fold": {
            "source_group": ["specific-activity"],
            "target_group": ["purification"],
            "source_target": "fraction",
            "operation": ["verify_fold_purification"],
            "error_msg": "Fold purification verification failed",
        },
    },
    "build_stock_configs": lambda p: set(),
    "build_dilution_configs": lambda p: set(),
    "build_pka_configs": lambda p: {},
    "build_standard_configs": lambda p: set(),
    "build_assay_configs": lambda p: {},
    "build_bglb_configs": lambda p: {},
    "build_hh_configs": lambda p: {},
    "build_multiplier_configs": lambda p: {},
}


ALL_LABS = {
    "Color": COLOR,
    "Buffer": BUFFER,
    "A280": A280,
    "Bradford": BRADFORD,
    "Optimal pH": OPTIMAL_PH,
    "Specific Activity": SPECIFIC_ACTIVITY,
    "Purification": PURIFICATION,
}


def parse_runtime_value(kind, raw):
    if kind == "bool_yint":
        return bool(raw)
    raw = raw.strip()
    if kind == "float":
        return float(raw)
    if kind == "int":
        return int(raw)
    if kind == "text":
        return raw
    if kind == "int_list":
        return [int(x.strip()) for x in raw.split(",") if x.strip() != ""]
    if kind == "float_list":
        return [float(x.strip()) for x in raw.split(",") if x.strip() != ""]
    raise ValueError(f"Unknown runtime param kind: {kind}")


def build_configs_from_params(preset, raw_params):
    parsed = {}
    for spec in preset["runtime_params"]:
        key = spec["key"]
        kind = spec["kind"]
        if kind == "bool_yint":
            parsed[key] = bool(raw_params.get(key, spec.get("default", True)))
            continue
        if key not in raw_params or str(raw_params[key]).strip() == "":
            raise ValueError(f"'{spec['label']}' is required")
        parsed[key] = parse_runtime_value(kind, raw_params[key])

    return {
        "operation_configs": preset["build_operation_configs"](parsed),
        "stock_configs": preset["build_stock_configs"](parsed),
        "dilution_configs": preset["build_dilution_configs"](parsed),
        "pka_configs": preset["build_pka_configs"](parsed),
        "standard_configs": preset["build_standard_configs"](parsed),
        "assay_configs": preset["build_assay_configs"](parsed),
        "bglb_configs": preset["build_bglb_configs"](parsed),
        "hh_configs": preset["build_hh_configs"](parsed),
        "multiplier_configs": preset["build_multiplier_configs"](parsed),
    }


def grouped_params(preset):
    order = []
    buckets = {}
    for p in preset["runtime_params"]:
        g = p.get("group", "Parameters")
        if g not in buckets:
            buckets[g] = []
            order.append(g)
        buckets[g].append(p)
    return [(g, buckets[g]) for g in order]


def output_basename(preset):
    return "".join(c.lower() for c in preset["name"] if c.isalnum())


def file_match(preset):
    return preset.get("file_match")

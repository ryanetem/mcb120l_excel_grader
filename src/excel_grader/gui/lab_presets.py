from __future__ import annotations


# Color (dye serial dilutions)
COLOR = {
    "name": "Color",
    "description": "Dye serial dilutions, raw absorbance averages, "
                   "blank correction.",

    "runtime_params": [
        {
            "key": "stock_red",
            "label": "Red",
            "default": "",
            "kind": "float",
            "group": "Stock Concentrations",
        },
        {
            "key": "stock_blue",
            "label": "Blue",
            "default": "",
            "kind": "float",
            "group": "Stock Concentrations",
        },
        {
            "key": "stock_yellow",
            "label": "Yellow",
            "default": "",
            "kind": "float",
            "group": "Stock Concentrations",
        },
        {
            "key": "dilution_factors_1_3",
            "label": "1-3",
            "default": "",
            "kind": "int_list",
            "group": "Dilution Factors",
        },
        {
            "key": "dilution_factors_4_6",
            "label": "4-6",
            "default": "",
            "kind": "int_list",
            "group": "Dilution Factors",
        },
    ],

    "operation_configs": {
        "stock": {
            "source_group": "stock",
            "target_group": "stock",
            "operation": "verify_stock",
            "error_msg": "stock verification failed",
        },
        "concentration": {
            "source_group": "dilution-factor",
            "target_group": "concentration",
            "operation": "division",
            "numerator": "stock_color_concentration",
            "error_msg": "concentration verification failed",
        },
        "average": {
            "source_group": "raw",
            "target_group": "average",
            "operation": "mean",
            "error_msg": "average verification failed",
        },
        "corrected": {
            "source_group": "average",
            "target_group": "corrected",
            "operation": "blank_correction",
            "dilution_col": "color_concentration_1-3",
            "error_msg": "corrected verification failed",
        },
    },

    "build_stock_configs": lambda p: {
        "red": p["stock_red"],
        "blue": p["stock_blue"],
        "yellow": p["stock_yellow"],
    },
    # combine both dilution factor sets into one since there is only one DILUTION_CONFIGS constant
    "build_dilution_configs": lambda p: (
        set(p["dilution_factors_1_3"]) | set(p["dilution_factors_4_6"])
    ),
    "build_pka_configs": lambda p: {},
}


# Buffer (pNP enzyme kinetics, HH)
# stock concentration first (column order), then dilution factor, then pKa for the HH step
BUFFER = {
    "name": "Buffer",
    "description": "pNP enzyme kinetics, working dilutions, "
                   "graph, Henderson-Hasselbalch.",

    "runtime_params": [
        {
            "key": "stock_concentration",
            "label": "pNP stock (mM)",
            "default": "",
            "kind": "float",
            "group": "Stock Concentrations",
        },
        {
            "key": "dilution_factors",
            "label": "Dilution Factor",
            "default": "",
            "kind": "int_list",
            "group": "Dilution Factor",
        },
        {
            "key": "pka_pnp",
            "label": "pKa (pNP)",
            "default": "",
            "kind": "float",
            "group": "Henderson-Hasselbalch",
        },
    ],

    "operation_configs": {
        "stock-concentration": {
            "source_group": "stock-concentration",
            "target_group": "stock-concentration",
            "operation": "verify_stock",
            "error_msg": "stock verification failed",
        },
        "dilution": {
            "source_group": "dilution",
            "target_group": "dilution",
            "operation": "verify_dilution_factor",
            "error_msg": "dilution verification failed",
        },
        "concentration": {
            "source_group": "stock-concentration",
            "target_group": "diluted-concentration",
            "operation": "verify_working",
            "dilution_col": "pnp_dilution_factor",
            "error_msg": "Working stock verification failed",
        },
        "average": {
            "source_group": "raw",
            "target_group": "average",
            "operation": "mean",
            "error_msg": "average verification failed",
        },
        "corrected": {
            "source_group": "average",
            "target_group": "corrected",
            "operation": "blank_correction",
            "dilution_col": "pnp_diluted-concentration",
            "error_msg": "corrected verification failed",
        },
        "graph": {
            "source_group": "corrected",
            "target_group": "graph",
            "operation": "graph",
            "dilution_col": "pnp_diluted-concentration",
            "set_y_int_to_0": "True",
            "error_msg": "Graph verification failed",
        },
        "hh": {
            "source_group": "graph",
            "target_group": "hh",
            "operation": "verify_hh_ph",
            "dilution_col": "graph_slope_naoh",
            "error_msg": "Henderson-Hasselbalch verification failed",
        },
    },

    "build_stock_configs": lambda p: {p["stock_concentration"]},
    "build_dilution_configs": lambda p: set(p["dilution_factors"]),
    "build_pka_configs": lambda p: {"pnp": p["pka_pnp"]},
}


# A280 (Lab 9: BSA standards, unknown dilutions)
A280 = {
    "name": "A280",
    "description": "BSA standard curve, unknown protein concentration "
                   "via Beer-Lambert (Lab 9, A280 method).",

    "runtime_params": [
        {
            "key": "standard_concentrations",
            "label": "Standard concentrations (mg/mL)",
            "default": "",
            "kind": "float_list",
            "group": "BSA Standards",
        },
        {
            "key": "dilution_factors",
            "label": "Dilution Factor",
            "default": "",
            "kind": "int_list",
            "group": "Unknown Sample",
        },
    ],

    # doesn't run because no lab 9 config 
    "operation_configs": {},
    "_pipeline_unimplemented": True,

    "build_stock_configs": lambda p: set(p["standard_concentrations"]),
    "build_dilution_configs": lambda p: set(p["dilution_factors"]),
    "build_pka_configs": lambda p: {},
}



# Bradford (Lab 9: BSA standards with quadratic standard curve)
BRADFORD = {
    "name": "Bradford",
    "description": "BSA standard curve (quadratic), unknown protein "
                   "concentration (Lab 9, Bradford method).",

    "runtime_params": [
        {
            "key": "standard_concentrations",
            "label": "Standard concentrations (mg/mL)",
            "default": "",
            "kind": "float_list",
            "group": "BSA Standards",
        },
    ],

    "operation_configs": {},
    "_pipeline_unimplemented": True,

    "build_stock_configs": lambda p: set(p["standard_concentrations"]),
    "build_dilution_configs": lambda p: set(),
    "build_pka_configs": lambda p: {},
}


# registry the GUI reads, order is dropdown order
ALL_LABS = {
    "Color": COLOR,
    "Buffer": BUFFER,
    "A280": A280,
    "Bradford": BRADFORD,
}



# helpers used by the GUI
def parse_runtime_value(kind: str, raw: str):
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


def build_configs_from_params(preset: dict, raw_params: dict[str, str]) -> dict:
    parsed: dict = {}
    for spec in preset["runtime_params"]:
        key = spec["key"]
        if key not in raw_params or raw_params[key].strip() == "":
            raise ValueError(f"'{spec['label']}' is required")
        parsed[key] = parse_runtime_value(spec["kind"], raw_params[key])

    return {
        "operation_configs": preset["operation_configs"],
        "stock_configs": preset["build_stock_configs"](parsed),
        "dilution_configs": preset["build_dilution_configs"](parsed),
        "pka_configs": preset["build_pka_configs"](parsed),
    }


def grouped_params(preset: dict) -> list[tuple[str, list[dict]]]:
    order: list[str] = []
    buckets: dict[str, list[dict]] = {}
    for p in preset["runtime_params"]:
        g = p.get("group", "Parameters")
        if g not in buckets:
            buckets[g] = []
            order.append(g)
        buckets[g].append(p)
    return [(g, buckets[g]) for g in order]


def is_pipeline_unimplemented(preset: dict) -> bool:
    return bool(preset.get("_pipeline_unimplemented"))


def output_basename(preset: dict) -> str:
    return preset["name"].lower()

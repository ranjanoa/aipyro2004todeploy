import pandas as pd
import logging
import re
import numpy as np

# Setup logger
logger = logging.getLogger("formula_processor")

def preprocess_formula(formula, sorted_variable_names):
    """
    Wraps variable names containing spaces in backticks for Pandas eval().
    """
    processed = formula
    for v in sorted_variable_names:
        if ' ' in v:
            pattern = r'(?<!`)\b' + re.escape(v) + r'\b(?!`)'
            processed = re.sub(pattern, f"`{v}`", processed)
    return processed

def evaluate_formulas(state_map, controls_cfg, indicators_cfg, calc_vars_cfg):
    """
    Evaluates formulas based on the current state_map.
    """
    if not calc_vars_cfg:
        return {}

    new_values = {}
    lookup_keys = set(controls_cfg.keys()) | set(indicators_cfg.keys()) | {v.get('friendly_name', k) for k,v in calc_vars_cfg.items()}
    sorted_vars = sorted(list(lookup_keys), key=len, reverse=True)

    try:
        temp_df = pd.DataFrame([state_map])
        for _, cfg in calc_vars_cfg.items():
            formula = cfg.get('formula')
            friendly_name = cfg.get('friendly_name')
            if not formula or not friendly_name: continue
            processed_formula = preprocess_formula(formula, sorted_vars)
            try:
                result = temp_df.eval(processed_formula)
                val = float(result.iloc[0])
                new_values[friendly_name] = val
                temp_df[friendly_name] = val
            except Exception as e:
                logger.error(f"Formula error for '{friendly_name}': {e}")
                new_values[friendly_name] = 0.0
    except Exception as general_err:
        logger.error(f"General error in evaluate_formulas: {general_err}")

    return new_values

def generate_calculated_actions(raw_actions, state_map, controls_cfg, indicators_cfg, calc_vars_cfg):
    """
    Generates 'Action' objects for derived variables.
    """
    if not calc_vars_cfg:
        return []

    target_context = state_map.copy()
    for action in raw_actions:
        target_context[action['var_name']] = action['fingerprint_set_point']

    calculated_targets = evaluate_formulas(target_context, controls_cfg, indicators_cfg, calc_vars_cfg)
    calculated_currents = evaluate_formulas(state_map, controls_cfg, indicators_cfg, calc_vars_cfg)

    new_actions = []
    for _, cfg in calc_vars_cfg.items():
        if cfg.get('is_control'):
            name = cfg.get('friendly_name')
            curr_val = calculated_currents.get(name, 0.0)
            target_val = calculated_targets.get(name, 0.0)
            
            def_min = cfg.get('default_min', -9999)
            def_max = cfg.get('default_max', 9999)
            target_val = max(def_min, min(def_max, target_val))

            new_actions.append({
                "var_name": name,
                "current_setpoint": curr_val,
                "fingerprint_set_point": target_val,
                "diff": target_val - curr_val,
                "reason": "Calculated (Synced)",
                "type": "Control",
                "is_calculated": True
            })
    return new_actions

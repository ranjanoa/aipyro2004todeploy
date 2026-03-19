import json
import os
import config
import pandas as pd
import numpy as np
import formula_processor

# ==============================================================================
# 1. CONFIGURATION MANAGEMENT
# ==============================================================================
def load_model_config():
    """Loads the central configuration for variables and limits."""
    try:
        if os.path.exists(config.MODEL_CONFIG_PATH):
            with open(config.MODEL_CONFIG_PATH, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"⚠️ Config Load Error: {e}")

    return {"model_name": "Default", "control_variables": {}, "indicator_variables": {}}

def save_model_config(new_config):
    """Saves updated configuration to disk."""
    try:
        with open(config.MODEL_CONFIG_PATH, 'w') as f:
            json.dump(new_config, f, indent=2)
        return True, "Saved"
    except Exception as e:
        return False, str(e)

# ==============================================================================
# 2. VARIABLE HELPERS
# ==============================================================================
def get_control_variables():
    conf = load_model_config()
    return conf.get('control_variables', {})

def get_indicator_variables():
    conf = load_model_config()
    return conf.get('indicator_variables', {})

def get_tag_to_name_map():
    """Maps DB Column Names -> Human Friendly Names"""
    conf = load_model_config()
    mapping = {}
    for name, data in conf.get('control_variables', {}).items():
        if 'tag_name' in data: mapping[data['tag_name']] = name
    for name, data in conf.get('indicator_variables', {}).items():
        if 'tag_name' in data: mapping[data['tag_name']] = name
    return mapping

def get_name_to_tag_map():
    """Maps Human Friendly Names -> DB Column Names"""
    tag_map = get_tag_to_name_map()
    return {v: k for k, v in tag_map.items()}

# ==============================================================================
# 3. DATA FORMATTERS (API RESPONSES)
# ==============================================================================
def build_api_response(real_df, match_row, future_df, score, confidence, mode):
    """
    Main Aggregator: Joins raw sensor recommendations with calculated metrics.
    Keeping the Core Engines 100% clean and independent.
    """
    controls = get_control_variables()
    indicators = get_indicator_variables()
    conf = load_model_config()
    calc_vars_cfg = conf.get('calculated_variables', {})

    # 1. SCORE CALCULATION
    if (score is None or score <= 0.1) and not real_df.empty:
        total_error = 0
        valid_vars = 0
        for var, data in controls.items():
            col = data.get('tag_name', var)
            try:
                curr = float(real_df.iloc[-1][col]) if col in real_df.columns else 0
                hist = float(match_row.get(col, 0))
                if curr != 0:
                    total_error += abs((hist - curr) / curr)
                    valid_vars += 1
            except: pass
        if valid_vars > 0:
            score = round(max(0, 100 - (total_error / valid_vars * 100)), 1)

    # 2. RAW ACTIONS (From NN/Fingerprint)
    actions = []
    current_state = real_df.iloc[-1].to_dict() if not real_df.empty else {}
    
    for var, data in controls.items():
        col = data.get('tag_name', var)
        try:
            curr_val = float(current_state.get(col, 0.0))
            target_val = float(match_row.get(col, 0.0))
        except: continue

        diff = target_val - curr_val
        reason = "Stable"
        if abs(diff) > 0.1:
            pct = abs(diff / curr_val) if curr_val != 0 else 0
            reason = "Optimizing" if pct < 0.02 else ("Ramping" if diff > 0 else "Ramping")

        actions.append({
            "var_name": var,
            "current_setpoint": curr_val,
            "fingerprint_set_point": target_val,
            "diff": diff,
            "reason": reason,
            "type": "Control"
        })

    # 3. CALCULATED INDEPENDENT ACTIONS
    tag_to_name = get_tag_to_name_map()
    mapped_state = {tag_to_name.get(k, k): v for k, v in current_state.items()}
    
    # Independent calculation join
    calc_actions = formula_processor.generate_calculated_actions(actions, mapped_state, controls, indicators, calc_vars_cfg)
    actions.extend(calc_actions)

    # 4. CHART DATA
    live_history = {}
    fingerprint_pred = {}
    
    clean_real = real_df.copy()
    clean_real.columns = [str(c).strip() for c in clean_real.columns]
    clean_future = future_df.copy()
    clean_future.columns = [str(c).strip() for c in clean_future.columns]

    top_vars = list(controls.keys())[:5]
    for v in top_vars:
        col = controls[v].get('tag_name', v)
        if col in clean_real.columns:
            live_history[v] = clean_real[col].fillna(0).tolist()
        if col in clean_future.columns:
            fingerprint_pred[v] = clean_future[col].fillna(0).tolist()

    return {
        "match_score": score,
        "confidence": confidence,
        "fingerprint_timestamp": str(match_row.get(config.TIMESTAMP_COLUMN, "N/A")),
        "actions": actions,
        "live_history": live_history,
        "fingerprint_prediction": fingerprint_pred,
        "top_variables": top_vars
    }

def build_no_fingerprint_response(current_state):
    return {
        "fingerprint_Found": "False",
        "match_score": 0,
        "actions": [],
        "debug_message": "No valid historical match found."
    }

# ==============================================================================
# 4. UTILS & STRATEGY HELPERS
# ==============================================================================
def get_optimization_weights():
    """Returns weights for variable matching (0-10 scale)."""
    conf = load_model_config()
    weights = {}
    for var, data in conf.get('control_variables', {}).items():
        weights[var] = data.get('priority', 5)
    return weights

def get_setpoint_tag_map():
    """Maps Friendly Name -> PLC Write Tag"""
    conf = load_model_config()
    mapping = {}
    for name, data in conf.get('control_variables', {}).items():
        if data.get('is_setpoint'):
            mapping[name] = data.get('tag_name', name)
    return mapping

def get_setpoint_scale_factors():
    """Returns scaling factors if tags require multiplication/division."""
    conf = load_model_config()
    factors = {}
    for name, data in conf.get('control_variables', {}).items():
        factors[name] = data.get('scale_factor', 1.0)
    return factors
import pandas as pd
import numpy as np
import logging
import os
import json
from datetime import datetime, timedelta

# ADVANCED MATH IMPORTS
try:
    from scipy.spatial.distance import mahalanobis
    from scipy.linalg import pinv
except ImportError:
    mahalanobis = None
    pinv = None

# LOCAL IMPORTS
try:
    import config
except ImportError:
    config = None

 # formula_processor removed (integrated into process_model)


# ==============================================================================
# 0. ENHANCED LOGGING SETUP
# ==============================================================================
def setup_logging():
    """Sets up a specific logger for the Fingerprint Engine."""
    _logger = logging.getLogger("FingerprintEngine")
    _logger.setLevel(logging.INFO)

    if not _logger.handlers:
        if not os.path.exists("logs"):
            os.makedirs("logs", exist_ok=True)
        fh = logging.FileHandler("logs/fingerprint_debug.log", encoding='utf-8')
        fh.setLevel(logging.INFO)
        # Fix: Windows console (cp1252) can't render emoji ([INIT], [OK], [ERR]).
        # Reconfigure stdout to UTF-8 so log messages with unicode chars work.
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            except Exception:
                pass
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(funcName)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        _logger.addHandler(fh)
        _logger.addHandler(ch)
    return _logger


engine_logger = setup_logging()

# GLOBAL PROCESS MODEL INIT
process_model = None
try:
    import process_model
    HAS_PROCESS_MODEL = True
except ImportError:
    HAS_PROCESS_MODEL = False

# ==============================================================================
# 1. GLOBAL CACHE & CONFIG
# ==============================================================================
CACHE_DF = None
CACHE_COV = None
CACHE_MTIME = 0.0

STATE_FILE = os.path.join(getattr(config, 'JSON_DIR', 'files/json'), "engine_state.json")


def get_config_path():
    if config:
        default_path = os.path.join(getattr(config, 'DATA_DIR', 'files/data'), "fingerprint4.csv")
        return getattr(config, 'HISTORICAL_DATA_CSV_PATH', default_path)
    return "files/data/fingerprint4.csv"


def get_timestamp_col():
    if config:
        return getattr(config, 'TIMESTAMP_COLUMN', "1_timestamp")
    return "1_timestamp"


def load_engine_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_engine_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        engine_logger.error(f"State Save Error: {e}")


def get_model_config_safe():
    if HAS_PROCESS_MODEL and process_model:
        try:
            return process_model.load_model_config()
        except Exception:
            pass
    return {}


def get_active_strategy(conf=None):
    """
    Returns the currently active strategy block from model_config.json.
    Switch strategies by changing 'active_strategy' field in the JSON.
    Falls back to base config fields if no strategy is defined.
    """
    if conf is None:
        conf = get_model_config_safe()
    strategy_name = conf.get('active_strategy', None)
    strategies = conf.get('strategies', {})
    if strategy_name and strategy_name in strategies:
        strat = strategies[strategy_name]
        engine_logger.info(f"[STRATEGY] Active: {strategy_name} — {strat.get('description', '')}")
        return strategy_name, strat
    return 'DEFAULT', {}


# ==============================================================================
# 2. LOW-LEVEL HELPERS
# ==============================================================================
def ensure_calculated_columns(df):
    """
    Checks if df is missing any calculated columns defined in model_config.json.
    If missing, materializes them and saves the updated DF back to CSV and Parquet.
    """
    if df is None or df.empty: return df

    conf = get_model_config_safe()
    calc_cfg = conf.get('calculated_variables', {})
    if not calc_cfg: return df

    # Check for missing columns
    # We use friendly_name as the column identifier
    missing = [cfg.get('friendly_name') for k,cfg in calc_cfg.items()
               if cfg.get('friendly_name') not in df.columns and cfg.get('friendly_name')]

    if missing:
        engine_logger.info(f"[INIT] Missing calculated columns in history: {missing}. Materializing...")
        controls_cfg = conf.get('control_variables', {})
        indicators_cfg = conf.get('indicator_variables', {})

        # Enrich
        enriched_df = process_model.materialize_df(df, controls_cfg, indicators_cfg, calc_cfg)

        # Save back to CSV
        csv_path = get_config_path()
        parquet_path = csv_path.replace('.csv', '.parquet')
        try:
            enriched_df.to_csv(csv_path, index=False)
            engine_logger.info(f"[OK] CSV enriched and saved: {csv_path}")

            # Also update Parquet so next load is instant
            enriched_df.to_parquet(parquet_path, engine='pyarrow')
            engine_logger.info(f"[OK] Parquet cache updated: {parquet_path}")
        except Exception as e:
            engine_logger.error(f"[ERR] Failed to save enriched dataset: {e}")

        return enriched_df

    return df


def robust_read_csv(file_path):
    parquet_path = file_path.replace('.csv', '.parquet')
    try:
        # 1. Try Loading from Parquet
        if os.path.exists(parquet_path):
            csv_mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else 0
            parquet_mtime = os.path.getmtime(parquet_path)

            if csv_mtime <= parquet_mtime:
                df = pd.read_parquet(parquet_path)
                engine_logger.info(f"Loaded Parquet file instantly with {len(df)} rows.")

                # Double check if any NEW calculated variables were added to config since last save
                enriched_df = ensure_calculated_columns(df)
                return enriched_df

        # 2. Fallback to CSV
        if not os.path.exists(file_path):
            engine_logger.warning(f"Data file not found at: {file_path} or {parquet_path}")
            return pd.DataFrame()

        engine_logger.info("Reading raw CSV. This will take a moment before optimizing...")
        df = pd.read_csv(file_path)
        df.columns = [str(c).strip() for c in df.columns]

        # Ensure all calculated columns are present before caching
        df = ensure_calculated_columns(df)

        try:
            df.to_parquet(parquet_path, engine='pyarrow')
            engine_logger.info(f"Optimized history and saved Parquet cache to {parquet_path}")
        except Exception as pe:
            engine_logger.warning(f"Could not save Parquet file: {pe} (Install pyarrow to enable caching).")

        return df
    except Exception as e:
        engine_logger.error(f"Data Read Error: {e}")
        return pd.DataFrame()


def map_csv_headers(hist_df, controls_cfg, indicators_cfg):
    """Restored mapping logic using 'tag_name' from JSON."""
    if hist_df.empty: return hist_df
    df = hist_df.copy()
    rename_map = {}
    all_vars = {}
    if controls_cfg: all_vars.update(controls_cfg)
    if indicators_cfg: all_vars.update(indicators_cfg)

    for friendly, cfg in all_vars.items():
        opc = cfg.get('tag_name')
        if opc and opc in df.columns:
            rename_map[opc] = friendly

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def map_tags_to_friendly_names(current_state_map, controls_cfg, indicators_cfg, calc_vars_cfg=None):
    mapped_state = current_state_map.copy()
    all_vars = {}
    if controls_cfg: all_vars.update(controls_cfg)
    if indicators_cfg: all_vars.update(indicators_cfg)
    opc_lookup = {}
    for friendly_name, cfg in all_vars.items():
        if 'tag_name' in cfg: opc_lookup[cfg['tag_name']] = friendly_name
    for key, value in current_state_map.items():
        if key in opc_lookup: mapped_state[opc_lookup[key]] = value

    # NEW: Evaluate formulas after mapping raw tags
    if calc_vars_cfg:
        mapped_state.update(process_model.evaluate_formulas(mapped_state, controls_cfg, indicators_cfg, calc_vars_cfg))
    return mapped_state


def align_magnitude(target_val, current_val):
    try:
        if target_val == 0 or current_val == 0: return target_val
        ratio = abs(current_val / target_val)
        if 800 < ratio < 1200: return target_val * 1000.0
        if 0.0008 < ratio < 0.0012: return target_val / 1000.0
        if 80 < ratio < 120: return target_val * 100.0
        return target_val
    except Exception:
        return target_val


def pre_calculate_slopes(df, controls_cfg):
    df_slopes = df.copy()
    if controls_cfg:
        for tag_key in controls_cfg.keys():
            if tag_key in df.columns:
                df_slopes[f"{tag_key}_slope"] = df[tag_key].diff().fillna(0)
    return df_slopes


def get_heat_input(fuel_tag, flow_value, current_state, conf):
    """
    Computes specific heat input (GJ/h) = flow (t/h) * calorific_value (GJ/t).
    Pairing is defined in model_config.json under 'fuel_calorific_pairing'.
    Falls back to raw flow value if CV tag not available.
    """
    pairing = conf.get('fuel_calorific_pairing', {})
    cv_tag = pairing.get(fuel_tag)
    if cv_tag:
        cv_value = float(current_state.get(cv_tag, 0))
        if cv_value > 0:
            heat_input = flow_value * cv_value
            return heat_input
    return flow_value  # Fallback: use raw flow if CV not available


def check_future_stability(historical_df, candidate_ts):
    """
    Checks if the process remains stable after the candidate timestamp.
    Stability tags are read from the ACTIVE STRATEGY's stability_tags first,
    then falls back to logic_tags.stability_tags in model_config.json.
    """
    ts_col = get_timestamp_col()
    if ts_col not in historical_df.columns: return False
    try:
        conf = get_model_config_safe()
        strategy_name, strat = get_active_strategy(conf)
        lookahead = conf.get('logic_tags', {}).get('stability_lookahead', 120)

        # Strategy's own stability_tags take priority; fall back to shared logic_tags
        stability_tag_list = strat.get('stability_tags', [])
        if not stability_tag_list:
            stability_tag_list = conf.get('logic_tags', {}).get('stability_tags', [])

        # Legacy fallback: old single-tag config
        if not stability_tag_list:
            legacy_tag = conf.get('logic_tags', {}).get('primary_stability_tag')
            if legacy_tag:
                threshold_pct = conf.get('logic_tags', {}).get('stability_threshold_pct', 0.05)
                stability_tag_list = [{'tag': legacy_tag, 'threshold_pct': threshold_pct}]

        if not stability_tag_list: return True

        match_idx = historical_df.index[historical_df[ts_col] == candidate_ts].tolist()
        if not match_idx: return False
        idx = match_idx[0]
        if idx + 1 + lookahead >= len(historical_df): return False

        future_slice = historical_df.iloc[idx + 1: idx + 1 + lookahead]
        if future_slice.empty: return False

        for entry in stability_tag_list:
            tag_name = entry.get('tag') if isinstance(entry, dict) else entry
            threshold_pct = entry.get('threshold_pct', 0.05) if isinstance(entry, dict) else 0.05

            if tag_name in future_slice.columns:
                std_dev = future_slice[tag_name].std()
                mean_val = future_slice[tag_name].mean()
                if mean_val != 0 and (std_dev / abs(mean_val)) > threshold_pct:
                    engine_logger.debug(
                        f"Stability FAIL [{strategy_name}] on [{tag_name}]: "
                        f"cv={std_dev/abs(mean_val):.3f} > {threshold_pct}")
                    return False

        return True
    except Exception:
        return True


def get_cached_dataframe(controls_cfg, indicators_cfg):
    global CACHE_DF, CACHE_MTIME, CACHE_COV
    csv_path = get_config_path()
    try:
        if not os.path.exists(csv_path): return pd.DataFrame()
        current_mtime = float(os.path.getmtime(csv_path))
        if CACHE_DF is not None and CACHE_MTIME == current_mtime: return CACHE_DF

        engine_logger.info("Reloading dataframe from disk (cache miss or update)...")
        hist_df = robust_read_csv(csv_path)
        hist_df = map_csv_headers(hist_df, controls_cfg, indicators_cfg)
        ts_col = get_timestamp_col()
        if ts_col in hist_df.columns:
            hist_df[ts_col] = pd.to_datetime(hist_df[ts_col], format="%Y-%m-%d %H:%M:%S", errors='coerce')
        CACHE_DF = hist_df
        CACHE_MTIME = current_mtime
        CACHE_COV = None
        return hist_df
    except Exception as e:
        engine_logger.error(f"Cache Error: {e}")
        return pd.DataFrame()


# ==============================================================================
# 3. DYNAMIC WEIGHT BIAS (OPERATIONAL MATRIX)
# ==============================================================================
def calculate_dynamic_weights(current_state, base_weights):
    """
    All rules, thresholds, tags, and weights are read from model_config.json.
    Nothing is hardcoded. Rules can be enabled/disabled via 'matrix_rules' in config.
    Hot kiln: fuel-first priority enforced by 'hot_kiln_rule.priority_action'.
    """
    if not HAS_PROCESS_MODEL or not process_model: return base_weights

    new_weights = base_weights.copy()
    try:
        full_conf = process_model.load_model_config()
        matrix = full_conf.get('operational_matrix_settings', {})
        if not matrix.get('enabled', False): return base_weights

        tags = matrix.get('tags', {})
        lim = matrix.get('limits', {})
        bias = matrix.get('matrix_bias', {})
        actuators = matrix.get('actuators', {})
        rules_enabled = matrix.get('matrix_rules', {})
        hot_kiln_rule = matrix.get('hot_kiln_rule', {})

        bzt = float(current_state.get(tags.get('bzt'), 0))
        o2 = float(current_state.get(tags.get('o2_inlet'), 0))
        c4_temp = float(current_state.get(tags.get('c4_temp'), 0))

        fuel_tag = actuators.get('fuel_main')
        feed_tag = actuators.get('feed')
        fan_tag = actuators.get('id_fan')
        calc_tag = actuators.get('fuel_calciner')

        # --- RULE 1: HOT KILN ---
        if rules_enabled.get('hot_kiln_enabled', True):
            if bzt > lim.get('bzt_hot', 9999):
                priority = hot_kiln_rule.get('priority_action', 'fuel_first')
                fuel_w = hot_kiln_rule.get('fuel_weight', bias.get('hot_kiln_fuel_weight', -15.0))
                feed_w = hot_kiln_rule.get('feed_weight', bias.get('hot_kiln_feed_weight', 10.0))
                fuel_first_only = hot_kiln_rule.get('apply_feed_only_if_fuel_already_reduced', True)

                if fuel_tag:
                    new_weights[fuel_tag] = fuel_w

                # Feed increase is secondary — only applied if fuel is already trending down
                # and priority_action allows it
                if feed_tag and priority == 'fuel_first' and not fuel_first_only:
                    new_weights[feed_tag] = feed_w
                elif feed_tag and priority != 'fuel_first':
                    new_weights[feed_tag] = feed_w

                engine_logger.info(
                    f"KILN HOT ({bzt:.0f}°C): Fuel weight={fuel_w} applied first. "
                    f"Feed weight applied: {not fuel_first_only}")

        # --- RULE 2: COLD KILN ---
        if rules_enabled.get('cold_kiln_enabled', True):
            if lim.get('bzt_cold', 0) > bzt > 500:
                if fuel_tag:
                    new_weights[fuel_tag] = bias.get('cold_kiln_fuel_weight', 15.0)
                engine_logger.info(f"KILN COLD ({bzt:.0f}°C): Adjusted weights for High Fuel")

        # --- RULE 3: LOW O2 → ID FAN (disabled by default per operator instruction) ---
        if rules_enabled.get('low_o2_id_fan_enabled', False):
            if o2 < lim.get('o2_min', 9999) and o2 > 0.1:
                if fan_tag:
                    new_weights[fan_tag] = bias.get('low_o2_fan_weight', 0)
                engine_logger.info(f"LOW O2 ({o2:.1f}%): Adjusted weights for High Draft")

        # --- RULE 5: STRATEGY OPTIMIZATION (PROACTIVE TARGETS) ---
        # Read the active strategy's optimization goals (e.g., TSR MAX)
        # and merge them into the scoring weights.
        strategy_name, strat = get_active_strategy(full_conf)
        opt_cfg = strat.get('optimisation_target', {})
        if opt_cfg:
            # Primary Tag (e.g., % TSR Kiln Inst)
            primary = opt_cfg.get('primary_tag')
            if primary:
                # We use a positive bias to "hunt" for higher values of the primary KPI.
                # Default weight of 5.0 makes it a significant driver of the search score.
                new_weights[primary] = opt_cfg.get('primary_weight', 5.0)
                engine_logger.info(f"STRATEGY BIAS: Added primary target '{primary}' weight={new_weights[primary]}")

            # Co-targets (e.g., Specific Heat Consumption -> -0.4)
            for ct in opt_cfg.get('co_targets', []):
                if not isinstance(ct, dict): continue   # skip inline comments/strings
                ctag = ct.get('tag')
                if not ctag or ctag.startswith('_'): continue
                cweight = ct.get('weight', 0.0)
                new_weights[ctag] = cweight
                engine_logger.info(f"STRATEGY BIAS: Added co-target '{ctag}' weight={cweight}")

    except Exception as e:
        engine_logger.error(f"Weight Bias Error: {e}")
        return base_weights

    return new_weights


# ==============================================================================
# 4. CORE SCORING ENGINE & MATCH CALCULATION
# ==============================================================================
def calculate_match_percentage(current_state, row, controls_cfg):
    """Calculates a numerical 0-100% similarity score."""
    if not isinstance(current_state, dict) or not controls_cfg: return 0.0
    conf = get_model_config_safe()
    fuel_pairing = conf.get('fuel_calorific_pairing', {})

    dist_sum, count = 0.0, 0
    for tag, props in controls_cfg.items():
        if tag in row:
            curr_val = float(current_state.get(tag, 0))
            hist_val = align_magnitude(row.get(tag, 0), curr_val)

            # Use heat input (flow × CV) for fuel tags if pairing is available
            if tag in fuel_pairing:
                curr_val = get_heat_input(tag, curr_val, current_state, conf)
                hist_val_raw = float(row.get(tag, 0))
                hist_cv_tag = fuel_pairing[tag]
                hist_cv = float(row.get(hist_cv_tag, 0))
                if hist_cv > 0:
                    hist_val = hist_val_raw * hist_cv

            if curr_val != 0:
                dist_sum += ((abs(curr_val - hist_val) / curr_val) ** 2)
                count += 1
    if count == 0: return 0.0
    return max(0, min(100, 100 * (1 - np.sqrt(dist_sum / count))))


def _calculate_core_score(row, current_state, controls_cfg, weights=None, active_constraints=None, inv_cov=None,
                          live_slopes=None, penalty_weight=1000.0, is_advanced=False, active_tags_ordered=None):
    score = 0.0
    now = pd.Timestamp.now()
    ts_col = get_timestamp_col()
    conf = get_model_config_safe()
    scoring_cfg = conf.get('scoring_settings', {})
    aggression = float(scoring_cfg.get('search_aggression', 1.0))
    fuel_pairing = conf.get('fuel_calorific_pairing', {})

    # 1. OPTIMIZATION SCORE (Gains / Hunters)
    # Use heat content (flow × CV) for fuel tags, not raw mass flow.
    # This ensures the AI compares actual thermal energy, not just tonnage.
    if weights:
        for tag, w in weights.items():
            if tag in fuel_pairing:
                # Use heat content = mass flow × calorific value at the historical timestamp
                cv_tag = fuel_pairing[tag]
                hist_cv = float(row.get(cv_tag, 0))
                hist_flow = float(row.get(tag, 0))
                tag_val = hist_flow * hist_cv if hist_cv > 0 else hist_flow
            else:
                tag_val = float(row.get(tag, 0))
            score += tag_val * w * aggression

    # 2. DISTANCE PENALTY (Similarity / Safety)
    if isinstance(current_state, dict):
        dist_sum = 0.0

        # Determine which variables to include in distance calculation
        if active_constraints and hasattr(active_constraints, 'items'):
            source_items = active_constraints.items()
        elif controls_cfg and hasattr(controls_cfg, 'items'):
            source_items = controls_cfg.items()
        else:
            source_items = []

        # Vectorized Mahalanobis Support (Bug #1 Fix: iterate active_tags_ordered, not source_items dict)
        use_mahalanobis = is_advanced and inv_cov is not None and mahalanobis is not None
        mahal_tags = active_tags_ordered if active_tags_ordered else []

        if use_mahalanobis and mahal_tags:
            u_vec, v_vec = [], []
            for tag in mahal_tags:   # strict ordered list — dimensions guaranteed to match inv_cov
                curr_val = float(current_state.get(tag, 0))
                hist_val = align_magnitude(row.get(tag, 0), curr_val)
                if tag in fuel_pairing:
                    curr_val = get_heat_input(tag, curr_val, current_state, conf)
                    hist_cv_tag = fuel_pairing[tag]
                    hist_cv = float(row.get(hist_cv_tag, 0))
                    if hist_cv > 0:
                        hist_val = float(row.get(tag, 0)) * hist_cv
                u_vec.append(curr_val)
                v_vec.append(hist_val)
            try:
                m_dist = mahalanobis(u_vec, v_vec, inv_cov)
                if np.isnan(m_dist) or m_dist > 500:
                    use_mahalanobis = False # Matrix is mathematically absurd, fallback to Euclidean
                else:
                    dist_sum = m_dist ** 2
                    engine_logger.debug(f"[SCORE] Mahalanobis distance={m_dist:.4f}")
            except Exception:
                use_mahalanobis = False  # Fallback to Z-score Euclidean

        # Fallback: Z-Score Normalised Weighted Euclidean Distance (Bug #5 Fix)
        # Normalise every variable to its historical population scale before comparing.
        # Prevents mixing temperatures (1350°C) with fuel flows (5 t/h) in raw Euclidean.
        if not use_mahalanobis or dist_sum == 0.0:
            for tag, props in source_items:
                prio = int(props.get('priority', 3))
                if not is_advanced and prio != 1: continue
                if prio == 0 or props.get('is_calculated', False) or 'formula' in props: continue

                curr_val = float(current_state.get(tag, 0))
                hist_val = align_magnitude(row.get(tag, 0), curr_val)

                if tag in fuel_pairing:
                    curr_val = get_heat_input(tag, curr_val, current_state, conf)
                    hist_cv_tag = fuel_pairing[tag]
                    hist_cv = float(row.get(hist_cv_tag, 0))
                    if hist_cv > 0:
                        hist_val = float(row.get(tag, 0)) * hist_cv

                if curr_val != 0:
                    multipliers = scoring_cfg.get('priority_multipliers', {'1': 10.0, '2': 5.0})
                    weight = float(multipliers.get(str(prio), 1.0)) if is_advanced else 1.0
                    raw_delta = abs(curr_val - hist_val) / abs(curr_val)
                    # Safety Cap: Prevent division-by-near-zero explosion. Max 300% distance penalty per tag.
                    normalised_delta = min(raw_delta, 3.0)
                    dist_sum += (normalised_delta ** 2) * weight

        p_weight = scoring_cfg.get('distance_penalty_weight', penalty_weight)
        # Cap absolute total penalty to prevent wiping out scores past the -900000 gate
        total_penalty = dist_sum * p_weight
        if total_penalty > 800000:
            total_penalty = 800000
        score -= total_penalty

    # 3. SLOPE / DIRECTIONAL TREND BONUS (Bug #3 Fix)
    # Reward fingerprints that were moving in the SAME direction as the current plant state.
    # Penalty for fingerprints moving in the OPPOSITE direction (physically dangerous).
    if live_slopes and is_advanced:
        slope_cfg = conf.get('scoring_settings', {})
        slope_bonus = float(slope_cfg.get('trend_match_bonus', 50.0))
        slope_penalty = float(slope_cfg.get('trend_mismatch_penalty', 100.0))
        slope_bonus_total = 0.0
        slope_penalty_total = 0.0
        for tag, live_slope in live_slopes.items():
            if tag in row:
                # Compute historical slope: difference vs preceding row
                # Using a simple proxy: if hist value > current it was rising, else falling
                curr_val = float(current_state.get(tag, 0))
                hist_val = float(row.get(tag, curr_val))
                hist_direction = hist_val - curr_val  # positive = historically was higher
                if live_slope != 0 and hist_direction != 0:
                    if (live_slope > 0) == (hist_direction > 0):
                        slope_bonus_total += slope_bonus
                    else:
                        slope_penalty_total += slope_penalty
        score += slope_bonus_total - slope_penalty_total
        if slope_bonus_total > 0 or slope_penalty_total > 0:
            engine_logger.debug(f"[SCORE] Slope bonus={slope_bonus_total:.0f} / penalty={slope_penalty_total:.0f}")

    # 4. AGE PENALTY + RECENCY BOOST
    # Recent data is preferred. age_penalty_per_day decays scores for old fingerprints.
    # recency_boost gives a flat bonus for fingerprints within the last N days.
    if ts_col in row and pd.notnull(row[ts_col]):
        try:
            age_days = (now - row[ts_col]).total_seconds() / 86400.0
            age_penalty = scoring_cfg.get('age_penalty_per_day', 0.5)
            score -= (age_days * age_penalty)
            # Flat bonus for very recent fingerprints (e.g., last 14 days)
            recency_days = float(scoring_cfg.get('recency_boost_days', 14))
            recency_bonus = float(scoring_cfg.get('recency_boost_value', 200))
            if age_days <= recency_days:
                score += recency_bonus
        except:
            pass
    return score


# ==============================================================================
# 5. SEARCH & OPTIMIZATION
# ==============================================================================
def apply_golden_filter(hist_df):
    """Applies golden_filter_tag plus the golden_prefilter block.
    Uses the ACTIVE STRATEGY's golden_prefilter if defined, otherwise falls back
    to the top-level golden_prefilter in model_config.json.
    """
    if hist_df.empty: return hist_df
    conf = get_model_config_safe()
    logic = conf.get('logic_tags', {})
    strategy_name, strat = get_active_strategy(conf)

    # Existing golden_filter_tag (single-tag upper limit from logic_tags)
    filter_tag = logic.get('golden_filter_tag')
    filter_limit = logic.get('golden_filter_max', 850.0)
    if filter_tag and filter_tag in hist_df.columns:
        before = len(hist_df)
        hist_df = hist_df[hist_df[filter_tag] <= filter_limit]
        engine_logger.info(f"[PREFILTER] golden_filter_tag '{filter_tag}': removed {before - len(hist_df)} rows.")

    # Strategy prefilter takes priority over top-level golden_prefilter
    prefilter = strat.get('golden_prefilter', conf.get('golden_prefilter', {}))
    if prefilter:
        engine_logger.info(f"[PREFILTER] Applying strategy '{strategy_name}' prefilter ({len(prefilter)} tags)")

    for tag, limits in (prefilter or {}).items():
        # Skip metadata/comment keys used in strategy templates (prefixed with _ or named 'comment')
        if tag.startswith('_') or tag == 'comment': continue
        if tag not in hist_df.columns: continue
        if not isinstance(limits, dict): continue
        lo = limits.get('min', None)
        hi = limits.get('max', None)
        before = len(hist_df)
        if lo is not None and hi is not None:
            hist_df = hist_df[hist_df[tag].between(float(lo), float(hi))]
        elif lo is not None:
            hist_df = hist_df[hist_df[tag] >= float(lo)]
        elif hi is not None:
            hist_df = hist_df[hist_df[tag] <= float(hi)]
        removed = before - len(hist_df)
        if removed > 0:
            engine_logger.info(f"[PREFILTER] '{tag}' [{lo}-{hi}]: removed {removed:,} rows. Remaining: {len(hist_df):,}")

    return hist_df


def get_mahalanobis_matrix(hist_df, active_cols):
    global CACHE_COV
    if mahalanobis is None or pinv is None: return None
    try:
        # Bug #2 Fix: Key on hash of sorted tag list, not just the count.
        # A same-sized but different set of tags would previously return a corrupt matrix.
        cache_key = hash(tuple(sorted(active_cols)))
        if CACHE_COV is not None and isinstance(CACHE_COV, tuple) and CACHE_COV[0] == cache_key:
            return CACHE_COV[1]
        sub_df = hist_df[active_cols].dropna()
        if sub_df.empty: return None
        cov_matrix = np.cov(sub_df.values.T)
        # Mathematical Safety: Ridge Regularization
        # Prevents pseudo-inverse explosion if a sensor has 0 variance (flatlined in history)
        if cov_matrix.ndim == 2:
            np.fill_diagonal(cov_matrix, cov_matrix.diagonal() + 1e-6)
        inv_cov = pinv(cov_matrix)
        CACHE_COV = (cache_key, inv_cov)  # Store as (key, matrix) tuple
        return inv_cov
    except Exception:
        return None


def find_best_fingerprint_advanced(current_real_df_window, historical_df, frontend_strategy, current_state,
                                   weights=None):
    if historical_df.empty or not frontend_strategy: return []

    initial_count = len(historical_df)

    if HAS_PROCESS_MODEL and process_model:
        all_vars_cfg = {**process_model.get_control_variables(), **process_model.get_indicator_variables()}
    else:
        full_config = get_model_config_safe()
        all_vars_cfg = {**full_config.get('control_variables', {}), **full_config.get('indicator_variables', {})}

    engine_logger.info(f"[SEARCH] Starting optimization on total dataset of {initial_count} rows.")

    valid_history = apply_golden_filter(historical_df.copy())
    after_golden = len(valid_history)
    if after_golden < initial_count:
        engine_logger.info(f"[SEARCH] Golden Filter applied: {after_golden} rows remaining.")

    ts_col = get_timestamp_col()
    active_constraints = {}
    active_tags = []

    # --- TWO-STAGE SEARCH: Standard (25% tol) -> Steering (100% tol) ---
    search_phases = [
        {'name': 'Standard', 'tol': 0.25},
        {'name': 'Steering (Relaxed)', 'tol': 1.0}
    ]

    working_history = valid_history.copy()
    final_matches = pd.DataFrame()

    for phase in search_phases:
        engine_logger.info(f"[SEARCH] Starting Phase: {phase['name']} (Tolerance: {phase['tol'] * 100:.0f}%)")
        phase_history = working_history.copy()
        tol_pct = phase['tol']

        for tag, strategy in frontend_strategy.items():
            if tag not in phase_history.columns: continue
            try:
                # NEW: Skip Priority 0 variables AND calculated variables from filtering phase per user objective.
                # These are "calculated-only" and should not restrict history search.
                cfg_var = all_vars_cfg.get(tag, {})
                prio = int(cfg_var.get('priority', 3))
                if prio == 0 or cfg_var.get('is_calculated', False) or 'formula' in cfg_var:
                    continue

                # Robustly extract min/max from strategy config
                abs_min = float(strategy.get('custom_min', strategy.get('default_min', strategy.get('min', -9e9))))
                abs_max = float(strategy.get('custom_max', strategy.get('default_max', strategy.get('max', 9e9))))
                cur_val = float(current_state.get(tag, 0))

                # Bug #4 Fix: Apply Absolute Tolerance Bounds
                # A 25% tolerance on an 800 rpm fan is ±200 rpm (physically too wide).
                # If tolerance_abs is defined, restrict the target delta mathematically.
                abs_band = float(strategy.get('tolerance_abs', cfg_var.get('tolerance_abs', 9e9)))

                if cur_val != 0:
                    delta_pct = abs(cur_val * tol_pct)
                    eff_delta = min(delta_pct, abs_band)
                    tol_min = cur_val - eff_delta
                    tol_max = cur_val + eff_delta
                else:
                    tol_min = -min(tol_pct, abs_band)
                    tol_max = min(tol_pct, abs_band)

                eff_min = max(abs_min, tol_min)
                eff_max = min(abs_max, tol_max)

                phase_history = phase_history[phase_history[tag].between(eff_min, eff_max)]
                if phase_history.empty:
                    # PERSISTENT FILE LOGGING FOR DEBUGGING
                    try:
                        with open("c:/Users/ranja/projects/CimporDeployment-main10032026/files/json/search_failure_debug.txt", "a") as df:
                            df.write(f"\n--- {datetime.now().isoformat()} ---\n")
                            df.write(f"Phase: {phase['name']}\n")
                            df.write(f"Rejected at tag: {tag}\n")
                            df.write(f"Current RT value: {cur_val:.4f}\n")
                            df.write(f"Target range: [{eff_min:.4f} to {eff_max:.4f}]\n")
                            df.write(f"Config Limits: [{abs_min:.1f} to {abs_max:.1f}]\n")
                    except: pass

                    engine_logger.warning(f"[SEARCH] '{phase['name']}' FAILED at tag '{tag}'. Val: {cur_val:.2f}, Target: [{eff_min:.2f} - {eff_max:.2f}]")
                    break
            except:
                continue

        if not phase_history.empty:
            engine_logger.info(f"[SEARCH] Phase '{phase['name']}' found {len(phase_history)} matches.")
            final_matches = phase_history
            # Also capture the constraints used for scoring
            for tag, strategy in frontend_strategy.items():
                cfg_var = all_vars_cfg.get(tag, {})
                prio = int(cfg_var.get('priority', 3))
                if prio == 0 or cfg_var.get('is_calculated', False) or 'formula' in cfg_var:
                    continue
                active_constraints[tag] = strategy.copy()
                active_constraints[tag]['eff_tol'] = tol_pct
            break
        else:
            engine_logger.warning(f"[SEARCH] Phase '{phase['name']}' yielded zero matches.")

    if final_matches.empty:
        engine_logger.error("[SEARCH] CRITICAL: No matches even in Steering mode. Using Golden dataset as fallback.")
        final_matches = working_history  # Last resort: absolute closest in entire Golden dataset
        # Ensure we have some constraints for scoring even if search failed
        if not active_constraints:
            for tag, strategy in frontend_strategy.items():
                cfg_var = all_vars_cfg.get(tag, {})
                prio = int(cfg_var.get('priority', 3))
                if prio == 0 or cfg_var.get('is_calculated', False) or 'formula' in cfg_var:
                    continue
                active_constraints[tag] = strategy.copy()
                active_constraints[tag]['eff_tol'] = 1.0

    valid_history = final_matches
    scoring_tags = []
    if HAS_PROCESS_MODEL and process_model:
        all_vars_cfg = {**process_model.get_control_variables(), **process_model.get_indicator_variables()}
    else:
        conf = get_model_config_safe()
        all_vars_cfg = {**conf.get('control_variables', {}), **conf.get('indicator_variables', {})}

    for t in frontend_strategy.keys():
        if t in valid_history.columns:
            # Skip tags that have priority 0 or are calculated (excluded from matching score)
            cfg_var = all_vars_cfg.get(t, {})
            prio = int(cfg_var.get('priority', 3))
            is_calc = cfg_var.get('is_calculated', False) or 'formula' in cfg_var

            if prio == 0 or is_calc:
                continue
            scoring_tags.append(t)

    active_tags = scoring_tags
    inv_cov = get_mahalanobis_matrix(valid_history, active_tags)

    if ts_col in valid_history.columns:
        valid_history[ts_col] = pd.to_datetime(valid_history[ts_col], errors='coerce')

    # Bug #3 Fix: Compute live directional trends (slopes) from the real-time window
    # The engine now prefers historical states that were moving in the SAME direction
    # as the current plant state (e.g., prefer rising-BZT matches when BZT is rising now)
    live_slopes = {}
    try:
        if current_real_df_window is not None and not current_real_df_window.empty:
            for tag in active_tags:
                if tag in current_real_df_window.columns:
                    tail = current_real_df_window[tag].dropna().tail(10)  # last 10 measurements
                    if len(tail) >= 2:
                        live_slopes[tag] = float(tail.iloc[-1] - tail.iloc[0])  # positive = rising
    except Exception:
        live_slopes = {}

    # Improvement #3: Direction-Aware Percentile Gap
    # TSR_MAX hunts toward the 90th percentile (maximize).
    # SHC_MIN hunts toward the 10th percentile (minimize).
    # The gap to the target percentile dynamically boosts the weight the further
    # away you are from the historical optimum — engine hunts harder when more room exists.
    try:
        conf_tmp = get_model_config_safe()
        strategy_name_tmp, strat_tmp = get_active_strategy(conf_tmp)
        opt_tmp = strat_tmp.get('optimisation_target', {})
        primary_tag_tmp = opt_tmp.get('primary_tag')
        primary_direction = opt_tmp.get('primary_direction', 'maximize').lower()
        if primary_tag_tmp and primary_tag_tmp in valid_history.columns:
            curr_primary = float(current_state.get(primary_tag_tmp, 0))
            if primary_direction == 'minimize':
                # For SHC: target the 10th percentile (best = lowest)
                target_percentile = float(valid_history[primary_tag_tmp].quantile(0.10))
                gap_to_target = max(0.0, curr_primary - target_percentile)  # positive = we're above target
                engine_logger.info(f"[SCORE] SHC Percentile Gap: p10={target_percentile:.1f}, curr={curr_primary:.1f}, gap={gap_to_target:.1f}")
            else:
                # For TSR: target the 90th percentile (best = highest)
                target_percentile = float(valid_history[primary_tag_tmp].quantile(0.90))
                gap_to_target = max(0.0, target_percentile - curr_primary)  # positive = we're below target
                engine_logger.info(f"[SCORE] TSR Percentile Gap: p90={target_percentile:.1f}, curr={curr_primary:.1f}, gap={gap_to_target:.1f}")
            # Amplify the primary weight proportionally to the gap
            if gap_to_target > 0 and primary_tag_tmp in weights:
                weights[primary_tag_tmp] = weights[primary_tag_tmp] + gap_to_target * 0.1
    except Exception:
        pass

    def _adv_score_wrapper(row):
        # Bug #1 Fix: Pass active_tags in strict order so u_vec/v_vec dimensions always
        # match inv_cov. Previously, source_items dict iteration could be in any order.
        return _calculate_core_score(
            row, current_state, None, weights,
            active_constraints=active_constraints,
            inv_cov=inv_cov,
            live_slopes=live_slopes,             # Bug #3: directional slope vectors
            active_tags_ordered=active_tags,      # Bug #1: guarantees vector ordering
            is_advanced=True
        )

    final_matches = final_matches.copy()
    final_matches['score'] = final_matches.apply(_adv_score_wrapper, axis=1)
    df_sorted = final_matches.sort_values(by='score', ascending=False)
    df_sorted = df_sorted[df_sorted['score'] > -900000]

    stable_rows = []
    engine_logger.info(f"OPTIMIZATION: Found {len(df_sorted)} matches.")

    DIVERSITY_MINUTES = 60 # Ensure matches are from distinct historical events

    for _, r in df_sorted.iterrows():
        match_ts = r.get(ts_col)

        # 1. Temporal Diversity Check
        is_diverse = True
        for existing in stable_rows:
            existing_ts = existing.get(ts_col)
            if abs((match_ts - existing_ts).total_seconds()) < (DIVERSITY_MINUTES * 60):
                is_diverse = False
                break

        if not is_diverse: continue

        # 2. Stability Check
        if check_future_stability(historical_df, match_ts):
            stable_rows.append(r)

        if len(stable_rows) >= 5: break

    return stable_rows


# ==============================================================================
# 6. MAIN CONTROLLER
# ==============================================================================

# --- GLOBAL CACHE FOR AUTO MODE ---
LAST_AUTO_SCAN_TIME = None
CACHED_AUTO_RESULT = None


def get_scan_interval():
    return getattr(config, 'SCAN_INTERVAL_SECONDS', 300)


def calculate_kpis(current_state):
    """
    Calculates Key Performance Indicators for the UI.
    Generic implementation: iterates over 'kpi_tags' in model_config.json.
    """
    try:
        conf = get_model_config_safe()
        strategy_name, _ = get_active_strategy(conf)
        kpi_definitions = conf.get('kpi_tags', {})

        results = {'ActiveStrategy': strategy_name}
        for kpi_name, defn in kpi_definitions.items():
            tag = defn.get('tag')
            dec = defn.get('decimals', 1)
            if tag:
                val = current_state.get(tag, 0)
                try:
                    results[kpi_name] = round(float(val), dec)
                except (ValueError, TypeError):
                    results[kpi_name] = 0.0
            else:
                results[kpi_name] = 0.0
        return results
    except Exception as e:
        engine_logger.error(f"KPI calculation error: {e}")
        return {'ActiveStrategy': 'ERROR', 'BZT': 0, 'O2': 0, 'Feed': 0, 'MotorCurrent': 0}


def check_disturbance_rules(current_state):
    """
    Checks safety rules from model_config.json 'safety_rules'.
    All thresholds and actions are config-driven.
    Enforces gradual ramp via 'ramp_rate' — no step changes ever produced.
    """
    if not HAS_PROCESS_MODEL or not process_model: return None
    try:
        conf = process_model.load_model_config()
        # Also read nudge_settings for a default rate cap
        nudge = conf.get('nudge_settings', {})
        default_ramp_rate = nudge.get('min_step_fraction', 0.005)

        for rule in conf.get('safety_rules', []):
            live = float(current_state.get(rule['condition_var'], 9999))
            op = rule.get('operator')
            thresh = rule.get('threshold')

            if (op == '>' and live > thresh) or (op == '<' and live < thresh):
                tgt = rule['action_var']
                action_type = rule.get('action_type', 'offset')
                raw_value = rule['action_value']

                # Enforce ramp_rate — the action_value per cycle is capped
                ramp_rate = rule.get('ramp_rate', None)
                curr = float(current_state.get(tgt, 0))

                if action_type == 'offset':
                    # Cap the offset to ramp_rate to ensure gradual change
                    if ramp_rate is not None:
                        capped_value = max(-abs(ramp_rate), min(abs(ramp_rate), raw_value))
                    else:
                        # Fallback: cap to default_ramp_rate fraction of current value
                        capped_value = raw_value * default_ramp_rate if curr != 0 else raw_value
                    new_v = curr + capped_value
                elif action_type == 'min_clamp':
                    # Convert legacy min_clamp to a gradual offset toward the clamp value
                    target_clamped = float(raw_value)
                    diff = target_clamped - curr
                    if ramp_rate is not None:
                        step = max(-abs(ramp_rate), min(abs(ramp_rate), diff))
                    else:
                        step = diff * default_ramp_rate
                    new_v = curr + step
                else:
                    new_v = curr + raw_value

                engine_logger.warning(
                    f"SAFETY RULE '{rule['name']}': {rule['condition_var']}={live:.1f} {op} {thresh}. "
                    f"Nudging {tgt}: {curr:.3f} → {new_v:.3f} (ramp_rate={ramp_rate})")
                return {
                    "match_score": "SAFETY-CLAMP",
                    "timestamp": str(pd.Timestamp.now()),
                    "actions": [{"var_name": tgt, "fingerprint_set_point": new_v,
                                 "current_setpoint": str(curr),
                                 "reason": f"SAFETY: {rule['name']} (gradual)"}]
                }
    except Exception as e:
        engine_logger.error(f"Disturbance Rule Error: {e}")
    return None


def get_live_fingerprint_action(current_real_df_window, frontend_strategy=None):
    """
    Main Loop. All nudge step parameters are read from model_config.json 'nudge_settings'.
    No hardcoded step fractions or full-jump fallbacks.
    """
    global LAST_AUTO_SCAN_TIME, CACHED_AUTO_RESULT

    if current_real_df_window.empty: return None
    try:
        raw_state = current_real_df_window.iloc[-1].to_dict()
        now = pd.Timestamp.now()

        mode = getattr(config, 'FINGERPRINT_MODE_TYPE', 'AUTO') if config else "AUTO"

        # 1. Configuration & Mapping
        if HAS_PROCESS_MODEL and process_model:
            controls_cfg = process_model.get_control_variables()
            indicators_cfg = process_model.get_indicator_variables()
            base_weights = process_model.get_optimization_weights()
            if not frontend_strategy:
                frontend_strategy = {
                    k: {"priority": int(v.get('priority', 3)),
                        "min": float(v.get('default_min', -9e9)),
                        "max": float(v.get('default_max', 9e9)),
                        "tolerance_pct": 25}
                    for k, v in controls_cfg.items()
                }
        else:
            controls_cfg = getattr(config, 'control_variables', {}) if config else {}
            indicators_cfg = getattr(config, 'indicator_variables', {}) if config else {}
            base_weights = {}
            frontend_strategy = frontend_strategy or {}

        # Read nudge settings from config — no hardcoded step values
        full_conf = get_model_config_safe()
        calc_vars_cfg = full_conf.get('calculated_variables', {})
        strategy_name, strat = get_active_strategy(full_conf)
        nudge_cfg = full_conf.get('nudge_settings', {})
        step_fraction = nudge_cfg.get('step_fraction', 0.15)
        min_step_fraction = nudge_cfg.get('min_step_fraction', 0.005)
        allow_full_jump = nudge_cfg.get('allow_full_jump', False)

        engine_logger.info(f"[CYCLE] Mode={mode}  Strategy={strategy_name}")

        current_state = map_tags_to_friendly_names(raw_state, controls_cfg, indicators_cfg, calc_vars_cfg)

        if (d := check_disturbance_rules(current_state)): return d

        dynamic_weights = calculate_dynamic_weights(current_state, base_weights)

        target_vals, target_disp, reason = {}, "Searching...", "Optimized"
        future_data, top_matches, match_meta = [], [], {}

        # =========================================================
        # DECISION BLOCK: MANUAL vs AUTO (TIMED)
        # =========================================================

        if mode == 'MANUAL':
            engine_logger.info("=== CYCLE START | Mode: MANUAL ===")
            try:
                with open(os.path.join(config.JSON_DIR, "current_target.json"), 'r') as f:
                    data = json.load(f)
                    target_disp = data.get("fingerprint_timestamp", "Manual")
                    for a in data.get('actions', []): target_vals[a['var_name']] = float(a['fingerprint_set_point'])
                    reason = "Manual Target"
            except:
                mode = 'AUTO'  # Fallback

        if mode != 'MANUAL':
            time_since_last = (now - LAST_AUTO_SCAN_TIME).total_seconds() if LAST_AUTO_SCAN_TIME else 99999

            if time_since_last >= get_scan_interval() or CACHED_AUTO_RESULT is None:
                engine_logger.info(f"=== CYCLE START | Mode: AUTO [SCANNING NEW TARGET] ===")

                hist_df = get_cached_dataframe(controls_cfg, indicators_cfg)
                best_rows = find_best_fingerprint_advanced(
                    current_real_df_window, hist_df, frontend_strategy, current_state, weights=dynamic_weights
                )

                if best_rows:
                    best = best_rows[0]
                    ts_col = get_timestamp_col()

                    # Build rich match metadata — operators see WHY this timestamp was selected
                    match_meta = {'strategy': strategy_name}
                    opt_conf = strat.get('optimisation_target', full_conf.get('optimisation_target', {}))
                    co_targets = opt_conf.get('co_targets', [])

                    # Primary KPI at matched timestamp
                    primary_tag = opt_conf.get('primary_tag')
                    if primary_tag and primary_tag in best:
                        match_meta['primary_tag'] = primary_tag
                        match_meta['primary_value_at_match'] = round(float(best.get(primary_tag, 0)), 2)

                    # Motor current always included (even if not primary target)
                    motor_tag = full_conf.get('optimisation_target', {}).get('primary_tag', 'Motor 1 Current')
                    if motor_tag in best:
                        match_meta['motor_current_at_match'] = round(float(best.get(motor_tag, 0)), 1)

                    # TSR and SHC always included
                    for kpi_tag, kpi_key in [('% TSR Kiln Inst', 'tsr_at_match'),
                                             ('Specific Heat Consumption Inst', 'shc_at_match')]:
                        if kpi_tag in best:
                            match_meta[kpi_key] = round(float(best.get(kpi_tag, 0)), 2)

                    # Co-target values
                    for ct in co_targets:
                        ctag = ct.get('tag')
                        if ctag and ctag in best:
                            key = ctag.replace(' ', '_').lower()
                            match_meta[key] = round(float(best.get(ctag, 0)), 1)

                    # Fuel rates
                    for fuel_tag in full_conf.get('fuel_calorific_pairing', {}).keys():
                        if fuel_tag in best:
                            key = 'matched_' + fuel_tag.replace(' ', '_').lower()[:30]
                            match_meta[key] = round(float(best.get(fuel_tag, 0)), 3)

                    CACHED_AUTO_RESULT = {
                        'target_vals': best.to_dict(),
                        'target_disp': str(best.get(ts_col)),
                        'top_matches': [str(r.get(ts_col)) for r in best_rows],
                        'match_meta':  match_meta
                    }
                    LAST_AUTO_SCAN_TIME = now
                    engine_logger.info(
                        f"[AUTO] Strategy={strategy_name} Target={CACHED_AUTO_RESULT['target_disp']} "
                        f"| Primary ({primary_tag})={match_meta.get('primary_value_at_match','?')} "
                        f"| TSR={match_meta.get('tsr_at_match','?')}% "
                        f"| SHC={match_meta.get('shc_at_match','?')} kcal/kg")
                else:
                    engine_logger.warning("[AUTO] No matches found. Keeping previous target.")
                    LAST_AUTO_SCAN_TIME = now

            else:
                engine_logger.info(f"=== CYCLE START | Mode: AUTO [USING CACHED TARGET] ===")
                engine_logger.info(f"Next scan in {int(get_scan_interval() - time_since_last)} seconds.")

            if CACHED_AUTO_RESULT:
                target_vals = CACHED_AUTO_RESULT["target_vals"]
                target_disp = CACHED_AUTO_RESULT["target_disp"]
                top_matches = CACHED_AUTO_RESULT.get("top_matches", [])
                match_meta  = CACHED_AUTO_RESULT.get("match_meta", {})
                reason = "Best Match (Cached)"

        # =========================================================
        # CONTROL LOOP — Nudge calculation, fully config-driven
        # =========================================================
        ui_actions = []

        for tag, cfg_var in controls_cfg.items():
            # Skip if explicitly excluded from AI control (aipc: false)
            if not cfg_var.get('aipc', True): continue
            if not cfg_var.get('is_setpoint', True): continue

            curr = float(current_state.get(tag, 0))
            tgt = align_magnitude(float(target_vals.get(tag, curr)), curr)

            gap = tgt - curr

            # Use variable-specific nudge_speed (expert-tuned in JSON) or global step_fraction
            var_speed = cfg_var.get('nudge_speed', step_fraction)
            # Calculate a CONSTANT step size (e.g., 25% of the current value)
            constant_step = abs(curr) * var_speed

            # If the gap is larger than our constant step, take the full constant step
            if abs(gap) > constant_step:
                step = constant_step if gap > 0 else -constant_step
            # If the gap is smaller than the constant step, just snap perfectly to the target!
            else:
                step = gap

            ui_actions.append({
                "var_name": tag,
                "fingerprint_set_point": curr + step,
                "final_target": float(target_vals.get(tag, curr)),
                "current_setpoint": str(curr),
                "reason": f"{reason} (Linear Ramp @ {var_speed*100:.1f}%)"
            })

        return {
            "match_score": f"ACTIVE-{mode}", "timestamp": str(now),
            "target_timestamp": target_disp, "top_matches": top_matches,
            "fingerprint_future": future_data,
            "match_meta": match_meta,
            "calculated_metrics": calculate_kpis(current_state),
            "actions": ui_actions
        }
    except Exception as e:
        engine_logger.error(f"Runtime Error: {e}", exc_info=True)
        return None


# ==============================================================================
# 7. LEGACY API SUPPORT (RESTORED)
# ==============================================================================
def calculate_deviation_ranges(real_data_series, user_deviation_json):
    deviation_ranges = {}
    deviation_data = user_deviation_json.get("deviation", {})
    engine_logger.info("--- [SCAN] Calculating Deviation Ranges ---")
    for key, values in deviation_data.items():
        if key not in real_data_series: continue
        try:
            current_value = float(real_data_series.get(key, 0))
            if current_value == 0: continue
            abs_min = values.get("Min")
            abs_max = values.get("Max")
            lower_pct = float(values.get("Lower", 80)) / 100.0
            higher_pct = float(values.get("Higher", 120)) / 100.0
            calc_min = current_value * lower_pct
            calc_max = current_value * higher_pct
            final_min = float(abs_min) if abs_min is not None else calc_min
            if abs_min is not None and calc_min < float(abs_min): final_min = float(abs_min)
            final_max = float(abs_max) if abs_max is not None else calc_max
            if abs_max is not None and calc_max > float(abs_max): final_max = float(abs_max)
            deviation_ranges[key] = (final_min, final_max)
        except Exception:
            continue
    return deviation_ranges, {}, {}


def filter_historical_by_deviation(historical_df, deviation_ranges):
    if historical_df.empty: return pd.DataFrame()
    initial_count = len(historical_df)
    engine_logger.info(f"--- [SCAN] Filtering History (Initial: {initial_count}) ---")
    df_filtered = historical_df.copy()
    try:
        for col, (min_val, max_val) in deviation_ranges.items():
            if col in df_filtered.columns:
                prev_len = len(df_filtered)
                df_filtered = df_filtered[df_filtered[col].between(min_val, max_val)]
                new_len = len(df_filtered)
                if prev_len - new_len > 0:
                    engine_logger.info(
                        f"Filter {col} [{min_val:.1f}-{max_val:.1f}]: Removed {prev_len - new_len} rows. Remaining: {new_len}")
        return df_filtered
    except Exception as e:
        engine_logger.error(f"Filtering Error: {e}")
        return pd.DataFrame()


def rank_and_select_recommendations(historical_df, candidates, weights=None, current_state=None, controls_cfg=None,
                                    **kwargs):
    engine_logger.info("--- [SCAN] Ranking & Selection Started ---")
    ts_col = get_timestamp_col()
    if isinstance(candidates, list):
        df = historical_df[historical_df[ts_col].isin(candidates)].copy()
    elif hasattr(candidates, 'empty'):
        df = candidates.copy() if not candidates.empty else pd.DataFrame()
    else:
        return []
    if df.empty: return []

    conf = get_model_config_safe()
    df['score'] = 0.0
    if weights:
        for tag, w in weights.items():
            if tag in df.columns:
                df['score'] += df[tag].fillna(0) * w

    if isinstance(current_state, dict) and controls_cfg:
        dist_sum = pd.Series(0.0, index=df.index)

        for tag, props in controls_cfg.items():
            if tag not in df.columns: continue
            try:
                user_min = float(props.get('min', props.get('Min', props.get('default_min', -9e9))))
                user_max = float(props.get('max', props.get('Max', props.get('default_max', 9e9))))

                out_of_bounds = (df[tag] < user_min) | (df[tag] > user_max)
                df.loc[out_of_bounds, 'score'] = -999999.9

                prio = int(props.get('priority', 3))
                curr_val = float(current_state.get(tag, 0))

                # Use specific heat input for fuel tags
                if tag in conf.get('fuel_calorific_pairing', {}):
                    curr_val = get_heat_input(tag, curr_val, current_state, conf)

                if curr_val != 0:
                    scoring_cfg = conf.get('scoring_settings', {})
                    multipliers = scoring_cfg.get('priority_multipliers', {'1': 10.0, '2': 5.0})
                    weight = float(multipliers.get(str(prio), 1.0))

                    hist_vals = df[tag].copy()
                    ratios = np.abs(curr_val / hist_vals.replace(0, np.nan))
                    hist_vals = np.where((ratios > 800) & (ratios < 1200), hist_vals * 1000.0, hist_vals)
                    hist_vals = np.where((ratios > 0.0008) & (ratios < 0.0012), hist_vals / 1000.0, hist_vals)
                    hist_vals = np.where((ratios > 80) & (ratios < 120), hist_vals * 100.0, hist_vals)

                    dist_sum += ((np.abs(curr_val - hist_vals) / curr_val) ** 2) * weight

            except Exception:
                continue

        p_weight = conf.get('scoring_settings', {}).get('distance_penalty_weight', 1000.0)
        df['score'] -= (dist_sum * p_weight)

    if ts_col in df.columns:
        now = pd.Timestamp.now()
        age_days = (now - df[ts_col]).dt.total_seconds() / 86400.0
        age_penalty = conf.get('scoring_settings', {}).get('age_penalty_per_day', 0.05)
        df['score'] -= (age_days.fillna(0) * age_penalty)

    df = df.sort_values(by=['score'], ascending=False)
    stable_candidates = []
    unstable_candidates = []
    for _, row in df.iterrows():
        ts = row[ts_col]
        score = row['score']
        if check_future_stability(historical_df, ts):
            stable_candidates.append(ts)
            if len(stable_candidates) <= 5:
                engine_logger.info(f"MATCH #{len(stable_candidates)}: {ts} (Score: {score:.1f}) - Stable: YES")
        else:
            unstable_candidates.append(ts)
        if len(stable_candidates) >= 5: break
    if len(stable_candidates) < 5:
        needed = 5 - len(stable_candidates)
        stable_candidates.extend(unstable_candidates[:needed])
    return stable_candidates


def pre_filter_by_constraints(historical_df, current_state, controls_cfg):
    if not controls_cfg or not isinstance(current_state, dict): return historical_df
    df_filtered = historical_df.copy()
    conf = get_model_config_safe()
    for tag, cfg in controls_cfg.items():
        try:
            if int(cfg.get('priority', 100)) == 1:
                val = float(current_state.get(tag, 0))
                if val == 0: continue

                # Use heat input for fuel tags
                if tag in conf.get('fuel_calorific_pairing', {}):
                    val = get_heat_input(tag, val, current_state, conf)

                min_v, max_v = val * 0.75, val * 1.25
                if tag in df_filtered.columns:
                    df_filtered = df_filtered[df_filtered[tag].between(min_v, max_v)]
                if len(df_filtered) < 5: return historical_df
        except:
            continue
    return df_filtered


def find_candidates_hierarchical(hist_df, current_state, controls_cfg, indicators_cfg):
    engine_logger.info("--- [SCAN] Starting Hierarchical Candidate Search ---")
    all_vars = {}
    if controls_cfg: all_vars.update(controls_cfg)
    if indicators_cfg: all_vars.update(indicators_cfg)
    p1_vars = {k: v for k, v in all_vars.items() if int(v.get('priority', 99)) == 1}

    def get_auto_ranges(vars_dict, multiplier=1.0):
        ranges = {}
        for tag, cfg in vars_dict.items():
            if tag in current_state:
                try:
                    val = float(current_state[tag])
                    if val != 0:
                        ranges[tag] = (val * (1.0 - (0.10 * multiplier)), val * (1.0 + (0.10 * multiplier)))
                except:
                    pass
        return ranges

    engine_logger.info("[SCAN] Attempting Pass 1: Strict +/- 10% on Priority 1 tags")
    candidates = filter_historical_by_deviation(hist_df, get_auto_ranges(p1_vars, 1.0))
    if candidates.empty:
        engine_logger.info("[SCAN] Pass 1 yielded 0 results. Attempting Pass 2: Loose +/- 30%")
        candidates = filter_historical_by_deviation(hist_df, get_auto_ranges(p1_vars, 3.0))
    return candidates if not candidates.empty else pd.DataFrame()
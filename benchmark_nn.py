import os
import sys
import pandas as pd
import numpy as np
import random
import time
from datetime import datetime

# Import application modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import config
import process_model
from fingerprint_engine import robust_read_csv
from modules.ai_core import mbrl_manager

# --- SCRIPT CONFIGURATION ---
SAMPLE_COUNT = 10000       # Number of historical events to benchmark
ROLLOUT_STEPS = 15          # Minutes to predict into the future
TARGET_TARGET = None        # Will default to model_config.json's primary target
print_details = False       # Print every single batch prediction (True/False)

def run_benchmark():
    global TARGET_TARGET, SAMPLE_COUNT
    print("=" * 60)
    print(" 🚀 NEURAL NETWORK OFFLINE BENCHMARK INITIALIZATION")
    print("=" * 60)

    # 1. LOAD CONFIGURATION
    conf = process_model.load_model_config()
    bindings = conf.get('ai_bindings', {})
    TARGET_TARGET = bindings.get('primary_prediction_target', 'sinteringZoneTemp')
    print(f"[+] Active Benchmarking Target: {TARGET_TARGET}")
    print(f"[+] Sample Pool Size: {SAMPLE_COUNT} Batches")
    print(f"[+] Simulation Horizon: {ROLLOUT_STEPS} Minutes")

    # 2. LOAD HISTORICAL DATA
    print("[+] Loading Golden Dataset (fingerprint4.csv)...")
    try:
        df = robust_read_csv(getattr(config, 'HISTORICAL_DATA_CSV_PATH', 'files/data/fingerprint4.csv'))
    except Exception as e:
        print(f"[!] FAILED TO LOAD DATA: {e}")
        return

    if df.empty or len(df) < 200:
        print("[!] Historic Dataset is too small or empty.")
        return
        
    print(f"    -> Successfully loaded {len(df)} rows.")

    # 3. INITIALIZE WORLD MODEL
    print("[+] Waking up the Neural Network Ensembles...")
    mbrl_manager._initialize_system()
    if mbrl_manager._world_model is None:
        print("[!] Neural Network failed to load. Ensure files/models/ exists.")
        return

    # 4. PREPARE VECTORS
    if TARGET_TARGET not in df.columns:
        print(f"[!] The Target Variable '{TARGET_TARGET}' is not in the CSV columns!")
        # Fallback search for a proxy
        keys = list(df.columns)
        if 'BZT' in keys: TARGET_TARGET = 'BZT'
        else:
            print("Cannot benchmark without valid target.")
            return

    # Filter out NaNs specifically for the target variable to avoid math errors
    valid_indices = df[df[TARGET_TARGET].notna()].index.tolist()
    # We need at least HISTORY_WINDOW (5) past points, and ROLLOUT_STEPS (15) future points
    usable_starts = [i for i in valid_indices if 10 < i < (len(df) - ROLLOUT_STEPS - 1)]

    if len(usable_starts) < SAMPLE_COUNT:
        print(f"[!] Not enough clean contiguous data to sample {SAMPLE_COUNT} batches. Reducing to {len(usable_starts)}.")
        SAMPLE_COUNT = len(usable_starts)

    # Randomly select batches to test
    test_indices = random.sample(usable_starts, SAMPLE_COUNT)
    
    a_cols = mbrl_manager._env_config['a_cols']

    # --- METRICS TRACKERS ---
    mae_list = []
    mse_list = []
    directional_correct = 0
    directional_total = 0
    confidences = []
    
    start_time = time.time()
    
    print("\n[+] Benchmarking in progress (Evaluating Physics...)\n")

    # 5. EXECUTE BACKTESTING
    for i, idx in enumerate(test_indices):
        # Slice contextual history (the 5 minutes the NN is allowed to "see")
        hist_window_df = df.iloc[idx - mbrl_manager.HISTORY_WINDOW : idx].copy()
        
        # Extract the True Future (the 15 minutes that actually happened)
        future_window_df = df.iloc[idx : idx + ROLLOUT_STEPS].copy()
        
        # Extract starting value securely
        start_val = hist_window_df.iloc[-1][TARGET_TARGET]
        true_end_val = future_window_df.iloc[-1][TARGET_TARGET]
        
        # Extract the exact setpoints the human operator used in the snapshot, 
        # locking them as constant overrides for the simulation step.
        operator_controls = hist_window_df.iloc[-1][a_cols].to_dict()
        
        # Simulate Rollout
        sim_results = mbrl_manager.simulate_what_if(hist_window_df, operator_controls, TARGET_TARGET, steps=ROLLOUT_STEPS)
        predicted_rollout = sim_results.get('simulated', [])
        
        if not predicted_rollout or len(predicted_rollout) < ROLLOUT_STEPS:
            continue
            
        pred_end_val = predicted_rollout[-1]
        
        # Compute Error
        abs_err = abs(pred_end_val - true_end_val)
        mae_list.append(abs_err)
        mse_list.append(abs_err ** 2)
        
        # Compute Directional Physics Check (Did it get the vector right?)
        true_trend = true_end_val - start_val
        pred_trend = pred_end_val - start_val
        
        # Only evaluate directional accuracy if there was a meaningful physical change (> 1 unit variance)
        if abs(true_trend) > 1.0:
            directional_total += 1
            if np.sign(true_trend) == np.sign(pred_trend):
                directional_correct += 1

        # Extract Neural Network Confidence for this specific state
        raw_s = hist_window_df[mbrl_manager._env_config['s_cols']].values
        raw_a = hist_window_df[a_cols].values
        norm_s = mbrl_manager._normalize(raw_s, 'state')
        norm_a = mbrl_manager._normalize(raw_a, 'action')
        obs = np.concatenate([norm_s, norm_a], axis=1).flatten()
        import torch
        obs_tensor = torch.FloatTensor(obs).unsqueeze(0).to(mbrl_manager.device)
        _, variance = mbrl_manager._world_model.predict(obs_tensor)
        raw_var = variance.mean().item()
        if np.isnan(raw_var) or np.isinf(raw_var): conf = 0.0
        else: conf = max(0, min(100, 100 - (raw_var * 1000)))
        confidences.append(conf)

        if print_details:
            print(f"[{i+1}/{SAMPLE_COUNT}] True: {true_end_val:.1f} | Pred: {pred_end_val:.1f} | Err: {abs_err:.1f} | Conf: {conf:.1f}%")
        elif (i+1) % 10 == 0:
            sys.stdout.write(f"\rProcessed {i+1}/{SAMPLE_COUNT} batches...")
            sys.stdout.flush()

    sys.stdout.write("\n")
    
    if len(mae_list) == 0:
        print("[!] No successful predictions parsed!")
        return

    # 6. GENERATE FINAL REPORT
    final_mae = np.mean(mae_list)
    final_rmse = np.sqrt(np.mean(mse_list))
    dir_acc = (directional_correct / directional_total * 100.0) if directional_total > 0 else 0
    avg_conf = np.mean(confidences)
    
    elapsed = time.time() - start_time
    
    report = f"""
============================================================
 📊 OFFLINE NEURAL NETWORK PERFORMANCE REPORT
============================================================
 Metric Target Variable    : {TARGET_TARGET}
 Sample Count Tested       : {len(mae_list)} Random Batches
 Prediction Time Horizon   : {ROLLOUT_STEPS} Minutes
 Simulation Compute Time   : {elapsed:.2f} seconds
------------------------------------------------------------
 Mean Absolute Error (MAE) : {final_mae:.2f} units avg deviation
 Root Mean Sq Error (RMSE) : {final_rmse:.2f} units (punishes severe errors)
"""
    if directional_total > 0:
        report += f" Directional Accuracy      : {dir_acc:.1f}% ({directional_correct}/{directional_total} trends verified)\n"
    else:
        report += f" Directional Accuracy      : N/A (Plant was constantly stable)\n"
    report += f" Average Model Confidence  : {avg_conf:.1f}% across all samples\n"
    report += "============================================================\n"
    
    if dir_acc > 70.0 and final_mae < 25.0:
        report += "\n✅ DIAGNOSIS: EXCELLENT. The AI strongly models the physical thermodynamics of the plant.\n"
    elif dir_acc > 50.0:
        report += "\n⚠️ DIAGNOSIS: ADEQUATE. The model performs better than random guessing but could use more diverse training data.\n"
    else:
        report += "\n❌ DIAGNOSIS: POOR. The model is failing to identify vectors and is guessing randomly. Consider retraining.\n"
    
    print(report)
    with open('benchmark_report.md', 'w', encoding='utf-8') as f:
        f.write("# Neural Network Formal Backtesting Benchmark\\n\\n")
        f.write("```text\\n")
        f.write(report)
        f.write("```\\n")
    print(f"[+] Saved professional printed report to benchmark_report.md")
        

if __name__ == "__main__":
    run_benchmark()

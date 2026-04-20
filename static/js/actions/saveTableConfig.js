import { state } from "../inits/state.js";
import { MOCK_CONFIG } from "../inits/config.js";

export async function saveTableConfig() {
    //  const cfg = JSON.parse(JSON.stringify(state.currentModelConfig));

    //         if (cfg.ai_bindings) {
    //             cfg.ai_bindings.primary_control_actor = document.getElementById('bind-primary_control_actor').value;
    //             cfg.ai_bindings.primary_prediction_target = document.getElementById('bind-primary_prediction_target').value;
    //         }

    //         document.querySelectorAll('#config-controls-body input').forEach(input => {
    //             const tag = input.getAttribute('data-tag');
    //             const field = input.getAttribute('data-field');
    //             if (cfg.control_variables[tag]) {
    //                 if (input.type === 'checkbox') {
    //                     cfg.control_variables[tag][field] = input.checked;
    //                 } else {
    //                     cfg.control_variables[tag][field] = parseFloat(input.value);
    //                 }
    //             }
    //         });

    //         if (!cfg.optimization_settings) cfg.optimization_settings = {};
    //         cfg.optimization_settings.target_variable = document.getElementById('config-opt-target').value;
    //         cfg.optimization_settings.target_setpoint = parseFloat(document.getElementById('config-opt-setpoint').value);

    //         try {
    //             const res = await fetch(`${MOCK_CONFIG.API_URL}/api/config`, {
    //                 method: 'POST',
    //                 headers: { 'Content-Type': 'application/json' },
    //                 body: JSON.stringify(cfg)
    //             });
    //             if (res.ok) {
    //                 alert("Configuration Updated Successfully!");
    //                 location.reload();
    //             } else {
    //                 alert("Failed to update configuration.");
    //             }
    //         } catch (e) {
    //             alert("Error saving configuration: " + e.message);
    //         }
    //     }

         const cfg = JSON.parse(JSON.stringify(state.currentModelConfig));

            // Save Active Strategy
            cfg.active_strategy = document.getElementById('config-active-strategy').value;

            // Harvest values from both tables
            document.querySelectorAll('#config-controls-body input, #config-indicators-body input').forEach(input => {
                const tag = input.getAttribute('data-tag'); 
                const field = input.getAttribute('data-field');
                const targetObj = cfg.control_variables[tag] || cfg.indicator_variables[tag];
                
                if (targetObj) {
                    if (field === 'filtering_enabled') {
                        if (!targetObj.filtering) targetObj.filtering = { ema_alpha: 0.2, median_window: 3 };
                        targetObj.filtering.enabled = input.checked;
                    } else if (input.type === 'checkbox') {
                        targetObj[field] = input.checked;
                    } else {
                        targetObj[field] = parseFloat(input.value);
                    }
                }
            });

            try {
                const res = await fetch(`${MOCK_CONFIG.API_URL}/api/config`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cfg) });
                if (res.ok) { alert("Configuration Updated Successfully!"); location.reload(); } 
                else { alert("Failed to update configuration."); }
            } catch (e) { alert("Error saving configuration: " + e.message); }
        }
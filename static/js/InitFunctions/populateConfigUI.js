
export function populateConfigUI(cfg) {
    //   const bindContainer = document.getElementById('config-ai-bindings');
    //         bindContainer.innerHTML = '';

    //         if (cfg.ai_bindings) {
    //             const b = cfg.ai_bindings;
    //             const fields = [
    //                 { label: "Primary Control", key: "primary_control_actor", val: b.primary_control_actor },
    //                 { label: "Primary Target", key: "primary_prediction_target", val: b.primary_prediction_target }
    //             ];
    //             fields.forEach(f => {
    //                 bindContainer.innerHTML += `
    //                     <div>
    //                         <label class="text-[9px] font-bold text-gray-500 uppercase block mb-1">${f.label}</label>
    //                         <input type="text" id="bind-${f.key}" value="${f.val}" class="w-full bg-[#122a33] border border-[#476570] text-white text-xs p-2 rounded outline-none focus:border-[#ebf552]">
    //                     </div>`;
    //             });
    //         }

    //         const ctrlBody = document.getElementById('config-controls-body');
    //         ctrlBody.innerHTML = '';

    //         if (cfg.control_variables) {
    //             Object.keys(cfg.control_variables).sort().forEach(key => {
    //                 const c = cfg.control_variables[key];
    //                 const isChecked = c.aipc ? 'checked' : '';
    //                 ctrlBody.innerHTML += `
    //                     <tr class="hover:bg-white/5 transition-colors group">
    //                         <td class="px-4 py-2 font-bold text-gray-300">${key}</td>
    //                         <td class="px-2 py-2 text-gray-500 font-mono">${c.unit || ''}</td>
    //                         <td class="px-2 py-2"><input type="number" data-tag="${key}" data-field="default_min" value="${c.default_min}" class="w-full bg-[#122a33] border border-[#476570] text-white text-xs p-2 rounded outline-none focus:border-[#ebf552]0"></td>
    //                         <td class="px-2 py-2"><input type="number" data-tag="${key}" data-field="default_max" value="${c.default_max}" class="w-full bg-[#122a33] border border-[#476570] text-white text-xs p-2 rounded outline-none focus:border-[#ebf552]"></td>
    //                         <td class="px-2 py-2"><input type="number" data-tag="${key}" data-field="priority" value="${c.priority}" class="w-full bg-[#122a33] border border-[#476570] text-white text-xs p-2 rounded outline-none focus:border-[#ebf552]"></td>
    //                         <td class="px-2 py-2"><input type="number" step="0.01" data-tag="${key}" data-field="nudge_speed" value="${c.nudge_speed || 0.05}" class="w-full bg-[#122a33] border border-[#476570] text-white text-xs p-2 rounded outline-none focus:border-[#ebf552]"></td>
    //                         <td class="px-4 py-2 text-center"><input type="checkbox" data-tag="${key}" data-field="aipc" ${isChecked} class="w-4 h-4 accent-[#ebf552]"></td>
    //                     </tr>`;
    //             });
    //         }

    //         const optTargetSel = document.getElementById('config-opt-target');
    //         optTargetSel.innerHTML = '';

    //         const allTags = [...Object.keys(cfg.control_variables || {}), ...Object.keys(cfg.indicator_variables || {})].sort();
    //         allTags.forEach(t => {
    //             const opt = document.createElement('option');
    //             opt.value = t;
    //             opt.text = t;
    //             if (cfg.optimization_settings && t === cfg.optimization_settings.target_variable) {
    //                 opt.selected = true;
    //             }
    //             optTargetSel.appendChild(opt);
    //         });

    //         if (cfg.optimization_settings) {
    //             document.getElementById('config-opt-setpoint').value = cfg.optimization_settings.target_setpoint;
    //         }

     // Populate Active Strategy Selector
            const strategySel = document.getElementById('config-active-strategy');
            strategySel.innerHTML = '';
            if (cfg.strategies) {
                Object.keys(cfg.strategies).sort().forEach(sKey => {
                    const opt = document.createElement('option');
                    opt.value = sKey;
                    opt.text = sKey;
                    if (sKey === cfg.active_strategy) opt.selected = true;
                    strategySel.appendChild(opt);
                });
            }

            const ctrlBody = document.getElementById('config-controls-body');
            const indBody = document.getElementById('config-indicators-body');
            ctrlBody.innerHTML = '';
            indBody.innerHTML = '';

            const renderRow = (key, c, isMV) => {
                const isFilteringEnabled = (c.filtering && c.filtering.enabled) ? 'checked' : '';
                const isAIPC = c.aipc ? 'checked' : '';
                
                return `
                    <tr class="hover:bg-white/5 transition-colors group">
                        <td class="text-white border-gray-200 px-4 py-2 font-bold text-gray-300">${key}</td>
                        <td class="text-white border-gray-200 px-2 py-2 text-gray-500 font-mono">${c.unit || ''}</td>
                        <td class="text-white border-gray-200 px-2 py-2"><input type="number" data-tag="${key}" data-field="default_min" value="${c.default_min ?? 0}" class="w-16 bg-black/30 border border-white/10 rounded px-1 py-1 text-center text-blue-300"></td>
                        <td class="text-white border-gray-200 px-2 py-2"><input type="number" data-tag="${key}" data-field="default_max" value="${c.default_max ?? 0}" class="w-16 bg-black/30 border border-white/10 rounded px-1 py-1 text-center text-blue-300"></td>
                        <td class="text-white border-gray-200 px-2 py-2"><input type="number" data-tag="${key}" data-field="priority" value="${c.priority ?? 5}" class="w-12 bg-black/30 border border-white/10 rounded px-1 py-1 text-center text-yellow-500 font-bold"></td>
                        <td class="text-white border-gray-200 px-2 py-2"><input type="number" step="0.01" data-tag="${key}" data-field="nudge_speed" value="${c.nudge_speed ?? 0.05}" class="text-white border-gray-200 w-14 bg-black/30 border border-white/10 rounded px-1 py-1 text-center text-gray-400"></td>
                        ${isMV ? `<td class="text-white border-gray-200 px-3 py-2 text-center"><input type="checkbox" data-tag="${key}" data-field="aipc" ${isAIPC} class="w-4 h-4 accent-[#ebf552]"></td>` : ''}
                        <td class="text-white border-gray-200px-3 py-2 text-center"><input type="checkbox" data-tag="${key}" data-field="filtering_enabled" ${isFilteringEnabled} class="w-4 h-4 accent-[#ebf552]"></td>
                    </tr>`;
            };

            if (cfg.control_variables) {
                Object.keys(cfg.control_variables).sort().forEach(key => {
                    ctrlBody.innerHTML += renderRow(key, cfg.control_variables[key], true);
                });
            }
            if (cfg.indicator_variables) {
                Object.keys(cfg.indicator_variables).sort().forEach(key => {
                    indBody.innerHTML += renderRow(key, cfg.indicator_variables[key], false);
                });
            }
}
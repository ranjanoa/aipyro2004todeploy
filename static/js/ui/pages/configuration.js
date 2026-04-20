export function Configuration() {
    const container = document.createElement("div");
    container.className = "configuration-container hidden h-full flex-col gap-4 overflow-y-auto pr-2 custom-scrollbar";
    container.id = "panel-config"

    //     container.innerHTML = `
    //             <div
    //                 class="glass-panel fit-content p-4 border-l-4 border-l-[#ebf552] shrink-0 flex justify-between items-center bg-[#1a3842]">
    //                 <div class="flex items-center gap-4">
    //                     <h3 class="text-lg font-bold text-white">System Configuration</h3>
    //                     <div class="h-6 w-px bg-white/10"></div>
    //                     <label class="flex items-center cursor-pointer group">
    //                         <span
    //                             class="text-[10px] font-bold text-gray-500 group-hover:text-blue-400 mr-2 uppercase tracking-widest transition-colors">Developer
    //                             Mode</span>
    //                         <div class="relative">
    //                             <input type="checkbox" id="config-ui-toggle" class="sr-only" onchange="Actions.toggleConfigView()">
    //                             <div class="w-8 h-4 bg-gray-700 rounded-full shadow-inner"></div>
    //                             <div
    //                                 class="dot absolute w-2 h-2 bg-white rounded-full shadow left-1 top-1 transition-transform">
    //                             </div>
    //                         </div>
    //                     </label>
    //                 </div>
    //                 <button onclick="Actions.syncData()"
    //                     class="bg-yellow-900 border border-gray-200 px-4 py-1.5 rounded hover:bg-[#ebf552] hover:text-[#122a33] text-xs font-bold transition-all shadow-sm active:scale-95">SYNC
    //                     DATA LAKE</button>
    //             </div>

    //             <div id="config-table-view" class="flex flex-col gap-6 pb-8">
    //                 <div class="glass-panel overflow-hidden border border-white/5">
    //                     <div class="p-3 bg-white/5 border-b border-gray-100 flex justify-between items-center">
    //                         <h4 class="text-xs font-black text-white uppercase tracking-tighter">AI Core Bindings</h4>
    //                         <span class="text-[9px] text-gray-500 font-bold">Maps AI roles to process tags</span>
    //                     </div>
    //                     <div class="p-4 bg-[#0e2229]/50">
    //                         <div id="config-ai-bindings" class="grid grid-cols-2 gap-6"></div>
    //                     </div>
    //                 </div>

    //                 <div class="glass-panel overflow-hidden border border-white/5">
    //                     <div class="p-3 bg-white/5 border-b border-gray-100 flex justify-between items-center">
    //                         <h4 class="text-xs font-black text-white uppercase tracking-tighter">Control Variables (MVs)
    //                         </h4>
    //                     </div>
    //                     <div class="overflow-x-auto">
    //                         <table class="w-full text-left text-[11px]">
    //                             <thead>
    //                                 <tr class="bg-[#122a33] text-gray-400 uppercase font-black border-b border-[#476570]">
    //                                     <th class="px-4 py-3 text-white">Variable Name</th>
    //                                     <th class="px-2 py-3 text-white">Unit</th>
    //                                     <th class="px-2 py-3 text-white">Min</th>
    //                                     <th class="px-2 py-3 text-white">Max</th>
    //                                     <th class="px-2 py-3 text-white">Priority</th>
    //                                     <th class="px-2 py-3 text-white">Nudge</th>
    //                                     <th class="px-4 py-3 text-white text-center">AI En</th>
    //                                 </tr>
    //                             </thead>
    //                             <tbody id="config-controls-body" class="divide-y divide-white/5"></tbody>
    //                         </table>
    //                     </div>
    //                 </div>

    //                 <div class="glass-panel overflow-hidden border border-white/5">
    //                     <div class="p-3 bg-white/5 border-b border-gray-100">
    //                         <h4 class="text-xs font-black text-white uppercase tracking-tighter">Optimization Strategy
    //                             Target</h4>
    //                     </div>
    //                     <div class="p-6 bg-[#0e2229]/50 border-b border-gray-100">
    //                         <div class="flex items-center gap-8">
    //                             <div class="flex-1"><label
    //                                     class="text-[10px] font-bold text-gray-500 uppercase block mb-1">Target
    //                                     Variable</label><select id="config-opt-target"
    //                                     class="border border-gray-300 rounded px-3 py-1.5 outline-none w-64 font-bold text-sm text-select-white"></select>
    //                             </div>
    //                             <div class="w-48"><label
    //                                     class="text-[10px] font-bold text-gray-500 uppercase block mb-1">Target
    //                                     Setpoint</label><input type="number" id="config-opt-setpoint"
    //                                     class="w-full bg-[#122a33] border border-[#476570] text-ai-cyan font-mono font-bold rounded p-2 outline-none">
    //                             </div>
    //                         </div>
    //                     </div>
    //                     <div class="p-4 bg-white/5 flex justify-end"><button onclick="Actions.saveTableConfig()"
    //                             class="bg-yellow-900 border border-gray-200 px-4 py-1.5 rounded hover:bg-[#ebf552] hover:text-[#122a33] text-xs font-bold transition-all shadow-sm active:scale-95">Apply
    //                             Changes</button></div>
    //                 </div>
    //             </div>

    //             <div id="config-json-view"
    //                 class="hidden  custom-container flex-1 glass-panel flex flex-col min-h-0 bg-[#1a3842] border-2 border-dashed border-white/10">
    //                 <div class="p-3 bg-red-900/10 border-b border-gray-100 flex justify-between items-center"><span
    //                         class="text-white font-bold text-red-400 animate-pulse">!! STANDBY: RAW JSON EDITOR
    //                         !!</span><span class="text-[9px] text-gray-500">Manual edit bypasses UI validation.</span></div>
    //                 <textarea id="config-editor"
    //                     class="min-h-[350px]
    // flex-1 bg-[#0e2229] text-gray-300 p-6 font-mono text-sm resize-none border-none outline-none"></textarea>
    //                 <div class="p-4 bg-[#152e36] border-t  border-gray-100 flex justify-end shrink-0 gap-4"><button
    //                         onclick="Actions.saveConfig()"
    //                         class="px-4 py-2.5 bg-red-600 text-white text-xs font-black uppercase rounded hover:bg-red-500 shadow-xl transition-all active:scale-95">Overwrite
    //                         JSON</button></div>
    //             </div>
    //   `;
    container.innerHTML = ` <div class="glass-panel border-l-yellow-600 fit-content p-4 border-l-4 border-l-[#ebf552] shrink-0 flex justify-between items-center bg-[#1a3842]">
                <div class="flex items-center gap-4">
                    <h3 class="text-lg font-bold text-white">System Configuration</h3>
                    <div class="h-6 w-px bg-white/10"></div>
                   
                    <label class="switch">
                                            <span class="label-text text-[10px] font-bold text-gray-500 group-hover:text-blue-400 mr-2 uppercase tracking-widest transition-colors">Developer Mode</span>

  <input type="checkbox" id="config-ui-toggle" onchange="Actions.toggleConfigView()">
  <span class="slider round"></span>
</label>
                </div>
                <button onclick="Actions.syncData()" class="hoverWhite bg-yellow-900 text-[#ebf552] border-gray-200 border border-[#ebf552] px-4 py-1.5 rounded hover:bg-[#ebf552] hover:text-[#122a33] text-xs font-bold transition-all shadow-sm active:scale-95">SYNC DATA LAKE</button>
            </div>

            <div id="config-table-view" class="flex flex-col gap-6 pb-8">
                <div class="glass-panel overflow-hidden border-gray-200 border border-white/5">
                    <div class="p-3 bg-white/5 border-b border-gray-200 border-white/10 flex justify-between items-center">
                        <h4 class="text-xs font-black text-white uppercase tracking-tighter">Active Optimization Strategy</h4>
                    </div>
                    <div class="p-4 bg-[#0e2229]/50">
                        <div class="flex items-center gap-4">
                            <div class="flex-1">
                                <label class="text-[10px] font-bold text-white uppercase block mb-1">Select Strategy</label>
                                <select id="config-active-strategy" class="w-full border border-gray-300 rounded px-3 py-1.5 outline-none w-64 font-bold text-sm text-select-white"></select>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="glass-panel overflow-hidden border-gray-200 border border-white/5">
                    <div class="p-3 bg-white/5 border-b border-gray-200 border-white/10 flex justify-between items-center">
                        <h4 class="text-xs font-black text-white uppercase tracking-tighter">Control Variables (MVs)</h4>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-[11px]">
                            <thead>
                                <tr class="bg-[#122a33] text-gray-400 uppercase font-black border-gray-200 border-b border-[#476570]">
                                    <th class="px-4 text-white py-3">Variable Name</th>
                                    <th class="px-2 text-white py-3">Unit</th>
                                    <th class="px-2 text-white py-3">Min</th>
                                    <th class="px-2 text-white py-3">Max</th>
                                    <th class="px-2 text-white py-3">Priority</th>
                                    <th class="px-2 text-white py-3">Nudge</th>
                                    <th class="px-3 text-white py-3 text-center">AI Enable</th>
                                    <th class="px-3 text-white py-3 text-center">Filtering</th>
                                </tr>
                            </thead>
                            <tbody id="config-controls-body" class="divide-y divide-white/5"></tbody>
                        </table>
                    </div>
                </div>

                <div class="glass-panel overflow-hidden border border-gray-200 border-white/5">
                    <div class="p-3 bg-white/5 border-b border-gray-200 border-white/10 flex justify-between items-center">
                        <h4 class="text-xs font-black text-white uppercase tracking-tighter">Indicator Variables (Signal Filtering)</h4>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-[11px]">
                            <thead>
                                <tr class="bg-[#122a33] text-gray-400 uppercase font-black border-b border-gray-200 border-[#476570]">
                                    <th class="px-4 text-white py-3">Variable Name</th>
                                    <th class="px-2 text-white py-3">Unit</th>
                                    <th class="px-2 text-white py-3">Min</th>
                                    <th class="px-2 text-white py-3">Max</th>
                                    <th class="px-2 text-white py-3">Priority</th>
                                    <th class="px-2 text-white py-3">Nudge</th>
                                    <th class="px-4 text-white py-3 text-center">Filtering</th>
                                </tr>
                            </thead>
                            <tbody id="config-indicators-body" class="divide-y divide-white/5"></tbody>
                        </table>
                    </div>
                </div>
                
                <div class="flex justify-end pt-2">
                    <button onclick="Actions.saveTableConfig()" class="hoverWhite bg-yellow-900 border-gray-200 px-4 py-1.5 bg-[#ebf552] text-[#122a33] text-xs font-black uppercase rounded shadow-lg hover:brightness-110 active:scale-95 transition-all">Apply Changes</button>
                </div>
            </div>

            <div id="config-json-view" class="custom-container hidden flex-1 glass-panel flex flex-col min-h-0 bg-[#1a3842] border-2 border-dashed border-white/10">
                <div class="p-3 bg-red-900/10 border-gray-200 border-b border-white/5 flex justify-between items-center"><span class="text-white text-[10px] font-bold text-red-400 animate-pulse">!! STANDBY: RAW JSON EDITOR !!</span><span class="text-[9px] text-gray-500">Manual edit bypasses UI validation.</span></div>
                <textarea id="config-editor" class="flex-1 bg-[#0e2229] text-gray-300 p-6 font-mono text-sm resize-none border-none outline-none"></textarea>
                <div class="p-4 bg-[#152e36] border-gray-200  border-t border-[#476570] flex justify-end shrink-0 gap-4"><button onclick="Actions.saveConfig()" class="hoverWhite border-gray-200 px-4 py-1.5 bg-red-600 text-white text-xs font-black uppercase rounded hover:bg-red-500 shadow-xl transition-all active:scale-95">Overwrite JSON</button></div>
            </div>  `;


    return container;
}

import { initCharts } from "../shared/chart.js";
import { initSocket } from "../shared/socket.js";
import { initializeApp } from "../modules/app-init.js";
import { restoreState } from "../InitFunctions/restore.js"
import { initOpSummary } from "../optSum/initOpSummary.js"
import { initOpkiln } from "../optSum/optSumkiln/initOpkiln.js"
import { initOpPreheater } from "../optSum/optSumPreheater/initOppreheater.js";
import { initOpCooler } from "../optSum/optSumCooler/initOpCooler.js"
export function bootstrap() {
    initCharts();
    initializeApp().then(() => {
        initOpSummary();
        initOpkiln();
        initOpPreheater();
        initOpCooler();
    });
    initSocket();
    restoreState();
}
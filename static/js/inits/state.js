export const state = {

    charts: {
        timeSeriesChart: null,
        trendChart: null,
        mbrlTrendChart: null,
        mbrlUncertChart: null,
        opSummaryChartCanvas: null,
        opSummaryCoolerChartCanvas: null,
        opSummarykilnChartCanvas: null,
        opSummaryPreheaterChartCanvas: null
    },

    controlDefaults: {},

    allRecommendations: [],

    currentModelConfig: {},

    activeTrendVariable: null,
    activeMbrlVar: null,

    ui: {
        isSidebarOpen: true,
        isDashSidebarOpen: true
    },

    aiTargets: {},

    isHybridEngaged: false,
    selectedBatchIndex: 0,

    dataFlow: {
        lastDataTime: Date.now(),
        isStalled: false
    },
    isAutoMode: false,

    latestLiveValues: {},
    // Op Summary State
    opActiveTrends: [],
    opActiveTrendsKiln: [],
    opActiveTrendsPreheater: [],
    opActiveTrendsCooler: [],
    opHistoryData: {},
    opPredictionData: {},

    opHistoryDataKiln: {},
    opPredictionDataKiln: {},

    opHistoryDataPreheater: {},
    opPredictionDataPreheater: {},

     opHistoryDataCooler: {},
    opPredictionDataCooler: {},

};

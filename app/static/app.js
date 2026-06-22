const API_URL = "/api/v1/agent/analyze";
const OPTIONS_API_URL = "/api/v1/agent/options";
const DATA_CATALOG_API_URL = "/api/v1/agent/data-catalog";
const SCORE_REFERENCES_API_URL = "/api/v1/agent/score-references";
const IMPORTS_API_URL = "/api/v1/imports";
const AUTH_LOGIN_API_URL = "/api/v1/auth/login";
const AUTH_REGISTER_API_URL = "/api/v1/auth/register";
const AUTH_LOGOUT_API_URL = "/api/v1/auth/logout";
const AUTH_ME_API_URL = "/api/v1/auth/me";
const USER_PROFILE_API_URL = "/api/v1/user/profile";
const SESSIONS_API_URL = "/api/v1/sessions";
const FAVORITES_API_URL = "/api/v1/favorites/jobs";
const AGENT_RUNS_API_URL = "/api/v1/agent/runs";
const AUTH_TOKEN_STORAGE_KEY = "exam_agent_access_token";
const ACTIVE_SESSION_STORAGE_KEY = "exam_agent_active_session_id";
const PROFILE_STORAGE_KEY = "exam_agent_user_profile";
const SHORTLIST_STORAGE_KEY = "exam_agent_shortlisted_jobs";
const COMPARE_STORAGE_KEY = "exam_agent_compare_jobs";
const ANALYSIS_HISTORY_STORAGE_KEY = "exam_agent_analysis_history";
const CHAT_CONTEXT_LIMIT = 12;
const ANALYSIS_HISTORY_LIMIT = 200;
const ANALYSIS_DISCLAIMER_TEXT = "数据来源与 AI 分析仅供参考，岗位资格、分数线、招录条件以官方公告、职位表和招录单位解释为准。AI 可能存在理解偏差，请在报名前自行核对原始公告。";
const PROFILE_UNSET_OPTION = "未填写";
const PROFILE_CORE_FIELDS = ["province", "exam_type", "education", "major", "identity"];
const PROFILE_TRACKED_FIELDS = [...PROFILE_CORE_FIELDS, "city", "accept_relocation"];
const PROFILE_FIELD_LABELS = {
    province: "省份",
    exam_type: "考试类型",
    data_granularity: "数据粒度",
    education: "学历",
    major: "专业",
    identity: "身份",
    city: "城市",
    accept_relocation: "异地意愿"
};

const ROUTE_TITLES = {
    overview: "概览",
    analyst: "招考分析师",
    "single-job": "单岗位查询",
    shortlist: "岗位备选",
    compare: "岗位对比",
    scores: "分数线参考",
    history: "分析记录",
    "data-center": "数据中心",
    "data-import": "数据导入",
    profile: "我的画像"
};

const IMPORT_FIELD_LABELS = {
    year: "年份",
    province: "省份",
    region: "地区",
    exam_type: "考试类型",
    section_title: "分段标题",
    candidate_no: "准考证号",
    candidate_name: "姓名",
    unit_name: "用人单位",
    unit_code: "单位代码",
    job_name: "岗位名称",
    job_code: "职位代码",
    recruit_count: "招考人数",
    education_requirement: "学历要求",
    degree_requirement: "学位要求",
    identity_requirement: "身份要求",
    political_requirement: "政治面貌",
    major_category: "专业类别",
    major_requirement: "专业要求",
    major_requirement_junior_college: "专科专业要求",
    major_requirement_bachelor: "本科专业要求",
    major_requirement_graduate: "研究生专业要求",
    qualification_requirement: "资格条件",
    job_description: "职位简介",
    contact_phone: "咨询电话",
    work_address: "单位地址",
    xingce_score: "行测成绩",
    shenlun_score: "申论成绩",
    professional_score: "专业成绩",
    subject1_name: "科目 1 名称",
    subject1_score: "科目 1 成绩",
    subject2_name: "科目 2 名称",
    subject2_score: "科目 2 成绩",
    subject3_name: "科目 3 名称",
    subject3_score: "科目 3 成绩",
    bonus_score: "加分",
    review_status: "资格标志",
    written_score: "笔试成绩",
    interview_score: "面试成绩",
    total_score: "总成绩",
    rank: "排名",
    status: "状态",
    group_name: "组别",
    remark: "备注",
    min_score: "最低进面分",
    max_score: "最高分",
    avg_score: "平均分",
    interview_count: "进面人数",
    signup_count: "报名人数",
    approved_count: "审核通过人数",
    paid_count: "缴费人数",
    competition_ratio: "竞争比",
    source_sheet: "来源 Sheet",
    source_file: "来源文件",
    raw_row_json: "原始行"
};
const IMPORT_FIELD_ORDER = [
    "year",
    "province",
    "region",
    "exam_type",
    "data_granularity",
    "section_title",
    "candidate_no",
    "candidate_name",
    "unit_code",
    "unit_name",
    "job_code",
    "job_name",
    "recruit_count",
    "education_requirement",
    "degree_requirement",
    "identity_requirement",
    "political_requirement",
    "xingce_score",
    "shenlun_score",
    "professional_score",
    "subject1_name",
    "subject1_score",
    "subject2_name",
    "subject2_score",
    "subject3_name",
    "subject3_score",
    "bonus_score",
    "written_score",
    "interview_score",
    "total_score",
    "rank",
    "review_status",
    "status",
    "group_name",
    "major_category",
    "major_requirement",
    "major_requirement_junior_college",
    "major_requirement_bachelor",
    "major_requirement_graduate",
    "qualification_requirement",
    "job_description",
    "contact_phone",
    "work_address",
    "min_score",
    "max_score",
    "avg_score",
    "interview_count",
    "signup_count",
    "approved_count",
    "paid_count",
    "competition_ratio",
    "remark",
    "source_sheet",
    "source_file"
];
const IMPORT_MAPPING_PROTECTED_FIELDS = new Set([
    "year",
    "province",
    "exam_type",
    "source_file",
    "source_sheet",
    "data_granularity",
    "raw_row_json",
    "extra_fields_json"
]);
const IMPORT_LOW_CONFIDENCE_THRESHOLD = 0.75;
const IMPORT_OUTPUT_PREVIEW_FIELDS = {
    job_table: [
        "year", "province", "exam_type", "unit_name", "job_code", "job_name",
        "recruit_count", "education_requirement", "degree_requirement", "major_requirement",
        "identity_requirement", "political_requirement", "job_description", "contact_phone", "remark"
    ],
    score_line_table: [
        "year", "province", "exam_type", "unit_name", "job_code", "job_name",
        "recruit_count", "min_score", "max_score", "avg_score", "interview_count"
    ],
    signup_table: [
        "year", "province", "exam_type", "unit_name", "job_code", "job_name",
        "recruit_count", "signup_count", "approved_count", "paid_count", "competition_ratio"
    ]
};
const DEFAULT_IMPORT_DATA_TYPES = [
    ["job_table", "岗位表"],
    ["score_line_table", "进面分数线表"],
    ["candidate_score_table", "笔试面试成绩汇总表"],
    ["signup_table", "报名人数 / 竞争比表"],
    ["major_catalog", "专业目录表"],
    ["review_candidate_list", "资格复审人员名单"],
    ["unknown", "未识别表（仅确认，不可入库）"]
];
const IMPORT_PROVINCE_ALIASES = [
    ["北京", ["北京", "北京市", "beijing"]],
    ["天津", ["天津", "天津市", "tianjin"]],
    ["上海", ["上海", "上海市", "shanghai"]],
    ["重庆", ["重庆", "重庆市", "chongqing"]],
    ["河北", ["河北", "河北省", "hebei"]],
    ["山西", ["山西", "山西省", "shanxi"]],
    ["辽宁", ["辽宁", "辽宁省", "liaoning"]],
    ["吉林", ["吉林", "吉林省", "jilin"]],
    ["黑龙江", ["黑龙江", "黑龙江省", "heilongjiang"]],
    ["江苏", ["江苏", "江苏省", "jiangsu"]],
    ["浙江", ["浙江", "浙江省", "zhejiang"]],
    ["安徽", ["安徽", "安徽省", "anhui"]],
    ["福建", ["福建", "福建省", "fujian"]],
    ["江西", ["江西", "江西省", "jiangxi"]],
    ["山东", ["山东", "山东省", "shandong"]],
    ["河南", ["河南", "河南省", "henan"]],
    ["湖北", ["湖北", "湖北省", "hubei"]],
    ["湖南", ["湖南", "湖南省", "hunan"]],
    ["广东", ["广东", "广东省", "guangdong"]],
    ["海南", ["海南", "海南省", "hainan"]],
    ["四川", ["四川", "四川省", "sichuan"]],
    ["贵州", ["贵州", "贵州省", "guizhou"]],
    ["云南", ["云南", "云南省", "yunnan"]],
    ["陕西", ["陕西", "陕西省", "shaanxi", "shanxi"]],
    ["甘肃", ["甘肃", "甘肃省", "gansu"]],
    ["青海", ["青海", "青海省", "qinghai"]],
    ["台湾", ["台湾", "台湾省", "taiwan"]],
    ["内蒙古", ["内蒙古", "内蒙古自治区", "neimenggu", "inner mongolia"]],
    ["广西", ["广西", "广西壮族自治区", "guangxi"]],
    ["西藏", ["西藏", "西藏自治区", "xizang", "tibet"]],
    ["宁夏", ["宁夏", "宁夏回族自治区", "ningxia"]],
    ["新疆", ["新疆", "新疆维吾尔自治区", "xinjiang"]],
    ["香港", ["香港", "香港特别行政区", "xianggang", "hongkong", "hong kong"]],
    ["澳门", ["澳门", "澳门特别行政区", "aomen", "macau", "macao"]]
];
const DATASET_GROUP_CONTAINER_IDS = {
    jobs: "jobDatasetList",
    scores: "scoreDatasetList",
    reviews: "reviewDatasetList",
    other: "otherDatasetList"
};

const DEFAULT_PROFILE = {
    exam_type: "",
    province: "",
    city: "",
    education: "",
    major: "",
    identity: "",
    accept_relocation: "视岗位而定",
    preferences: [],
    filled_fields: []
};

let currentRoute = "overview";
let authToken = loadStoredText(AUTH_TOKEN_STORAGE_KEY);
let currentUser = null;
let activeSessionId = readStoredSessionId();
let userProfile = normalizeUserProfile(loadStoredObject(PROFILE_STORAGE_KEY, DEFAULT_PROFILE));
const storedShortlistedJobs = loadStoredArray(SHORTLIST_STORAGE_KEY);
let shortlistedJobs = storedShortlistedJobs.map(normalizeJob);
let comparedJobKeys = new Set(loadStoredArray(COMPARE_STORAGE_KEY));
migrateComparedJobKeys(storedShortlistedJobs, shortlistedJobs);
let analysisHistory = loadStoredArray(ANALYSIS_HISTORY_STORAGE_KEY)
    .map(normalizeAnalysisHistoryRecord)
    .filter(Boolean)
    .slice(0, ANALYSIS_HISTORY_LIMIT);
let chatHistory = [];
let dataCatalog = null;
let jobRefCounter = 0;
let analysisInFlight = false;
let currentAbortController = null;
let currentRequestId = 0;
let currentPendingMessage = null;
let currentJobContext = null;
let lastRecommendationJobs = [];
let currentImportPreview = null;
let datasetRowsState = createDatasetRowsState();
let datasetRowsRequestCounter = 0;
const analyzedJobKeys = new Set();
const jobRegistry = new Map();

document.addEventListener("DOMContentLoaded", initializeApp);

async function initializeApp() {
    bindGlobalEvents();
    initializeCustomSelects();
    renderAccountState();
    renderProfileForm();
    renderProfileSurfaces();
    renderShortlist();
    renderCompare();
    renderAnalysisHistory();
    hydrateAnalyzedJobKeys();
    updateDecisionCounts();
    await Promise.all([
        loadAllFilterOptions(),
        loadDataCatalog(),
        restoreAuthSession()
    ]);
    applyProfileToAnalyst();
    renderAnalysisConditionSurfaces();
    syncChatPromptVisibility();
    syncAnalystSubmitState();
    renderRoute(getInitialRoute(), { updateHash: false });
    updateSessionSurface();
    await restoreActiveSessionMessages({ silent: true, navigate: false });
}

function bindGlobalEvents() {
    document.addEventListener("click", handleGlobalClick);
    document.addEventListener("click", handleCustomSelectDocumentClick);
    document.addEventListener("keydown", handleCustomSelectGlobalKeydown);
    window.addEventListener("hashchange", () => {
        renderRoute(getInitialRoute(), { updateHash: false });
    });

    document.getElementById("sidebarCollapseButton")?.addEventListener("click", toggleSidebar);
    document.getElementById("mobileMenuButton")?.addEventListener("click", openMobileNav);
    document.getElementById("mobileScrim")?.addEventListener("click", closeMobileNav);
    document.getElementById("contextPanelToggle")?.addEventListener("click", toggleContextPanel);
    document.getElementById("clearChatButton")?.addEventListener("click", clearChat);
    document.getElementById("clearShortlistButton")?.addEventListener("click", clearShortlist);
    document.getElementById("clearHistoryButton")?.addEventListener("click", clearAnalysisHistory);
    document.getElementById("historyTypeFilter")?.addEventListener("change", renderAnalysisHistory);

    document.getElementById("analysisForm")?.addEventListener("submit", handleAnalystSubmit);
    document.getElementById("question")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
        }
    });
    document.getElementById("question")?.addEventListener("input", () => {
        resizeAnalystTextarea();
        syncAnalystSubmitState();
    });

    document.getElementById("singleJobForm")?.addEventListener("submit", handleSingleJobSubmit);
    document.getElementById("scoreFilterForm")?.addEventListener("submit", handleScoreFilterSubmit);
    document.getElementById("importUploadForm")?.addEventListener("submit", handleImportUpload);
    document.getElementById("importConfirmButton")?.addEventListener("click", handleImportConfirm);
    document.getElementById("importResetButton")?.addEventListener("click", resetImportForm);
    document.getElementById("importFile")?.addEventListener("change", handleImportFileChange);
    document.getElementById("profileForm")?.addEventListener("submit", handleProfileSubmit);
    document.getElementById("devLoginForm")?.addEventListener("submit", handleDevLoginSubmit);
    document.getElementById("datasetRowsSearchForm")?.addEventListener("submit", handleDatasetRowsSearch);
    document.getElementById("datasetRowsPageSize")?.addEventListener("change", handleDatasetRowsPageSizeChange);

    document.getElementById("analystRegion")?.addEventListener("change", handleAnalystProvinceChange);
    document.getElementById("profileProvince")?.addEventListener("change", handleProfileProvinceChange);
    ["analystExamType", "analystRegion", "analystCity", "analystEducation", "analystIdentity"]
        .forEach((id) => document.getElementById(id)?.addEventListener("change", renderAnalysisConditionSurfaces));
    document.getElementById("analystMajor")?.addEventListener("input", renderAnalysisConditionSurfaces);
    window.addEventListener("import:confirmed", handleImportConfirmed);
}

function handleGlobalClick(event) {
    if (!event.target.closest(".sidebar-account-shell")) {
        closeAccountMenu();
    }

    const dialogClose = event.target.closest("[data-dialog-close]");
    if (dialogClose) {
        document.getElementById(dialogClose.dataset.dialogClose)?.close();
        return;
    }

    const authSwitch = event.target.closest("[data-auth-switch]");
    if (authSwitch) {
        setAuthDialogMode(authSwitch.dataset.authSwitch);
        return;
    }

    const cloudAction = event.target.closest("[data-cloud-action]");
    if (cloudAction) {
        handleCloudAction(cloudAction);
        return;
    }

    const startAnalystPromptButton = event.target.closest("[data-start-analyst-prompt]");
    if (startAnalystPromptButton) {
        startAnalystPrompt(startAnalystPromptButton.dataset.startAnalystPrompt);
        return;
    }

    const routeButton = event.target.closest("[data-route-target]");
    if (routeButton) {
        navigateTo(routeButton.dataset.routeTarget);
        return;
    }

    const analystPrompt = event.target.closest("[data-analyst-prompt]");
    if (analystPrompt) {
        startAnalystPrompt(analystPrompt.dataset.analystPrompt, { navigate: false });
        return;
    }

    const jobAction = event.target.closest("[data-job-action]");
    if (jobAction) {
        handleJobAction(jobAction.dataset.jobAction, jobAction.dataset.jobRef);
        return;
    }

    const historyAction = event.target.closest("[data-history-action]");
    if (historyAction) {
        handleHistoryAction(historyAction.dataset.historyAction, historyAction.dataset.historyId);
        return;
    }

    const uiAction = event.target.closest("[data-ui-action]");
    if (uiAction) {
        handleUiAction(uiAction.dataset.uiAction, uiAction);
        return;
    }
}

function handleUiAction(action, element = null) {
    if (action === "focus-analyst-input") {
        navigateTo("analyst");
        document.getElementById("question")?.focus();
    } else if (action === "retry-data-catalog") {
        loadDataCatalog();
    } else if (action === "retry-scores") {
        searchScoreReferences();
    } else if (action === "import-remap") {
        handleImportRemap();
    } else if (action === "import-save-template") {
        handleImportSaveTemplate();
    } else if (action === "retry-single-job") {
        document.getElementById("singleJobForm")?.requestSubmit();
    } else if (action === "show-all-prompts") {
        toggleQuickPromptPanel();
    } else if (action === "toggle-analysis-filters") {
        toggleAnalysisFilterPanel();
    } else if (action === "account-menu") {
        handleAccountMenuAction();
    } else if (action === "account-auth") {
        handleAccountAuthAction();
    } else if (action === "delete-database-dataset") {
        handleDeleteDatabaseDataset(element);
    } else if (action === "view-dataset-data") {
        openDatasetRowsDialog(element);
    } else if (action === "dataset-rows-previous") {
        loadDatasetRowsPage(datasetRowsState.page - 1);
    } else if (action === "dataset-rows-next") {
        loadDatasetRowsPage(datasetRowsState.page + 1);
    } else if (action === "sort-dataset-rows") {
        handleDatasetRowsSort(element?.dataset.sortKey || "");
    } else if (action === "retry-dataset-rows") {
        loadDatasetRowsPage(datasetRowsState.page);
    } else if (action === "open-cloud-sessions") {
        openCloudPanel("sessions");
    } else if (action === "open-cloud-favorites") {
        openCloudPanel("favorites");
    } else if (action === "open-cloud-runs") {
        openCloudPanel("runs");
    }
}


const CUSTOM_SELECT_SELECTOR = [
    ".search-panel select",
    ".filter-panel select",
    ".form-grid select",
    ".history-toolbar select",
    ".import-type-control select",
    ".mapping-editor select"
].join(", ");

function initializeCustomSelects(root = document) {
    root.querySelectorAll(CUSTOM_SELECT_SELECTOR).forEach((select) => {
        if (shouldEnhanceCustomSelect(select)) {
            enhanceCustomSelect(select);
        }
    });
}

function shouldEnhanceCustomSelect(select) {
    return select instanceof HTMLSelectElement
        && !select.multiple;
}

function enhanceCustomSelect(select) {
    if (select.dataset.customSelectEnhanced === "true") {
        refreshCustomSelect(select);
        return;
    }
    select.dataset.customSelectEnhanced = "true";
    select.classList.add("native-select-hidden");

    const shell = document.createElement("div");
    shell.className = "custom-select";
    shell.dataset.selectId = select.id || "";

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "custom-select-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");

    const value = document.createElement("span");
    value.className = "custom-select-value";

    const chevron = document.createElement("span");
    chevron.className = "custom-select-chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = '<svg viewBox="0 0 24 24"><path d="m6 9 6 6 6-6"/></svg>';

    trigger.append(value, chevron);

    const menu = document.createElement("div");
    menu.className = "custom-select-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;

    shell.append(trigger, menu);
    select.insertAdjacentElement("afterend", shell);

    trigger.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        toggleCustomSelect(select);
    });
    trigger.addEventListener("keydown", (event) => handleCustomSelectTriggerKeydown(event, select));
    select.addEventListener("change", () => refreshCustomSelect(select));

    const observer = new MutationObserver(() => refreshCustomSelect(select));
    observer.observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ["disabled"] });
    select._customSelect = { shell, trigger, value, menu, observer };
    refreshCustomSelect(select);
}

function refreshCustomSelect(select) {
    if (!(select instanceof HTMLSelectElement) || !select._customSelect) {
        return;
    }
    const { shell, trigger, value, menu } = select._customSelect;
    const selectedOption = select.selectedOptions?.[0] || select.options?.[select.selectedIndex];
    value.textContent = selectedOption?.textContent || "请选择";
    trigger.disabled = select.disabled;
    shell.classList.toggle("is-disabled", select.disabled);
    menu.innerHTML = "";
    Array.from(select.options).forEach((option, index) => {
        const optionButton = document.createElement("button");
        optionButton.type = "button";
        optionButton.className = "custom-select-option";
        optionButton.setAttribute("role", "option");
        optionButton.setAttribute("aria-selected", String(option.selected));
        optionButton.dataset.value = option.value;
        optionButton.dataset.optionIndex = String(index);
        optionButton.innerHTML = `
            <span>${escapeHtml(option.textContent || option.value || "请选择")}</span>
            <span class="custom-select-check" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg>
            </span>
        `;
        optionButton.classList.toggle("is-selected", option.selected);
        optionButton.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            selectCustomSelectOption(select, option.value);
        });
        optionButton.addEventListener("keydown", (event) => handleCustomSelectOptionKeydown(event, select));
        menu.appendChild(optionButton);
    });
}

function toggleCustomSelect(select) {
    if (!(select instanceof HTMLSelectElement) || select.disabled) {
        return;
    }
    const customSelect = select._customSelect;
    if (!customSelect) {
        return;
    }
    const willOpen = customSelect.menu.hidden;
    closeAllCustomSelects(select);
    if (willOpen) {
        customSelect.menu.hidden = false;
        customSelect.shell.classList.add("is-open");
        customSelect.trigger.setAttribute("aria-expanded", "true");
        const activeOption = customSelect.menu.querySelector(".custom-select-option.is-selected")
            || customSelect.menu.querySelector(".custom-select-option");
        activeOption?.scrollIntoView({ block: "nearest" });
    } else {
        closeCustomSelect(select);
    }
}

function closeCustomSelect(select) {
    const customSelect = select?._customSelect;
    if (!customSelect) {
        return;
    }
    customSelect.menu.hidden = true;
    customSelect.shell.classList.remove("is-open");
    customSelect.trigger.setAttribute("aria-expanded", "false");
}

function closeAllCustomSelects(exceptSelect = null) {
    document.querySelectorAll("select[data-custom-select-enhanced='true']").forEach((select) => {
        if (select !== exceptSelect) {
            closeCustomSelect(select);
        }
    });
}

function selectCustomSelectOption(select, value) {
    if (!(select instanceof HTMLSelectElement)) {
        return;
    }
    select.value = value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    closeCustomSelect(select);
    select._customSelect?.trigger.focus({ preventScroll: true });
}

function handleCustomSelectDocumentClick(event) {
    if (!event.target.closest(".custom-select")) {
        closeAllCustomSelects();
    }
}

function handleCustomSelectGlobalKeydown(event) {
    if (event.key === "Escape") {
        closeAllCustomSelects();
    }
}

function handleCustomSelectTriggerKeydown(event, select) {
    if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        if (select._customSelect?.menu.hidden) {
            toggleCustomSelect(select);
        }
        const options = Array.from(select._customSelect?.menu.querySelectorAll(".custom-select-option") || []);
        const target = event.key === "ArrowUp" ? options.at(-1) : options[0];
        target?.focus({ preventScroll: true });
    }
}

function handleCustomSelectOptionKeydown(event, select) {
    const options = Array.from(select._customSelect?.menu.querySelectorAll(".custom-select-option") || []);
    const currentIndex = options.indexOf(event.currentTarget);
    if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectCustomSelectOption(select, event.currentTarget.dataset.value || "");
    } else if (event.key === "ArrowDown") {
        event.preventDefault();
        options[Math.min(currentIndex + 1, options.length - 1)]?.focus({ preventScroll: true });
    } else if (event.key === "ArrowUp") {
        event.preventDefault();
        options[Math.max(currentIndex - 1, 0)]?.focus({ preventScroll: true });
    } else if (event.key === "Escape") {
        event.preventDefault();
        closeCustomSelect(select);
        select._customSelect?.trigger.focus({ preventScroll: true });
    }
}

async function handleImportConfirmed() {
    try {
        await Promise.all([
            loadDataCatalog(),
            loadAllFilterOptions()
        ]);
        renderAnalysisConditionSurfaces();
        if (currentRoute === "scores") {
            await searchScoreReferences();
        }
    } catch (error) {
        showToast("数据已入库，但页面刷新失败，可以手动刷新数据中心。", "warning");
        console.warn("Import refresh failed:", error);
    }
}

async function handleDeleteDatabaseDataset(element) {
    const datasetId = String(element?.dataset.datasetId || "").trim();
    const sourceKind = String(element?.dataset.sourceKind || "imported").trim();
    if (!datasetId) {
        showToast("缺少数据集 ID，无法删除。", "error");
        return;
    }
    if (!window.confirm(getDatasetDeleteConfirmation(sourceKind))) {
        return;
    }
    setButtonLoading(element, true, "删除中...");
    try {
        await apiFetch(`${IMPORTS_API_URL}/datasets/${encodeURIComponent(datasetId)}`, {
            method: "DELETE"
        });
        await Promise.all([
            loadDataCatalog(),
            loadAllFilterOptions()
        ]);
        renderAnalysisConditionSurfaces();
        if (currentRoute === "scores") {
            await searchScoreReferences();
        }
        showToast("已删除该数据库数据集，相关页面已刷新。", "success");
    } catch (error) {
        showToast(getErrorText(error), "error");
    } finally {
        setButtonLoading(element, false);
    }
}

function getDatasetDeleteConfirmation(sourceKind) {
    if (sourceKind === "builtin_seed") {
        return "这是内置种子数据。确定从数据库中删除吗？删除后可通过迁移脚本重新导入。";
    }
    if (sourceKind === "migrated") {
        return "这是历史迁移数据。确定从数据库中删除吗？删除后不会删除原始备份文件。";
    }
    return "确定删除这批导入数据吗？该操作只会删除数据库中的结构化记录，不会删除原始文件。";
}

function createDatasetRowsState() {
    return {
        datasetId: "",
        title: "在线查看数据",
        page: 1,
        pageSize: 50,
        keyword: "",
        sortBy: "",
        sortOrder: "asc",
        total: 0,
        totalPages: 1,
        requestId: 0
    };
}

function openDatasetRowsDialog(element) {
    const datasetId = String(element?.dataset.datasetId || "").trim();
    const title = String(element?.dataset.datasetTitle || "在线查看数据").trim();
    if (!datasetId) {
        showToast("缺少数据集 ID，无法查看明细。", "error");
        return;
    }

    datasetRowsState = {
        ...createDatasetRowsState(),
        datasetId,
        title
    };
    setText("datasetRowsTitle", title);
    setText("datasetRowsMeta", "正在读取数据集信息…");
    const privacyNotice = document.getElementById("datasetRowsPrivacy");
    if (privacyNotice) {
        privacyNotice.hidden = true;
        privacyNotice.textContent = "";
    }
    setText("datasetRowsPageSummary", "第 1 / 1 页 · 共 0 条");
    setValue("datasetRowsKeyword", "");
    setValue("datasetRowsPageSize", "50");
    refreshCustomSelect(document.getElementById("datasetRowsPageSize"));
    renderDatasetRowsLoading();
    syncDatasetRowsPagination();

    const dialog = document.getElementById("datasetRowsDialog");
    if (dialog && !dialog.open) {
        dialog.showModal();
    }
    loadDatasetRowsPage(1);
}

function handleDatasetRowsSearch(event) {
    event.preventDefault();
    datasetRowsState.keyword = String(document.getElementById("datasetRowsKeyword")?.value || "").trim();
    loadDatasetRowsPage(1);
}

function handleDatasetRowsPageSizeChange(event) {
    const pageSize = Number(event.currentTarget?.value || 50);
    datasetRowsState.pageSize = [25, 50, 100, 200].includes(pageSize) ? pageSize : 50;
    loadDatasetRowsPage(1);
}

function handleDatasetRowsSort(sortKey) {
    const cleanSortKey = String(sortKey || "").trim();
    if (!cleanSortKey) {
        return;
    }
    if (datasetRowsState.sortBy === cleanSortKey) {
        datasetRowsState.sortOrder = datasetRowsState.sortOrder === "asc" ? "desc" : "asc";
    } else {
        datasetRowsState.sortBy = cleanSortKey;
        datasetRowsState.sortOrder = "asc";
    }
    loadDatasetRowsPage(1);
}

async function loadDatasetRowsPage(page) {
    if (!datasetRowsState.datasetId) {
        return;
    }
    const nextPage = Math.max(1, Math.min(Number(page || 1), datasetRowsState.totalPages || 1));
    datasetRowsState.page = nextPage;
    const requestId = ++datasetRowsRequestCounter;
    datasetRowsState.requestId = requestId;
    renderDatasetRowsLoading();
    syncDatasetRowsPagination(true);

    const params = new URLSearchParams({
        page: String(nextPage),
        page_size: String(datasetRowsState.pageSize),
        sort_order: datasetRowsState.sortOrder
    });
    if (datasetRowsState.keyword) {
        params.set("keyword", datasetRowsState.keyword);
    }
    if (datasetRowsState.sortBy) {
        params.set("sort_by", datasetRowsState.sortBy);
    }

    try {
        const data = await apiFetch(
            `${IMPORTS_API_URL}/datasets/${encodeURIComponent(datasetRowsState.datasetId)}/rows?${params.toString()}`,
            { skipAuth: true }
        );
        if (requestId !== datasetRowsState.requestId) {
            return;
        }
        datasetRowsState.page = Number(data?.page || 1);
        datasetRowsState.pageSize = Number(data?.page_size || datasetRowsState.pageSize);
        datasetRowsState.total = Number(data?.total || 0);
        datasetRowsState.totalPages = Math.max(1, Number(data?.total_pages || 1));
        setText("datasetRowsTitle", sanitizeSourceText(data?.title, datasetRowsState.title));
        setText("datasetRowsMeta", formatDatasetRowsMeta(data));
        renderDatasetRowsPrivacyNotice(data);
        renderDatasetRows(data);
    } catch (error) {
        if (requestId !== datasetRowsState.requestId) {
            return;
        }
        renderDatasetRowsError(getErrorText(error));
    } finally {
        if (requestId === datasetRowsState.requestId) {
            syncDatasetRowsPagination(false);
        }
    }
}

function formatDatasetRowsMeta(data) {
    return [
        data?.data_type_label,
        data?.province,
        isValidCatalogYear(data?.year) ? `${data.year} 年` : "",
        data?.exam_type,
        `共 ${formatNumber(data?.total || 0)} 条`
    ].filter(Boolean).join(" · ");
}

function renderDatasetRowsPrivacyNotice(data) {
    const notice = document.getElementById("datasetRowsPrivacy");
    if (!notice) {
        return;
    }
    const message = String(data?.privacy_notice || "").trim();
    notice.textContent = message;
    notice.hidden = !message;
}

function renderDatasetRowsLoading() {
    const container = document.getElementById("datasetRowsContent");
    if (container) {
        container.innerHTML = '<div class="dataset-viewer-loading" role="status">正在读取数据库明细…</div>';
    }
}

function renderDatasetRows(data) {
    const container = document.getElementById("datasetRowsContent");
    if (!container) {
        return;
    }
    const columns = normalizeArray(data?.columns).filter((column) => column?.key && column?.label);
    const items = normalizeArray(data?.items);
    const hasExtraFields = items.some((item) => Object.keys(item?.extra_fields || {}).length);
    if (!items.length || !columns.length) {
        const description = datasetRowsState.keyword
            ? "没有匹配当前关键词的记录，请尝试职位代码、岗位名称或招录单位。"
            : (data?.message || "该数据集暂无可查看明细。");
        container.innerHTML = `
            <div class="dataset-viewer-empty">
                <strong>${datasetRowsState.keyword ? "未找到匹配数据" : "暂无明细"}</strong>
                <p>${escapeHtml(description)}</p>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="dataset-table-scroll" tabindex="0" aria-label="数据集明细表格，可横向滚动">
            <table class="dataset-rows-table">
                <caption class="visually-hidden">${escapeHtml(data?.title || "数据集")}清洗后的数据库明细</caption>
                <thead>
                    <tr>
                        ${columns.map((column) => renderDatasetRowsHeader(column)).join("")}
                        ${hasExtraFields ? '<th scope="col" class="dataset-extra-fields-heading">原表字段</th>' : ""}
                    </tr>
                </thead>
                <tbody>
                    ${items.map((item) => `
                        <tr>
                            ${columns.map((column) => renderDatasetRowsCell(item?.[column.key], column.key)).join("")}
                            ${hasExtraFields ? renderDatasetExtraFieldsCell(item?.extra_fields) : ""}
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function renderDatasetExtraFieldsCell(extraFields) {
    const entries = Object.entries(extraFields || {}).filter(([key]) => key);
    if (!entries.length) {
        return '<td class="dataset-extra-fields-cell"><span>-</span></td>';
    }
    return `
        <td class="dataset-extra-fields-cell">
            <details class="dataset-extra-fields">
                <summary>查看原表字段</summary>
                <dl>
                    ${entries.map(([key, value]) => `
                        <div>
                            <dt>${escapeHtml(key)}</dt>
                            <dd>${escapeHtml(formatDatasetRowsCellValue(value))}</dd>
                        </div>
                    `).join("")}
                </dl>
            </details>
        </td>
    `;
}

function renderDatasetRowsHeader(column) {
    const isActive = datasetRowsState.sortBy === column.key;
    const ariaSort = isActive
        ? (datasetRowsState.sortOrder === "asc" ? "ascending" : "descending")
        : "none";
    const indicator = isActive ? (datasetRowsState.sortOrder === "asc" ? "升序" : "降序") : "";
    return `
        <th scope="col" aria-sort="${ariaSort}" data-field="${escapeHtml(column.key)}">
            <button type="button" data-ui-action="sort-dataset-rows" data-sort-key="${escapeHtml(column.key)}">
                <span>${escapeHtml(column.label)}</span>
                ${indicator ? `<small>${indicator}</small>` : ""}
            </button>
        </th>
    `;
}

function renderDatasetRowsCell(value, key) {
    const displayValue = formatDatasetRowsCellValue(value);
    return `
        <td data-field="${escapeHtml(key)}" title="${escapeHtml(displayValue)}">
            <span>${escapeHtml(displayValue)}</span>
        </td>
    `;
}

function formatDatasetRowsCellValue(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }
    if (typeof value === "number") {
        return Number.isFinite(value) ? String(value) : "-";
    }
    if (typeof value === "object") {
        return JSON.stringify(value);
    }
    return String(value);
}

function renderDatasetRowsError(message) {
    const container = document.getElementById("datasetRowsContent");
    if (container) {
        container.innerHTML = createErrorState(
            "数据明细读取失败",
            message || "请稍后重试。",
            "重新加载",
            "retry-dataset-rows"
        );
    }
}

function syncDatasetRowsPagination(loading = false) {
    const page = datasetRowsState.page || 1;
    const totalPages = datasetRowsState.totalPages || 1;
    setText(
        "datasetRowsPageSummary",
        `第 ${formatNumber(page)} / ${formatNumber(totalPages)} 页 · 共 ${formatNumber(datasetRowsState.total)} 条`
    );
    const previous = document.getElementById("datasetRowsPrevious");
    const next = document.getElementById("datasetRowsNext");
    if (previous) {
        previous.disabled = loading || page <= 1;
    }
    if (next) {
        next.disabled = loading || page >= totalPages;
    }
}

async function restoreAuthSession() {
    if (!authToken) {
        setActiveSession(null);
        renderAccountState();
        return;
    }
    try {
        const data = await apiFetch(AUTH_ME_API_URL);
        currentUser = data?.user || null;
        applyServerProfile(data?.profile);
    } catch {
        authToken = "";
        currentUser = null;
        setActiveSession(null);
        removeStoredValue(AUTH_TOKEN_STORAGE_KEY);
    }
    renderAccountState();
}

function renderAccountState() {
    const loggedIn = Boolean(currentUser && authToken);
    const displayName = currentUser?.display_name || currentUser?.nickname || currentUser?.username;
    const accountName = loggedIn ? displayName : "未登录";
    setText("accountDisplayName", accountName);
    setText("accountStatusText", loggedIn ? "Plus" : "点击登录 / 注册");

    const dot = document.getElementById("accountStatusDot");
    if (dot) {
        dot.textContent = loggedIn ? getUserInitials(displayName || currentUser.username) : "未";
        dot.classList.toggle("online", loggedIn);
    }

    const menuButton = document.getElementById("accountMenuButton");
    if (menuButton) {
        menuButton.setAttribute("aria-label", loggedIn ? `打开 ${accountName} 的账号菜单` : "登录或注册账号");
        if (!loggedIn) {
            menuButton.setAttribute("aria-expanded", "false");
        }
    }

    const authButton = document.getElementById("accountAuthButton");
    if (authButton) {
        authButton.textContent = loggedIn ? "退出登录" : "登录 / 注册";
    }

    const accountMenu = document.getElementById("accountMenu");
    if (accountMenu && !loggedIn) {
        accountMenu.hidden = true;
    }

    document.querySelectorAll(".cloud-entry").forEach((button) => {
        button.disabled = !loggedIn;
        button.title = loggedIn ? "" : "请先登录";
    });
    updateSessionSurface();
}

function getUserInitials(value) {
    const text = String(value || "").trim();
    if (!text) {
        return "U";
    }
    if (/[\u4e00-\u9fff]/.test(text)) {
        return text.replace(/\s+/g, "").slice(0, 2);
    }
    const parts = text.split(/[\s._-]+/).filter(Boolean);
    const initials = parts.length > 1
        ? `${parts[0][0] || ""}${parts[1][0] || ""}`
        : text.slice(0, 2);
    return initials.toUpperCase();
}

function handleAccountMenuAction() {
    if (!currentUser || !authToken) {
        openDialog("authDialog");
        return;
    }
    const menu = document.getElementById("accountMenu");
    const button = document.getElementById("accountMenuButton");
    if (!menu) {
        return;
    }
    const shouldOpen = menu.hidden;
    menu.hidden = !shouldOpen;
    button?.setAttribute("aria-expanded", String(shouldOpen));
}

function closeAccountMenu() {
    const menu = document.getElementById("accountMenu");
    const button = document.getElementById("accountMenuButton");
    if (menu && !menu.hidden) {
        menu.hidden = true;
    }
    button?.setAttribute("aria-expanded", "false");
}

function setAuthDialogMode(mode = "login") {
    const normalizedMode = mode === "register" ? "register" : "login";
    const form = document.getElementById("devLoginForm");
    if (form) {
        form.dataset.authFormMode = normalizedMode;
    }
    document.querySelectorAll("[data-auth-switch]").forEach((button) => {
        const active = button.dataset.authSwitch === normalizedMode;
        button.classList.toggle("active", active);
        button.setAttribute("aria-selected", String(active));
    });
    setText("authDialogTitle", normalizedMode === "register" ? "创建工作台账号" : "登录到工作台");
    setText(
        "authDialogSubtitle",
        normalizedMode === "register"
            ? "注册后可以同步画像、收藏岗位和长期会话，后续换设备也能继续使用。"
            : "保存画像、备选岗位、长期会话和 Agent 运行记录。"
    );
    setText(
        "authModeHint",
        normalizedMode === "register" ? "已有账号？切换到登录即可继续。" : "还没有账号？切换到注册即可创建。"
    );
    const submitButton = document.getElementById("devLoginSubmitButton");
    if (submitButton) {
        submitButton.dataset.authMode = normalizedMode;
        submitButton.textContent = normalizedMode === "register" ? "创建账号" : "登录";
    }
    const passwordInput = document.getElementById("devLoginPassword");
    if (passwordInput) {
        passwordInput.autocomplete = normalizedMode === "register" ? "new-password" : "current-password";
        passwordInput.placeholder = normalizedMode === "register" ? "设置至少 6 位密码" : "输入密码";
    }
    const errorElement = document.getElementById("devLoginError");
    if (errorElement) {
        errorElement.hidden = true;
        errorElement.textContent = "";
    }
}

async function handleAccountAuthAction() {
    closeAccountMenu();
    if (currentUser && authToken) {
        if (!window.confirm("确定退出当前账号吗？本地画像和备选不会删除。")) {
            return;
        }
        try {
            await apiFetch(AUTH_LOGOUT_API_URL, { method: "POST" });
        } catch (error) {
            console.warn("Logout request failed:", error);
        }
        authToken = "";
        currentUser = null;
        setActiveSession(null);
        removeStoredValue(AUTH_TOKEN_STORAGE_KEY);
        renderAccountState();
        showToast("已退出登录，本地功能仍可继续使用。", "success");
        return;
    }
    setAuthDialogMode("login");
    openDialog("authDialog");
}

async function handleDevLoginSubmit(event) {
    event.preventDefault();
    const submitButton = event.submitter || document.getElementById("devLoginSubmitButton");
    const mode = submitButton?.dataset.authMode === "register" ? "register" : "login";
    const errorElement = document.getElementById("devLoginError");
    if (errorElement) {
        errorElement.hidden = true;
        errorElement.textContent = "";
    }
    setButtonLoading(submitButton, true, mode === "register" ? "注册中..." : "登录中...");
    try {
        const username = getValue("devLoginUsername");
        const password = getValue("devLoginPassword");
        const endpoint = mode === "register" ? AUTH_REGISTER_API_URL : AUTH_LOGIN_API_URL;
        const body = mode === "register"
            ? {
                username,
                password,
                email: getValue("devLoginEmail"),
                display_name: getValue("devLoginNickname")
            }
            : { username, password };
        const data = await apiFetch(endpoint, {
            method: "POST",
            body: JSON.stringify(body),
            skipAuth: true
        });
        authToken = String(data?.access_token || "");
        currentUser = data?.user || null;
        saveStoredText(AUTH_TOKEN_STORAGE_KEY, authToken);
        const me = await apiFetch(AUTH_ME_API_URL);
        currentUser = me?.user || currentUser;
        applyServerProfile(me?.profile);
        renderAccountState();
        document.getElementById("authDialog")?.close();
        await restoreActiveSessionMessages({ silent: true, navigate: false });
        showToast(mode === "register" ? "注册成功，已启用长期会话。" : "登录成功，已启用长期会话。", "success");
    } catch (error) {
        if (errorElement) {
            errorElement.textContent = getErrorText(error);
            errorElement.hidden = false;
        }
    } finally {
        setButtonLoading(submitButton, false);
    }
}

function applyServerProfile(profile) {
    if (!profile || typeof profile !== "object") {
        return;
    }
    const mapped = normalizeUserProfile({
        exam_type: profile.exam_type || profile.target_exam_type || "",
        province: profile.province || "",
        city: profile.city || "",
        education: profile.education || profile.education_level || "",
        major: profile.major || "",
        identity: profile.identity || (profile.is_fresh_graduate ? "应届生" : ""),
        accept_relocation: profile.accept_relocation || "视岗位而定",
        preferences: normalizeArray(profile.preferences),
        filled_fields: normalizeArray(profile.filled_fields)
    });
    const hasServerProfile = PROFILE_TRACKED_FIELDS.some((field) => isProfileFieldFilled(mapped, field));
    if (!hasServerProfile) {
        return;
    }
    userProfile = mapped;
    saveStoredValue(PROFILE_STORAGE_KEY, userProfile);
    renderProfileForm();
    applyProfileToAnalyst();
    renderProfileSurfaces();
}

function openDialog(id) {
    const dialog = document.getElementById(id);
    if (!dialog) {
        return;
    }
    if (typeof dialog.showModal === "function") {
        dialog.showModal();
    } else {
        dialog.setAttribute("open", "");
    }
}

async function openCloudPanel(type) {
    if (!currentUser || !authToken) {
        openDialog("authDialog");
        return;
    }
    const titles = {
        sessions: ["Conversation history", "历史会话"],
        favorites: ["Saved positions", "云端收藏岗位"],
        runs: ["Agent observability", "Agent 运行记录"]
    };
    const [kicker, title] = titles[type] || titles.sessions;
    setText("cloudDialogKicker", kicker);
    setText("cloudDialogTitle", title);
    const content = document.getElementById("cloudDialogContent");
    if (content) {
        content.innerHTML = '<div class="cloud-loading">正在读取数据…</div>';
    }
    openDialog("cloudDialog");
    try {
        if (type === "sessions") {
            const data = await apiFetch(SESSIONS_API_URL);
            renderCloudSessions(data?.items);
        } else if (type === "favorites") {
            const data = await apiFetch(FAVORITES_API_URL);
            renderCloudFavorites(data?.items);
        } else {
            const data = await apiFetch(AGENT_RUNS_API_URL);
            renderCloudRuns(data?.items);
        }
    } catch (error) {
        if (content) {
            content.innerHTML = `<div class="cloud-empty error-state"><strong>读取失败</strong><p>${escapeHtml(getErrorText(error))}</p></div>`;
        }
    }
}

function renderCloudSessions(items) {
    const content = document.getElementById("cloudDialogContent");
    const sessions = normalizeArray(items);
    if (!content) {
        return;
    }
    content.innerHTML = sessions.length
        ? `<div class="cloud-list">${sessions.map((session) => `
            <button class="cloud-list-item" type="button" data-cloud-action="open-session" data-session-id="${Number(session.id)}">
                <span><strong>${escapeHtml(session.title || "未命名会话")}</strong><small>${escapeHtml(session.scene || "general_chat")} · ${Number(session.message_count || 0)} 条消息</small></span>
                <time>${escapeHtml(formatDateTime(session.last_message_at || session.updated_at))}</time>
            </button>
        `).join("")}</div>`
        : '<div class="cloud-empty"><strong>还没有历史会话</strong><p>登录后在招考分析师中提问，系统会自动保存会话。</p></div>';
}

function renderCloudFavorites(items) {
    const content = document.getElementById("cloudDialogContent");
    const favorites = normalizeArray(items);
    if (!content) {
        return;
    }
    content.innerHTML = favorites.length
        ? `<div class="cloud-list">${favorites.map((favorite) => `
            <article class="cloud-list-item static-item">
                <span><strong>${escapeHtml(favorite.job_name || favorite.job_id)}</strong><small>${escapeHtml(favorite.department_name || "招录单位未填写")} · ${escapeHtml(favorite.region || "地区未填写")}</small></span>
                <button class="danger-quiet-button compact-button" type="button" data-cloud-action="delete-favorite" data-favorite-id="${Number(favorite.id)}">移除</button>
            </article>
        `).join("")}</div>`
        : '<div class="cloud-empty"><strong>还没有云端收藏</strong><p>登录后把岗位加入备选，会同时保存为云端收藏。</p></div>';
}

function renderCloudRuns(items) {
    const content = document.getElementById("cloudDialogContent");
    const runs = normalizeArray(items);
    if (!content) {
        return;
    }
    content.innerHTML = runs.length
        ? `<div class="cloud-list">${runs.map((run) => `
            <button class="cloud-list-item" type="button" data-cloud-action="view-run" data-run-id="${Number(run.id)}">
                <span><strong>${escapeHtml(truncateText(run.question || "未命名请求", 80))}</strong><small>${escapeHtml(run.intent || "未识别意图")} · ${Number(run.tool_call_count || 0)} 次调用 · ${Number(run.latency_ms || 0)} ms</small></span>
                <time>${escapeHtml(formatDateTime(run.created_at))}</time>
            </button>
        `).join("")}</div>`
        : '<div class="cloud-empty"><strong>还没有运行记录</strong><p>每次 Agent 请求都会记录 request_id、执行状态和工具调用。</p></div>';
}

async function handleCloudAction(element) {
    const action = element.dataset.cloudAction;
    if (action === "open-session") {
        await openSavedSession(Number(element.dataset.sessionId));
    } else if (action === "delete-favorite") {
        await deleteCloudFavorite(Number(element.dataset.favoriteId));
    } else if (action === "view-run") {
        await renderRunDetail(Number(element.dataset.runId));
    }
}

async function openSavedSession(sessionId) {
    await loadSavedSession(sessionId, { navigate: true, toast: true, closeDialog: true });
}

async function restoreActiveSessionMessages(options = {}) {
    if (!authToken || !currentUser || !activeSessionId) {
        updateSessionSurface();
        return;
    }
    await loadSavedSession(activeSessionId, {
        navigate: Boolean(options.navigate),
        toast: !options.silent,
        closeDialog: false
    });
}

async function loadSavedSession(sessionId, options = {}) {
    try {
        const data = await apiFetch(`${SESSIONS_API_URL}/${sessionId}/messages`);
        const messages = normalizeArray(data?.items);
        chatHistory = [];
        currentJobContext = null;
        lastRecommendationJobs = [];
        setActiveSession(sessionId);
        const list = document.getElementById("chatMessages");
        if (list) {
            list.innerHTML = "";
        }
        messages.forEach((message) => {
            const node = appendChatMessage(message.role, message.content);
            rememberChatMessage(message.role, message.content);
            if (message.role === "assistant") {
                appendHistoricalSources(node, message.metadata_json?.citations || message.metadata_json?.sources);
            }
        });
        if (!messages.length && list) {
            list.innerHTML = createChatEmptyState();
        }
        if (options.closeDialog !== false) {
            document.getElementById("cloudDialog")?.close();
        }
        if (options.navigate) {
            navigateTo("analyst");
        }
        syncChatPromptVisibility();
        if (options.toast) {
            showToast(`已载入会话 #${sessionId}`, "success");
        }
    } catch (error) {
        setActiveSession(null);
        if (options.toast !== false) {
            showToast(getErrorText(error), "error");
        } else {
            console.warn("Restore session failed:", error);
        }
    }
}

function setActiveSession(sessionId) {
    const numericSessionId = Number(sessionId);
    activeSessionId = Number.isInteger(numericSessionId) && numericSessionId > 0
        ? numericSessionId
        : null;
    if (activeSessionId) {
        saveStoredText(ACTIVE_SESSION_STORAGE_KEY, activeSessionId);
    } else {
        removeStoredValue(ACTIVE_SESSION_STORAGE_KEY);
    }
    updateSessionSurface();
}

function updateSessionSurface() {
    const title = activeSessionId && currentUser
        ? `长期会话 #${activeSessionId}`
        : "本地临时对话";
    setText("analystSessionTitle", title);
}

function appendHistoricalSources(messageNode, sources) {
    const items = normalizeArray(sources).slice(0, 3);
    const bubble = messageNode?.querySelector(".chat-bubble");
    if (!bubble || !items.length) {
        return;
    }
    const list = document.createElement("div");
    list.className = "source-list";
    list.innerHTML = items.map((source) => `
        <div class="source-item">
            <strong>${escapeHtml(sanitizeSourceText(source.title || source.document_name, "政策资料"))}</strong>
            ${escapeHtml(sanitizeSourceText(source.snippet || source.text_preview, "历史会话引用"))}
        </div>
    `).join("");
    bubble.appendChild(list);
}

async function deleteCloudFavorite(favoriteId) {
    try {
        await apiFetch(`${FAVORITES_API_URL}/${favoriteId}`, { method: "DELETE" });
        showToast("已移除云端收藏。", "success");
        await openCloudPanel("favorites");
    } catch (error) {
        showToast(getErrorText(error), "error");
    }
}

async function renderRunDetail(runId) {
    const content = document.getElementById("cloudDialogContent");
    if (content) {
        content.innerHTML = '<div class="cloud-loading">正在读取运行详情…</div>';
    }
    try {
        const [run, toolData] = await Promise.all([
            apiFetch(`${AGENT_RUNS_API_URL}/${runId}`),
            apiFetch(`${AGENT_RUNS_API_URL}/${runId}/tool-calls`)
        ]);
        const calls = normalizeArray(toolData?.items);
        const citations = normalizeArray(run?.citations_json);
        if (content) {
            content.innerHTML = `
                <div class="run-detail">
                    <div class="run-meta-grid">
                        <div><span>request_id</span><strong>${escapeHtml(run.request_id || "暂无")}</strong></div>
                        <div><span>状态</span><strong>${escapeHtml(run.status || "未知")}</strong></div>
                        <div><span>意图</span><strong>${escapeHtml(run.intent || "未识别")}</strong></div>
                        <div><span>耗时</span><strong>${Number(run.latency_ms || 0)} ms</strong></div>
                    </div>
                    <section><h3>用户问题</h3><p>${escapeHtml(run.question || "暂无")}</p></section>
                    <section><h3>工具调用</h3>${calls.length ? calls.map((call) => `
                        <article class="tool-call-card">
                            <div><strong>${escapeHtml(call.tool_name || "系统能力")}</strong><span>${escapeHtml(call.status || "unknown")}</span></div>
                            <p>${escapeHtml(call.tool_output_summary || "无输出摘要")}</p>
                        </article>
                    `).join("") : '<p class="muted-copy">本次没有工具调用。</p>'}</section>
                    <section><h3>政策引用</h3>${citations.length ? citations.map((source) => `
                        <article class="source-item"><strong>${escapeHtml(sanitizeSourceText(source.title || source.document_name, "政策资料"))}</strong>${escapeHtml(sanitizeSourceText(source.snippet || source.text_preview, "已保存引用"))}</article>
                    `).join("") : '<p class="muted-copy">本次没有可核验政策引用。</p>'}</section>
                </div>
            `;
        }
    } catch (error) {
        if (content) {
            content.innerHTML = `<div class="cloud-empty error-state"><strong>读取失败</strong><p>${escapeHtml(getErrorText(error))}</p></div>`;
        }
    }
}

async function apiFetch(url, options = {}) {
    const { skipAuth = false, ...fetchOptions } = options;
    const headers = {
        ...(fetchOptions.body ? { "Content-Type": "application/json" } : {}),
        ...(authToken && !skipAuth ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(fetchOptions.headers || {})
    };
    const response = await fetch(url, { ...fetchOptions, headers });
    if (!response.ok) {
        throw new Error(await readResponseError(response));
    }
    return response.status === 204 ? {} : response.json();
}

function toggleQuickPromptPanel(forceOpen) {
    const panel = document.getElementById("quickPromptGroups");
    const compactRow = document.getElementById("compactPromptRow");
    if (!panel) {
        return;
    }
    const open = typeof forceOpen === "boolean" ? forceOpen : panel.hidden;
    panel.hidden = !open;
    if (compactRow) {
        compactRow.hidden = open;
    }
    document.querySelectorAll('[data-ui-action="show-all-prompts"]').forEach((button) => {
        button.setAttribute("aria-expanded", String(open));
    });
}

function toggleAnalysisFilterPanel() {
    const panel = document.getElementById("analystFilterPanel");
    const button = document.querySelector('[data-ui-action="toggle-analysis-filters"]');
    if (!panel) {
        return;
    }
    const open = panel.hidden;
    panel.hidden = !open;
    button?.setAttribute("aria-expanded", String(open));
    if (open) {
        panel.querySelector("select, input")?.focus({ preventScroll: true });
    }
}

function startAnalystPrompt(prompt, options = {}) {
    const question = String(prompt || "").trim();
    if (!question) {
        return;
    }
    if (options.navigate !== false) {
        navigateTo("analyst");
    }
    toggleQuickPromptPanel(false);
    const questionInput = document.getElementById("question");
    if (!questionInput) {
        return;
    }
    questionInput.value = question;
    resizeAnalystTextarea();
    syncAnalystSubmitState();
    questionInput.focus();
    window.requestAnimationFrame(() => {
        if (!analysisInFlight) {
            document.getElementById("analysisForm")?.requestSubmit();
        }
    });
}

function getInitialRoute() {
    const route = window.location.hash.replace(/^#\/?/, "");
    return ROUTE_TITLES[route] ? route : "overview";
}

function navigateTo(route) {
    if (!ROUTE_TITLES[route]) {
        console.warn(`未找到页面：${route}`);
        route = "overview";
    }
    renderRoute(route, { updateHash: true });
}

function renderRoute(route, options = {}) {
    const requestedRoute = ROUTE_TITLES[route] ? route : "overview";
    const targetPage = document.querySelector(`[data-page="${requestedRoute}"]`);
    if (!targetPage) {
        console.warn(`未找到页面：${requestedRoute}`);
        return;
    }
    currentRoute = requestedRoute;
    document.querySelectorAll("[data-page]").forEach((page) => {
        const active = page.dataset.page === currentRoute;
        page.hidden = !active;
        page.classList.toggle("active", active);
    });
    document.querySelectorAll(".nav-item").forEach((item) => {
        const active = item.dataset.routeTarget === currentRoute;
        item.classList.toggle("active", active);
        item.setAttribute("aria-current", active ? "page" : "false");
    });

    const mobileTitle = document.getElementById("mobilePageTitle");
    if (mobileTitle) {
        mobileTitle.textContent = ROUTE_TITLES[currentRoute];
    }
    if (options.updateHash !== false) {
        window.history.pushState(null, "", `#${currentRoute}`);
    }

    closeMobileNav();
    document.getElementById("workspaceMain")?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "smooth" });

    if (currentRoute === "shortlist") {
        renderShortlist();
    } else if (currentRoute === "compare") {
        renderCompare();
    } else if (currentRoute === "scores") {
        ensureScoreResultsLoaded();
    } else if (currentRoute === "history") {
        renderAnalysisHistory();
    } else if (currentRoute === "analyst") {
        syncAnalystSubmitState();
    }
}

function toggleSidebar() {
    const collapsed = document.body.classList.toggle("sidebar-collapsed");
    const button = document.getElementById("sidebarCollapseButton");
    button?.setAttribute("aria-label", collapsed ? "展开侧边栏" : "收起侧边栏");
    button?.setAttribute("title", collapsed ? "展开侧边栏" : "收起侧边栏");
}

function openMobileNav() {
    document.body.classList.add("mobile-nav-open");
    const scrim = document.getElementById("mobileScrim");
    if (scrim) {
        scrim.hidden = false;
    }
}

function closeMobileNav() {
    document.body.classList.remove("mobile-nav-open");
    const scrim = document.getElementById("mobileScrim");
    if (scrim) {
        scrim.hidden = true;
    }
}

function toggleContextPanel() {
    const collapsed = document.body.classList.toggle("context-collapsed");
    document.getElementById("contextPanelToggle")?.setAttribute(
        "aria-label",
        collapsed ? "展开决策侧边栏" : "收起决策侧边栏"
    );
}

async function loadAllFilterOptions() {
    try {
        const options = await fetchOptions(userProfile.province);
        populateBaseOptions(options);
    } catch (error) {
        showToast(`筛选项加载失败：${getErrorText(error)}`, "error");
        populateBaseOptions({
            provinces: ["不限", userProfile.province],
            cities: ["不限", userProfile.city],
            educations: ["不限", "大专", "本科", "硕士", "博士"],
            identities: ["不限", "应届生", "服务基层项目人员", "退役大学生士兵", "普通人员"]
        });
    }
}

async function fetchOptions(province = "不限") {
    const response = await fetch(`${OPTIONS_API_URL}?province=${encodeURIComponent(province || "不限")}`);
    if (!response.ok) {
        throw new Error(await readResponseError(response));
    }
    return response.json();
}

function populateBaseOptions(options) {
    const provinces = uniqueValues(["不限", ...normalizeArray(options?.provinces)]);
    const cities = uniqueValues(["不限", userProfile.city, ...normalizeArray(options?.cities)]);
    const educations = uniqueValues(["不限", ...normalizeArray(options?.educations)]);
    const identities = uniqueValues(["不限", ...normalizeArray(options?.identities)]);

    populateSelect("analystRegion", provinces, userProfile.province || "不限");
    populateSelect("singleJobProvince", provinces, userProfile.province || "不限");
    populateSelect("profileProvince", [PROFILE_UNSET_OPTION, ...provinces], userProfile.province || PROFILE_UNSET_OPTION);
    populateSelect("analystCity", cities, userProfile.city || "不限");
    populateSelect("profileCity", [PROFILE_UNSET_OPTION, ...cities], userProfile.city || PROFILE_UNSET_OPTION);
    populateSelect("analystEducation", educations, userProfile.education || "不限");
    populateSelect("profileEducation", [PROFILE_UNSET_OPTION, ...educations], userProfile.education || PROFILE_UNSET_OPTION);
    populateSelect("analystIdentity", identities, userProfile.identity || "不限");
    populateSelect("profileIdentity", [PROFILE_UNSET_OPTION, ...identities], userProfile.identity || PROFILE_UNSET_OPTION);

    const scoreProvince = document.getElementById("scoreProvince");
    if (scoreProvince && scoreProvince.options.length <= 1) {
        provinces
            .filter((item) => item !== "不限")
            .forEach((province) => scoreProvince.appendChild(createOption(province, province)));
    }
}

function populateSelect(id, values, selectedValue) {
    const select = document.getElementById(id);
    if (!select) {
        return;
    }
    const safeValues = uniqueValues(values.filter(Boolean));
    if (selectedValue && !safeValues.includes(selectedValue)) {
        safeValues.push(selectedValue);
    }
    select.innerHTML = "";
    safeValues.forEach((value) => select.appendChild(createOption(value, value, value === selectedValue)));
    if (safeValues.length > 0) {
        select.value = safeValues.includes(selectedValue) ? selectedValue : safeValues[0];
    }
    refreshCustomSelect(select);
}

function createOption(value, label = value, selected = false) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    option.selected = selected;
    return option;
}

async function handleAnalystProvinceChange(event) {
    await refreshCityOptions("analystCity", event.target.value, "不限");
    renderAnalysisConditionSurfaces();
}

async function handleProfileProvinceChange(event) {
    const province = event.target.value === PROFILE_UNSET_OPTION ? "不限" : event.target.value;
    try {
        const options = await fetchOptions(province);
        populateSelect(
            "profileCity",
            [PROFILE_UNSET_OPTION, "不限", ...normalizeArray(options?.cities)],
            PROFILE_UNSET_OPTION
        );
    } catch (error) {
        showToast(`城市选项加载失败：${getErrorText(error)}`, "error");
    }
}

async function refreshCityOptions(selectId, province, selectedCity) {
    try {
        const options = await fetchOptions(province);
        populateSelect(selectId, ["不限", ...normalizeArray(options?.cities)], selectedCity || "不限");
    } catch (error) {
        showToast(`城市选项加载失败：${getErrorText(error)}`, "error");
    }
}

async function loadDataCatalog() {
    setText("overviewDataStatus", "读取中");
    setText("overviewCoverageNote", "正在读取当前数据覆盖情况…");
    renderDatasetLoadingState();
    try {
        const response = await fetch(DATA_CATALOG_API_URL);
        if (!response.ok) {
            throw new Error(await readResponseError(response));
        }
        dataCatalog = await response.json();
        renderDataCatalog();
        renderCoverageSurfaces();
    } catch (error) {
        dataCatalog = null;
        setText("contextDataSummary", "数据覆盖信息暂时不可用。");
        setText("contextJobProvinceCount", "--");
        setText("contextScoreProvinceCount", "--");
        setText("contextDataYear", "--");
        setText("overviewDataStatus", "暂不可用");
        setText("overviewCoverageNote", "数据覆盖信息加载失败，可以稍后重试。");
        renderDataCatalogError();
        showToast("数据覆盖信息加载失败，可以稍后重试。", "error");
        console.error("Data catalog request failed:", error);
    }
}

function renderCoverageSurfaces() {
    if (!dataCatalog) {
        return;
    }
    const jobProvinceCount = countDatasetProvinces(getJobLikeDatasets());
    const scoreProvinceCount = countDatasetProvinces(getScoreLikeDatasets());
    setText("overviewJobProvinceCount", formatNumber(jobProvinceCount));
    setText("overviewScoreProvinceCount", formatNumber(scoreProvinceCount));
    setText("overviewYear", dataCatalog.default_year || 2025);
    setText("overviewDataStatus", "可用");
    setText("contextJobProvinceCount", formatNumber(jobProvinceCount));
    setText("contextScoreProvinceCount", formatNumber(scoreProvinceCount));
    setText("contextDataYear", dataCatalog.default_year || 2025);
    setText(
        "overviewCoverageNote",
        `已导入 ${jobProvinceCount} 个地区的职位表、${scoreProvinceCount} 个地区的历史分数参考。职位表和分数线覆盖范围可能不同。`
    );
    setText("sidebarDataYear", dataCatalog.default_year || 2025);
    setText(
        "contextDataSummary",
        `已导入 ${jobProvinceCount} 个职位表地区和 ${scoreProvinceCount} 个分数线地区，默认展示 ${dataCatalog.default_year || 2025} 年数据。`
    );
}

function renderDataCatalog() {
    if (!dataCatalog) {
        return;
    }
    setText("dataProvinceCount", formatNumber(dataCatalog.province_count));
    setText("dataJobRecordCount", formatNumber(dataCatalog.job_record_count));
    setText("dataScoreRecordCount", formatNumber(dataCatalog.score_record_count));
    setText("dataReviewRecordCount", formatNumber(dataCatalog.review_record_count));
    setText("dataDefaultYear", dataCatalog.default_year || 2025);

    renderDatasetGroups(dataCatalog.dataset_groups || buildDatasetGroupsFromCatalog(dataCatalog));

    const scoreProvince = document.getElementById("scoreProvince");
    if (scoreProvince) {
        const selected = scoreProvince.value;
        scoreProvince.innerHTML = '<option value="">全部已导入省份</option>';
        uniqueValues(getScoreLikeDatasets().map((dataset) => dataset.province))
            .filter(Boolean)
            .forEach((province) => {
                scoreProvince.appendChild(createOption(province, province));
            });
        scoreProvince.value = Array.from(scoreProvince.options).some((option) => option.value === selected)
            ? selected
            : "";
        refreshCustomSelect(scoreProvince);
    }
}

function renderDatasetLoadingState() {
    Object.values(DATASET_GROUP_CONTAINER_IDS).forEach((id) => {
        const container = document.getElementById(id);
        if (container) {
            container.innerHTML = `
                <div class="dataset-skeleton" aria-label="正在读取数据"></div>
                <div class="dataset-skeleton" aria-hidden="true"></div>
            `;
        }
    });
}

function renderDataCatalogError() {
    const errorPanel = createErrorState(
        "数据覆盖暂时无法读取",
        "可以稍后重试。职位表和分数线数据本身不会因此被修改。",
        "重新加载",
        "retry-data-catalog"
    );
    Object.values(DATASET_GROUP_CONTAINER_IDS).forEach((id) => {
        const container = document.getElementById(id);
        if (container) {
            container.innerHTML = errorPanel;
        }
    });
}

function renderDatasetGroups(groups) {
    const normalizedGroups = normalizeArray(groups);
    Object.values(DATASET_GROUP_CONTAINER_IDS).forEach((id) => renderDatasetList(id, []));
    normalizedGroups.forEach((group) => {
        const containerId = DATASET_GROUP_CONTAINER_IDS[group?.key];
        if (!containerId) {
            return;
        }
        renderDatasetList(containerId, group.items);
    });
}

function buildDatasetGroupsFromCatalog(catalog) {
    const groups = {
        jobs: [],
        scores: [],
        reviews: [],
        other: []
    };
    const datasets = normalizeArray(catalog?.database_datasets);
    const fallbackDatasets = datasets.length
        ? datasets
        : [
            ...normalizeArray(catalog?.job_datasets),
            ...normalizeArray(catalog?.score_datasets),
            ...normalizeArray(catalog?.review_datasets),
            ...normalizeArray(catalog?.imported_datasets)
        ];
    fallbackDatasets.forEach((dataset) => {
        const key = getDatasetGroupKey(dataset);
        if (groups[key]) {
            groups[key].push(dataset);
        }
    });
    return Object.entries(groups).map(([key, items]) => ({ key, items }));
}

function getDatasetGroupKey(dataset) {
    const dataType = String(dataset?.data_type || "");
    const kind = String(dataset?.kind || "");
    const targetTable = String(dataset?.target_table || "");
    if (dataType === "job_table" || kind === "jobs" || targetTable === "exam_jobs") {
        return "jobs";
    }
    if (["score_line_table", "candidate_score_table"].includes(dataType)) {
        return "scores";
    }
    if (["scores", "candidate_scores"].includes(kind)) {
        return "scores";
    }
    if (["exam_score_lines", "exam_candidate_scores"].includes(targetTable)) {
        return "scores";
    }
    if (dataType === "review_candidate_list" || kind === "review_candidates" || targetTable === "exam_review_candidates") {
        return "reviews";
    }
    return "other";
}

function countDatasetProvinces(datasets) {
    return new Set(
        normalizeArray(datasets)
            .map((dataset) => String(dataset?.province || "").trim())
            .filter(Boolean)
    ).size;
}

function getScoreLikeDatasets() {
    if (!dataCatalog) {
        return [];
    }
    return normalizeArray(dataCatalog.score_datasets);
}

function getJobLikeDatasets() {
    if (!dataCatalog) {
        return [];
    }
    return normalizeArray(dataCatalog.job_datasets);
}

function renderDatasetList(id, datasets) {
    const container = document.getElementById(id);
    if (!container) {
        return;
    }
    const items = normalizeArray(datasets).filter((dataset) => {
        if (Number(dataset?.record_count || 0) <= 0) {
            return false;
        }
        if (!isValidCatalogYear(dataset?.year)) {
            console.warn(`跳过非法年份数据集：${dataset?.year}`, dataset);
            return false;
        }
        return true;
    });
    container.innerHTML = items.length
        ? items.map((dataset) => {
            const title = sanitizeSourceText(dataset.title, `${dataset.year || 2025} 年${dataset.province || "当前地区"}招考数据`);
            const datasetId = dataset.dataset_id || "";
            const viewButton = canViewDataset(dataset)
                ? `<button class="quiet-button compact-button dataset-view-button" type="button" data-ui-action="view-dataset-data" data-dataset-id="${escapeHtml(datasetId)}" data-dataset-title="${escapeHtml(title)}" aria-label="查看${escapeHtml(title)}的数据库明细">查看数据</button>`
                : "";
            const deleteButton = canDeleteDataset(dataset)
                ? `<button class="danger-quiet-button compact-button" type="button" data-ui-action="delete-database-dataset" data-dataset-id="${escapeHtml(datasetId)}" data-source-kind="${escapeHtml(dataset.source_kind || "")}" aria-label="删除${escapeHtml(title)}">删除</button>`
                : "";
            return `
            <article class="dataset-item">
                <div>
                    <strong>${escapeHtml(title)}</strong>
                    <span>${escapeHtml(formatDatasetMeta(dataset))}</span>
                </div>
                <div class="dataset-actions">
                    <span class="badge success">${escapeHtml(dataset.status || "可用")}</span>
                    ${viewButton}
                    ${deleteButton}
                </div>
            </article>
        `;
        }).join("")
        : '<div class="empty-state compact-empty"><strong>暂无已导入数据</strong><p>当前目录中还没有可展示的数据集。</p></div>';
}

function canViewDataset(dataset) {
    return Boolean(
        String(dataset?.dataset_id || "").trim()
        && dataset?.storage === "database"
    );
}

function canDeleteDataset(dataset) {
    const datasetId = String(dataset?.dataset_id || "").trim();
    return Boolean(
        datasetId
        && dataset?.storage === "database"
    );
}

function formatDatasetMeta(dataset) {
    const sourceKind = dataset?.source_kind || dataset?.origin;
    const sourceLabels = {
        builtin_seed: "内置种子",
        imported: "导入",
        migrated: "迁移"
    };
    const sourceLabel = sourceLabels[sourceKind] || "";
    const sourceDisplayName = dataset?.source_display_name || "";
    return [
        dataset?.province,
        isValidCatalogYear(dataset?.year) ? `${dataset.year} 年` : "",
        dataset?.exam_type,
        dataset?.data_type_label || dataset?.data_type || dataset?.kind,
        `${formatNumber(dataset?.record_count)} 条记录`,
        dataset?.storage ? `存储：${dataset.storage}` : "",
        sourceLabel ? `来源：${sourceLabel}` : "",
        sourceDisplayName ? `数据说明：${sourceDisplayName}` : ""
    ].filter(Boolean).join(" · ");
}

function isValidCatalogYear(value) {
    const year = Number(value);
    return Number.isInteger(year) && year >= 1900 && year <= 2100;
}

function renderProfileForm() {
    setValue("profileExamType", userProfile.exam_type || "");
    setValue("profileMajor", userProfile.major);
    setValue("profileRelocation", userProfile.accept_relocation);
    document.querySelectorAll('input[name="preferences"]').forEach((input) => {
        input.checked = normalizeArray(userProfile.preferences).includes(input.value);
    });
}

function normalizeUserProfile(profile) {
    const normalized = {
        ...DEFAULT_PROFILE,
        ...(profile && typeof profile === "object" ? profile : {})
    };
    normalized.preferences = normalizeArray(normalized.preferences);
    const storedFilledFields = normalizeArray(normalized.filled_fields)
        .filter((field) => PROFILE_TRACKED_FIELDS.includes(field));
    normalized.filled_fields = storedFilledFields.length > 0
        ? storedFilledFields
        : PROFILE_TRACKED_FIELDS.filter((field) => {
            const value = String(normalized[field] || "").trim();
            return Boolean(value && !["不限", "未设置", PROFILE_UNSET_OPTION, "请选择"].includes(value));
        });
    return normalized;
}

function readProfileFormValue(id) {
    const value = getValue(id);
    return value === PROFILE_UNSET_OPTION ? "" : value;
}

function applyProfileToAnalyst() {
    setValue("analystExamType", userProfile.exam_type || "省考");
    setValue("analystRegion", userProfile.province || "不限");
    setValue("analystCity", userProfile.city || "不限");
    setValue("analystEducation", userProfile.education || "不限");
    setValue("analystMajor", userProfile.major);
    setValue("analystIdentity", userProfile.identity || "不限");
    setValue("singleJobProvince", userProfile.province || "不限");
    renderAnalysisConditionSurfaces();
}

async function handleProfileSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submitButton = form.querySelector('button[type="submit"]');
    userProfile = {
        exam_type: readProfileFormValue("profileExamType"),
        province: readProfileFormValue("profileProvince"),
        city: readProfileFormValue("profileCity"),
        education: readProfileFormValue("profileEducation"),
        major: getValue("profileMajor"),
        identity: readProfileFormValue("profileIdentity"),
        accept_relocation: getValue("profileRelocation") || "视岗位而定",
        preferences: Array.from(form.querySelectorAll('input[name="preferences"]:checked'))
            .map((input) => input.value),
        filled_fields: []
    };
    userProfile.filled_fields = PROFILE_TRACKED_FIELDS.filter((field) => String(userProfile[field] || "").trim());
    if (!saveStoredValue(PROFILE_STORAGE_KEY, userProfile)) {
        showToast("画像保存失败，请检查浏览器存储权限后重试。", "error");
        return;
    }
    applyProfileToAnalyst();
    renderProfileSurfaces();
    const status = document.getElementById("profileSaveStatus");
    if (status) {
        status.textContent = `已于 ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })} 保存。`;
    }
    if (!currentUser || !authToken) {
        showToast("报考画像已保存到当前浏览器，并同步到招考分析师。", "success");
        return;
    }
    setButtonLoading(submitButton, true, "同步中…");
    try {
        const data = await apiFetch(USER_PROFILE_API_URL, {
            method: "PUT",
            body: JSON.stringify({
                education_level: userProfile.education,
                major: userProfile.major,
                is_fresh_graduate: userProfile.identity.includes("应届"),
                target_region: `${userProfile.province || ""}${userProfile.city || ""}`,
                target_exam_type: userProfile.exam_type,
                work_preference: `异地意愿：${userProfile.accept_relocation}`,
                province: userProfile.province,
                city: userProfile.city,
                exam_type: userProfile.exam_type,
                education: userProfile.education,
                identity: userProfile.identity,
                accept_relocation: userProfile.accept_relocation,
                preferences: userProfile.preferences,
                filled_fields: userProfile.filled_fields
            })
        });
        applyServerProfile(data?.profile);
        if (status) {
            status.textContent = "画像已保存到浏览器并同步到当前账号。";
        }
        showToast("报考画像已同步到当前账号。", "success");
    } catch (error) {
        showToast(`本地画像已保存，云端同步失败：${getErrorText(error)}`, "error");
    } finally {
        setButtonLoading(submitButton, false);
    }
}

function renderProfileSurfaces() {
    const overviewEntries = [
        ["exam_type", "考试"],
        ["province", "省份"],
        ["education", "学历"],
        ["major", "专业"],
        ["identity", "身份"]
    ];
    const contextEntries = [
        ["province", "省份"],
        ["education", "学历"],
        ["major", "专业"],
        ["identity", "身份"],
        ["exam_type", "考试类型"]
    ];
    const profileState = getProfileState(userProfile);
    const complete = profileState.status === "complete";
    const hasDetails = profileState.filledFields.length > 0;
    const summary = buildProfileSummary(userProfile);
    const overview = document.getElementById("overviewProfileChips");
    if (overview) {
        overview.innerHTML = hasDetails
            ? overviewEntries
                .filter(([field]) => isProfileFieldFilled(userProfile, field))
                .map(([field, label]) => `<span class="profile-chip">${escapeHtml(label)}<strong>${escapeHtml(formatProfileFieldValue(userProfile, field))}</strong></span>`)
                .join("")
            : "";
    }
    setText(
        "overviewProfileState",
        profileState.status === "complete"
            ? `画像已完善。${summary}`
            : (profileState.status === "partial"
                ? `画像部分完善。已填写：${profileState.filledLabels.join("、")}；待补充：${profileState.missingLabels.join("、")}。`
                : "未填写画像。完善后可以直接按画像推荐岗位。")
    );
    setText("overviewProfileAction", complete ? "编辑画像" : "完善画像");
    setText(
        "analystProfileSummaryText",
        hasDetails
            ? `${profileState.label} · ${summary}`
            : profileState.label
    );
    setText("analystProfileAction", complete ? "编辑画像" : "完善画像");

    const context = document.getElementById("contextProfile");
    if (context) {
        context.innerHTML = hasDetails
            ? `
                <div class="context-empty">
                    <strong>${escapeHtml(profileState.label)}</strong>
                    ${profileState.missingLabels.length ? `<p>待补充：${escapeHtml(profileState.missingLabels.join("、"))}</p>` : ""}
                </div>
                ${contextEntries
            .filter(([field]) => isProfileFieldFilled(userProfile, field))
            .map(([field, label]) => `
                <div class="context-profile-row">
                    <span>${escapeHtml(label)}</span>
                    <strong>${escapeHtml(formatProfileFieldValue(userProfile, field))}</strong>
                </div>
            `)
            .join("")}`
            : `
                <div class="context-empty">
                    <strong>未填写画像</strong>
                    <p>填写省份、学历、专业和身份后，分析师可以减少重复追问。</p>
                    <button type="button" data-route-target="profile">去完善</button>
                </div>
            `;
    }
    setText("sidebarProvince", isProfileFieldFilled(userProfile, "province") ? userProfile.province : "未设置");
    renderAnalysisConditionSurfaces();
    updateDecisionGuidance();
}

function isProfileComplete(profile) {
    return PROFILE_CORE_FIELDS.every((field) => isProfileFieldFilled(profile, field));
}

function getProfileState(profile) {
    const filledFields = PROFILE_CORE_FIELDS.filter((field) => isProfileFieldFilled(profile, field));
    const missingFields = PROFILE_CORE_FIELDS.filter((field) => !filledFields.includes(field));
    const status = filledFields.length === 0
        ? "empty"
        : (missingFields.length === 0 ? "complete" : "partial");
    return {
        status,
        label: status === "empty" ? "未填写画像" : (status === "partial" ? "画像部分完善" : "画像已完善"),
        filledFields,
        missingFields,
        filledLabels: filledFields.map((field) => formatProfileFieldValue(profile, field)),
        missingLabels: missingFields.map((field) => PROFILE_FIELD_LABELS[field])
    };
}

function isProfileFieldFilled(profile, field) {
    const text = String(profile?.[field] || "").trim();
    if (!text || ["未设置", PROFILE_UNSET_OPTION, "请选择"].includes(text)) {
        return false;
    }
    if (text !== "不限") {
        return true;
    }
    return normalizeArray(profile?.filled_fields).includes(field);
}

function hasMeaningfulProfileValue(value) {
    const text = String(value || "").trim();
    return Boolean(text && !["不限", "未设置", "请选择"].includes(text));
}

function formatProfileValue(value) {
    return hasMeaningfulProfileValue(value) ? String(value).trim() : "未设置";
}

function formatProfileFieldValue(profile, field) {
    return isProfileFieldFilled(profile, field) ? String(profile?.[field] || "").trim() : "未填写";
}

function buildProfileSummary(profile) {
    return ["province", "exam_type", "education", "major", "identity"]
        .filter((field) => isProfileFieldFilled(profile, field))
        .map((field) => formatProfileFieldValue(profile, field))
        .join(" · ") || "未填写画像";
}

function getCurrentAnalysisFilters() {
    return {
        exam_type: getValue("analystExamType") || userProfile.exam_type || "省考",
        province: getValue("analystRegion") || "不限",
        city: getValue("analystCity") || "不限",
        education: getValue("analystEducation") || "不限",
        major: getValue("analystMajor") || "不限",
        identity: getValue("analystIdentity") || "不限"
    };
}

function renderAnalysisConditionSurfaces() {
    const filters = getCurrentAnalysisFilters();
    const entries = [
        ["考试类型", filters.exam_type],
        ["省份", filters.province],
        ["城市", filters.city],
        ["学历", filters.education],
        ["专业", filters.major || "不限"],
        ["身份", filters.identity]
    ];
    const context = document.getElementById("contextFilterSummary");
    if (context) {
        context.innerHTML = entries.map(([label, value]) => `
            <div class="context-profile-row">
                <span>${escapeHtml(label)}</span>
                <strong>${escapeHtml(value || "不限")}</strong>
            </div>
        `).join("");
    }

    const profileState = getProfileState(userProfile);
    const profileComplete = profileState.status === "complete";
    const same = profileComplete && areProfileAndFiltersEqual(userProfile, filters);
    setText(
        "analystCurrentFilterSummary",
        [
            hasMeaningfulProfileValue(filters.province) ? filters.province : "不限省份",
            hasMeaningfulProfileValue(filters.city) ? filters.city : "不限城市",
            hasMeaningfulProfileValue(filters.education) ? filters.education : "不限学历",
            hasMeaningfulProfileValue(filters.major) ? filters.major : "不限专业",
            hasMeaningfulProfileValue(filters.identity) ? filters.identity : "不限身份"
        ].join(" · ")
    );
    const statusText = profileState.status === "empty"
        ? "未填写画像 · 当前按本次筛选条件分析"
        : (profileState.status === "partial"
        ? "画像部分完善 · 本次分析优先使用当前条件"
        : (same
            ? "当前分析条件与我的画像一致"
            : "本次条件与画像不一致，将优先使用当前筛选条件"));
    ["analystConditionStatus", "contextFilterMatch"].forEach((id) => {
        const element = document.getElementById(id);
        if (!element) {
            return;
        }
        element.textContent = statusText;
        element.classList.toggle("is-match", same);
        element.classList.toggle("is-different", profileComplete && !same);
        element.classList.toggle("is-incomplete", !profileComplete);
    });
}

function renderRecognizedConditions(payload = null) {
    const location = payload?.location_preference || {};
    const items = [];
    if (location.city) {
        items.push(location.city);
    }
    const resultLimit = Number(payload?.result_limit);
    if (Number.isFinite(resultLimit) && resultLimit > 0 && resultLimit < 5) {
        items.push(`推荐 ${resultLimit} 个`);
    }
    let text = items.length ? `本轮识别条件：${items.join(" · ")}` : "";
    if (text && location.nearby && location.city) {
        text += `。当前未接入地理距离数据，先按${location.city}及${location.province || "同省"}区内岗位筛选。`;
    }
    ["analystRecognizedConditions", "contextRecognizedConditions"].forEach((id) => {
        const element = document.getElementById(id);
        if (!element) {
            return;
        }
        element.textContent = text;
        element.hidden = !text;
    });
}

function areProfileAndFiltersEqual(profile, filters) {
    const pairs = [
        [profile.exam_type, filters.exam_type],
        [profile.province, filters.province],
        [profile.city, filters.city],
        [profile.education, filters.education],
        [profile.major, filters.major],
        [profile.identity, filters.identity]
    ];
    return pairs.every(([profileValue, filterValue]) => normalizeComparableValue(profileValue) === normalizeComparableValue(filterValue));
}

function normalizeComparableValue(value) {
    return String(value || "").trim().toLowerCase();
}

async function handleAnalystSubmit(event) {
    event.preventDefault();
    if (analysisInFlight) {
        stopCurrentGeneration();
        return;
    }

    const question = getValue("question");
    if (!question) {
        showToast("请先输入要咨询的问题。", "error");
        document.getElementById("question")?.focus();
        return;
    }

    const submitButton = document.getElementById("analyzeButton");
    if (submitButton?.disabled) {
        return;
    }

    analysisInFlight = true;
    const requestId = ++currentRequestId;
    const abortController = new AbortController();
    currentAbortController = abortController;
    const payload = buildAnalystPayload(question);
    renderRecognizedConditions(payload);
    payload.messages = [...chatHistory, { role: "user", content: question }].slice(-CHAT_CONTEXT_LIMIT);
    addAnalysisHistoryRecord({
        type: "chat",
        title: "向招考分析师提问",
        summary: question,
        question,
        province: payload.region,
        year: dataCatalog?.default_year || 2025,
        status: "已发送"
    });
    appendChatMessage("user", question);
    rememberChatMessage("user", question);
    syncChatPromptVisibility();
    setValue("question", "");
    resizeAnalystTextarea();

    const pendingMessage = appendChatLoadingMessage(question);
    currentPendingMessage = pendingMessage;
    setAnalystInputDisabled(true);
    setSendButtonState("loading");
    document.getElementById("analysisForm")?.setAttribute("aria-busy", "true");

    try {
        const data = await postAnalyze(payload, { signal: abortController.signal });
        if (requestId !== currentRequestId) {
            return;
        }
        renderAnalystResponse(pendingMessage, data, payload);
    } catch (error) {
        if (requestId !== currentRequestId || error?.name === "AbortError") {
            return;
        }
        setValue("question", question);
        resizeAnalystTextarea();
        replaceChatMessage(
            pendingMessage,
            `
                <div class="message-error" role="alert">
                    <strong>这次分析失败了，可以稍后重试，或换一种问法。</strong>
                    <p>你的问题已经保留在输入框中，可以修改后再次发送。</p>
                    <button class="quiet-button" type="button" data-ui-action="focus-analyst-input">编辑后重试</button>
                </div>
            `
        );
        showToast("这次分析失败了，可以稍后重试。", "error");
        addAnalysisHistoryRecord({
            type: "error",
            title: "分析请求失败",
            summary: "这次分析没有完成，可以稍后重试或换一种问法。",
            question,
            related_position_code: extractPositionCodeFromText(question),
            province: payload.region,
            year: dataCatalog?.default_year || 2025,
            status: "失败"
        });
        console.error("Analyst request failed:", error);
    } finally {
        if (requestId !== currentRequestId) {
            return;
        }
        analysisInFlight = false;
        currentAbortController = null;
        currentPendingMessage = null;
        document.getElementById("analysisForm")?.removeAttribute("aria-busy");
        setAnalystInputDisabled(false);
        syncAnalystSubmitState();
    }
}

function stopCurrentGeneration() {
    if (!analysisInFlight) {
        return;
    }

    currentRequestId += 1;
    currentAbortController?.abort();
    currentAbortController = null;
    analysisInFlight = false;
    document.getElementById("analysisForm")?.removeAttribute("aria-busy");
    setAnalystInputDisabled(false);

    if (currentPendingMessage) {
        replaceChatMessage(
            currentPendingMessage,
            '<p class="generation-stopped" role="status">已停止本次生成。</p>'
        );
    }
    currentPendingMessage = null;
    syncAnalystSubmitState();
    document.getElementById("question")?.focus();
}

function setAnalystInputDisabled(disabled) {
    const input = document.getElementById("question");
    if (input) {
        input.disabled = Boolean(disabled);
    }
}

function buildAnalystPayload(question) {
    const currentFilters = getCurrentAnalysisFilters();
    const contextPreference = inferAnalysisContextPreference(question);
    const selectedFilters = contextPreference === "profile"
        ? {
            exam_type: userProfile.exam_type || "省考",
            province: userProfile.province || "不限",
            city: userProfile.city || "不限",
            education: userProfile.education || "不限",
            major: userProfile.major || "",
            identity: userProfile.identity || "不限"
        }
        : { ...currentFilters };
    const questionLocation = inferQuestionLocationPreference(question);
    if (questionLocation.province) {
        selectedFilters.province = questionLocation.province;
    }
    if (questionLocation.city) {
        selectedFilters.city = questionLocation.city;
    }
    const examType = selectedFilters.exam_type || "省考";
    const isInstitution = examType === "事业单位";
    return {
        mode: isPolicyQuestion(question)
            ? "policy_qa"
            : (isJobRecommendationQuestion(question) ? "job_recommendation" : "analyst"),
        target: isInstitution ? "事业编" : "公务员",
        exam_type: isInstitution ? "" : examType,
        region: selectedFilters.province || "不限",
        city: selectedFilters.city || "不限",
        education: selectedFilters.education || "不限",
        major: selectedFilters.major || "不限",
        identity: selectedFilters.identity || "不限",
        question,
        result_limit: inferResultLimit(question),
        session_id: activeSessionId,
        save_history: Boolean(currentUser && authToken),
        profile: { ...userProfile },
        current_filters: currentFilters,
        context_preference: contextPreference,
        location_preference: questionLocation,
        current_job: currentJobContext ? buildCurrentJobPayload(currentJobContext) : null,
        last_recommendations: lastRecommendationJobs
            .slice(0, 5)
            .map(buildCurrentJobPayload)
    };
}

function buildCurrentJobPayload(rawJob) {
    const job = normalizeJob(rawJob);
    return {
        position_code: job.position_code,
        job_title: job.position_name,
        department: job.department,
        unit_name: job.unit_name,
        province: job.province,
        region: job.region || job.province,
        city: job.city,
        year: job.year,
        exam_type: job.exam_type,
        recruit_count: job.recruit_count,
        education_requirement: job.education,
        degree_requirement: job.degree_requirement,
        major_requirement: job.major_required,
        identity_requirement: job.identity_required,
        political_requirement: job.political_requirement,
        grassroots_requirement: job.grassroots_requirement,
        qualification_requirement: job.qualification_requirement,
        agency_level: job.agency_level,
        is_public_service: job.is_public_service,
        is_law_enforcement: job.is_law_enforcement,
        job_description: job.job_description,
        contact_phone: job.contact_phone,
        work_address: job.work_address,
        remark: job.remark,
        min_score: job.score_min,
        avg_score: job.avg_score,
        max_score: job.max_score,
        score_match_type: job.score_match_type,
        score_match_confidence: job.score_confidence,
        score_match_reason: job.score_match_reason,
        registration_count: job.applicant_count,
        competition_ratio: job.competition_ratio,
        interview_count: job.interview_count,
        notes: job.notes,
        data_source_label: job.data_source_label,
        score_data_source_label: job.score_data_source_label,
        score_source_type: job.score_source_type,
        score_sample_count: job.score_sample_count,
        review_score_sample: job.review_score_sample,
        candidate_score_sample: job.candidate_score_sample,
        candidate_score_sample_count: job.candidate_score_sample_count,
        review_written_score_min: job.review_written_score_min,
        review_written_score_avg: job.review_written_score_avg,
        review_written_score_max: job.review_written_score_max,
        review_xingce_score_min: job.review_xingce_score_min,
        review_xingce_score_avg: job.review_xingce_score_avg,
        review_xingce_score_max: job.review_xingce_score_max,
        review_shenlun_score_min: job.review_shenlun_score_min,
        review_shenlun_score_avg: job.review_shenlun_score_avg,
        review_shenlun_score_max: job.review_shenlun_score_max,
        review_professional_score_min: job.review_professional_score_min,
        review_professional_score_avg: job.review_professional_score_avg,
        review_professional_score_max: job.review_professional_score_max,
        review_total_score_min: job.review_total_score_min,
        review_total_score_avg: job.review_total_score_avg,
        review_total_score_max: job.review_total_score_max,
        review_rank_min: job.review_rank_min,
        review_rank_max: job.review_rank_max,
        candidate_written_score_min: job.candidate_written_score_min,
        candidate_written_score_avg: job.candidate_written_score_avg,
        candidate_written_score_max: job.candidate_written_score_max,
        candidate_interview_score_min: job.candidate_interview_score_min,
        candidate_interview_score_avg: job.candidate_interview_score_avg,
        candidate_interview_score_max: job.candidate_interview_score_max,
        candidate_total_score_min: job.candidate_total_score_min,
        candidate_total_score_avg: job.candidate_total_score_avg,
        candidate_total_score_max: job.candidate_total_score_max,
        candidate_rank_min: job.candidate_rank_min,
        candidate_rank_max: job.candidate_rank_max
    };
}

function inferAnalysisContextPreference(question) {
    const text = String(question || "").replace(/\s+/g, "");
    if (/(按我的画像|根据我的画像|用我的画像)/.test(text)) {
        return "profile";
    }
    if (/(按当前条件|当前筛选|已经筛选好|筛选好了|按我选的条件)/.test(text)) {
        return "current_filters";
    }
    if (/(北京|天津|上海|重庆|河北|山西|辽宁|吉林|黑龙江|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|四川|贵州|云南|陕西|甘肃|青海|宁夏|新疆|西藏|内蒙古|本科|硕士|博士|应届生|服务基层项目人员)/.test(text)) {
        return "question";
    }
    return "current_filters_then_profile";
}

function isPolicyQuestion(question) {
    return /(应届生身份|服务基层项目人员|专业目录|资格审查|资格复审|基层工作经历|基层经历|政策|报考指南|人民警察岗位.*特殊要求|人民警察.*体检|人民警察.*体测)/.test(String(question || ""));
}

function isJobRecommendationQuestion(question) {
    return /(推荐|筛选|筛岗位|找岗位|能报哪些|能报什么|可报岗位|附近的?岗位|附近的?$|周边的?岗位)/.test(String(question || ""));
}

function inferQuestionLocationPreference(question) {
    const text = String(question || "").replace(/\s+/g, "");
    if (/南宁/.test(text)) {
        return {
            province: "广西",
            city: "南宁",
            nearby: /(附近|周边|就近|离.*近)/.test(text)
        };
    }
    return { province: "", city: "", nearby: false };
}

async function postAnalyze(payload, options = {}) {
    const response = await fetch(API_URL, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...(authToken ? { Authorization: `Bearer ${authToken}` } : {})
        },
        body: JSON.stringify(payload),
        signal: options.signal
    });
    if (!response.ok) {
        throw new Error(await readResponseError(response));
    }
    return response.json();
}

function renderAnalystResponse(messageNode, data, payload) {
    const answer = sanitizeUserFacingText(data?.analysis_report || data?.summary)
        || "当前没有生成有效回答，请换一种说法再试。";
    const resultLimit = Math.max(1, Math.min(Number(payload?.result_limit) || 5, 5));
    const responseCount = Number(data?.recommendation_count);
    const displayLimit = Number.isFinite(responseCount) && responseCount > 0
        ? Math.min(resultLimit, responseCount)
        : resultLimit;
    const jobs = shouldDisplayJobs(data)
        ? getStructuredResponseJobs(data).slice(0, displayLimit)
        : [];
    const isContextFollowup = Boolean(data?.is_context_followup);
    if (jobs.length > 0) {
        lastRecommendationJobs = jobs.map(normalizeJob);
        currentJobContext = lastRecommendationJobs[0] || currentJobContext;
    }
    if (jobs.length > 0 && !isContextFollowup) {
        replaceChatMessage(messageNode, createRecommendationResponse(jobs, answer, data, payload));
    } else {
        replaceChatMessage(messageNode, renderMarkdown(answer));
    }
    rememberChatMessage("assistant", answer);
    if (jobs.length > 0 && data?.intent === "job_recommendation") {
        renderRecognizedConditions({
            ...payload,
            result_limit: jobs.length
        });
    }

    const policyResponse = isPolicyResponse(data, payload);
    const citationSource = normalizeArray(data?.citations).length
        ? data.citations
        : data?.sources;
    const sources = normalizeArray(citationSource).slice(0, 3);
    const hasPolicyEvidence = sources.length > 0;
    if (policyResponse || hasPolicyEvidence) {
        const sourceList = document.createElement("div");
        sourceList.className = "source-list";
        sourceList.innerHTML = sources.length
            ? sources.map((source) => `
                <div class="source-item">
                    <strong>${escapeHtml(sanitizeSourceText(source.title || source.source_type, "政策资料"))}</strong>
                    ${escapeHtml(sanitizeSourceText(source.snippet, "已作为本次回答的参考依据。"))}
                </div>
            `).join("")
            : `
                <div class="source-item">
                    <strong>通用解释</strong>
                    当前没有检索到可核验的政策来源，本回答仅供理解参考。
                </div>
            `;
        messageNode.querySelector(".chat-bubble")?.appendChild(sourceList);
    }
    if (policyResponse || hasPolicyEvidence) {
        const reminder = document.createElement("div");
        reminder.className = "policy-official-reminder";
        reminder.setAttribute("role", "note");
        reminder.innerHTML = "<strong>报考提醒</strong>具体以官方公告、职位表和资格审查为准。";
        messageNode.querySelector(".chat-bubble")?.appendChild(reminder);
    }
    appendAnalysisDisclaimer(messageNode);
    if (data?.session_id) {
        setActiveSession(Number(data.session_id));
    }
    appendRunMetadata(messageNode, data);
    if (jobs.length > 0 && /分析/.test(String(payload?.question || ""))) {
        jobs.forEach((job) => analyzedJobKeys.add(getJobKey(job)));
        updateDecisionCounts();
    }
    recordAnalystResult({
        answer,
        data,
        payload,
        jobs,
        policyResponse
    });
    scrollChatToBottom();
}

function appendRunMetadata(messageNode, data) {
    const bubble = messageNode?.querySelector(".chat-bubble");
    const runId = data?.agent_run_id;
    const requestId = String(data?.request_id || "").trim();
    const toolCount = uniqueValues(normalizeArray(data?.used_tools).filter(Boolean)).length;
    const dataSourceCount = getResponseDataSourceCount(data);
    if (!bubble || (!runId && !requestId)) {
        return;
    }
    const details = document.createElement("details");
    details.className = "run-debug-details";
    details.innerHTML = `
        <summary>
            <span>运行详情</span>
            ${runId ? `<small>运行 #${escapeHtml(runId)}</small>` : ""}
        </summary>
        <div class="run-debug-content">
            <dl class="run-debug-meta">
                ${runId ? `<div><dt>运行编号</dt><dd>#${escapeHtml(runId)}</dd></div>` : ""}
                ${requestId ? `<div><dt>request_id</dt><dd>${escapeHtml(requestId)}</dd></div>` : ""}
                ${toolCount > 0 ? `<div><dt>使用工具</dt><dd>${toolCount} 个</dd></div>` : ""}
                ${dataSourceCount > 0 ? `<div><dt>数据来源</dt><dd>${dataSourceCount} 个</dd></div>` : ""}
            </dl>
        ${normalizeArray(data?.persistence_warnings).length
            ? `<p class="run-warning">${escapeHtml(data.persistence_warnings.join("；"))}</p>`
            : ""}
        </div>
    `;
    bubble.appendChild(details);
}

function getResponseDataSourceCount(data) {
    const sourceKeys = new Set();
    const citations = normalizeArray(data?.citations).length
        ? normalizeArray(data.citations)
        : normalizeArray(data?.sources);
    citations.forEach((source, index) => {
        const label = String(source?.title || source?.source_type || "").trim();
        sourceKeys.add(label || `citation-${index + 1}`);
    });
    getStructuredResponseJobs(data).forEach((rawJob) => {
        const job = normalizeJob(rawJob);
        const jobSource = friendlyJobSource(job);
        if (jobSource) {
            sourceKeys.add(`job:${jobSource}`);
        }
        if (String(job.score_source_type || "none") !== "none") {
            const scoreSource = friendlyScoreSource(job);
            if (scoreSource) {
                sourceKeys.add(`score:${scoreSource}`);
            }
        }
    });
    return sourceKeys.size;
}

function createAnalysisDisclaimerMarkup() {
    return `
        <aside class="analysis-disclaimer analysis-result-disclaimer" role="note" aria-label="AI 分析使用说明">
            <span class="analysis-disclaimer-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 10v6M12 7h.01"/></svg>
            </span>
            <p>${escapeHtml(ANALYSIS_DISCLAIMER_TEXT)}</p>
        </aside>
    `;
}

function appendAnalysisDisclaimer(messageNode) {
    const bubble = messageNode?.querySelector(".chat-bubble");
    if (!bubble || bubble.querySelector(".analysis-result-disclaimer")) {
        return;
    }
    bubble.insertAdjacentHTML("beforeend", createAnalysisDisclaimerMarkup());
}

function isPolicyResponse(data, payload) {
    if (getStructuredResponseJobs(data).length > 0) {
        return false;
    }
    const usedTools = normalizeArray(data?.used_tools).join(" ");
    return data?.intent === "policy_qa"
        || payload?.mode === "policy_qa"
        || usedTools.includes("policy_tool")
        || isPolicyQuestion(payload?.question);
}

function shouldDisplayJobs(data) {
    return getStructuredResponseJobs(data).length > 0;
}

function getStructuredResponseJobs(data) {
    const containers = [data, data?.data, data?.result]
        .filter((value) => value && typeof value === "object" && !Array.isArray(value));
    for (const container of containers) {
        const recommendations = normalizeArray(container?.recommendations).filter(isStructuredJob);
        if (recommendations.length > 0) {
            return recommendations;
        }
        const matchedJobs = normalizeArray(container?.matched_jobs).filter(isStructuredJob);
        if (matchedJobs.length > 0) {
            return matchedJobs;
        }
    }
    return [];
}

function isStructuredJob(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return false;
    }
    return Boolean(
        value.position_name
        || value.position
        || value.department
        || value.unit
        || value.full_position_code
        || value.display_position_code
        || value.position_code
        || value.job_id
    );
}

function createRecommendationResponse(jobs, answer, data, payload) {
    const cards = jobs
        .map((job) => createJobCard(job, {
            compact: true,
            showActions: false,
            deferRiskSummary: true
        }))
        .join("");
    const riskItems = buildRecommendationRiskItems(jobs, data, payload);
    const risksSection = riskItems.length > 0
        ? `
            <section class="chat-response-section recommendation-risks" role="note">
                <h2>风险提醒 / 数据缺失</h2>
                <ul>${riskItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
            </section>
        `
        : "";
    const actions = jobs.map(createRecommendationActionGroup).join("");
    return `
        <section class="chat-response-section" aria-label="岗位推荐卡片">
            <div class="chat-job-list">${cards}</div>
        </section>
        <section class="chat-response-section recommendation-analysis">
            <h2>AI 分析</h2>
            <div>${renderMarkdown(answer)}</div>
        </section>
        ${risksSection}
        <section class="chat-response-section recommendation-actions" aria-label="岗位操作">
            <h2>岗位操作</h2>
            ${actions}
        </section>
    `;
}

function buildRecommendationRiskItems(jobs, data, payload) {
    const items = [];
    const normalizedJobs = jobs.map(normalizeJob);
    if (normalizedJobs.some((job) => job.applicant_count === null)) {
        items.push("暂无报名人数，不能判断报名热度。");
    }
    if (normalizedJobs.some((job) => !job.competition_ratio)) {
        items.push("暂无竞争比，不能判断竞争强弱。");
    }
    if (normalizedJobs.some(hasIdentityRestriction)) {
        items.push("该岗位存在身份要求，需核对自己是否符合。");
    }
    if (normalizedJobs.some((job) => Number(job.recruit_count) === 1)) {
        items.push("该岗位只招 1 人，结果波动和低容错风险更高。");
    }
    if (normalizedJobs.some(isPoliceJob)) {
        items.push("公安岗通常还要关注体检、体测、视力、政审等要求，具体以公告、职位表和体检标准文件为准。");
    }
    if (normalizedJobs.some((job) => job.score_min === null)) {
        items.push("暂无该岗位精确进面分记录，不能据此判断分数压力。");
    } else if (normalizedJobs.some((job) => job.score_match_type !== "exact_position_code")) {
        items.push("当前分数是同类岗位历史分数参考，非该岗位精确进面分。");
    }

    normalizeArray(data?.risks)
        .map(sanitizeUserFacingText)
        .filter((risk) => risk && isApplicableRecommendationRisk(risk, normalizedJobs))
        .forEach((risk) => items.push(risk));
    return uniqueValues(items);
}

function isApplicableRecommendationRisk(risk, jobs) {
    const text = String(risk || "");
    const allowedPatterns = [
        /暂无报名人数/,
        /暂无竞争比/,
        /存在身份要求/,
        /身份.*核对/,
        /只招\s*1\s*人/,
        /公安岗通常还要关注/,
        /暂无该岗位精确进面分/,
        /同类岗位历史分数参考/
    ];
    return allowedPatterns.some((pattern) => pattern.test(text));
}

function hasIdentityRestriction(job) {
    const identity = String(job?.identity_required || "").trim();
    return Boolean(identity && identity !== "不限");
}

function isPoliceJob(job) {
    const text = [
        job?.department,
        job?.position_name,
        job?.notes
    ].map((value) => String(value || "")).join(" ");
    return /(公安|人民警察|警务|警察职位)/.test(text);
}

function getJobDataGapMessages(job) {
    const gaps = [];
    const missingFields = getJobDataMissingFields(job);
    if (missingFields.includes("报名人数")) {
        gaps.push("暂无报名人数数据");
    }
    if (missingFields.includes("竞争比")) {
        gaps.push("暂无竞争比数据，无法据此判断竞争压力");
    }
    if (missingFields.includes("精确进面分") && job.score_min === null) {
        gaps.push("暂无精确进面分");
    } else if (missingFields.includes("精确进面分")) {
        gaps.push("当前分数只是历史参考，不是该岗位职位代码精确进面分");
    }
    return gaps;
}

function getJobDataMissingFields(job) {
    const missing = [];
    if (job.applicant_count === null) {
        missing.push("报名人数");
    }
    if (!job.competition_ratio) {
        missing.push("竞争比");
    }
    if (job.score_min === null || job.score_match_type !== "exact_position_code") {
        missing.push("精确进面分");
    }
    return missing;
}

function createRecommendationActionGroup(rawJob, index) {
    const job = normalizeJob(rawJob);
    const ref = registerJob(job);
    const shortlisted = hasShortlistedJob(job);
    const compared = comparedJobKeys.has(getJobKey(job));
    return `
        <div class="recommendation-action-group">
            <strong>${escapeHtml(`${index + 1}. ${job.position_name || getDisplayPositionCode(job) || "岗位"}`)}</strong>
            <div class="job-actions">
                ${createJobAction("toggle-shortlist", ref, shortlisted ? "已加入" : "加入备选", shortlisted ? "selected-action" : "primary-action")}
                ${createJobAction("toggle-compare", ref, compared ? "移出对比" : "加入对比")}
                ${createJobAction("copy", ref, "复制代码")}
                ${createJobAction("analyze", ref, "分析岗位")}
            </div>
        </div>
    `;
}

function appendChatMessage(role, content) {
    const list = document.getElementById("chatMessages");
    if (!list) {
        return null;
    }
    list.querySelector(".chat-empty-state")?.remove();
    const article = document.createElement("article");
    article.className = `chat-message ${role === "user" ? "from-user" : "from-assistant"}`;
    const avatar = `<div class="chat-avatar ${role === "user" ? "user-avatar" : "assistant-avatar"}" aria-hidden="true">${role === "user" ? "我" : "AI"}</div>`;
    const responseDisclaimer = role === "assistant" ? createAnalysisDisclaimerMarkup() : "";
    const bubble = `<div class="chat-bubble markdown-content">${role === "user" ? escapeHtml(content).replace(/\n/g, "<br>") : `${renderMarkdown(content)}${responseDisclaimer}`}</div>`;
    article.innerHTML = role === "user" ? `${bubble}${avatar}` : `${avatar}${bubble}`;
    list.appendChild(article);
    scrollChatToBottom();
    return article;
}

function appendChatLoadingMessage(question) {
    const list = document.getElementById("chatMessages");
    list?.querySelector(".chat-empty-state")?.remove();
    const article = document.createElement("article");
    article.className = "chat-message from-assistant";
    article.innerHTML = `
        <div class="chat-avatar assistant-avatar" aria-hidden="true">AI</div>
        <div class="chat-bubble chat-loading-bubble" aria-live="polite">
            <div class="chat-loading" aria-label="分析师正在回复"><span></span><span></span><span></span></div>
            <span class="chat-loading-copy">AI 正在分析...</span>
        </div>
    `;
    list.appendChild(article);
    const status = article.querySelector(".chat-loading-copy");
    const stages = getChatLoadingStages(question);
    let stageIndex = 0;
    article._loadingTimer = window.setInterval(() => {
        stageIndex = Math.min(stageIndex + 1, stages.length - 1);
        if (status) {
            status.textContent = stages[stageIndex];
        }
        if (stageIndex === stages.length - 1) {
            window.clearInterval(article._loadingTimer);
            article._loadingTimer = null;
        }
    }, 1100);
    scrollChatToBottom();
    return article;
}

function replaceChatMessage(messageNode, html) {
    if (messageNode?._loadingTimer) {
        window.clearInterval(messageNode._loadingTimer);
        messageNode._loadingTimer = null;
    }
    const bubble = messageNode?.querySelector(".chat-bubble");
    if (bubble) {
        bubble.classList.remove("chat-loading-bubble");
        bubble.classList.add("markdown-content");
        bubble.removeAttribute("aria-live");
        bubble.innerHTML = html;
    }
}

function rememberChatMessage(role, content) {
    const text = String(content || "").trim();
    if (!text) {
        return;
    }
    chatHistory.push({ role, content: text });
    chatHistory = chatHistory.slice(-CHAT_CONTEXT_LIMIT);
}

function syncChatPromptVisibility() {
    const analystPage = document.querySelector('[data-page="analyst"]');
    const hasChat = chatHistory.length > 0 || Boolean(document.querySelector("#chatMessages .chat-message"));
    analystPage?.classList.toggle("has-chat", hasChat);
}

function clearChat() {
    if (analysisInFlight) {
        showToast("分析师正在回复，请稍等片刻。", "error");
        return;
    }
    chatHistory = [];
    setActiveSession(null);
    currentJobContext = null;
    lastRecommendationJobs = [];
    const messages = document.getElementById("chatMessages");
    if (messages) {
        messages.innerHTML = createChatEmptyState();
    }
    setValue("question", "");
    resizeAnalystTextarea();
    syncAnalystSubmitState();
    syncChatPromptVisibility();
    toggleQuickPromptPanel(false);
    renderRecognizedConditions();
    showToast("已开始新对话。", "success");
}

function createChatEmptyState() {
    return `
        <div class="chat-empty-state">
            <span class="chat-empty-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M8 10h8M8 14h5"/><path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 3v-5a2 2 0 0 1-1-1.73V6a2 2 0 0 1 2-2Z"/></svg>
            </span>
            <div>
                <strong>从一个真实问题开始</strong>
                <p>你可以直接问我怎么选岗，也可以让我按你的画像推荐岗位。</p>
            </div>
        </div>
    `;
}

function getChatLoadingStages(question) {
    const text = String(question || "");
    if (isPolicyQuestion(text)) {
        return ["AI 正在分析...", "正在查询政策资料...", "正在整理通俗解释..."];
    }
    if (/(推荐|岗位|职位|能报|筛选)/.test(text)) {
        return ["AI 正在分析...", "正在检索岗位...", "正在整理建议..."];
    }
    return ["AI 正在分析...", "正在核对问题和当前条件...", "正在整理建议..."];
}

function syncAnalystSubmitState() {
    if (analysisInFlight) {
        setSendButtonState("loading");
        return;
    }
    setSendButtonState(getValue("question") ? "ready" : "disabled");
}

function setSendButtonState(state) {
    const button = document.getElementById("analyzeButton");
    if (!button) {
        return;
    }

    const normalizedState = ["idle", "ready", "loading", "disabled"].includes(state)
        ? state
        : "idle";
    const loading = normalizedState === "loading";
    const disabled = normalizedState === "disabled";
    button.classList.toggle("is-loading", loading);
    button.disabled = disabled;
    button.dataset.state = normalizedState;
    button.setAttribute("aria-label", loading ? "停止生成" : "发送问题");
    button.title = loading ? "停止生成" : "发送问题";
    button.innerHTML = loading
        ? '<svg class="stop-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="6.5" y="6.5" width="11" height="11" rx="1.5"></rect></svg>'
        : '<svg class="send-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M6.5 10.5 12 5l5.5 5.5"></path></svg>';
}

function resizeAnalystTextarea() {
    const textarea = document.getElementById("question");
    if (!textarea) {
        return;
    }
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 62), 160)}px`;
}

function scrollChatToBottom() {
    window.requestAnimationFrame(() => {
        const list = document.getElementById("chatMessages");
        list?.lastElementChild?.scrollIntoView({
            behavior: "smooth",
            block: "end"
        });
    });
}

async function handleSingleJobSubmit(event) {
    event.preventDefault();
    const query = getValue("singleJobQuery");
    if (!query) {
        showToast("请输入岗位代码、岗位名称或单位名称。", "error");
        return;
    }

    const button = document.getElementById("singleJobSubmitButton");
    setButtonLoading(button, true, "查询中…");
    const result = document.getElementById("singleJobResult");
    result.innerHTML = createLoadingPanel("正在回查岗位详情和分数匹配信息…");

    try {
        const data = await postAnalyze({
            mode: "single_job_query",
            target: "公务员",
            exam_type: getValue("singleJobExamType") || "省考",
            region: getValue("singleJobProvince") || userProfile.province || "不限",
            city: "不限",
            education: userProfile.education || "不限",
            major: userProfile.major || "",
            identity: userProfile.identity || "不限",
            question: query,
            result_limit: 1,
            messages: []
        });
        const jobs = normalizeArray(data?.matched_jobs).slice(0, 1);
        if (jobs.length > 0) {
            const job = normalizeJob(jobs[0]);
            currentJobContext = job;
            lastRecommendationJobs = [job];
            const displayPositionCode = getDisplayPositionCode(job);
            result.innerHTML = `
                <div class="inline-summary">${escapeHtml(sanitizeUserFacingText(data.summary) || "已找到最匹配的岗位记录。")}</div>
                ${createJobCard(jobs[0], { detailed: true })}
            `;
            addAnalysisHistoryRecord({
                type: "single_job_analysis",
                title: `查询岗位：${job.position_name || displayPositionCode}`,
                summary: sanitizeUserFacingText(data.analysis_report || data.summary) || "已找到匹配岗位并展示岗位条件与风险。",
                question: query,
                related_position_code: displayPositionCode,
                province: job.province || getValue("singleJobProvince"),
                year: job.year || 2025,
                status: "完成"
            });
        } else {
            result.innerHTML = createEmptyState(
                "没有找到对应岗位",
                "没有找到对应岗位，可以检查职位代码、省份或关键词。",
                "返回招考分析师",
                "analyst"
            );
            addAnalysisHistoryRecord({
                type: "single_job_analysis",
                title: "单岗位查询无结果",
                summary: "没有找到对应岗位，可以检查职位代码、省份或关键词。",
                question: query,
                related_position_code: extractPositionCodeFromText(query),
                province: getValue("singleJobProvince"),
                year: 2025,
                status: "无结果"
            });
        }
    } catch (error) {
        result.innerHTML = createErrorState(
            "岗位查询失败",
            "这次查询没有完成，可以检查条件后重试。",
            "重新查询",
            "retry-single-job"
        );
        showToast("岗位查询失败，可以稍后重试。", "error");
        addAnalysisHistoryRecord({
            type: "error",
            title: "单岗位查询失败",
            summary: "这次岗位查询没有完成，可以检查条件后重试。",
            question: query,
            related_position_code: extractPositionCodeFromText(query),
            province: getValue("singleJobProvince"),
            year: 2025,
            status: "失败"
        });
        console.error("Single job request failed:", error);
    } finally {
        setButtonLoading(button, false, "查询岗位");
    }
}

function createJobCard(job, options = {}) {
    const normalized = normalizeJob(job);
    const displayPositionCode = getDisplayPositionCode(normalized);
    const ref = registerJob(normalized);
    const shortlisted = hasShortlistedJob(normalized);
    const compared = comparedJobKeys.has(getJobKey(normalized));
    const status = getJobStatus(normalized);
    const riskClass = getRiskClass(normalized);
    const scoreStatus = formatScoreMatchType(normalized.score_match_type);
    const actions = [];

    if (options.showActions === false) {
        // Recommendation replies render actions after the analysis and risk sections.
    } else if (options.shortlistPage) {
        actions.push(createJobAction("analyze", ref, "分析岗位"));
        actions.push(createJobAction("toggle-compare", ref, compared ? "移出对比" : "加入对比"));
        actions.push(createJobAction("copy", ref, "复制代码"));
        actions.push(createJobAction("remove-shortlist", ref, "移出备选", "danger-action"));
    } else {
        actions.push(createJobAction("toggle-shortlist", ref, shortlisted ? "已加入" : "加入备选", shortlisted ? "selected-action" : "primary-action"));
        actions.push(createJobAction("analyze", ref, "分析岗位"));
        actions.push(createJobAction("copy", ref, "复制代码"));
        if (shortlisted) {
            actions.push(createJobAction("toggle-compare", ref, compared ? "移出对比" : "加入对比"));
        }
    }
    const jobInformationSections = createJobInformationSections(normalized);
    const scoreReferenceSection = createScoreReferenceSection(normalized);
    const subtitle = [
        normalized.department || normalized.unit || "招录单位",
        normalized.city || normalized.region || normalized.province,
        normalized.year ? `${normalized.year} 年` : "",
        normalized.exam_type
    ].filter(Boolean).join(" · ");
    const riskFlags = normalized.risk_flags
        .map((flag) => `<span class="badge risk">${escapeHtml(flag)}</span>`)
        .join("");

    return `
        <article class="job-card">
            <div class="job-card-head">
                <div>
                    <h3>${escapeHtml(normalized.position_name || "未命名岗位")}</h3>
                    <p class="job-card-eyebrow">${escapeHtml(subtitle)}</p>
                    ${displayPositionCode ? `<span class="job-code">职位代码 ${escapeHtml(displayPositionCode)}</span>` : ""}
                </div>
                <div class="badge-row">
                    <span class="badge ${status.className}">${escapeHtml(status.label)}</span>
                    <span class="badge ${getScoreMatchClass(normalized.score_match_type)}">${escapeHtml(scoreStatus)}</span>
                    <span class="badge ${riskClass}">${escapeHtml(normalized.risk_level)}</span>
                </div>
            </div>

            ${jobInformationSections}

            ${scoreReferenceSection}

            ${riskFlags ? `<div class="badge-row job-risk-flags" aria-label="风险标签">${riskFlags}</div>` : ""}

            <div class="job-summary-grid">
                <div class="job-summary-block">
                    <strong>推荐理由</strong>
                    <p>${escapeHtml(normalized.recommend_reason || "该岗位通过当前条件初筛，建议继续核对官方职位表。")}</p>
                </div>
                ${options.deferRiskSummary ? "" : `<div class="job-summary-block risk-block">
                    <strong>风险提醒</strong>
                    <p>${escapeHtml(normalized.risk_summary || "缺少报名人数或竞争比时，不能判断岗位是否稳妥。")}</p>
                </div>`}
            </div>

            <div class="job-source-row single-source">
                <div>
                    岗位数据来源
                    <strong>${escapeHtml(friendlyJobSource(normalized))}</strong>
                    <p class="job-card-disclaimer">请以官方公告和职位表为准，AI 分析仅辅助参考。</p>
                </div>
            </div>

            ${actions.length ? `<div class="job-actions">${actions.join("")}</div>` : ""}
        </article>
    `;
}

function createJobInformationSections(job) {
    const location = [job.province, job.city || job.region].filter(Boolean).join(" · ");
    const coreItems = renderInfoItems([
        { label: "招录单位", value: job.unit_name || job.department, wide: true },
        { label: "招录人数", value: job.recruit_count, suffix: " 人" },
        { label: "省份 / 地区", value: location },
        { label: "机构层级", value: job.agency_level },
        { label: "是否参公", value: job.is_public_service },
        { label: "行政执法类", value: job.is_law_enforcement },
        { label: "报名人数", value: job.applicant_count, suffix: " 人" },
        { label: "竞争比", value: job.competition_ratio }
    ]);
    const restrictionItems = renderInfoItems([
        { label: "学历要求", value: job.education },
        { label: "学位要求", value: job.degree_requirement },
        { label: "专业要求", value: job.major_required, wide: String(job.major_required || "").length > 28 },
        { label: "身份要求", value: job.identity_required },
        { label: "政治面貌", value: job.political_requirement },
        { label: "基层经历", value: job.grassroots_requirement },
        { label: "资格条件", value: job.qualification_requirement, wide: true, emphasis: true }
    ]);
    const descriptionItems = renderInfoItems([
        { label: "职位简介", value: job.job_description, wide: true },
        { label: "咨询电话", value: job.contact_phone },
        { label: "单位地址", value: job.work_address, wide: true },
        { label: "备注", value: job.remark, wide: true }
    ]);

    return [
        createJobDetailSection("岗位基础信息", coreItems),
        createJobDetailSection("报考限制条件", restrictionItems),
        createJobDetailSection("岗位说明", descriptionItems)
    ].filter(Boolean).join("");
}

function renderInfoItems(items) {
    return normalizeArray(items)
        .map((item) => {
            if (!hasDisplayValue(item?.value)) {
                return "";
            }
            const value = `${item.value}${item.suffix || ""}`;
            return createJobDetailItem(item.label, value, {
                wide: Boolean(item.wide),
                emphasis: Boolean(item.emphasis)
            });
        })
        .filter(Boolean);
}

function createJobDetailSection(title, items) {
    if (!items.length) {
        return "";
    }
    return `
        <section class="job-detail-section" aria-label="${escapeHtml(title)}">
            <h4>${escapeHtml(title)}</h4>
            <div class="job-detail-grid">${items.join("")}</div>
        </section>
    `;
}

function createJobDetailItem(label, value, options = {}) {
    if (!hasDisplayValue(value)) {
        return "";
    }
    const classes = [
        "job-detail-item",
        options.wide ? "wide" : "",
        options.emphasis ? "emphasis" : ""
    ].filter(Boolean).join(" ");
    return `
        <div class="${classes}">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(String(value))}</strong>
        </div>
    `;
}

function hasDisplayValue(value) {
    return value !== null && value !== undefined && String(value).trim() !== "";
}

function formatPublicJobFlag(value) {
    const normalized = String(value ?? "").trim().toLowerCase();
    if (value === true || value === 1 || ["1", "true", "yes", "是"].includes(normalized)) {
        return "是";
    }
    if (value === false || value === 0 || ["0", "false", "no", "否"].includes(normalized)) {
        return "否";
    }
    return String(value ?? "").trim();
}

function createScoreReferenceSection(job) {
    const sourceType = String(job?.score_source_type || "");
    const matchType = String(job?.score_match_type || "no_match");
    if (sourceType === "review_candidate_sample" || matchType === "review_candidate_sample") {
        return renderReviewScoreSample(job);
    }
    if (sourceType === "candidate_score_sample" || matchType === "candidate_score_sample") {
        return renderCandidateScoreSample(job);
    }
    if (matchType === "exact_position_code" && hasDisplayValue(job?.score_min)) {
        return renderScoreLineReference(job);
    }
    if (hasDisplayValue(job?.score_min)) {
        const stats = createScoreStatItem("历史参考分", job.score_min);
        return createScorePanel({
            title: "历史分数参考",
            badge: formatScoreMatchType(matchType),
            stats,
            source: friendlyScoreSource(job),
            note: getScoreMatchReason(job),
            tone: "reference"
        });
    }
    return createScorePanel({
        title: "暂无分数参考",
        badge: "待补充数据",
        stats: "",
        source: "",
        note: "当前没有可与该岗位可靠关联的官方分数线或成绩样本。",
        tone: "empty"
    });
}

function renderScoreLineReference(job) {
    const stats = renderScoreStatItems([
        { label: "最低进面分", value: firstPresent(job?.score_min, job?.min_interview_score) },
        { label: "最高分", value: firstPresent(job?.max_score, job?.max_interview_score) },
        { label: "平均分", value: job?.avg_score },
        { label: "进面人数", value: job?.interview_count, suffix: " 人" },
        { label: "招录人数", value: job?.recruit_count, suffix: " 人" }
    ]);
    return createScorePanel({
        title: "官方进面分",
        badge: "精确分数",
        stats,
        source: friendlyScoreSource(job),
        note: "历史进面分仅用于风险参考，不代表今年分数线。",
        tone: "official"
    });
}

function renderReviewScoreSample(job) {
    return createScoreSampleSection(job, "review");
}

function renderCandidateScoreSample(job) {
    return createScoreSampleSection(job, "candidate");
}

function renderScoreStatItems(items) {
    return normalizeArray(items)
        .map((item) => createScoreStatItem(item?.label, item?.value, item?.suffix || ""))
        .filter(Boolean)
        .join("");
}

function createScoreSampleSection(job, prefix) {
    const isReview = prefix === "review";
    const sample = isReview ? (job.review_score_sample || {}) : (job.candidate_score_sample || {});
    const sampleCount = isReview
        ? job.score_sample_count
        : firstPresent(job.candidate_score_sample_count, job.score_sample_count);
    const rows = [];
    const addDistribution = (label, field) => {
        const value = formatScoreStatRange(
            scoreStatValue(job, sample, prefix, field, "min"),
            scoreStatValue(job, sample, prefix, field, "avg"),
            scoreStatValue(job, sample, prefix, field, "max")
        );
        if (value) {
            rows.push(createScoreDistributionRow(label, value));
        }
    };

    addDistribution("笔试成绩", "written_score");
    if (isReview) {
        addDistribution("行测成绩", "xingce_score");
        addDistribution("申论成绩", "shenlun_score");
        addDistribution("专业成绩", "professional_score");
        addDistribution("总成绩", "total_score");
    } else {
        addDistribution("面试成绩", "interview_score");
        addDistribution("总成绩", "total_score");
    }
    const rankRange = formatRankRange(
        scoreStatValue(job, sample, prefix, "rank", "min"),
        scoreStatValue(job, sample, prefix, "rank", "max")
    );
    if (rankRange) {
        rows.push(createScoreDistributionRow("排名范围", rankRange));
    }

    const referenceMin = scoreStatValue(job, sample, prefix, "written_score", "min");
    const stats = [
        hasDisplayValue(sampleCount)
            ? createScoreStatItem("成绩样本数", formatNumber(sampleCount), " 条")
            : "",
        hasDisplayValue(referenceMin)
            ? createScoreStatItem(isReview ? "入围样本最低笔试分" : "样本最低笔试分", referenceMin)
            : ""
    ].filter(Boolean).join("");
    return createScorePanel({
        title: isReview ? "资格复审成绩样本" : "候选人成绩样本",
        badge: "非官方进面分",
        stats,
        distributions: rows.join(""),
        source: friendlyScoreSource(job),
        note: isReview
            ? "该数据由资格复审名单按岗位聚合得到，不等同于官方最低进面分。"
            : "该数据由候选人成绩表按岗位聚合得到，不等同于岗位官方最低进面分。",
        tone: "sample"
    });
}

function createScorePanel({ title, badge, stats, distributions = "", source, note, tone }) {
    return `
        <section class="job-score-panel ${escapeHtml(tone || "")}" aria-label="分数参考">
            <div class="job-score-panel-head">
                <strong>${escapeHtml(title)}</strong>
                ${badge ? `<span>${escapeHtml(badge)}</span>` : ""}
            </div>
            ${stats ? `<div class="job-score-stat-grid">${stats}</div>` : ""}
            ${distributions ? `<div class="job-score-distributions">${distributions}</div>` : ""}
            ${source ? `<p class="job-score-source">分数来源：<strong>${escapeHtml(source)}</strong></p>` : ""}
            ${note ? `<p class="job-score-note">${escapeHtml(note)}</p>` : ""}
        </section>
    `;
}

function createScoreStatItem(label, value, suffix = "") {
    if (!hasDisplayValue(value)) {
        return "";
    }
    return `
        <div class="job-score-stat">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(`${formatCompactNumber(value)}${suffix}`)}</strong>
        </div>
    `;
}

function createScoreDistributionRow(label, value) {
    return `
        <div class="job-score-distribution-row">
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `;
}

function formatRankRange(min, max) {
    if (!hasDisplayValue(min) && !hasDisplayValue(max)) {
        return "";
    }
    if (hasDisplayValue(min) && hasDisplayValue(max)) {
        return Number(min) === Number(max)
            ? `第 ${formatCompactNumber(min)} 名`
            : `${formatCompactNumber(min)} - ${formatCompactNumber(max)}`;
    }
    return hasDisplayValue(min)
        ? `最低名次 ${formatCompactNumber(min)}`
        : `最高名次 ${formatCompactNumber(max)}`;
}

function scoreStatValue(job, sample, prefix, field, stat) {
    return optionalNumber(firstPresent(
        job?.[`${prefix}_${field}_${stat}`],
        sample?.[`${field}_${stat}`]
    ));
}

function formatScoreStatRange(min, avg, max, suffixText = "") {
    const parts = [];
    if (min !== null && min !== undefined) {
        parts.push(`低 ${formatCompactNumber(min)}`);
    }
    if (avg !== null && avg !== undefined) {
        parts.push(`均 ${formatCompactNumber(avg)}`);
    }
    if (max !== null && max !== undefined) {
        parts.push(`高 ${formatCompactNumber(max)}`);
    }
    if (!parts.length) {
        return "";
    }
    return `${parts.join(" · ")}${suffixText}`;
}

function formatCompactNumber(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
        return String(value || "");
    }
    return Number.isInteger(number) ? String(number) : number.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

function createJobAction(action, ref, label, className = "") {
    return `<button class="job-action ${className}" type="button" data-job-action="${action}" data-job-ref="${ref}">${escapeHtml(label)}</button>`;
}

function registerJob(job) {
    const ref = `job-${++jobRefCounter}`;
    jobRegistry.set(ref, job);
    return ref;
}

function handleJobAction(action, ref) {
    const job = jobRegistry.get(ref);
    if (!job) {
        showToast("岗位数据已失效，请刷新当前页面。", "error");
        return;
    }
    if (action === "toggle-shortlist") {
        toggleShortlistedJob(job);
    } else if (action === "remove-shortlist") {
        removeShortlistedJob(job);
    } else if (action === "toggle-compare") {
        toggleComparedJob(job);
    } else if (action === "analyze") {
        analyzeSelectedJob(job);
    } else if (action === "copy") {
        copyJobCode(job);
    }
}

function normalizeJob(job) {
    const positionCode = getDisplayPositionCode(job);
    const province = String(job?.province || job?.region || "").trim();
    let scoreSourceType = String(job?.score_source_type || "").trim();
    const scoreSourceLabel = String(job?.score_data_source_label || "").trim();
    if (!scoreSourceType && /资格复审|复审名单/.test(scoreSourceLabel)) {
        scoreSourceType = "review_candidate_sample";
    } else if (!scoreSourceType && /候选成绩|成绩样本/.test(scoreSourceLabel)) {
        scoreSourceType = "candidate_score_sample";
    }
    const scoreMin = firstPresent(job?.score_min, job?.min_score, job?.min_interview_score);
    const recruitCount = firstPresent(job?.recruit_count, job?.headcount);
    let normalizedScoreMin = optionalNumber(scoreMin);
    if (normalizedScoreMin === null && scoreSourceType === "review_candidate_sample") {
        normalizedScoreMin = optionalNumber(firstPresent(job?.review_written_score_min, job?.written_score_min));
    }
    if (normalizedScoreMin === null && scoreSourceType === "candidate_score_sample") {
        normalizedScoreMin = optionalNumber(firstPresent(job?.candidate_written_score_min, job?.written_score_min));
    }
    let scoreMatchType = String(job?.score_match_type || "no_match").trim();
    let scoreMatchReason = sanitizeUserFacingText(job?.score_match_reason);
    if (scoreSourceType === "review_candidate_sample") {
        scoreMatchType = "review_candidate_sample";
        if (!scoreMatchReason) {
            scoreMatchReason = "资格复审名单成绩样本聚合，不等同于官方最低进面分";
        }
    } else if (scoreSourceType === "candidate_score_sample") {
        scoreMatchType = "candidate_score_sample";
        if (!scoreMatchReason) {
            scoreMatchReason = "候选人成绩样本聚合，不等同于官方最低进面分";
        }
    } else if (normalizedScoreMin === null) {
        scoreMatchType = "no_match";
        scoreMatchReason = "暂无该岗位精确分数记录";
    } else if (scoreMatchType === "exact_position_code") {
        scoreSourceType = "score_line";
        scoreMatchReason = positionCode ? `职位代码 ${positionCode} 精确匹配` : "职位代码精确匹配";
    } else if (!["partial_position_code", "fuzzy_high_confidence", "similar_reference"].includes(scoreMatchType)) {
        scoreMatchType = "similar_reference";
        scoreMatchReason = "当前分数为历史参考，非该岗位职位代码精确匹配";
    } else if (!scoreMatchReason) {
        scoreMatchReason = "当前分数为历史参考，非该岗位职位代码精确匹配";
    }
    return {
        province,
        region: String(job?.region || "").trim(),
        city: String(job?.city || job?.district || "").trim(),
        year: Number(job?.year || job?.job_source_year || 2025),
        exam_type: String(job?.exam_type || "").trim(),
        position_code: positionCode,
        display_position_code: positionCode,
        full_position_code: positionCode,
        raw_position_code: String(job?.raw_position_code || job?.position_code || "").trim(),
        score_match_position_code: normalizePositionCode(job?.score_match_position_code || ""),
        matched_position_code: normalizePositionCode(job?.matched_position_code || ""),
        department: String(job?.department || job?.unit || "").trim(),
        unit: String(job?.unit || "").trim(),
        unit_name: String(job?.unit_name || job?.unit || job?.department || "").trim(),
        position_name: getJobDisplayTitle(job),
        recruit_count: optionalNumber(recruitCount),
        education: String(job?.education || job?.education_requirement || job?.education_required || "").trim(),
        degree_requirement: String(job?.degree_requirement || job?.degree || "").trim(),
        major_required: String(job?.major_requirement || job?.major_required || "").trim(),
        identity_required: String(job?.identity_requirement || job?.identity_required || "不限").trim(),
        political_requirement: String(job?.political_requirement || "").trim(),
        grassroots_requirement: String(job?.grassroots_requirement || job?.grassroots_experience || "").trim(),
        qualification_requirement: String(job?.qualification_requirement || job?.qualification || "").trim(),
        agency_level: String(job?.agency_level || job?.institution_level || "").trim(),
        is_public_service: formatPublicJobFlag(job?.is_public_service),
        is_law_enforcement: formatPublicJobFlag(job?.is_law_enforcement),
        job_description: String(job?.job_description || job?.position_description || "").trim(),
        contact_phone: String(job?.contact_phone || job?.consult_phone || "").trim(),
        work_address: String(job?.work_address || job?.unit_address || "").trim(),
        remark: String(job?.remark || "").trim(),
        score_min: normalizedScoreMin,
        avg_score: optionalNumber(job?.avg_score),
        max_score: optionalNumber(firstPresent(job?.max_score, job?.max_interview_score)),
        interview_count: optionalNumber(job?.interview_count),
        applicant_count: optionalNumber(firstPresent(job?.applicant_count, job?.applicants_count)),
        competition_ratio: String(job?.competition_ratio || "").trim(),
        score_match_type: scoreMatchType,
        score_confidence: optionalNumber(firstPresent(job?.score_confidence, job?.score_match_confidence)),
        score_match_reason: scoreMatchReason,
        risk_flags: normalizeJobRiskFlags(job),
        risk_level: normalizeRiskLevel(job),
        recommend_level: String(job?.match_level || "").trim(),
        recommend_reason: sanitizeUserFacingText(
            job?.recommend_reason
            || job?.recommendation_reason
            || job?.short_reason
            || job?.ai_analysis?.why_recommended
            || ""
        ),
        risk_summary: sanitizeUserFacingText(
            job?.risk_summary
            || job?.ai_analysis?.recruit_risk
            || normalizeArray(job?.risk_notes)[0]
            || ""
        ),
        notes: String(job?.notes || job?.remark || "").trim(),
        source_type: String(job?.source_type || "官方职位表").trim(),
        data_status: String(job?.data_status || "").trim(),
        score_source_type: scoreSourceType,
        score_sample_count: optionalNumber(job?.score_sample_count) || 0,
        review_score_sample: job?.review_score_sample || {},
        candidate_score_sample: job?.candidate_score_sample || {},
        candidate_score_sample_count: optionalNumber(job?.candidate_score_sample_count) || 0,
        review_written_score_min: optionalNumber(job?.review_written_score_min),
        review_written_score_avg: optionalNumber(job?.review_written_score_avg),
        review_written_score_max: optionalNumber(job?.review_written_score_max),
        review_xingce_score_min: optionalNumber(job?.review_xingce_score_min),
        review_xingce_score_avg: optionalNumber(job?.review_xingce_score_avg),
        review_xingce_score_max: optionalNumber(job?.review_xingce_score_max),
        review_shenlun_score_min: optionalNumber(job?.review_shenlun_score_min),
        review_shenlun_score_avg: optionalNumber(job?.review_shenlun_score_avg),
        review_shenlun_score_max: optionalNumber(job?.review_shenlun_score_max),
        review_professional_score_min: optionalNumber(job?.review_professional_score_min),
        review_professional_score_avg: optionalNumber(job?.review_professional_score_avg),
        review_professional_score_max: optionalNumber(job?.review_professional_score_max),
        review_total_score_min: optionalNumber(job?.review_total_score_min),
        review_total_score_avg: optionalNumber(job?.review_total_score_avg),
        review_total_score_max: optionalNumber(job?.review_total_score_max),
        review_rank_min: optionalNumber(job?.review_rank_min),
        review_rank_avg: optionalNumber(job?.review_rank_avg),
        review_rank_max: optionalNumber(job?.review_rank_max),
        candidate_written_score_min: optionalNumber(job?.candidate_written_score_min),
        candidate_written_score_avg: optionalNumber(job?.candidate_written_score_avg),
        candidate_written_score_max: optionalNumber(job?.candidate_written_score_max),
        candidate_interview_score_min: optionalNumber(job?.candidate_interview_score_min),
        candidate_interview_score_avg: optionalNumber(job?.candidate_interview_score_avg),
        candidate_interview_score_max: optionalNumber(job?.candidate_interview_score_max),
        candidate_xingce_score_min: optionalNumber(job?.candidate_xingce_score_min),
        candidate_xingce_score_avg: optionalNumber(job?.candidate_xingce_score_avg),
        candidate_xingce_score_max: optionalNumber(job?.candidate_xingce_score_max),
        candidate_shenlun_score_min: optionalNumber(job?.candidate_shenlun_score_min),
        candidate_shenlun_score_avg: optionalNumber(job?.candidate_shenlun_score_avg),
        candidate_shenlun_score_max: optionalNumber(job?.candidate_shenlun_score_max),
        candidate_professional_score_min: optionalNumber(job?.candidate_professional_score_min),
        candidate_professional_score_avg: optionalNumber(job?.candidate_professional_score_avg),
        candidate_professional_score_max: optionalNumber(job?.candidate_professional_score_max),
        candidate_total_score_min: optionalNumber(job?.candidate_total_score_min),
        candidate_total_score_avg: optionalNumber(job?.candidate_total_score_avg),
        candidate_total_score_max: optionalNumber(job?.candidate_total_score_max),
        candidate_rank_min: optionalNumber(job?.candidate_rank_min),
        candidate_rank_avg: optionalNumber(job?.candidate_rank_avg),
        candidate_rank_max: optionalNumber(job?.candidate_rank_max),
        data_source_label: String(job?.data_source_label || "").trim(),
        score_data_source_label: String(job?.score_data_source_label || "").trim(),
        created_at: String(job?.created_at || new Date().toISOString())
    };
}

function getJobDisplayTitle(job) {
    const candidates = [
        job?.job_name,
        job?.position_name,
        job?.position,
        job?.title
    ]
        .map((value) => sanitizeUserFacingText(value))
        .filter(Boolean);
    const descriptive = candidates.find((value) => !/^\d+$/.test(value));
    if (descriptive) {
        return descriptive;
    }
    if (candidates.length > 0) {
        return `岗位 ${candidates[0]}`;
    }
    const positionCode = getDisplayPositionCode(job);
    return positionCode ? `职位代码 ${positionCode}` : "未命名岗位";
}

function normalizeJobRiskFlags(job) {
    const explicit = normalizeArray(job?.risk_flags)
        .map((item) => String(item || "").trim())
        .filter(Boolean);
    if (explicit.length > 0) {
        return uniqueValues(explicit);
    }
    const flags = [];
    if (optionalNumber(firstPresent(job?.applicant_count, job?.applicants_count)) === null) {
        flags.push("待补报名数据");
    }
    if (!String(job?.competition_ratio || "").trim()) {
        flags.push("暂无竞争比");
    }
    const scoreSourceType = String(job?.score_source_type || "").trim();
    if (optionalNumber(firstPresent(job?.min_score, job?.min_interview_score, job?.score_min)) === null) {
        flags.push("待补充分数");
    } else if (String(job?.score_match_type || "no_match") !== "exact_position_code") {
        if (scoreSourceType === "review_candidate_sample") {
            flags.push("资格复审样本");
        } else if (scoreSourceType === "candidate_score_sample") {
            flags.push("候选成绩样本");
        } else {
            flags.push("暂无精确分数");
        }
    }
    const identity = String(job?.identity_requirement || job?.identity_required || "").trim();
    if (identity && identity !== "不限") {
        flags.push("身份需核验");
    }
    const major = String(job?.major_requirement || job?.major_required || "").trim();
    if (major && !major.includes("不限")) {
        flags.push("专业需核验");
    }
    return uniqueValues(flags);
}

function normalizeRiskLevel(job) {
    const explicit = String(job?.risk_level || job?.competition_level || "").trim();
    if (explicit && explicit !== "未知") {
        return explicit;
    }
    if (Number(job?.recruit_count || job?.headcount || 0) === 1) {
        return "波动风险";
    }
    if (!job?.competition_ratio || (job?.min_interview_score === null || job?.min_interview_score === undefined) && !job?.score_sample_count) {
        return "数据待补充";
    }
    return "谨慎评估";
}

function getJobStatus(job) {
    if (job.recommend_level.includes("推荐关注")) {
        return { label: "推荐关注", className: "primary" };
    }
    if (job.score_match_type === "no_match") {
        return { label: "待补充数据", className: "risk" };
    }
    return { label: "可报备选", className: "success" };
}

function getRiskClass(job) {
    const text = String(job.risk_level || "");
    if (/高|波动|警告/.test(text)) {
        return "danger";
    }
    if (/待补充|谨慎|未知/.test(text)) {
        return "risk";
    }
    return "success";
}

function friendlyJobSource(job) {
    if (job.data_source_label) {
        return job.data_source_label;
    }
    const year = job.year || 2025;
    const province = job.province || "当前地区";
    return `${year} 年${province}公务员考试职位表`;
}

function friendlyScoreSource(job) {
    if (job.score_data_source_label) {
        return job.score_data_source_label;
    }
    const year = job.year || 2025;
    const province = job.province || "当前地区";
    const matchType = String(job.score_match_type || "no_match");
    const sourceType = String(job.score_source_type || "");
    if (sourceType === "review_candidate_sample" || matchType === "review_candidate_sample") {
        return "资格复审名单成绩样本";
    }
    if (sourceType === "candidate_score_sample" || matchType === "candidate_score_sample") {
        return "候选人成绩样本";
    }
    if (matchType === "no_match") {
        return "暂无该岗位精确进面分记录";
    }
    if (matchType !== "exact_position_code") {
        return "历史分数参考，非该岗位职位代码精确进面分";
    }
    return `${year} 年${province}公务员考试进面分数线表`;
}

function formatScoreMatchType(value) {
    const labels = {
        exact_position_code: "精确分数",
        partial_position_code: "历史参考",
        fuzzy_high_confidence: "历史参考",
        similar_reference: "同类参考",
        review_candidate_sample: "资格复审样本",
        candidate_score_sample: "候选成绩样本",
        no_match: "暂无分数参考"
    };
    return labels[value] || "暂无分数参考";
}

function getScoreMatchReason(job) {
    if (job.score_source_type === "review_candidate_sample" || job.score_match_type === "review_candidate_sample") {
        return job.score_match_reason || "资格复审名单成绩样本聚合，不等同于官方最低进面分";
    }
    if (job.score_source_type === "candidate_score_sample" || job.score_match_type === "candidate_score_sample") {
        return job.score_match_reason || "候选人成绩样本聚合，不等同于官方最低进面分";
    }
    if (job.score_min === null || job.score_match_type === "no_match") {
        return "暂无该岗位精确分数记录";
    }
    if (job.score_match_type === "exact_position_code") {
        return job.score_match_reason
            || (job.position_code ? `职位代码 ${job.position_code} 精确匹配` : "职位代码精确匹配");
    }
    return job.score_match_reason || "当前分数为历史参考，非该岗位职位代码精确匹配";
}

function getScoreMatchClass(value) {
    if (value === "exact_position_code") {
        return "success";
    }
    if (["partial_position_code", "fuzzy_high_confidence"].includes(value)) {
        return "primary";
    }
    return "risk";
}

function toggleShortlistedJob(job) {
    const normalizedJob = normalizeJob(job);
    const key = getJobKey(normalizedJob);
    if (shortlistedJobs.some((item) => getJobKey(item) === key)) {
        removeShortlistedJob(normalizedJob);
        return;
    }
    shortlistedJobs.unshift({ ...normalizedJob, created_at: new Date().toISOString() });
    if (!persistShortlist()) {
        shortlistedJobs = shortlistedJobs.filter((item) => getJobKey(item) !== key);
        return;
    }
    showToast("已加入备选", "success");
    syncFavoriteToServer(normalizedJob);
    addAnalysisHistoryRecord({
        type: "shortlist",
        title: `加入备选：${normalizedJob.position_name || normalizedJob.position_code}`,
        summary: `${normalizedJob.department || "招录单位"} · ${normalizedJob.position_name || "未命名岗位"}`,
        related_position_code: getDisplayPositionCode(normalizedJob),
        province: normalizedJob.province,
        year: normalizedJob.year,
        status: "已加入"
    });
    refreshJobDependentViews();
}

function removeShortlistedJob(job) {
    const key = getJobKey(job);
    shortlistedJobs = shortlistedJobs.filter((item) => getJobKey(item) !== key);
    comparedJobKeys.delete(key);
    persistShortlist();
    persistCompare();
    showToast("已移出岗位备选。", "success");
    removeFavoriteFromServer(job);
    refreshJobDependentViews();
}

function clearShortlist() {
    if (shortlistedJobs.length === 0) {
        showToast("当前没有备选岗位。", "success");
        return;
    }
    if (!window.confirm("确定清空全部备选岗位吗？此操作无法撤销。")) {
        return;
    }
    shortlistedJobs = [];
    comparedJobKeys.clear();
    persistShortlist();
    persistCompare();
    refreshJobDependentViews();
    clearServerFavorites();
    showToast("已清空全部备选岗位。", "success");
}

async function syncFavoriteToServer(rawJob) {
    if (!currentUser || !authToken) {
        return;
    }
    const job = normalizeJob(rawJob);
    const jobId = getDisplayPositionCode(job) || job.job_id || getJobKey(job);
    try {
        await apiFetch(FAVORITES_API_URL, {
            method: "POST",
            body: JSON.stringify({
                job_id: jobId,
                job_name: job.position_name,
                department_name: job.department,
                region: [job.province, job.city].filter(Boolean).join(""),
                exam_type: job.exam_type,
                raw_job_json: job,
                note: "来自岗位备选"
            })
        });
    } catch (error) {
        showToast(`岗位已保存在本地，云端收藏失败：${getErrorText(error)}`, "error");
    }
}

async function removeFavoriteFromServer(rawJob) {
    if (!currentUser || !authToken) {
        return;
    }
    const job = normalizeJob(rawJob);
    const jobId = getDisplayPositionCode(job) || job.job_id || getJobKey(job);
    try {
        const data = await apiFetch(FAVORITES_API_URL);
        const favorite = normalizeArray(data?.items).find((item) => item.job_id === jobId);
        if (favorite) {
            await apiFetch(`${FAVORITES_API_URL}/${favorite.id}`, { method: "DELETE" });
        }
    } catch (error) {
        showToast(`本地备选已移除，云端收藏同步失败：${getErrorText(error)}`, "error");
    }
}

async function clearServerFavorites() {
    if (!currentUser || !authToken) {
        return;
    }
    try {
        const data = await apiFetch(FAVORITES_API_URL);
        await Promise.all(
            normalizeArray(data?.items).map((item) =>
                apiFetch(`${FAVORITES_API_URL}/${item.id}`, { method: "DELETE" })
            )
        );
    } catch (error) {
        showToast(`本地备选已清空，云端收藏同步失败：${getErrorText(error)}`, "error");
    }
}

function toggleComparedJob(job) {
    const normalizedJob = normalizeJob(job);
    const key = getJobKey(normalizedJob);
    if (!hasShortlistedJob(normalizedJob)) {
        shortlistedJobs.unshift({ ...normalizedJob, created_at: new Date().toISOString() });
        persistShortlist();
    }
    if (comparedJobKeys.has(key)) {
        comparedJobKeys.delete(key);
        showToast("已移出岗位对比。", "success");
    } else {
        if (comparedJobKeys.size >= 5) {
            showToast("岗位对比最多选择 5 个岗位。", "error");
            return;
        }
        comparedJobKeys.add(key);
        showToast("已加入岗位对比。", "success");
        addAnalysisHistoryRecord({
            type: "compare",
            title: `加入对比：${normalizedJob.position_name || normalizedJob.position_code}`,
            summary: `${normalizedJob.department || "招录单位"} · ${normalizedJob.position_name || "未命名岗位"}`,
            related_position_code: getDisplayPositionCode(normalizedJob),
            province: normalizedJob.province,
            year: normalizedJob.year,
            status: "已加入"
        });
    }
    persistCompare();
    refreshJobDependentViews();
}

function analyzeSelectedJob(job) {
    const normalizedJob = normalizeJob(job);
    currentJobContext = normalizedJob;
    lastRecommendationJobs = [normalizedJob];
    const positionCode = getDisplayPositionCode(normalizedJob);
    analyzedJobKeys.add(getJobKey(normalizedJob));
    addAnalysisHistoryRecord({
        type: "single_job_analysis",
        title: `准备分析：${normalizedJob.position_name || positionCode}`,
        summary: "已将岗位带入招考分析师，准备分析资格条件、分数参考和风险。",
        question: positionCode
            ? `分析 ${positionCode} 这个岗位值不值得报。`
            : `分析 ${normalizedJob.department} ${normalizedJob.position_name} 这个岗位值不值得报。`,
        related_position_code: positionCode,
        province: normalizedJob.province,
        year: normalizedJob.year,
        status: "待分析"
    });
    updateDecisionCounts();
    navigateTo("analyst");
    const questionInput = document.getElementById("question");
    questionInput.value = positionCode
        ? `分析 ${positionCode} 这个岗位值不值得报，重点说明资格条件、分数参考和风险。`
        : `分析“${normalizedJob.department} ${normalizedJob.position_name}”这个岗位值不值得报。`;
    resizeAnalystTextarea();
    syncAnalystSubmitState();
    questionInput.focus();
}

async function copyJobCode(job) {
    const positionCode = getDisplayPositionCode(job);
    if (!positionCode) {
        showToast("当前岗位没有可复制的职位代码。", "error");
        return;
    }
    try {
        await navigator.clipboard.writeText(positionCode);
        showToast(`已复制职位代码 ${positionCode}。`, "success");
    } catch {
        const textarea = document.createElement("textarea");
        textarea.value = positionCode;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
        showToast(`已复制职位代码 ${positionCode}。`, "success");
    }
}

function renderShortlist() {
    const list = document.getElementById("shortlistList");
    if (!list) {
        return;
    }
    setText(
        "shortlistSummary",
        shortlistedJobs.length > 0
            ? `已保存 ${shortlistedJobs.length} 个岗位，其中 ${comparedJobKeys.size} 个已加入对比。`
            : ""
    );
    document.getElementById("clearShortlistButton").disabled = shortlistedJobs.length === 0;
    list.innerHTML = shortlistedJobs.length
        ? shortlistedJobs.map((job) => createJobCard(job, { shortlistPage: true, detailed: true })).join("")
        : createEmptyState(
            "你还没有加入备选岗位",
            "可以先去招考分析师推荐岗位，或在单岗位查询中搜索岗位代码后加入备选。",
            "去招考分析师",
            "analyst"
        );
}

function renderCompare() {
    const selector = document.getElementById("compareSelector");
    const content = document.getElementById("compareContent");
    if (!selector || !content) {
        return;
    }
    cleanComparedKeys();
    if (shortlistedJobs.length === 0) {
        selector.innerHTML = "";
        content.innerHTML = createEmptyState(
            "暂无可对比岗位",
            "先把感兴趣的岗位加入备选，再从中选择 2–5 个进行比较。",
            "查看岗位备选",
            "shortlist"
        );
        return;
    }

    const selectedCount = comparedJobKeys.size;
    const options = shortlistedJobs.map((job) => {
        const key = getJobKey(job);
        const checked = comparedJobKeys.has(key);
        const ref = registerJob(job);
        return `
            <label>
                <input type="checkbox" ${checked ? "checked" : ""} data-job-action="toggle-compare" data-job-ref="${ref}">
                <span>${escapeHtml(job.position_name)} · ${escapeHtml(getDisplayPositionCode(job) || "无代码")}</span>
            </label>
        `;
    }).join("");
    selector.innerHTML = `
        <div class="compare-selector-head">
            <div>
                <strong>选择对比岗位</strong>
                <span>已选择 ${selectedCount} 个，支持同时比较 2–5 个岗位。</span>
            </div>
            <span class="badge ${selectedCount >= 2 ? "success" : "risk"}">${selectedCount}/5</span>
        </div>
        <div class="compare-option-list">${options}</div>
    `;

    const selectedJobs = shortlistedJobs.filter((job) => comparedJobKeys.has(getJobKey(job)));
    if (selectedJobs.length < 2) {
        content.innerHTML = createEmptyState(
            "请至少选择 2 个岗位进行对比",
            `当前已选择 ${selectedJobs.length} 个，最多可同时比较 5 个岗位。`
        );
        return;
    }
    content.innerHTML = createCompareTable(selectedJobs);
}

function createCompareTable(jobs) {
    const fields = [
        ["单位", (job) => job.department || job.unit],
        ["岗位名称", (job) => job.position_name],
        ["职位代码", (job) => getDisplayPositionCode(job)],
        ["招录人数", (job) => formatValue(job.recruit_count, " 人")],
        ["学历要求", (job) => job.education],
        ["专业要求摘要", (job) => truncateText(job.major_required || "暂无", 80)],
        ["身份要求", (job) => job.identity_required],
        ["最低进面分", (job) => formatValue(job.score_min)],
        ["分数匹配方式", (job) => formatScoreMatchType(job.score_match_type)],
        ["风险提醒", (job) => truncateText(job.risk_summary || job.risk_level || "待核对", 100)]
    ];
    return `
        <div class="compare-table-wrap">
            <table class="compare-table">
                <thead>
                    <tr>
                        <th scope="col">对比字段</th>
                        ${jobs.map((job) => `<th scope="col">${escapeHtml(job.position_name)}</th>`).join("")}
                    </tr>
                </thead>
                <tbody>
                    ${fields.map(([label, getter]) => `
                        <tr>
                            <th scope="row">${escapeHtml(label)}</th>
                            ${jobs.map((job) => `<td>${escapeHtml(getter(job) || "暂无")}</td>`).join("")}
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function refreshJobDependentViews() {
    renderShortlist();
    renderCompare();
    updateDecisionCounts();
    updateRenderedJobActions();
}

function recordAnalystResult({ answer, data, payload, jobs, policyResponse }) {
    const usedTools = normalizeArray(data?.used_tools).join(" ");
    let type = "chat";
    let title = "招考分析师回复";

    if (policyResponse) {
        type = "policy";
        title = "政策解释";
    } else if (data?.intent === "single_job_query" || usedTools.includes("job_tool.find_single_job")) {
        type = "single_job_analysis";
        title = "单岗位分析";
    } else if (jobs.length > 0 || data?.intent === "job_recommendation" || usedTools.includes("job_tool.search_jobs")) {
        type = "recommendation";
        title = `岗位推荐${jobs.length ? ` · ${jobs.length} 个` : ""}`;
    } else if (data?.intent === "score_or_risk_query" || usedTools.includes("score_tool.search_scores")) {
        type = "score_risk";
        title = "分数与风险分析";
    }

    const normalizedJobs = jobs.map(normalizeJob);
    const firstJob = normalizedJobs[0] || null;
    const recommendedJobs = normalizedJobs.map((job) => ({
        full_position_code: getDisplayPositionCode(job),
        position_name: job.position_name,
        province: job.province,
        year: job.year,
        data_missing: getJobDataMissingFields(job)
    }));
    addAnalysisHistoryRecord({
        type,
        title,
        summary: answer,
        ai_analysis_summary: answer,
        question: payload?.question,
        related_position_code: firstJob ? getDisplayPositionCode(firstJob) : "",
        province: firstJob?.province || payload?.region,
        year: firstJob?.year || dataCatalog?.default_year || 2025,
        recommendation_count: recommendedJobs.length,
        recommended_position_codes: recommendedJobs.map((job) => job.full_position_code).filter(Boolean),
        recommended_position_names: recommendedJobs.map((job) => job.position_name).filter(Boolean),
        recommended_jobs: recommendedJobs,
        data_missing_fields: uniqueValues(recommendedJobs.flatMap((job) => job.data_missing)),
        status: jobs.length === 0 && type === "recommendation" ? "无结果" : "完成"
    });
}

function hydrateAnalyzedJobKeys() {
    analysisHistory.forEach((record) => {
        normalizeArray(record.recommended_jobs).forEach((job) => {
            if (!job.full_position_code) {
                return;
            }
            analyzedJobKeys.add([
                job.province || record.province || "unknown",
                job.year || record.year || 2025,
                job.full_position_code
            ].join("|"));
        });
        if (
            record.related_position_code
            && ["recommendation", "single_job_analysis"].includes(record.type)
        ) {
            analyzedJobKeys.add([
                record.province || "unknown",
                record.year || 2025,
                record.related_position_code
            ].join("|"));
        }
    });
}

function addAnalysisHistoryRecord(record) {
    const normalized = normalizeAnalysisHistoryRecord({
        ...record,
        id: record?.id || createHistoryId(),
        created_at: record?.created_at || new Date().toISOString()
    });
    if (!normalized) {
        return false;
    }

    const previous = analysisHistory;
    analysisHistory = [normalized, ...analysisHistory].slice(0, ANALYSIS_HISTORY_LIMIT);
    if (!saveStoredValue(ANALYSIS_HISTORY_STORAGE_KEY, analysisHistory)) {
        analysisHistory = previous;
        showToast("分析记录保存失败，请检查浏览器存储权限。", "error");
        return false;
    }

    if (
        normalized.related_position_code
        && ["recommendation", "single_job_analysis"].includes(normalized.type)
    ) {
        analyzedJobKeys.add([
            normalized.province || "unknown",
            normalized.year || 2025,
            normalized.related_position_code
        ].join("|"));
    }
    renderAnalysisHistory();
    updateDecisionCounts();
    return true;
}

function normalizeAnalysisHistoryRecord(record) {
    if (!record || typeof record !== "object") {
        return null;
    }
    const allowedTypes = new Set([
        "chat",
        "recommendation",
        "single_job_analysis",
        "policy",
        "score_risk",
        "shortlist",
        "compare",
        "error"
    ]);
    const type = allowedTypes.has(record.type) ? record.type : "chat";
    const recommendedJobs = normalizeArray(record.recommended_jobs)
        .filter((job) => job && typeof job === "object" && !Array.isArray(job))
        .slice(0, 5)
        .map((job) => ({
            full_position_code: getDisplayPositionCode({
                display_position_code: job.full_position_code || job.position_code
            }),
            position_name: truncateText(sanitizeUserFacingText(job.position_name), 100),
            province: truncateText(sanitizeUserFacingText(job.province), 30),
            year: Number(job.year) || 2025,
            data_missing: uniqueValues(
                normalizeArray(job.data_missing)
                    .map((item) => truncateText(sanitizeUserFacingText(item), 40))
                    .filter(Boolean)
            )
        }));
    return {
        id: String(record.id || createHistoryId()),
        type,
        title: truncateText(sanitizeUserFacingText(record.title) || getHistoryTypeLabel(type), 100),
        summary: truncateText(sanitizeUserFacingText(record.summary), 1200),
        ai_analysis_summary: truncateText(
            sanitizeUserFacingText(record.ai_analysis_summary || record.summary),
            1200
        ),
        question: truncateText(sanitizeUserFacingText(record.question), 500),
        created_at: String(record.created_at || new Date().toISOString()),
        related_position_code: getDisplayPositionCode({
            display_position_code: record.related_position_code
        }),
        province: truncateText(sanitizeUserFacingText(record.province), 30),
        year: Number(record.year) || 2025,
        recommendation_count: Math.max(
            0,
            Math.min(Number(record.recommendation_count) || recommendedJobs.length, 5)
        ),
        recommended_position_codes: uniqueValues([
            ...normalizeArray(record.recommended_position_codes)
                .map(normalizePositionCode)
                .filter(Boolean),
            ...recommendedJobs.map((job) => job.full_position_code).filter(Boolean)
        ]).slice(0, 5),
        recommended_position_names: uniqueValues([
            ...normalizeArray(record.recommended_position_names)
                .map((item) => truncateText(sanitizeUserFacingText(item), 100))
                .filter(Boolean),
            ...recommendedJobs.map((job) => job.position_name).filter(Boolean)
        ]).slice(0, 5),
        recommended_jobs: recommendedJobs,
        data_missing_fields: uniqueValues([
            ...normalizeArray(record.data_missing_fields)
                .map((item) => truncateText(sanitizeUserFacingText(item), 40))
                .filter(Boolean),
            ...recommendedJobs.flatMap((job) => job.data_missing)
        ]),
        status: truncateText(sanitizeUserFacingText(record.status) || "完成", 30)
    };
}

function createHistoryId() {
    return globalThis.crypto?.randomUUID?.()
        || `history-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function getHistoryTypeLabel(type) {
    const labels = {
        chat: "对话",
        recommendation: "岗位推荐",
        single_job_analysis: "单岗位分析",
        policy: "政策解释",
        score_risk: "分数风险",
        shortlist: "备选操作",
        compare: "对比操作",
        error: "错误记录"
    };
    return labels[type] || "分析记录";
}

function renderAnalysisHistory() {
    const container = document.getElementById("analysisHistoryList");
    if (!container) {
        return;
    }
    const type = getValue("historyTypeFilter");
    const records = type
        ? analysisHistory.filter((record) => record.type === type)
        : analysisHistory;

    setText(
        "historySummary",
        analysisHistory.length
            ? `共保存 ${analysisHistory.length} 条记录${type ? `，当前显示 ${records.length} 条` : ""}。`
            : ""
    );
    const clearButton = document.getElementById("clearHistoryButton");
    if (clearButton) {
        clearButton.disabled = analysisHistory.length === 0;
    }
    container.innerHTML = records.length
        ? records.map(renderAnalysisHistoryItem).join("")
        : createEmptyState(
            "暂无分析记录",
            "你可以先向招考分析师提问，或查询一个岗位。",
            "去招考分析师",
            "analyst"
        );
}

function renderAnalysisHistoryItem(record) {
    const createdAt = new Date(record.created_at);
    const time = Number.isNaN(createdAt.getTime())
        ? "时间未知"
        : createdAt.toLocaleString("zh-CN", {
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit"
        });
    const positionAction = record.related_position_code
        ? `<button class="history-position-button" type="button" data-history-action="open-position" data-history-id="${escapeHtml(record.id)}">职位代码 ${escapeHtml(record.related_position_code)}</button>`
        : "";
    const recommendationMeta = record.type === "recommendation" && record.recommendation_count > 0
        ? `<p class="history-summary"><strong>推荐岗位</strong>${escapeHtml(`${record.recommendation_count} 个 · ${record.recommended_position_names.join("、")}`)}</p>`
        : "";
    const missingMeta = record.data_missing_fields.length > 0
        ? `<p class="history-summary"><strong>数据缺失</strong>${escapeHtml(record.data_missing_fields.join("、"))}</p>`
        : "";
    return `
        <article class="history-item">
            <div class="history-item-head">
                <div>
                    <span class="badge ${record.type === "error" ? "danger" : "primary"}">${escapeHtml(getHistoryTypeLabel(record.type))}</span>
                    <h2>${escapeHtml(record.title)}</h2>
                </div>
                <time datetime="${escapeHtml(record.created_at)}">${escapeHtml(time)}</time>
            </div>
            ${record.question ? `<p class="history-question"><strong>问题</strong>${escapeHtml(record.question)}</p>` : ""}
            ${record.summary ? `<p class="history-summary">${escapeHtml(record.summary)}</p>` : ""}
            ${recommendationMeta}
            ${missingMeta}
            <div class="history-meta">
                ${record.province ? `<span>${escapeHtml(record.province)}</span>` : ""}
                ${record.year ? `<span>${escapeHtml(record.year)} 年</span>` : ""}
                <span>${escapeHtml(record.status)}</span>
                ${positionAction}
            </div>
            <div class="history-actions">
                <button class="quiet-button" type="button" data-history-action="copy" data-history-id="${escapeHtml(record.id)}">复制记录</button>
            </div>
        </article>
    `;
}

function clearAnalysisHistory() {
    if (analysisHistory.length === 0) {
        return;
    }
    if (!window.confirm("确定清空全部分析记录吗？此操作无法撤销。")) {
        return;
    }
    const previous = analysisHistory;
    analysisHistory = [];
    if (!saveStoredValue(ANALYSIS_HISTORY_STORAGE_KEY, analysisHistory)) {
        analysisHistory = previous;
        showToast("分析记录清空失败，请检查浏览器存储权限。", "error");
        return;
    }
    analyzedJobKeys.clear();
    renderAnalysisHistory();
    updateDecisionCounts();
    showToast("已清空分析记录。", "success");
}

function handleHistoryAction(action, id) {
    const record = analysisHistory.find((item) => item.id === id);
    if (!record) {
        showToast("这条分析记录已不存在。", "error");
        return;
    }
    if (action === "copy") {
        copyHistoryRecord(record);
    } else if (action === "open-position" && record.related_position_code) {
        navigateTo("single-job");
        setValue("singleJobQuery", record.related_position_code);
        if (record.province) {
            setValue("singleJobProvince", record.province);
        }
        document.getElementById("singleJobQuery")?.focus();
    }
}

async function copyHistoryRecord(record) {
    const text = [
        `[${getHistoryTypeLabel(record.type)}] ${record.title}`,
        record.question ? `问题：${record.question}` : "",
        record.summary ? `记录：${record.summary}` : "",
        record.related_position_code ? `职位代码：${record.related_position_code}` : "",
        `时间：${record.created_at}`
    ].filter(Boolean).join("\n");
    try {
        await navigator.clipboard.writeText(text);
    } catch {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        textarea.remove();
    }
    showToast("分析记录已复制。", "success");
}

function updateDecisionCounts() {
    const shortlistCount = shortlistedJobs.length;
    const compareCount = comparedJobKeys.size;
    const analyzedCount = analyzedJobKeys.size;
    setText("contextShortlistCount", shortlistCount);
    setText("contextCompareCount", compareCount);
    setText("contextRecentAnalysisCount", analyzedCount > 0 ? analyzedCount : "暂无");
    setText("overviewShortlistCount", shortlistCount);
    setText("overviewCompareCount", compareCount);
    setText("overviewAnalysisStatus", analyzedCount > 0 ? `${analyzedCount} 个岗位` : "暂无");
    const navCount = document.getElementById("shortlistNavCount");
    if (navCount) {
        navCount.textContent = shortlistCount;
        navCount.hidden = shortlistCount === 0;
    }
    updateDecisionGuidance();
}

function updateDecisionGuidance() {
    const action = document.getElementById("contextNextStepAction");
    let text = "";
    let actionLabel = "";
    let route = "";

    if (!isProfileComplete(userProfile)) {
        text = "建议先完善画像，分析师可以更准确地推荐岗位。";
        actionLabel = "去完善画像";
        route = "profile";
    } else if (shortlistedJobs.length === 0) {
        text = "建议先让分析师推荐 1–3 个岗位加入备选。";
        actionLabel = "去找岗位";
        route = "analyst";
    } else if (shortlistedJobs.length === 1) {
        text = "建议再加入 1–2 个岗位后进行对比。";
        actionLabel = "继续找岗位";
        route = "analyst";
    } else {
        text = "建议进入岗位对比，比较招录人数、分数、限制和风险。";
        actionLabel = "进入岗位对比";
        route = "compare";
    }

    setText("contextNextStep", text);
    if (action) {
        action.textContent = actionLabel;
        action.dataset.routeTarget = route;
    }
}

function updateRenderedJobActions() {
    document.querySelectorAll('[data-job-action="toggle-shortlist"]').forEach((button) => {
        const job = jobRegistry.get(button.dataset.jobRef);
        if (!job) {
            return;
        }
        const shortlisted = hasShortlistedJob(job);
        button.textContent = shortlisted ? "已加入" : "加入备选";
        button.classList.toggle("primary-action", !shortlisted);
        button.classList.toggle("selected-action", shortlisted);
    });
    document.querySelectorAll('[data-job-action="toggle-compare"]').forEach((button) => {
        const job = jobRegistry.get(button.dataset.jobRef);
        if (!job) {
            return;
        }
        button.textContent = comparedJobKeys.has(getJobKey(job)) ? "移出对比" : "加入对比";
    });
}

function persistShortlist() {
    const saved = saveStoredValue(SHORTLIST_STORAGE_KEY, shortlistedJobs);
    if (!saved) {
        showToast("备选岗位保存失败，请检查浏览器存储权限。", "error");
    }
    return saved;
}

function persistCompare() {
    const saved = saveStoredValue(COMPARE_STORAGE_KEY, Array.from(comparedJobKeys));
    if (!saved) {
        showToast("对比选择保存失败，请检查浏览器存储权限。", "error");
    }
    return saved;
}

function cleanComparedKeys() {
    const previousKeys = Array.from(comparedJobKeys);
    const validKeys = new Set(shortlistedJobs.map(getJobKey));
    comparedJobKeys = new Set(Array.from(comparedJobKeys).filter((key) => validKeys.has(key)));
    if (previousKeys.length !== comparedJobKeys.size) {
        persistCompare();
    }
}

function hasShortlistedJob(job) {
    const key = getJobKey(job);
    return shortlistedJobs.some((item) => getJobKey(item) === key);
}

function getJobKey(job) {
    const normalized = normalizeJob(job);
    return [
        normalized.province || "unknown",
        normalized.year || 2025,
        getDisplayPositionCode(normalized) || `${normalized.department}-${normalized.position_name}`
    ].join("|");
}

function migrateComparedJobKeys(storedJobs, normalizedJobs) {
    let changed = false;
    storedJobs.forEach((storedJob, index) => {
        const normalizedJob = normalizedJobs[index];
        if (!normalizedJob) {
            return;
        }
        const legacyPositionCode = selectCompletePositionCode(
            storedJob?.position_code,
            storedJob?.["职位代码"],
            storedJob?.["岗位代码"],
            storedJob?.full_position_code,
            storedJob?.job_id
        );
        const legacyKey = [
            String(storedJob?.province || storedJob?.region || "unknown").trim() || "unknown",
            Number(storedJob?.year || storedJob?.job_source_year || 2025),
            legacyPositionCode
                || `${String(storedJob?.department || storedJob?.unit || "").trim()}-${String(storedJob?.position_name || storedJob?.position || "未命名岗位").trim()}`
        ].join("|");
        const currentKey = getJobKey(normalizedJob);
        if (legacyKey !== currentKey && comparedJobKeys.has(legacyKey)) {
            comparedJobKeys.delete(legacyKey);
            comparedJobKeys.add(currentKey);
            changed = true;
        }
    });
    if (changed) {
        saveStoredValue(COMPARE_STORAGE_KEY, Array.from(comparedJobKeys));
    }
}

function handleImportFileChange() {
    const fileInput = document.getElementById("importFile");
    const file = fileInput?.files?.[0];
    renderImportFileSelection(file || null);
    if (file) {
        applyImportMetaAutoDetect(file.name, { overwrite: true, showHint: true });
    } else {
        renderImportAutoDetectHint("", "");
    }
}


function applyImportMetaAutoDetect(fileName, options = {}) {
    const { overwrite = true, showHint = true } = options;
    const detected = inferImportMetaFromFileName(fileName);
    const applied = [];

    if (detected.province && (overwrite || !getValue("importProvince"))) {
        setValue("importProvince", detected.province);
        applied.push(`省份 ${detected.province}`);
    }
    if (detected.exam_type && (overwrite || !getValue("importExamType"))) {
        setValue("importExamType", detected.exam_type);
        applied.push(`考试类型 ${detected.exam_type}`);
    }
    if (detected.year && (overwrite || !getValue("importYear") || getValue("importYear") === "2025")) {
        setValue("importYear", detected.year);
        applied.push(`年份 ${detected.year}`);
    }

    if (showHint) {
        if (applied.length) {
            renderImportAutoDetectHint(`已从文件名自动识别：${applied.join(" · ")}，可手动修改。`, "");
        } else {
            renderImportAutoDetectHint("未从文件名识别出省份、考试类型或年份，请手动填写后再上传。", "warning");
        }
    }
    return detected;
}

function inferImportMetaFromFileName(fileName) {
    const rawName = String(fileName || "").replace(/\.[^.]+$/, "");
    const compactName = rawName.replace(/[\s_\-—–·.()（）【】\[\]]+/g, "");
    const lowerName = rawName.toLowerCase();
    const compactLowerName = compactName.toLowerCase();
    return {
        province: detectImportProvince(`${compactName} ${rawName}`),
        exam_type: detectImportExamType(`${compactLowerName} ${lowerName}`),
        year: detectImportYear(rawName)
    };
}

function detectImportProvince(text) {
    const lowerText = String(text || "").toLowerCase();
    const aliasPairs = IMPORT_PROVINCE_ALIASES.flatMap(([value, aliases]) => (
        aliases.map((alias) => ({ value, alias: String(alias).toLowerCase() }))
    )).sort((a, b) => b.alias.length - a.alias.length);
    const matched = aliasPairs.find(({ alias }) => alias && lowerText.includes(alias));
    return matched?.value || "";
}

function detectImportExamType(text) {
    const value = String(text || "").toLowerCase();
    if (/国考|国家公务员|中央机关|中央国家机关|guokao|nationalcivilservice/.test(value)) {
        return "国考";
    }
    if (/事业单位|事业编|事业岗|事业人员|shiyedanwei/.test(value)) {
        return "事业单位";
    }
    if (/省考|公务员|公考|公安|法检|法院|检察院|选调生|civilservice/.test(value)) {
        return "公务员";
    }
    return "";
}

function detectImportYear(text) {
    const match = String(text || "").match(/(?:20)\d{2}/);
    return match ? match[0] : "";
}

function normalizeImportProvinceInput(value) {
    const text = String(value || "").trim();
    if (!text) {
        return "";
    }
    return detectImportProvince(text) || text;
}

function renderImportAutoDetectHint(message, type) {
    const hint = document.getElementById("importAutoDetectHint");
    if (!hint) {
        return;
    }
    hint.hidden = !message;
    hint.textContent = message || "";
    hint.className = `import-auto-detect-hint ${type || ""}`.trim();
}

function renderImportFileSelection(file) {
    const field = document.querySelector(".import-file-field");
    const emptyState = document.getElementById("importFileEmptyState");
    const selectedState = document.getElementById("importFileSelectedState");
    const selectedName = document.getElementById("importSelectedFileName");
    const hasFile = Boolean(file);
    field?.classList.toggle("has-file", hasFile);
    emptyState?.toggleAttribute("hidden", hasFile);
    selectedState?.toggleAttribute("hidden", !hasFile);
    if (selectedName) {
        selectedName.textContent = file?.name || "已选择文件";
        selectedName.title = file?.name || "";
    }
}

function resetImportForm() {
    document.getElementById("importUploadForm")?.reset();
    setValue("importYear", "2025");
    renderImportFileSelection(null);
    renderImportAutoDetectHint("", "");
    currentImportPreview = null;
    document.getElementById("importPreviewSection")?.setAttribute("hidden", "");
    document.getElementById("importConfirmSection")?.setAttribute("hidden", "");
    const confirmButton = document.getElementById("importConfirmButton");
    if (confirmButton) {
        confirmButton.disabled = false;
        confirmButton.textContent = "确认入库";
    }
    renderImportStatus("", "");
}

async function handleImportUpload(event) {
    event.preventDefault();
    const fileInput = document.getElementById("importFile");
    const file = fileInput?.files?.[0];
    if (!file) {
        const message = "请先选择一个 .xlsx / .xls / .csv 文件。";
        renderImportStatus(message, "error");
        showToast(message, "error");
        return;
    }
    if (!isSupportedImportFile(file.name)) {
        const message = "文件解析失败，请检查文件格式是否为 .xlsx / .xls / .csv。";
        renderImportStatus(message, "error");
        showToast(message, "error");
        return;
    }

    const button = document.getElementById("importUploadButton");
    const detectedMeta = inferImportMetaFromFileName(file.name);
    const normalizedProvince = normalizeImportProvinceInput(getValue("importProvince")) || detectedMeta.province;
    if (normalizedProvince && normalizedProvince !== getValue("importProvince")) {
        setValue("importProvince", normalizedProvince);
    }
    if (!getValue("importExamType") && detectedMeta.exam_type) {
        setValue("importExamType", detectedMeta.exam_type);
    }
    if ((!getValue("importYear") || getValue("importYear") === "2025") && detectedMeta.year) {
        setValue("importYear", detectedMeta.year);
    }
    const formData = new FormData();
    formData.append("file", file);
    const province = getValue("importProvince");
    const examType = getValue("importExamType") || detectedMeta.exam_type;
    const year = getValue("importYear") || detectedMeta.year;
    if (province) {
        formData.append("province", province);
    }
    if (examType) {
        formData.append("exam_type", examType);
    }
    if (year) {
        formData.append("year", year);
    }

    setButtonLoading(button, true, "识别中…");
    renderImportStatus("正在上传并识别文件…", "loading");
    document.getElementById("importPreviewSection")?.setAttribute("hidden", "");
    document.getElementById("importConfirmSection")?.setAttribute("hidden", "");

    try {
        const uploaded = await importFetchJson(`${IMPORTS_API_URL}/upload`, {
            method: "POST",
            body: formData
        });
        const preview = await importFetchJson(`${IMPORTS_API_URL}/${encodeURIComponent(uploaded.task_id)}/preview`);
        currentImportPreview = preview;
        if (!getValue("importProvince") && preview?.province) {
            setValue("importProvince", preview.province);
        }
        if (preview?.year) {
            setValue("importYear", preview.year);
        }
        renderImportPreview(preview);
        if (Number(preview?.valid_rows || 0) <= 0) {
            showToast("识别完成，但没有有效记录，不能入库。", "warning");
        } else if (preview?.requires_output_confirmation) {
            showToast("检测到混合表，请确认输出数据集和各自字段映射。", "warning");
        } else if (preview?.requires_type_confirmation) {
            showToast("系统不确定该文件类型，请手动确认数据类型和字段映射。", "warning");
        } else {
            showToast("识别完成，等待确认入库。", "success");
        }
    } catch (error) {
        const message = translateImportError(error);
        currentImportPreview = null;
        renderImportStatus(message, "error");
        document.getElementById("importPreviewSection")?.setAttribute("hidden", "");
        showToast(message, "error");
        console.error("Import upload failed:", error);
    } finally {
        setButtonLoading(button, false);
    }
}

async function handleImportConfirm() {
    const taskId = currentImportPreview?.task_id;
    if (!taskId) {
        const message = "请先上传文件并生成预览，再确认入库。";
        renderImportStatus(message, "error");
        showToast(message, "error");
        return;
    }
    if (Number(currentImportPreview?.valid_rows || 0) <= 0) {
        const message = "识别完成，但没有有效记录，不能入库。";
        renderImportStatus(message, "error");
        showToast(message, "error");
        return;
    }
    if (currentImportPreview?.importable === false) {
        const message = "当前文件类型暂不支持入库，请重新选择表类型或文件。";
        renderImportStatus(message, "error");
        showToast(message, "error");
        return;
    }
    const blockingReasons = normalizeArray(currentImportPreview?.blocking_reasons).filter(Boolean);
    if (currentImportPreview?.requires_type_confirmation || blockingReasons.length) {
        const message = blockingReasons[0]
            || "系统不确定该文件类型，请手动确认数据类型和字段映射。";
        renderImportStatus(message, "warning");
        showToast(message, "warning");
        return;
    }
    const button = document.getElementById("importConfirmButton");
    setButtonLoading(button, true, "入库中…");
    renderImportStatus("正在写入结构化数据源…", "loading");

    let finalButtonText = "确认入库";
    let finalButtonDisabled = false;
    try {
        const result = await importFetchJson(`${IMPORTS_API_URL}/${encodeURIComponent(taskId)}/confirm`, {
            method: "POST"
        });
        renderImportConfirmResult(result);
        const insertedCount = Number(result?.inserted_count ?? result?.inserted_rows ?? 0);
        const skippedCount = Number(result?.skipped_count ?? result?.skipped_rows ?? 0);
        const isImported = result?.status === "IMPORTED" && insertedCount > 0;
        const isPartial = result?.status === "PARTIAL_IMPORTED" && insertedCount > 0;
        if (isImported || isPartial) {
            const message = isPartial
                ? `部分入库成功：成功 ${formatNumber(insertedCount)} 条，跳过 ${formatNumber(skippedCount)} 条。`
                : `入库完成：成功写入 ${formatNumber(insertedCount)} 条，跳过 ${formatNumber(skippedCount)} 条。`;
            renderImportStatus(message, isPartial ? "warning" : "success");
            showToast(message, isPartial ? "warning" : "success");
            window.dispatchEvent(new CustomEvent("import:confirmed", { detail: result }));
            finalButtonText = isPartial ? "部分入库完成" : "入库完成";
            finalButtonDisabled = true;
        } else {
            const message = result?.message || "入库失败：有效记录未写入数据库，请查看错误原因。";
            renderImportStatus(message, "error");
            showToast(message, "error");
            finalButtonText = "入库失败";
            finalButtonDisabled = true;
        }
    } catch (error) {
        const message = translateImportError(error);
        renderImportStatus(message, "error");
        showToast(message, "error");
        console.error("Import confirm failed:", error);
    } finally {
        setButtonLoading(button, false);
        if (button) {
            button.disabled = finalButtonDisabled;
            button.textContent = finalButtonText;
        }
    }
}

async function importFetchJson(url, options = {}) {
    const headers = {
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...(options.headers || {})
    };
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
        throw new Error(await readResponseError(response));
    }
    return response.json();
}

function renderImportPreview(data) {
    const section = document.getElementById("importPreviewSection");
    if (!section) {
        return;
    }
    section.hidden = false;
    const isUnknown = !data?.detected_type || data.detected_type === "unknown";
    const hasValidRows = Number(data?.valid_rows || 0) > 0;
    const lowConfidence = Boolean(data?.requires_type_confirmation)
        || Boolean(data?.requires_output_confirmation)
        || (!data?.type_confirmed && Number(data?.confidence || 0) < IMPORT_LOW_CONFIDENCE_THRESHOLD);
    const isUnsupported = data?.importable === false && !isUnknown;
    const blockingReasons = normalizeArray(data?.blocking_reasons).filter(Boolean);
    let statusMessage = data?.template_message || (data?.multi_output
        ? "检测到该 Sheet 可生成多个数据集，请确认输出列表和各自字段映射。"
        : "识别完成，等待确认入库。");
    let statusType = "success";
    if (isUnknown) {
        statusMessage = "无法识别数据类型，请检查表头，或手动选择数据类型后重新清洗预览。";
        statusType = "error";
    } else if (isUnsupported) {
        statusMessage = data?.blocking_reasons?.[0] || "当前文件类型暂不支持入库。";
        statusType = "error";
    } else if (!hasValidRows) {
        statusMessage = "识别完成，但没有有效记录，不能入库。请查看缺失字段和 warning 明细。";
        statusType = "error";
    } else if (data?.requires_output_confirmation) {
        statusMessage = "检测到该 Sheet 可生成多个数据集，请确认输出列表和各自字段映射后重新清洗预览。";
        statusType = "warning";
    } else if (lowConfidence || blockingReasons.length) {
        statusMessage = blockingReasons[0]
            || "系统不确定该文件类型，请手动确认数据类型和字段映射。";
        statusType = "warning";
    }
    renderImportStatus(statusMessage, statusType);
    const confirmButton = document.getElementById("importConfirmButton");
    if (confirmButton) {
        const canConfirm = !isUnknown
            && !isUnsupported
            && hasValidRows
            && !lowConfidence
            && blockingReasons.length === 0
            && data?.status === "PREVIEW_READY";
        confirmButton.disabled = !canConfirm;
        confirmButton.textContent = "确认入库";
        confirmButton.title = canConfirm
            ? ""
            : (data?.blocking_reasons || []).join("；") || "请先修正预览中的问题";
    }
    renderImportWorkflowSteps(data);
    renderImportSummary(data);
    renderImportFieldMapping(data);
    renderImportPreviewRows(data?.preview_rows, data?.outputs);
    renderImportWarnings(data?.warnings, data?.warning_summary, data?.import_report);
}

function renderImportSummary(data) {
    const container = document.getElementById("importSummary");
    if (!container) {
        return;
    }
    const items = [
        ["识别类型", data?.detected_type_label || "未识别"],
        ...(data?.multi_output ? [["输出数据集", `${normalizeArray(data?.outputs).length} 个`]] : []),
        ["识别置信度", formatConfidence(data?.confidence)],
        ["数据粒度", formatImportGranularity(data?.data_granularity)],
        ["省份", data?.province || "未识别"],
        ["年份", data?.year || "未识别"],
        ["考试类型", data?.exam_type || "未识别"],
        [data?.multi_output ? "读取源行" : "读取记录", formatNumber(data?.total_rows)],
        [data?.multi_output ? "有效输出记录" : "有效记录", formatNumber(data?.valid_rows)],
        [data?.multi_output ? "输出异常记录" : "异常记录", formatNumber(data?.warning_rows)],
        ["当前状态", formatImportWorkflowStatus(data?.status)],
        ...(data?.header_row ? [["主表头行", `第 ${data.header_row} 行`]] : []),
        ...(data?.sub_header_row ? [["二级表头行", `第 ${data.sub_header_row} 行`]] : []),
        ...(data?.data_start_row ? [["数据起始行", `第 ${data.data_start_row} 行`]] : []),
        ...(data?.sheet_summary ? [["工作表", data.sheet_summary]] : []),
        ...(data?.template_name ? [["复用模板", data.template_name]] : [])
    ];
    container.innerHTML = items.map(([label, value]) => `
        <div>
            <span>${escapeHtml(label)}</span>
            <strong title="${escapeHtml(value)}">${escapeHtml(value)}</strong>
        </div>
    `).join("");
}

function renderImportWorkflowSteps(data) {
    const container = document.getElementById("importWorkflowSteps");
    if (!container) {
        return;
    }
    const status = String(data?.status || "");
    const activeStep = status === "NEED_TYPE_CONFIRMATION"
        ? 2
        : (status === "NEED_FIELD_MAPPING" ? 3 : 4);
    const steps = data?.multi_output
        ? ["上传文件", "确认 Sheet", "确认多输出映射", "清洗预览并入库"]
        : ["上传文件", "确认类型", "字段映射", "清洗预览并入库"];
    container.innerHTML = steps.map((label, index) => {
        const step = index + 1;
        const state = step < activeStep ? "complete" : (step === activeStep ? "active" : "pending");
        return `<li class="${state}" ${state === "active" ? 'aria-current="step"' : ""}><span>${step}</span><strong>${label}</strong></li>`;
    }).join("");
}

function formatImportWorkflowStatus(status) {
    const labels = {
        AUTO_DETECTED: "自动识别完成",
        NEED_TYPE_CONFIRMATION: "需要确认类型",
        NEED_FIELD_MAPPING: "需要字段映射",
        MAPPING_READY: "映射完成",
        PREVIEW_READY: "清洗预览可确认",
        IMPORTED: "已入库",
        PARTIAL_IMPORTED: "部分入库完成",
        IMPORT_FAILED: "入库失败"
    };
    return labels[status] || status || "--";
}

function formatImportGranularity(value) {
    const labels = {
        candidate_level: "候选人级成绩",
        job_level: "岗位级成绩",
        candidate_list_level: "候选人名单",
        summary_level: "汇总参考",
        region_level: "地区级成绩",
        mixed_sheet: "同一 Sheet 多输出",
        unknown: "未识别"
    };
    return labels[value] || value || "未识别";
}

function renderImportFieldMapping(data) {
    const container = document.getElementById("importFieldMapping");
    if (!container) {
        return;
    }
    if (data?.multi_output && normalizeArray(data?.outputs).length) {
        renderImportMultiOutputMapping(container, data);
        return;
    }
    const mapping = data?.field_mapping || {};
    const sourceMapping = data?.field_mapping_by_source
        || invertImportMapping(mapping || {});
    const sourceHeaders = uniqueValues([
        ...normalizeArray(data?.source_headers),
        ...Object.values(mapping || {}),
        ...Object.keys(sourceMapping || {})
    ]).filter(Boolean);
    const previewStandardFields = normalizeArray(data?.standard_fields);
    const standardFields = uniqueValues(
        previewStandardFields.length ? previewStandardFields : IMPORT_FIELD_ORDER
    ).filter((field) => field && !IMPORT_MAPPING_PROTECTED_FIELDS.has(field));
    const fieldStatuses = normalizeArray(data?.field_status);
    const importDataTypes = normalizeArray(data?.available_types)
        .filter((item) => item?.type_key && item?.label)
        .map((item) => [item.type_key, item.label]);
    const typeOptions = importDataTypes.length
        ? [...importDataTypes, ["unknown", "未识别表（仅确认，不可入库）"]]
        : DEFAULT_IMPORT_DATA_TYPES;
    const sheetOptions = normalizeArray(data?.sheet_options).filter(Boolean);

    container.innerHTML = `
        ${renderImportTypeCandidates(data?.type_candidates)}
        <div class="import-structure-controls">
            <label>工作表
                <select id="importSelectedSheet">
                    <option value="">全部可识别工作表</option>
                    ${sheetOptions.map((sheet) => `<option value="${escapeHtml(sheet)}" ${data?.selected_sheet === sheet ? "selected" : ""}>${escapeHtml(sheet)}</option>`).join("")}
                </select>
            </label>
            <label>主表头行
                <input id="importHeaderRow" type="number" min="1" inputmode="numeric" value="${escapeHtml(data?.header_row || "")}" placeholder="自动识别">
            </label>
            <label>二级表头行（可选）
                <input id="importSubHeaderRow" type="number" min="1" inputmode="numeric" value="${escapeHtml(data?.sub_header_row || "")}" placeholder="无">
            </label>
            <label>数据起始行
                <input id="importDataStartRow" type="number" min="1" inputmode="numeric" value="${escapeHtml(data?.data_start_row || "")}" placeholder="自动识别">
            </label>
        </div>
        <div class="import-type-control">
            <label for="importDetectedType">数据类型</label>
            <select id="importDetectedType">
                <option value="">请选择数据类型</option>
                ${typeOptions.map(([value, label]) => `
                    <option value="${escapeHtml(value)}" ${data?.detected_type === value ? "selected" : ""}>
                        ${escapeHtml(label)}
                    </option>
                `).join("")}
            </select>
            <small>${data?.requires_type_confirmation ? "系统不确定该文件类型，请手动确认类型、表头和字段映射。" : "如自动识别不准确，可手动切换后重新清洗。"}</small>
        </div>
        ${fieldStatuses.length ? `
            <div class="import-field-checks" aria-label="字段映射完整性">
                ${fieldStatuses.map(renderImportFieldStatus).join("")}
            </div>
        ` : ""}
        ${sourceHeaders.length ? `
            <div class="mapping-editor">
                ${sourceHeaders.map((source) => `
                    <label class="mapping-item editable-mapping-item">
                        <span title="${escapeHtml(source)}">${escapeHtml(source)}</span>
                        <select class="import-mapping-select" data-source-header="${escapeHtml(source)}">
                            <option value="">保留为原表字段（不映射）</option>
                            ${standardFields.map((field) => `
                                <option value="${escapeHtml(field)}" ${sourceMapping?.[source] === field ? "selected" : ""}>
                                    ${escapeHtml(getImportMappingFieldLabel(field))}（${escapeHtml(field)}）
                                </option>
                            `).join("")}
                        </select>
                    </label>
                `).join("")}
            </div>
        ` : '<div class="empty-state compact-empty"><strong>暂无字段映射</strong><p>请选择数据类型并重新清洗，或检查源文件表头。</p></div>'}
        <div class="import-template-controls">
            <label>模板名称
                <input id="importTemplateName" type="text" value="${escapeHtml(defaultImportTemplateName())}" placeholder="例如：黑龙江上岸分数汇总模板">
            </label>
            <div class="import-template-actions">
                <button class="quiet-button" type="button" data-ui-action="import-remap">重新清洗预览</button>
                <button class="quiet-button" type="button" data-ui-action="import-save-template">保存为模板</button>
            </div>
        </div>
    `;
    initializeCustomSelects(container);
}

function renderImportMultiOutputMapping(container, data) {
    const sheetOptions = normalizeArray(data?.sheet_options).filter(Boolean);
    const outputs = normalizeArray(data?.outputs);
    container.innerHTML = `
        <div class="import-multi-output-notice" role="status">
            <strong>检测到该 Sheet 可生成多个数据集</strong>
            <span>${escapeHtml(data?.mixed_output_label || data?.detected_type_label || "混合结构化数据")}</span>
            <small>自动识别仅作为推荐。请确认工作表、行范围、启用的输出和每个输出的字段映射。</small>
        </div>
        <div class="import-structure-controls">
            <label>工作表
                <select id="importSelectedSheet">
                    ${sheetOptions.map((sheet) => `<option value="${escapeHtml(sheet)}" ${data?.selected_sheet === sheet ? "selected" : ""}>${escapeHtml(sheet)}</option>`).join("")}
                </select>
            </label>
            <label>主表头行
                <input id="importHeaderRow" type="number" min="1" inputmode="numeric" value="${escapeHtml(data?.header_row || "")}" placeholder="自动识别">
            </label>
            <label>二级表头行（可选）
                <input id="importSubHeaderRow" type="number" min="1" inputmode="numeric" value="${escapeHtml(data?.sub_header_row || "")}" placeholder="无">
            </label>
            <label>数据起始行
                <input id="importDataStartRow" type="number" min="1" inputmode="numeric" value="${escapeHtml(data?.data_start_row || "")}" placeholder="自动识别">
            </label>
        </div>
        <div class="import-output-list" aria-label="输出数据集列表">
            ${outputs.map((output, outputIndex) => renderImportOutputMapping(output, outputIndex)).join("")}
        </div>
        <div class="import-template-controls">
            <label>模板名称
                <input id="importTemplateName" type="text" value="${escapeHtml(defaultImportTemplateName())}" placeholder="例如：省考混合表多输出模板">
            </label>
            <div class="import-template-actions">
                <button class="quiet-button" type="button" data-ui-action="import-remap">确认配置并重新清洗</button>
                <button class="quiet-button" type="button" data-ui-action="import-save-template">保存多输出模板</button>
            </div>
        </div>
    `;
    initializeCustomSelects(container);
}

function renderImportOutputMapping(output, outputIndex) {
    const mapping = output?.field_mapping || {};
    const sourceMapping = output?.field_mapping_by_source || invertImportMapping(mapping);
    const sourceHeaders = uniqueValues([
        ...normalizeArray(output?.source_headers),
        ...Object.values(mapping),
        ...Object.keys(sourceMapping)
    ]).filter(Boolean);
    const standardFields = uniqueValues(
        normalizeArray(output?.standard_fields).length
            ? output.standard_fields
            : IMPORT_FIELD_ORDER
    ).filter((field) => field && !IMPORT_MAPPING_PROTECTED_FIELDS.has(field));
    const fieldLabels = output?.field_labels || {};
    const detailsOpen = outputIndex === 0 ? "open" : "";
    return `
        <details class="import-output-card" ${detailsOpen}>
            <summary>
                <span><strong>${escapeHtml(output?.dataset_type_label || output?.dataset_type || "输出数据集")}</strong><small>正式结构化数据源</small></span>
                <span class="import-output-counts">有效 ${formatNumber(output?.valid_rows)} · warning ${formatNumber(output?.warning_rows)}</span>
            </summary>
            <div class="import-output-body">
                <label class="import-output-toggle">
                    <input class="import-output-enabled" type="checkbox" data-output-index="${outputIndex}" checked>
                    <span>确认生成该数据集</span>
                </label>
                <p class="import-output-dedupe">去重键：${escapeHtml(normalizeArray(output?.dedupe_keys).join(" + ") || "按数据类型默认规则")}</p>
                ${normalizeArray(output?.field_status).length ? `
                    <div class="import-field-checks" aria-label="${escapeHtml(output?.dataset_type_label || "输出")}字段完整性">
                        ${normalizeArray(output.field_status).map((item) => renderImportFieldStatus(item, fieldLabels)).join("")}
                    </div>
                ` : ""}
                <div class="mapping-editor">
                    ${sourceHeaders.map((source) => `
                        <label class="mapping-item editable-mapping-item">
                            <span title="${escapeHtml(source)}">${escapeHtml(source)}</span>
                            <select class="import-output-mapping-select" data-output-index="${outputIndex}" data-source-header="${escapeHtml(source)}">
                                <option value="">保留为原表字段（不映射）</option>
                                ${standardFields.map((field) => `
                                    <option value="${escapeHtml(field)}" ${sourceMapping?.[source] === field ? "selected" : ""}>
                                        ${escapeHtml(fieldLabels?.[field] || getImportMappingFieldLabel(field))}（${escapeHtml(field)}）
                                    </option>
                                `).join("")}
                            </select>
                        </label>
                    `).join("")}
                </div>
            </div>
        </details>
    `;
}

function renderImportTypeCandidates(candidates) {
    const items = normalizeArray(candidates).slice(0, 6);
    if (!items.length) {
        return "";
    }
    return `
        <section class="import-type-candidates" aria-labelledby="importTypeCandidatesTitle">
            <div class="import-block-heading">
                <strong id="importTypeCandidatesTitle">候选类型评分</strong>
                <span>评分接近时必须人工确认</span>
            </div>
            <div class="import-type-candidate-grid">
                ${items.map((item, index) => {
                    const hits = uniqueValues([
                        ...normalizeArray(item?.matched_keywords),
                        ...normalizeArray(item?.matched_features)
                    ]).slice(0, 5);
                    return `
                        <article class="import-type-candidate ${index === 0 ? "leading" : ""}">
                            <div><strong>${escapeHtml(item?.type_label || item?.type_key || "未知类型")}</strong><b>${escapeHtml(formatConfidence(item?.score))}</b></div>
                            <p>${hits.length ? `命中特征：${escapeHtml(hits.join("、"))}` : "未命中明显结构特征"}</p>
                        </article>
                    `;
                }).join("")}
            </div>
        </section>
    `;
}

function renderImportFieldStatus(item, fieldLabels = {}) {
    const requirement = item?.requirement === "required"
        ? "必填"
        : (item?.requirement === "required_any" ? "同组字段至少一项" : "可选");
    const isMissing = item?.satisfied === false;
    const stateText = isMissing
        ? "缺失或未映射"
        : (item?.mapped ? `已映射：${item.source}` : "未映射（将保留为原表字段）");
    return `
        <article class="import-field-check ${isMissing ? "missing" : (item?.mapped ? "mapped" : "optional")}">
            <div>
                <strong>${escapeHtml(fieldLabels?.[item?.field] || getImportMappingFieldLabel(item?.field || ""))}</strong>
                <span>${escapeHtml(item?.field || "")}</span>
            </div>
            <div>
                <b>${escapeHtml(requirement)}</b>
                <span>${escapeHtml(stateText)}</span>
                ${item?.note ? `<small>${escapeHtml(item.note)}</small>` : ""}
            </div>
        </article>
    `;
}

function invertImportMapping(mapping) {
    return Object.fromEntries(
        Object.entries(mapping || {})
            .filter(([, source]) => source)
            .map(([target, source]) => [source, target])
    );
}

function collectImportFieldMapping() {
    const mapping = {};
    document.querySelectorAll(".import-mapping-select").forEach((select) => {
        const source = select.dataset.sourceHeader || "";
        const target = select.value || "";
        if (source && !IMPORT_MAPPING_PROTECTED_FIELDS.has(target)) {
            mapping[source] = target || "__preserve__";
        }
    });
    return mapping;
}

function collectImportOutputs({ resetMappings = false } = {}) {
    return normalizeArray(currentImportPreview?.outputs).flatMap((output, outputIndex) => {
        const enabled = document.querySelector(`.import-output-enabled[data-output-index="${outputIndex}"]`);
        if (enabled && !enabled.checked) {
            return [];
        }
        const fieldMapping = {};
        if (!resetMappings) {
            document.querySelectorAll(`.import-output-mapping-select[data-output-index="${outputIndex}"]`).forEach((select) => {
                const source = select.dataset.sourceHeader || "";
                if (source) {
                    fieldMapping[source] = select.value || "__preserve__";
                }
            });
        }
        return [{
            dataset_type: output?.dataset_type || "",
            enabled: true,
            dedupe_keys: normalizeArray(output?.dedupe_keys),
            field_mapping: fieldMapping
        }];
    }).filter((output) => output.dataset_type);
}

function defaultImportTemplateName() {
    if (!currentImportPreview) {
        return "";
    }
    const province = getValue("importProvince") || currentImportPreview.preview_rows?.[0]?.province || "";
    const typeLabel = currentImportPreview.detected_type_label || "导入";
    const granularity = currentImportPreview.data_granularity === "summary_level" ? "上岸分数汇总" : "";
    return [province, granularity || typeLabel, "模板"].filter(Boolean).join("");
}

async function handleImportRemap() {
    const taskId = currentImportPreview?.task_id;
    if (!taskId) {
        showToast("请先上传文件并生成预览。", "error");
        return;
    }
    const isMultiOutput = Boolean(currentImportPreview?.multi_output);
    const detectedType = getValue("importDetectedType") || currentImportPreview?.detected_type || "";
    if (!detectedType || detectedType === "unknown") {
        showToast("请先选择要使用的数据类型。", "error");
        return;
    }
    const button = document.querySelector('[data-ui-action="import-remap"]');
    const typeChanged = detectedType !== String(currentImportPreview?.detected_type || "");
    const selectedHeaderRow = getOptionalImportRowNumber("importHeaderRow");
    const selectedSubHeaderRow = getOptionalImportRowNumber("importSubHeaderRow");
    const selectedDataStartRow = getOptionalImportRowNumber("importDataStartRow");
    const structureChanged = selectedHeaderRow !== (Number(currentImportPreview?.header_row) || null)
        || selectedSubHeaderRow !== (Number(currentImportPreview?.sub_header_row) || null)
        || selectedDataStartRow !== (Number(currentImportPreview?.data_start_row) || null)
        || getValue("importSelectedSheet") !== String(currentImportPreview?.selected_sheet || "");
    const selectedOutputs = isMultiOutput
        ? collectImportOutputs({ resetMappings: structureChanged })
        : [];
    if (isMultiOutput && selectedOutputs.length === 0) {
        showToast("请至少启用一个输出数据集。", "error");
        return;
    }
    setButtonLoading(button, true, "清洗中…");
    renderImportStatus("正在按新的字段映射重新清洗预览…", "loading");
    try {
        const preview = await importFetchJson(`${IMPORTS_API_URL}/${encodeURIComponent(taskId)}/remap`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                field_mapping: (typeChanged || structureChanged) ? {} : collectImportFieldMapping(),
                detected_type: detectedType,
                outputs: selectedOutputs,
                selected_sheet: getValue("importSelectedSheet"),
                header_row: selectedHeaderRow,
                sub_header_row: selectedSubHeaderRow,
                data_start_row: selectedDataStartRow
            })
        });
        currentImportPreview = preview;
        renderImportPreview(preview);
        document.getElementById("importConfirmSection")?.setAttribute("hidden", "");
        showToast(
            Number(preview?.valid_rows || 0) > 0
                ? "已重新清洗预览。"
                : "重新清洗完成，但仍没有有效记录。",
            Number(preview?.valid_rows || 0) > 0 ? "success" : "warning"
        );
    } catch (error) {
        const message = translateImportError(error);
        renderImportStatus(message, "error");
        showToast(message, "error");
        console.error("Import remap failed:", error);
    } finally {
        setButtonLoading(button, false);
    }
}

async function handleImportSaveTemplate() {
    const taskId = currentImportPreview?.task_id;
    if (!taskId) {
        showToast("请先上传文件并生成预览。", "error");
        return;
    }
    if (
        currentImportPreview?.status !== "PREVIEW_READY"
        || normalizeArray(currentImportPreview?.blocking_reasons).length
    ) {
        showToast("请先完成类型确认和字段映射，生成可入库的清洗预览后再保存模板。", "warning");
        return;
    }
    const templateName = getValue("importTemplateName") || defaultImportTemplateName();
    if (!templateName) {
        showToast("请填写模板名称。", "error");
        return;
    }
    const button = document.querySelector('[data-ui-action="import-save-template"]');
    setButtonLoading(button, true, "保存中…");
    try {
        const result = await importFetchJson(`${IMPORTS_API_URL}/${encodeURIComponent(taskId)}/save-template`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                template_name: templateName,
                province: getValue("importProvince") || currentImportPreview.preview_rows?.[0]?.province || "",
                data_type: currentImportPreview.detected_type || "",
                exam_type: getValue("importExamType") || currentImportPreview.preview_rows?.[0]?.exam_type || "",
                sheet_keyword: getValue("importSelectedSheet"),
                field_mapping: collectImportFieldMapping(),
                outputs: currentImportPreview?.multi_output ? collectImportOutputs() : [],
                header_row: getOptionalImportRowNumber("importHeaderRow"),
                sub_header_row: getOptionalImportRowNumber("importSubHeaderRow"),
                data_start_row: getOptionalImportRowNumber("importDataStartRow")
            })
        });
        showToast(result?.message || "导入模板已保存，下次相似文件将自动套用。", "success");
    } catch (error) {
        const message = translateImportError(error);
        showToast(message, "error");
        console.error("Import template save failed:", error);
    } finally {
        setButtonLoading(button, false);
    }
}

function getOptionalImportRowNumber(id) {
    const value = Number(getValue(id));
    return Number.isInteger(value) && value >= 1 ? value : null;
}

function renderImportPreviewRows(rows, outputs = []) {
    const container = document.getElementById("importPreviewRows");
    if (!container) {
        return;
    }
    const outputItems = normalizeArray(outputs);
    const renderByOutput = Boolean(currentImportPreview?.multi_output && outputItems.length);
    container.classList.toggle("multi-output-previews", renderByOutput);
    if (renderByOutput) {
        container.innerHTML = outputItems.map((output) => {
            const previewRows = normalizeArray(output?.preview_rows).slice(0, 20);
            return `
                <section class="import-output-preview" aria-label="${escapeHtml(output?.dataset_type_label || "数据集")}预览">
                    <div class="import-output-preview-head">
                        <div><strong>${escapeHtml(output?.dataset_type_label || output?.dataset_type || "数据集")}</strong><span>${formatNumber(output?.valid_rows)} 条有效记录</span></div>
                        <small>前 20 行清洗结果</small>
                    </div>
                    <div class="import-output-table-wrap">
                        ${previewRows.length
                            ? renderImportPreviewTable(previewRows, output?.dataset_type)
                            : '<div class="empty-state compact-empty"><strong>暂无预览行</strong><p>该输出尚未生成有效清洗结果。</p></div>'}
                    </div>
                </section>
            `;
        }).join("");
        return;
    }
    const items = normalizeArray(rows).slice(0, 20);
    if (!items.length) {
        container.innerHTML = '<div class="empty-state compact-empty"><strong>暂无预览行</strong><p>当前文件没有生成可展示的清洗结果。</p></div>';
        return;
    }
    container.innerHTML = renderImportPreviewTable(items, outputItems[0]?.dataset_type);
}

function renderImportPreviewTable(items, datasetType = "") {
    const columns = getImportPreviewColumns(items, datasetType);
    return `
        <table class="import-preview-table">
            <thead>
                <tr>${columns.map((column) => `<th scope="col" data-field="${escapeHtml(column)}">${escapeHtml(getImportFieldLabel(column))}</th>`).join("")}</tr>
            </thead>
            <tbody>
                ${items.map((row) => `
                    <tr>${columns.map((column) => `<td data-field="${escapeHtml(column)}">${escapeHtml(formatImportCell(row?.[column]))}</td>`).join("")}</tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function renderImportWarnings(warnings, warningSummary, importReport) {
    const container = document.getElementById("importWarnings");
    if (!container) {
        return;
    }
    const items = normalizeArray(warnings);
    const totalWarningCount = Number(currentImportPreview?.warning_count || items.length);
    const summaryItems = normalizeArray(warningSummary).length
        ? normalizeArray(warningSummary)
        : aggregateImportWarnings(items, importReport);
    container.innerHTML = summaryItems.length
        ? `
            ${summaryItems.map(renderImportWarningItem).join("")}
            ${items.length ? `
                <details class="warning-detail-panel">
                    <summary>查看明细（显示前 ${formatNumber(Math.min(items.length, 20))} / ${formatNumber(totalWarningCount)} 条）</summary>
                    <div class="warning-detail-list">
                        ${items.slice(0, 20).map(renderImportWarningItem).join("")}
                    </div>
                </details>
            ` : ""}
        `
        : '<div class="empty-state compact-empty"><strong>暂无 warning</strong><p>当前预览没有发现需要特别标记的异常行。</p></div>';
}

function renderImportWarningItem(warning) {
    return `
        <article class="warning-item">
            <strong>${escapeHtml(warning?.message || "需要人工核对")}</strong>
            <span>${escapeHtml([
                warning?.count ? `${formatNumber(warning.count)} 条` : "",
                warning?.row_index ? `第 ${warning.row_index} 行` : "",
                warning?.field && warning.field !== "duplicate_row" ? `字段 ${getImportFieldLabel(warning.field)}` : "",
                warning?.raw_value !== null && warning?.raw_value !== undefined ? `原值：${formatImportCell(warning.raw_value)}` : ""
            ].filter(Boolean).join(" · ") || "请检查源文件表头和数据值。")}</span>
        </article>
    `;
}

function aggregateImportWarnings(warnings, importReport) {
    const items = normalizeArray(warnings);
    const duplicateCount = Number(importReport?.duplicate_rows)
        || items.filter(isDuplicateImportWarning).length;
    const summary = [];
    if (duplicateCount) {
        summary.push({
            level: "warning",
            field: "duplicate_row",
            count: duplicateCount,
            message: `检测到 ${duplicateCount} 条重复记录，确认入库时将自动跳过。`
        });
    }
    return summary.concat(items.filter((warning) => !isDuplicateImportWarning(warning)));
}

function isDuplicateImportWarning(warning) {
    return warning?.field === "duplicate_row" || /重复/.test(String(warning?.message || ""));
}

function renderImportConfirmResult(result) {
    const section = document.getElementById("importConfirmSection");
    const container = document.getElementById("importConfirmResult");
    if (!section || !container) {
        return;
    }
    section.hidden = false;
    const insertedCount = Number(result?.inserted_count ?? result?.inserted_rows ?? 0);
    const imported = insertedCount > 0 && ["IMPORTED", "PARTIAL_IMPORTED"].includes(result?.status);
    const outputResults = normalizeArray(result?.output_results);
    const items = [
        ["status", result?.status || "--"],
        ["target", result?.target || "--"],
        ["storage", result?.storage || "database"],
        ["inserted_count", formatNumber(insertedCount)],
        ["updated_count", formatNumber(result?.updated_count)],
        ["skipped_count", formatNumber(result?.skipped_count ?? result?.skipped_rows)],
        ["warning_count", formatNumber(result?.warning_count)],
        ["valid_rows", formatNumber(result?.valid_rows)],
        ["warning_rows", formatNumber(result?.warning_rows)],
        ["dataset_id", result?.dataset_id || "未生成"],
        ...(result?.message ? [["说明", result.message]] : [])
    ];
    const resultItems = items.map(([label, value]) => `
        <div>
            <span>${escapeHtml(label)}</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `).join("");
    container.innerHTML = `
        ${outputResults.length ? `
            <div class="import-output-result-list">
                ${outputResults.map((output) => `
                    <article class="import-output-result">
                        <span>${escapeHtml(output?.dataset_type_label || output?.dataset_type || "输出数据集")}</span>
                        <strong>写入 ${formatNumber(output?.inserted_count)} 条</strong>
                        <small>跳过 ${formatNumber(output?.skipped_count)} 条</small>
                    </article>
                `).join("")}
            </div>
        ` : ""}
        ${resultItems}
        ${imported ? `
            <div class="import-confirm-actions">
                <button class="quiet-button" type="button" data-ui-action="retry-data-catalog">刷新数据中心</button>
                <button class="quiet-button" type="button" data-route-target="data-center">查看数据中心</button>
            </div>
        ` : ""}
    `;
}

function renderImportStatus(message, type) {
    const status = document.getElementById("importStatus");
    if (!status) {
        return;
    }
    status.hidden = !message;
    status.textContent = message || "";
    status.className = `import-status ${type || ""}`.trim();
}

function translateImportError(error) {
    const text = getErrorText(error);
    if (/表头|数据类型|置信度|未读取到可处理/.test(text)) {
        return "无法识别数据类型，请检查表头是否包含岗位、分数线、报名人数或专业目录相关字段。";
    }
    if (/格式|文件|Excel|CSV|编码|读取|上传|支持/.test(text)) {
        return "文件解析失败，请检查文件格式是否为 .xlsx / .xls / .csv。";
    }
    return text || "文件解析失败，请检查文件格式是否为 .xlsx / .xls / .csv。";
}

function isSupportedImportFile(fileName) {
    return /\.(xlsx|xls|csv)$/i.test(String(fileName || ""));
}

function formatConfidence(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(2) : "--";
}

function formatImportCell(value) {
    if (value === null || value === undefined || value === "") {
        return "-";
    }
    if (typeof value === "object") {
        return JSON.stringify(value);
    }
    return String(value);
}

function getImportPreviewColumns(rows, datasetType = "") {
    const columns = uniqueValues(rows.flatMap((row) => Object.keys(row || {})));
    const preferred = IMPORT_OUTPUT_PREVIEW_FIELDS[datasetType];
    if (preferred) {
        return preferred.filter((field) => columns.includes(field));
    }
    return IMPORT_FIELD_ORDER
        .filter((field) => columns.includes(field))
        .concat(columns.filter((field) => !IMPORT_FIELD_ORDER.includes(field)));
}

function getImportFieldLabel(field) {
    return currentImportPreview?.field_labels?.[field] || IMPORT_FIELD_LABELS[field] || field;
}

function getImportMappingFieldLabel(field) {
    if (field === "candidate_name") {
        return "隐私字段：姓名";
    }
    if (field === "candidate_no") {
        return "隐私字段：准考证号";
    }
    return getImportFieldLabel(field);
}

async function ensureScoreResultsLoaded() {
    const container = document.getElementById("scoreResults");
    if (container && !container.dataset.loaded) {
        await searchScoreReferences();
    }
}

async function handleScoreFilterSubmit(event) {
    event.preventDefault();
    await searchScoreReferences();
}

async function searchScoreReferences() {
    const button = document.getElementById("scoreFilterButton");
    const container = document.getElementById("scoreResults");
    setButtonLoading(button, true, "筛选中…");
    container.innerHTML = createLoadingPanel("正在读取已导入的历史进面分记录…");

    const params = new URLSearchParams();
    const values = {
        province: getValue("scoreProvince"),
        keyword: getValue("scoreKeyword"),
        position_code: getValue("scorePositionCode"),
        limit: "100"
    };
    Object.entries(values).forEach(([key, value]) => {
        if (value !== "") {
            params.set(key, value);
        }
    });

    try {
        const response = await fetch(`${SCORE_REFERENCES_API_URL}?${params.toString()}`);
        if (!response.ok) {
            throw new Error(await readResponseError(response));
        }
        const data = await response.json();
        container.dataset.loaded = "true";
        renderScoreResults(data);
        addAnalysisHistoryRecord({
            type: "score_risk",
            title: "查询分数线参考",
            summary: data?.returned
                ? `当前条件下展示 ${data.returned} 条历史分数参考。历史进面分不代表今年难度。`
                : "当前条件下暂无分数线记录。",
            question: [
                getValue("scoreProvince"),
                getValue("scorePositionCode"),
                getValue("scoreKeyword")
            ].filter(Boolean).join(" · "),
            province: getValue("scoreProvince"),
            year: getValue("scoreYear") || 2025,
            status: data?.returned ? "完成" : "无结果"
        });
    } catch (error) {
        container.innerHTML = createErrorState(
            "分数线记录加载失败",
            "这次没有读取到历史分数记录，可以稍后重试。",
            "重新加载",
            "retry-scores"
        );
        showToast("分数线记录加载失败，可以稍后重试。", "error");
        addAnalysisHistoryRecord({
            type: "error",
            title: "分数线参考加载失败",
            summary: "这次没有读取到历史分数记录，可以稍后重试。",
            question: [getValue("scoreProvince"), getValue("scorePositionCode"), getValue("scoreKeyword")].filter(Boolean).join(" · "),
            province: getValue("scoreProvince"),
            year: getValue("scoreYear") || 2025,
            status: "失败"
        });
        console.error("Score reference request failed:", error);
    } finally {
        setButtonLoading(button, false, "筛选记录");
    }
}

function renderScoreResults(data) {
    const items = normalizeArray(data?.items);
    setText(
        "scoreResultSummary",
        items.length > 0
            ? `共匹配 ${formatNumber(data.total)} 条成绩或分数线记录，本页展示前 ${formatNumber(data.returned)} 条。`
            : "当前条件下暂无成绩或分数线记录。"
    );
    const container = document.getElementById("scoreResults");
    container.innerHTML = items.length
        ? items.map(renderScoreResultItem).join("")
        : createEmptyState(
            "当前条件下暂无分数线记录",
            "可以检查省份、职位代码或岗位关键词。历史进面分只作为参考，不代表今年难度。"
        );
}

function renderScoreResultItem(item) {
    const isCandidateScore = item?.score_record_type === "candidate_score"
        || item?.data_type === "candidate_score_table"
        || item?.is_min_score_reference === false;
    const scoreFields = isCandidateScore
        ? `
            <div class="score-value"><span>笔试成绩</span><strong>${escapeHtml(formatScoreField(item.written_score))}</strong></div>
            <div><span>面试成绩</span><strong>${escapeHtml(formatScoreField(item.interview_score))}</strong></div>
            <div><span>总成绩</span><strong>${escapeHtml(formatScoreField(item.total_score))}</strong></div>
            <div><span>排名</span><strong>${escapeHtml(formatScoreField(item.rank))}</strong></div>
            <div><span>记录语义</span><strong>候选人成绩样本，不是岗位最低进面线</strong></div>
        `
        : `
            <div class="score-value"><span>最低进面分</span><strong>${escapeHtml(formatScoreField(item.min_interview_score))}</strong></div>
            <div><span>进面人数</span><strong>${escapeHtml(formatScoreField(item.interview_count, " 人"))}</strong></div>
        `;
    return `
        <article class="score-item">
            <div><span>记录类型</span><strong>${escapeHtml(item?.score_label || (isCandidateScore ? "候选人成绩" : "最低进面分"))}</strong></div>
            <div><span>年份 / 省份</span><strong>${escapeHtml(formatScoreField(item.year))} · ${escapeHtml(formatScoreField(item.province))}</strong></div>
            <div><span>用人单位</span><strong>${escapeHtml(formatScoreField(item.unit_name || item.unit || item.department))}</strong></div>
            <div><span>岗位名称</span><strong>${escapeHtml(formatScoreField(item.position_name || item.section_title))}</strong></div>
            <div><span>职位代码</span><strong>${escapeHtml(formatScoreField(getDisplayPositionCode(item)))}</strong></div>
            <div><span>地区 / 地址</span><strong>${escapeHtml(formatScoreLocation(item))}</strong></div>
            ${scoreFields}
            <div><span>数据来源</span><strong>${escapeHtml(formatScoreDataSource(item))}</strong></div>
        </article>
    `;
}

function formatScoreLocation(item) {
    return formatScoreField(item?.address || item?.region || item?.city);
}

function formatScoreField(value, suffix = "") {
    return value === undefined || value === null || String(value).trim() === ""
        ? "-"
        : `${value}${suffix}`;
}

function formatScoreDataSource(item) {
    if (item?.storage === "database") {
        if (item?.source_kind === "builtin_seed") {
            return "内置种子数据";
        }
        if (item?.source_kind === "migrated") {
            return "迁移数据";
        }
        return "导入数据库";
    }
    if (item?.storage === "csv") {
        return "内置数据";
    }
    return sanitizeSourceText(item?.source_description, "-") || "-";
}

function createLoadingPanel(text) {
    return `
        <div class="empty-state compact-empty state-loading" aria-live="polite" aria-busy="true">
            <div class="chat-loading" aria-label="加载中"><span></span><span></span><span></span></div>
            <strong>正在处理</strong>
            <p>${escapeHtml(text)}</p>
        </div>
    `;
}

function createEmptyState(title, description, actionLabel = "", route = "") {
    const action = actionLabel && route
        ? `<button class="primary-button" type="button" data-route-target="${escapeHtml(route)}">${escapeHtml(actionLabel)}</button>`
        : "";
    return `
        <div class="empty-state compact-empty">
            <span class="empty-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3.5h12a1.5 1.5 0 0 1 1.5 1.5v16L12 17l-7.5 4V5A1.5 1.5 0 0 1 6 3.5Z"/></svg>
            </span>
            <strong>${escapeHtml(title)}</strong>
            <p>${escapeHtml(description || "")}</p>
            ${action}
        </div>
    `;
}

function createErrorState(title, description, actionLabel = "", action = "") {
    const actionButton = actionLabel && action
        ? `<button class="quiet-button" type="button" data-ui-action="${escapeHtml(action)}">${escapeHtml(actionLabel)}</button>`
        : "";
    return `
        <div class="empty-state compact-empty state-error" role="alert">
            <span class="empty-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7.5v5M12 16.5v.01"/></svg>
            </span>
            <strong>${escapeHtml(title)}</strong>
            <p>${escapeHtml(description || "")}</p>
            ${actionButton}
        </div>
    `;
}

function renderMarkdown(text) {
    const lines = escapeHtml(String(text || "").replace(/\r\n?/g, "\n")).split("\n");
    const html = [];
    let paragraph = [];
    let listType = "";

    const inline = (value) => value.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    const closeParagraph = () => {
        if (paragraph.length) {
            html.push(`<p>${paragraph.map(inline).join("<br>")}</p>`);
            paragraph = [];
        }
    };
    const closeList = () => {
        if (listType) {
            html.push(`</${listType}>`);
            listType = "";
        }
    };
    const openList = (type) => {
        if (listType === type) {
            return;
        }
        closeList();
        html.push(`<${type}>`);
        listType = type;
    };

    lines.forEach((line) => {
        const trimmed = line.trim();
        const heading = trimmed.match(/^(#{2,3})\s+(.+)$/);
        const ordered = line.match(/^\s*\d+\.\s+(.+)$/);
        const unordered = line.match(/^\s*[-*]\s+(.+)$/);
        if (!trimmed) {
            closeParagraph();
            closeList();
        } else if (heading) {
            closeParagraph();
            closeList();
            const level = heading[1].length;
            html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        } else if (ordered || unordered) {
            closeParagraph();
            const item = ordered?.[1] || unordered?.[1] || "";
            openList(ordered ? "ol" : "ul");
            html.push(`<li>${inline(item)}</li>`);
        } else {
            closeList();
            paragraph.push(trimmed);
        }
    });
    closeParagraph();
    closeList();
    return html.join("");
}

function inferResultLimit(question) {
    const text = String(question || "").replace(/\s+/g, "");
    if (/推荐(一个|1个?)|给我(一个|1个?)|选一个|最适合的一个/.test(text)) {
        return 1;
    }
    const match = text.match(/(?:推荐|给我|筛出)([一二两三四五1-5])个?/);
    if (!match) {
        return 5;
    }
    const numbers = { 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5 };
    return Math.max(1, Math.min(Number(numbers[match[1]] || match[1]), 5));
}

function setButtonLoading(button, loading, loadingText = "") {
    if (!button) {
        return;
    }
    if (loading) {
        button.dataset.originalText = button.textContent;
        button.disabled = true;
        if (loadingText) {
            button.textContent = loadingText;
        }
    } else {
        button.disabled = false;
        if (button.dataset.originalText) {
            button.textContent = button.dataset.originalText;
            delete button.dataset.originalText;
        }
    }
}

function showToast(message, type = "success") {
    const region = document.getElementById("toastRegion");
    if (!region) {
        return;
    }
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    toast.setAttribute("role", type === "error" ? "alert" : "status");
    region.appendChild(toast);
    window.setTimeout(() => toast.remove(), 3600);
}

function loadStoredObject(key, fallback) {
    try {
        const value = JSON.parse(localStorage.getItem(key));
        return value && typeof value === "object" && !Array.isArray(value)
            ? { ...fallback, ...value }
            : { ...fallback };
    } catch {
        return { ...fallback };
    }
}

function loadStoredText(key) {
    try {
        return String(localStorage.getItem(key) || "");
    } catch {
        return "";
    }
}

function readStoredSessionId() {
    const value = Number(loadStoredText(ACTIVE_SESSION_STORAGE_KEY));
    return Number.isInteger(value) && value > 0 ? value : null;
}

function loadStoredArray(key) {
    try {
        const value = JSON.parse(localStorage.getItem(key));
        return Array.isArray(value) ? value : [];
    } catch {
        return [];
    }
}

function saveStoredText(key, value) {
    try {
        localStorage.setItem(key, String(value || ""));
        return true;
    } catch {
        return false;
    }
}

function removeStoredValue(key) {
    try {
        localStorage.removeItem(key);
        return true;
    } catch {
        return false;
    }
}

function saveStoredValue(key, value) {
    try {
        localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (error) {
        console.error(`Unable to save local storage key "${key}":`, error);
        return false;
    }
}

function getValue(id) {
    return String(document.getElementById(id)?.value || "").trim();
}

function setValue(id, value) {
    const element = document.getElementById(id);
    if (element && value !== undefined && value !== null) {
        element.value = value;
        refreshCustomSelect(element);
    }
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = String(value ?? "");
    }
}

function normalizeArray(value) {
    return Array.isArray(value) ? value : [];
}

function uniqueValues(values) {
    return Array.from(new Set(values.filter((value) => String(value || "").trim())));
}

function normalizePositionCode(value) {
    const text = String(value || "").trim();
    const groups = text.match(/\d+/g) || [];
    if (groups.length === 0) {
        return "";
    }
    const code = groups.reduce((best, current) => current.length >= best.length ? current : best, "");
    return code.length >= 6 ? code : "";
}

function extractPositionCodeFromText(value) {
    const text = String(value || "");
    const contextual = text.match(/(?:职位代码|岗位代码|职位编号|岗位编号|position_code)\D{0,12}(\d{6,20})/i);
    if (contextual) {
        return normalizePositionCode(contextual[1]);
    }
    const standalone = text.match(/(?:^|\D)(\d{6,20})(?!\d)/);
    return standalone ? normalizePositionCode(standalone[1]) : "";
}

function getDisplayPositionCode(job) {
    if (!job || typeof job !== "object") {
        return "";
    }
    const structuredCode = selectCompletePositionCode(
        job.display_position_code,
        job.full_position_code,
        job.position_code,
        job.positionCode,
        job.job_code,
        job.code,
        job["职位代码"],
        job["岗位代码"],
        job.raw_position_code,
        job.source_position_code,
        job.score_match_position_code,
        job.matched_position_code,
        job.score_match?.position_code,
        job.score_match?.matched_position_code,
        job.raw?.["职位代码"],
        job.raw?.["岗位代码"],
        job.job_id
    );
    if (structuredCode) {
        return structuredCode;
    }
    return extractPositionCodeFromText(job.score_match_reason || job.match_reason || "");
}

function selectCompletePositionCode(...values) {
    return values
        .map(normalizePositionCode)
        .filter(Boolean)
        .reduce((best, current) => current.length > best.length ? current : best, "");
}

function optionalNumber(value) {
    if (value === undefined || value === null || String(value).trim() === "") {
        return null;
    }
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function firstPresent(...values) {
    return values.find((value) => value !== undefined && value !== null && String(value).trim() !== "");
}

function formatValue(value, suffix = "") {
    return value === undefined || value === null || String(value).trim() === ""
        ? "暂无"
        : `${value}${suffix}`;
}

function formatNumber(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString("zh-CN") : "--";
}

function formatDateTime(value) {
    if (!value) {
        return "时间未知";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }
    return date.toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit"
    });
}

function truncateText(value, maxLength) {
    const text = String(value || "");
    return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function sanitizeSourceText(value, fallback = "") {
    const text = sanitizeUserFacingText(value);
    if (!text) {
        return fallback;
    }
    if (/\.csv\b|(?:^|[\\/])(?:app|data|raw_private|users?)(?:[\\/]|$)/i.test(text)) {
        return fallback;
    }
    return text;
}

function sanitizeUserFacingText(value) {
    const text = String(value || "").trim();
    if (!text) {
        return "";
    }
    return text
        .split(/\r?\n/)
        .filter((line) => !/(?:debug_[a-z_]*|source_file|raw_private|traceback|[A-Za-z]:\\[^ ]+|\/app\/data\/|[\w.-]+\.py\b)/i.test(line))
        .join("\n")
        .replace(/政策依据暂未获取成功[^。！？\n]*(?:[。！？]|$)/g, "暂未获取到可核验的政策依据，请以官方公告和职位表为准。")
        .replace(/\b(?:jobs|job_scores)_[a-z_]+_\d{4}\.csv\b/gi, "已导入招考数据")
        .replace(/rag[_\s-]*builder/gi, "政策文件服务")
        .replace(/\bRAG\b/gi, "政策文件")
        .replace(/\b(?:Elasticsearch|Celery|Redis|MinIO)\b/gi, "后台服务")
        .replace(/内部检索器/g, "政策文件查询服务")
        .replace(/\b[a-z_]+_tool(?:\.[a-z_][a-z0-9_]*)?\b/gi, "系统能力")
        .replace(/\bsk-[A-Za-z0-9_-]{12,}\b/gi, "[已隐藏密钥]")
        .replace(/((?:api[_-]?key|authorization|bearer)\s*[:=]?\s*)[A-Za-z0-9._-]{12,}/gi, "$1[已隐藏]")
        .trim();
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

async function readResponseError(response) {
    try {
        const data = await response.json();
        if (typeof data?.detail === "string") {
            return data.detail;
        }
        if (typeof data?.detail?.message === "string") {
            return data.detail.message;
        }
        if (Array.isArray(data?.detail)) {
            return data.detail.map((item) => item?.msg || JSON.stringify(item)).join("；");
        }
    } catch {
        return `${response.status} ${response.statusText || "请求失败"}`;
    }
    return `${response.status} ${response.statusText || "请求失败"}`;
}

function getErrorText(error) {
    return error?.message || "未知错误";
}

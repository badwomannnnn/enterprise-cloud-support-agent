import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/(\w:)/, "$1")), "..");
const { SKILL_DIR, RUNTIME_PYTHON } = process.env;
if (!SKILL_DIR || !RUNTIME_PYTHON) throw new Error("Set SKILL_DIR and RUNTIME_PYTHON");
const utils = await import(pathToFileURL(path.join(SKILL_DIR, "container_tools/artifact_tool_utils.mjs")).href);
const { resolvePresentationFont, applyPresentationChartFont, makeNativeBulletParagraphs, finalizePresentation } = utils;
const fontFamily = resolvePresentationFont({ fontFamily: "Microsoft YaHei" });
const metrics = JSON.parse(await fs.readFile(path.join(workspaceDir, "reports", "metrics.json"), "utf8"));

const W = 1280;
const H = 720;
const C = {
  ink: "#F5F8FB",
  muted: "#A9BDCF",
  navy: "#071426",
  navy2: "#102A43",
  panel: "#15314C",
  line: "#315774",
  teal: "#69D2E7",
  cyan: "#1EB5C9",
  amber: "#F2B84B",
  red: "#F16B6B",
  green: "#66D19E",
  white: "#FFFFFF",
};

const presentation = Presentation.create({ slideSize: { width: W, height: H } });

function addText(slide, text, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    typeface: fontFamily,
    fontSize: options.fontSize ?? 24,
    bold: options.bold ?? false,
    color: options.color ?? C.ink,
    alignment: options.alignment ?? "left",
    verticalAlignment: options.verticalAlignment ?? "middle",
    autoFit: "none",
  };
  return shape;
}

function addBox(slide, position, options = {}) {
  return slide.shapes.add({
    geometry: options.geometry ?? "roundRect",
    position,
    fill: options.fill ?? C.panel,
    line: { style: "solid", fill: options.line ?? C.line, width: options.lineWidth ?? 1.5 },
    borderRadius: options.borderRadius ?? 18,
  });
}

function addTitle(slide, title, kicker) {
  if (kicker) addText(slide, kicker.toUpperCase(), { left: 72, top: 34, width: 220, height: 26 }, { fontSize: 14, bold: true, color: C.teal });
  addText(slide, title, { left: 72, top: 66, width: 1120, height: 58 }, { fontSize: 34, bold: true });
  const rule = slide.shapes.add({
    geometry: "line",
    position: { left: 72, top: 132, width: 1136, height: 0 },
    fill: "none",
    line: { style: "solid", fill: C.line, width: 1 },
  });
  return rule;
}

function addBullets(slide, items, position, options = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { fill: "none", width: 0 },
  });
  shape.text = makeNativeBulletParagraphs(items, {
    marginLeftPoints: 16,
    hangingPoints: 8,
    spaceAfterPoints: options.spaceAfter ?? 12,
  });
  shape.text.style = {
    typeface: fontFamily,
    fontSize: options.fontSize ?? 22,
    color: options.color ?? C.ink,
    autoFit: "none",
  };
  return shape;
}

function connect(slide, from, to, fromSide = "right", toSide = "left") {
  // Artifact Tool renders the arrow head on the first connector endpoint.
  // Connect in reverse order so the visual arrow points into the destination.
  return slide.shapes.connect(to, from, {
    kind: "elbow",
    fromSide: toSide,
    toSide: fromSide,
    line: { style: "solid", fill: C.teal, width: 2.5 },
    head: { type: "arrow", width: "med", length: "med" },
  });
}

function labelBox(slide, label, sub, position, accent = false) {
  const box = addBox(slide, position, { fill: accent ? "#123F55" : C.panel, line: accent ? C.teal : C.line, lineWidth: accent ? 2.5 : 1.5 });
  addText(slide, label, { left: position.left + 12, top: position.top + 10, width: position.width - 24, height: 30 }, { fontSize: 22, bold: true, alignment: "center" });
  if (sub) addText(slide, sub, { left: position.left + 12, top: position.top + 44, width: position.width - 24, height: 28 }, { fontSize: 14, color: C.muted, alignment: "center" });
  return box;
}

// 1 Cover
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addText(slide, "企业云产品智能支持与工单协同 Agent", { left: 86, top: 164, width: 900, height: 118 }, { fontSize: 48, bold: true });
  addText(slide, "从知识问答到人工工单的可控闭环", { left: 90, top: 298, width: 700, height: 48 }, { fontSize: 25, color: C.teal });
  addText(slide, "Python  FastAPI  RAG  LangGraph  SQLite  腾讯混元", { left: 90, top: 380, width: 840, height: 34 }, { fontSize: 18, color: C.muted });
  addText(slide, "求职项目汇报", { left: 90, top: 602, width: 300, height: 32 }, { fontSize: 17, color: C.muted });
  addText(slide, "01", { left: 1030, top: 180, width: 150, height: 150 }, { fontSize: 84, bold: true, color: C.teal, alignment: "center" });
  slide.speakerNotes.textFrame.setText("模型接入参考：https://cloud.tencent.com/document/product/1729/111007 和 https://intl.cloud.tencent.com/zh/document/product/1300/80632");
}

// 2 Problem
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy2;
  addTitle(slide, "企业技术支持的断点", "业务背景");
  addText(slide, "用户通常只说“接口不能用了”", { left: 80, top: 170, width: 520, height: 62 }, { fontSize: 30, bold: true });
  addText(slide, "错误码、Request ID、发生时间和影响范围经常缺失。支持人员需要在文档、账户信息和工单系统之间切换。", { left: 82, top: 246, width: 500, height: 130 }, { fontSize: 21, color: C.muted });
  const items = [
    ["1", "信息不完整", "反复追问，定位速度慢"],
    ["2", "知识难复用", "答案缺少来源，经验散落"],
    ["3", "转交不连续", "人工接管时缺少上下文"],
  ];
  items.forEach((item, index) => {
    const y = 180 + index * 140;
    addText(slide, item[0], { left: 665, top: y, width: 58, height: 58 }, { fontSize: 28, bold: true, color: C.teal, alignment: "center" });
    addText(slide, item[1], { left: 742, top: y - 2, width: 250, height: 36 }, { fontSize: 24, bold: true });
    addText(slide, item[2], { left: 742, top: y + 36, width: 390, height: 34 }, { fontSize: 18, color: C.muted });
  });
  addText(slide, "目标：把问答、诊断和人工协同放进同一条可审计流程", { left: 82, top: 585, width: 1080, height: 48 }, { fontSize: 26, bold: true, color: C.amber });
  slide.speakerNotes.textFrame.setText("内容来源：项目需求说明与 README。虚拟产品场景，不代表真实客户数据。");
}

// 3 Architecture
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addTitle(slide, "系统架构与职责边界", "总体方案");
  const ui = labelBox(slide, "Streamlit", "用户支持与工程师工作台", { left: 70, top: 230, width: 210, height: 92 });
  const api = labelBox(slide, "FastAPI", "接口与结构校验", { left: 340, top: 230, width: 200, height: 92 });
  const agent = labelBox(slide, "Agent 工作流", "追问、检索、工具、升级", { left: 600, top: 215, width: 250, height: 122 }, true);
  const rag = labelBox(slide, "RAG", "带来源的知识依据", { left: 930, top: 160, width: 220, height: 88 });
  const tools = labelBox(slide, "诊断工具", "错误码、额度、服务状态", { left: 930, top: 285, width: 220, height: 88 });
  const ticket = labelBox(slide, "工单状态机", "分派、解决、关闭", { left: 930, top: 410, width: 220, height: 88 });
  connect(slide, ui, api);
  connect(slide, api, agent);
  connect(slide, agent, rag);
  connect(slide, agent, tools);
  connect(slide, agent, ticket);
  addText(slide, "模型", { left: 120, top: 448, width: 120, height: 30 }, { fontSize: 17, bold: true, color: C.teal });
  addText(slide, "理解和表达", { left: 120, top: 482, width: 180, height: 32 }, { fontSize: 20 });
  addText(slide, "工具", { left: 355, top: 448, width: 120, height: 30 }, { fontSize: 17, bold: true, color: C.teal });
  addText(slide, "返回确定性结果", { left: 355, top: 482, width: 190, height: 32 }, { fontSize: 20 });
  addText(slide, "状态机", { left: 610, top: 448, width: 120, height: 30 }, { fontSize: 17, bold: true, color: C.teal });
  addText(slide, "约束业务流转", { left: 610, top: 482, width: 190, height: 32 }, { fontSize: 20 });
  addText(slide, "边界清楚，才能解释、测试和审计", { left: 80, top: 595, width: 1080, height: 42 }, { fontSize: 28, bold: true, color: C.amber });
  slide.speakerNotes.textFrame.setText("来源：docs/system_architecture.svg 和 docs/架构说明.md。");
}

// 4 RAG
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy2;
  addTitle(slide, "知识检索与引用", "RAG");
  const stages = [
    ["17 篇文档", "产品说明、API、错误码"],
    ["切分与元数据", "标题、类别、来源"],
    ["混合检索", "n-gram 与错误码精确匹配"],
    ["带引用回答", "无依据时拒答"],
  ];
  const boxes = stages.map((stage, index) => labelBox(
    slide,
    stage[0],
    stage[1],
    { left: 62 + index * 300, top: 205, width: 235, height: 100 },
    index === 2,
  ));
  for (let index = 0; index < boxes.length - 1; index += 1) connect(slide, boxes[index], boxes[index + 1]);
  addText(slide, "检索失败要区分三种原因", { left: 82, top: 385, width: 440, height: 42 }, { fontSize: 27, bold: true });
  addBullets(slide, [
    "语料没有答案",
    "切分破坏上下文",
    "查询表达与文档差异过大",
  ], { left: 88, top: 438, width: 500, height: 165 }, { fontSize: 21, spaceAfter: 10 });
  addText(slide, "Recall@3", { left: 750, top: 390, width: 260, height: 50 }, { fontSize: 26, bold: true, color: C.teal, alignment: "center" });
  addText(slide, `${(metrics.recall_at_3 * 100).toFixed(1)}%`, { left: 750, top: 448, width: 260, height: 92 }, { fontSize: 58, bold: true, alignment: "center" });
  addText(slide, "固定测试集中的正确文档进入前三条", { left: 700, top: 548, width: 360, height: 44 }, { fontSize: 18, color: C.muted, alignment: "center" });
  slide.speakerNotes.textFrame.setText("指标来源：reports/metrics.json。语料全部为自行编写的虚拟产品资料。");
}

// 5 Agent
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addTitle(slide, "Agent 决策流程", "工作流");
  const input = labelBox(slide, "输入脱敏", "密钥、手机号、邮箱", { left: 60, top: 230, width: 190, height: 92 });
  const triage = labelBox(slide, "意图分诊", "六类问题", { left: 300, top: 230, width: 190, height: 92 });
  const enough = labelBox(slide, "信息完整？", "错误码、时间、影响范围", { left: 540, top: 215, width: 215, height: 122 }, true);
  const ask = labelBox(slide, "继续追问", "停止猜测", { left: 845, top: 150, width: 190, height: 88 });
  const diagnose = labelBox(slide, "检索与工具", "形成诊断依据", { left: 845, top: 290, width: 190, height: 88 });
  const escalate = labelBox(slide, "人工升级", "生成结构化工单", { left: 845, top: 430, width: 190, height: 88 });
  connect(slide, input, triage);
  connect(slide, triage, enough);
  connect(slide, enough, ask);
  connect(slide, enough, diagnose);
  connect(slide, enough, escalate);
  addText(slide, "缺信息", { left: 785, top: 158, width: 75, height: 24 }, { fontSize: 14, color: C.muted });
  addText(slide, "有依据", { left: 785, top: 298, width: 75, height: 24 }, { fontSize: 14, color: C.muted });
  addText(slide, "高风险", { left: 785, top: 438, width: 75, height: 24 }, { fontSize: 14, color: C.muted });
  addText(slide, "升级规则", { left: 1080, top: 184, width: 130, height: 32 }, { fontSize: 20, bold: true, color: C.teal });
  addBullets(slide, [
    "没有可靠依据",
    "两次方案无效",
    "安全事件",
    "生产大面积异常",
    "用户要求人工",
  ], { left: 1065, top: 225, width: 170, height: 260 }, { fontSize: 17, spaceAfter: 9 });
  addText(slide, "核心逻辑可脱离 LangGraph 单独测试", { left: 76, top: 592, width: 830, height: 42 }, { fontSize: 26, bold: true, color: C.amber });
  slide.speakerNotes.textFrame.setText("来源：app/workflow.py 和 app/triage.py。");
}

// 6 Tools and ticket
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy2;
  addTitle(slide, "工具调用与工单闭环", "人机协同");
  const table = slide.tables.add({
    rows: 6,
    columns: 2,
    left: 74,
    top: 180,
    width: 530,
    height: 360,
    columnWidths: [235, 295],
    values: [
      ["工具", "返回结果"],
      ["query_service_status", "模拟服务状态"],
      ["query_account_quota", "模拟账户额度"],
      ["query_error_code", "错误码说明"],
      ["create_ticket", "结构化工单编号"],
      ["query_ticket_status", "工单状态与负责人"],
    ],
  });
  table.styleOptions = { headerRow: true, bandedRows: true };
  table.borders.assign({ style: "solid", fill: C.line, width: 1 });
  for (let col = 0; col < 2; col += 1) {
    table.getCell(0, col).fill = C.teal;
    table.getCell(0, col).text.style = { typeface: fontFamily, fontSize: 18, bold: true, color: C.navy };
  }
  for (let row = 1; row < 6; row += 1) {
    for (let col = 0; col < 2; col += 1) {
      table.getCell(row, col).fill = row % 2 ? C.panel : "#102A43";
      table.getCell(row, col).text.style = { typeface: fontFamily, fontSize: 16, color: C.ink };
    }
  }
  addText(slide, "工单状态机", { left: 700, top: 182, width: 300, height: 42 }, { fontSize: 27, bold: true });
  const states = ["NEW", "NEED_INFO", "AI_PROCESSING", "HUMAN_PROCESSING", "RESOLVED", "CLOSED"];
  states.forEach((state, index) => {
    addText(slide, state, { left: 715, top: 242 + index * 52, width: 255, height: 34 }, { fontSize: 17, bold: index >= 3, color: index >= 3 ? C.teal : C.ink });
    if (index < states.length - 1) addText(slide, "↓", { left: 973, top: 242 + index * 52, width: 32, height: 34 }, { fontSize: 20, color: C.muted, alignment: "center" });
  });
  addText(slide, "非法跳转返回 409，解决方案确认后才进入候选知识区", { left: 700, top: 578, width: 460, height: 56 }, { fontSize: 20, color: C.amber });
  slide.speakerNotes.textFrame.setText("来源：app/tools.py、app/repository.py 和 API 设计。");
}

// 7 Security
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addTitle(slide, "安全、可靠性与降级", "工程能力");
  const rows = [
    ["敏感数据", "模型调用前遮盖密钥、手机号和邮箱", "安全事件直接升级"],
    ["Prompt Injection", "拦截绕过规则和索取系统提示的输入", "返回安全说明"],
    ["模型不可用", "真实接口失败后切换 Mock", "核心流程仍可演示"],
    ["无知识依据", "拒绝补全未知事实", "创建人工工单"],
    ["状态流转", "后端校验每次状态变化", "保留操作人和时间线"],
  ];
  const table = slide.tables.add({
    rows: 6,
    columns: 3,
    left: 72,
    top: 176,
    width: 1136,
    height: 380,
    columnWidths: [220, 570, 346],
    values: [["风险", "控制措施", "失败时行为"], ...rows],
  });
  table.styleOptions = { headerRow: true, bandedRows: true };
  table.borders.assign({ style: "solid", fill: C.line, width: 1 });
  for (let col = 0; col < 3; col += 1) {
    table.getCell(0, col).fill = C.teal;
    table.getCell(0, col).text.style = { typeface: fontFamily, fontSize: 18, bold: true, color: C.navy };
  }
  for (let row = 1; row < 6; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      table.getCell(row, col).fill = row % 2 ? C.panel : "#102A43";
      table.getCell(row, col).text.style = { typeface: fontFamily, fontSize: 16, color: C.ink };
    }
  }
  addText(slide, "演示稳定性和安全边界都由代码保障", { left: 80, top: 592, width: 900, height: 44 }, { fontSize: 27, bold: true, color: C.amber });
  slide.speakerNotes.textFrame.setText("来源：app/security.py、app/llm.py、app/repository.py。");
}

// 8 Metrics
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy2;
  addTitle(slide, "42 条固定样例的自动评测", "测试结果");
  const categories = ["意图分类", "Recall@3", "工具选择", "升级判断", "脱敏"];
  const values = [metrics.intent_accuracy, metrics.recall_at_3, metrics.tool_selection_accuracy, metrics.escalation_accuracy, metrics.redaction_success_rate];
  const chart = slide.charts.add("bar", {
    position: { left: 70, top: 175, width: 730, height: 410 },
    categories,
    series: [{ name: "准确率", values, fill: C.teal }],
    barOptions: { direction: "bar", grouping: "clustered", gapWidth: 52 },
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", textStyle: { typeface: fontFamily, fontSize: 16, fill: C.ink } },
    xAxis: { min: 0, max: 1, numberFormatCode: "0%", textStyle: { typeface: fontFamily, fontSize: 14, fill: C.muted } },
    yAxis: { textStyle: { typeface: fontFamily, fontSize: 16, fill: C.ink } },
    chartFill: C.navy2,
    plotAreaFill: C.navy2,
    chartLine: { fill: "none", width: 0 },
    plotAreaLine: { fill: "none", width: 0 },
  });
  applyPresentationChartFont(chart, { fontFamily });
  addText(slide, "测试边界", { left: 860, top: 190, width: 250, height: 42 }, { fontSize: 26, bold: true, color: C.teal });
  addBullets(slide, [
    "小规模虚拟产品语料",
    "本地延迟不含混元网络耗时",
    "自然语言答案仍需人工抽检",
    "指标可由脚本重复生成",
  ], { left: 850, top: 246, width: 340, height: 235 }, { fontSize: 19, spaceAfter: 12 });
  addText(slide, `本地平均处理 ${metrics.average_local_latency_ms.toFixed(2)} ms`, { left: 860, top: 515, width: 300, height: 46 }, { fontSize: 23, bold: true, color: C.amber });
  addText(slide, "只统计分类、检索与工具选择", { left: 860, top: 560, width: 310, height: 34 }, { fontSize: 16, color: C.muted });
  slide.speakerNotes.textFrame.setText("数据来源：data/evaluation_cases.json 和 reports/metrics.json。图表为可编辑原生图表。");
}

// 9 Close
{
  const slide = presentation.slides.add();
  slide.background.fill = C.navy;
  addTitle(slide, "项目成果与后续演进", "复盘");
  addText(slide, "已经完成", { left: 80, top: 180, width: 260, height: 42 }, { fontSize: 27, bold: true, color: C.teal });
  addBullets(slide, [
    "问答、追问、工具和人工升级闭环",
    "FastAPI、Streamlit 和 SQLite 可运行 Demo",
    "42 条样例、自动指标和失败记录",
    "架构图、两页方案、报告、PPT 和视频",
  ], { left: 78, top: 238, width: 500, height: 260 }, { fontSize: 21, spaceAfter: 13 });
  addText(slide, "仍有边界", { left: 690, top: 180, width: 260, height: 42 }, { fontSize: 27, bold: true, color: C.teal });
  addBullets(slide, [
    "业务工具和账户数据为模拟数据",
    "尚未实现多租户和真实权限",
    "知识库规模较小",
    "公开部署需补充监控和密钥管理",
  ], { left: 688, top: 238, width: 470, height: 250 }, { fontSize: 21, spaceAfter: 13 });
  addText(slide, "下一步：接入真实企业系统，加入人工知识审核和线上效果监控", { left: 80, top: 580, width: 1100, height: 50 }, { fontSize: 27, bold: true, color: C.amber });
  slide.speakerNotes.textFrame.setText("来源：README、测试报告和项目复盘。所有结果均来自当前仓库实现。");
}

const outputDir = path.join(workspaceDir, "docs", "deliverables");
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(stagingDir, { recursive: true });
const finalPath = path.join(outputDir, "企业云产品智能支持与工单协同Agent_项目汇报.pptx");
const candidatePath = path.join(stagingDir, "candidate.pptx");
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

await finalizePresentation({
  explicitTotalSlideCount: 9,
  requiredNativeTableOwnerSlides: [6, 7],
  requiredNativeChartOwnerSlides: [8],
  materializeLiteralChartWorkbooks: true,
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: RUNTIME_PYTHON,
  integrityValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(SKILL_DIR, "container_tools/inspect_presentation_layout_geometry.py"),
  layoutArgs: [
    "--expected-slide-size-emu", "12192000,6858000",
    "--validate-bullet-geometry",
    "--validate-heading-fit",
    "--require-native-table-slide", "6",
    "--require-native-table-slide", "7",
  ],
  fontPolicy: { basis: "design", families: [fontFamily] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "project-deck.validation.json"),
});

console.log(finalPath);

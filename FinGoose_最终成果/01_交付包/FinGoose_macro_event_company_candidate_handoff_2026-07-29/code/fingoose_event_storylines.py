from __future__ import annotations

from typing import Any


_PHASE_MEANINGS = {
    "PRECONDITION": "建立冲击发生前的约束条件",
    "INITIAL_SHOCK": "改变事件性质并启动核心市场重定价",
    "ESCALATION": "扩大冲击范围或提高传导强度",
    "POLICY_RESPONSE": "引入可能改变原有传导方向的政策响应",
    "EASING": "削弱先前冲击但不代表影响立即消失",
    "SECONDARY_SHOCK": "形成需要与首次冲击分开观察的新分支",
    "RESOLUTION": "标志事件进入结束或常态化管理阶段",
}


def _make_event(event_id: str, data: dict[str, Any]) -> list[dict[str, Any]]:
    node_ids = data["node_ids"]
    phases = data["phases"]
    titles = data["titles"]
    states = data["states"]
    if not (len(node_ids) == len(phases) == len(titles) == 5 and len(states) == 6):
        raise ValueError(f"{event_id}: storyline configuration must define five steps and six states")
    pending = set(data.get("pending", []))
    partial = set(data.get("partial", []))
    date_precision = set(data.get("date_precision", []))
    rows: list[dict[str, Any]] = []
    for index, (node_id, phase, title) in enumerate(
        zip(node_ids, phases, titles, strict=True), start=1
    ):
        before = states[index - 1]
        after = states[index]
        coverage = "PENDING" if node_id in pending else ("PARTIAL" if node_id in partial else "DIRECT")
        precision = "UNKNOWN" if node_id in pending else ("DATE" if node_id in date_precision else "TIMESTAMP")
        rows.append({
            "story_step_id": f"story-{event_id}-{index:02d}",
            "sequence": index,
            "phase": phase,
            "title_cn": title,
            "narrative_cn": f"{title}。事件状态由“{before}”转为“{after}”，后续观察应使用新的阶段基准。",
            "before_state_cn": before,
            "after_state_cn": after,
            "significance_cn": f"该步骤{_PHASE_MEANINGS[phase]}，并重新界定{data['focus']}的观察窗口与传导条件。",
            "evidence_node_ids": [node_id],
            "coverage": coverage,
            "time_precision_override": precision,
        })
    return rows


_DATA: dict[str, dict[str, Any]] = {
    "event-01": {
        "node_ids": ["fast-event-01-M01", "fast-event-01-M02", "fast-event-01-M04", "fast-event-01-M03", "fast-event-01-M05"],
        "phases": ["PRECONDITION", "ESCALATION", "INITIAL_SHOCK", "ESCALATION", "RESOLUTION"],
        "titles": ["国际公共卫生风险被正式确认", "欧洲封控使经济冲击显性化", "WHO 将 COVID-19 定性为全球大流行", "官方疫情报告补充全球扩散确认", "WHO 结束 PHEIC，事件进入常态化管理"],
        "states": ["疫情仍主要被视为局部公共卫生事件", "跨境公共卫生协调成为必要条件", "欧洲活动限制使需求冲击可观察", "全球市场同步评估需求、风险偏好和流动性", "全球大流行定性获得进一步官方材料支撑", "紧急状态结束并转入常态化管理"],
        "focus": "全球需求、风险偏好与流动性压力",
        "date_precision": ["fast-event-01-M02", "fast-event-01-M05"],
    },
    "event-02": {
        "node_ids": ["fast-event-02-M01", "fast-event-02-M02", "fast-event-02-M03", "fast-event-02-M04", "fast-event-02-M05"],
        "phases": ["PRECONDITION", "INITIAL_SHOCK", "INITIAL_SHOCK", "POLICY_RESPONSE", "POLICY_RESPONSE"],
        "titles": ["低库存与地缘紧张构成脆弱背景", "俄罗斯宣布启动军事行动", "北约确认大规模进攻成为市场主锚点", "北约启动磋商并加强威慑部署", "俄油价格上限改变能源贸易约束"],
        "states": ["能源供应脆弱性尚未完成证据闭环", "地缘风险可能放大供应敏感度", "军事行动由预期转为公开宣布", "大规模进攻获得国际组织公开确认", "联盟安全政策开始响应军事冲击", "制裁与能源贸易规则进入中期定价"],
        "focus": "能源供应、通胀预期与风险偏好",
        "pending": ["fast-event-02-M01"],
    },
    "event-03": {
        "node_ids": ["fast-event-03-M01", "fast-event-03-M02", "fast-event-03-M03", "fast-event-03-M04", "fast-event-03-M05"],
        "phases": ["PRECONDITION", "PRECONDITION", "INITIAL_SHOCK", "ESCALATION", "ESCALATION"],
        "titles": ["FOMC 预告加息条件即将成熟", "美国通胀升至 7.5% 强化紧缩约束", "美联储实施本轮首次加息", "单次加息扩大至 75 个基点", "政策利率升至 5.25%–5.50% 区间"],
        "states": ["政策利率仍处于零附近", "加息进入近期基准情景", "高通胀强化加快紧缩的必要性", "加息周期正式启动", "紧缩速度显著加快且终端利率预期上移", "政策利率到达高位平台"],
        "focus": "利率、美元流动性、权益估值与增长预期",
    },
    "event-04": {
        "node_ids": ["fast-event-04-M01", "fast-event-04-M02", "fast-event-04-M03", "fast-event-04-M04", "fast-event-04-M05"],
        "phases": ["PRECONDITION", "PRECONDITION", "INITIAL_SHOCK", "ESCALATION", "RESOLUTION"],
        "titles": ["二十条措施建立防疫优化基线", "官方表述释放政策转向信号", "十条优化措施启动重新开放主线", "出行与活动变化提供次日验证", "乙类乙管确认退出清零框架"],
        "states": ["防疫政策仍以严格控制为主", "政策开始转向优化执行", "市场获得更清晰的转向预期", "重新开放成为增长与风险偏好主线", "实际活动开始验证政策影响", "防疫制度完成结构性退出"],
        "focus": "中国增长、大宗商品需求、人民币与全球风险偏好",
        "partial": ["fast-event-04-M03"],
        "date_precision": ["fast-event-04-M01", "fast-event-04-M02", "fast-event-04-M03", "fast-event-04-M05"],
    },
    "event-05": {
        "node_ids": ["fast-event-05-M01", "fast-event-05-M02", "fast-event-05-M03", "fast-event-05-M04", "fast-event-05-M05"],
        "phases": ["PRECONDITION", "INITIAL_SHOCK", "POLICY_RESPONSE", "SECONDARY_SHOCK", "EASING"],
        "titles": ["证券组合处置暴露流动性压力", "监管机构关闭硅谷银行", "美国推出紧急稳定措施", "瑞信处置扩大跨境银行压力", "第一共和银行被收购后压力阶段性缓和"],
        "states": ["银行资产负债表风险尚未成为主线", "流动性压力公开暴露但证据不完整", "银行关闭使系统性风险进入定价", "政策开始稳定存款与流动性", "压力扩展到欧洲银行和资本工具", "主要失败机构完成阶段性处置"],
        "focus": "银行压力、利率重定价、避险需求与风险资产",
        "pending": ["fast-event-05-M01", "fast-event-05-M04"],
    },
    "event-06": {
        "node_ids": ["fast-event-06-M01", "fast-event-06-M02", "fast-event-06-M03", "fast-event-06-M04", "fast-event-06-M05"],
        "phases": ["PRECONDITION", "PRECONDITION", "INITIAL_SHOCK", "ESCALATION", "EASING"],
        "titles": ["银行动荡后的油价回落构成候选背景", "冲击前石油基线得到官方展望支持", "OPEC+ 宣布额外自愿减产", "沙特追加每日一百万桶减产", "OPEC+ 公布逐步退出自愿减产安排"],
        "states": ["油价受需求与金融压力共同影响", "供给政策敏感度可能上升但待补证", "冲击前供需基线可以独立观察", "额外减产改变近端供给预期", "沙特加码提高收紧承诺持续性", "退出路径使供应恢复速度可被评估"],
        "focus": "原油供给、通胀传导与全球增长",
        "pending": ["fast-event-06-M01"],
        "date_precision": ["fast-event-06-M04", "fast-event-06-M05"],
    },
    "event-07": {
        "node_ids": ["fast-event-07-M01", "fast-event-07-M02", "fast-event-07-M03", "fast-event-07-M04", "fast-event-07-M05"],
        "phases": ["INITIAL_SHOCK", "ESCALATION", "ESCALATION", "POLICY_RESPONSE", "POLICY_RESPONSE"],
        "titles": ["10 月 7 日袭击启动中东冲突主线", "油市报告记录冲击初期供需环境", "Galaxy Leader 被扣押使风险扩展至红海", "多国护航行动回应航运安全风险", "美英空袭构成政策响应再升级"],
        "states": ["中东风险尚未形成新的全球锚点", "冲突与能源风险溢价进入定价", "油市反应可与实际供给中断区分", "红海安全成为独立航运成本渠道", "多国护航形成组织化响应", "军事回应可能形成新的升级循环"],
        "focus": "能源风险溢价、航运成本、避险需求与风险资产",
        "pending": ["fast-event-07-M05"],
        "date_precision": ["fast-event-07-M03"],
    },
    "event-08": {
        "node_ids": ["fast-event-08-M01", "fast-event-08-M02", "fast-event-08-M03", "fast-event-08-M04", "fast-event-08-M05"],
        "phases": ["PRECONDITION", "PRECONDITION", "INITIAL_SHOCK", "INITIAL_SHOCK", "SECONDARY_SHOCK"],
        "titles": ["收益率曲线控制先行放宽", "政策展望建立正常化前基线", "日本央行正式结束负利率框架", "短端政策利率转正成为市场主锚点", "日经暴跌与套息交易调整形成二次冲击"],
        "states": ["超宽松仍以负利率和收益率控制为核心", "长端控制提高灵活性且正常化预期升温", "政策决定前条件获得官方基线", "负利率政策正式结束", "市场以主锚点重定价利差和日元", "风险资产与套息交易出现二次调整"],
        "focus": "日元利差、日本利率与全球套息交易风险",
        "partial": ["fast-event-08-M05"],
    },
    "event-09": {
        "node_ids": ["fast-event-09-M01", "fast-event-09-M02", "fast-event-09-M03", "fast-event-09-M04", "fast-event-09-M05"],
        "phases": ["PRECONDITION", "PRECONDITION", "INITIAL_SHOCK", "POLICY_RESPONSE", "POLICY_RESPONSE"],
        "titles": ["宏观与信贷报告建立政策前基线", "美联储降息构成外部金融背景", "中国公布货币、住房与资本市场组合政策", "存量房贷与降准措施面向居民资产负债表", "互换便利建立资本市场流动性支持"],
        "states": ["增长信贷与住房仍需要政策支持", "国内政策前基线获得官方记录", "外部降息改善金融背景但不证明国内因果", "一揽子支持成为市场主锚点", "政策延伸到房贷和居民资产负债表", "资本市场获得结构性流动性工具"],
        "focus": "中国增长、人民币、住房信用与风险资产",
        "date_precision": ["fast-event-09-M04", "fast-event-09-M05"],
    },
    "event-10": {
        "node_ids": ["fast-event-10-M01", "fast-event-10-M03", "fast-event-10-M02", "fast-event-10-M04", "fast-event-10-M05"],
        "phases": ["PRECONDITION", "INITIAL_SHOCK", "INITIAL_SHOCK", "POLICY_RESPONSE", "EASING"],
        "titles": ["美国优先贸易政策构成候选前置框架", "白宫事实清单先行披露措施与政策逻辑", "行政命令建立广泛对等关税框架", "国别税率与海关执行进入候选实施阶段", "首轮税率调整与暂停机制形成候选缓和节点"],
        "states": ["对等关税仍处于调查和预期阶段", "前置框架存在但证据尚未闭环", "措施范围与传导逻辑进入公开信息", "行政命令形成正式关税框架", "市场等待国别税率和执行细节", "首轮调整可能缓和冲击但仍待验证"],
        "focus": "贸易成本、美国通胀、全球增长与风险偏好",
        "pending": ["fast-event-10-M01", "fast-event-10-M04", "fast-event-10-M05"],
    },
}


STORYLINE_SPECS: dict[str, list[dict[str, Any]]] = {
    event_id: _make_event(event_id, data)
    for event_id, data in _DATA.items()
}

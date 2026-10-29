"""Add explicit audit grouping labels to the task-specific Q&A UI."""

from __future__ import annotations

from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_005 import (
    build_ui_bundle,
    main,
    render_workbench as _render_v5,
    write_ui,
)


GROUP_LABEL_OVERRIDE = r"""
<script>
const qaEvidenceAuditAnswerImpl005=window.qaEvidenceAuditAnswer;
window.qaEvidenceAuditAnswer=function(answer){return '<article class="qa-task-block"><h3>结论分类</h3><p>先区分官方事实、研究推断、计算事实与拒答边界，再展示各自依据。</p></article>'+qaEvidenceAuditAnswerImpl005(answer)};
qaEvidenceAuditAnswer=window.qaEvidenceAuditAnswer;
const qaIndustryCompanyAnswerImpl005=window.qaIndustryCompanyAnswer;
window.qaIndustryCompanyAnswer=function(answer){return '<article class="qa-task-block"><h3>反证与独立混杂</h3><p>公司结论同时检查限制性披露、事件窗口内独立公告与停复牌状态。</p></article>'+qaIndustryCompanyAnswerImpl005(answer)};
qaIndustryCompanyAnswer=window.qaIndustryCompanyAnswer;
renderMain();
</script>
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    return _render_v5(bundle).replace("</body>", GROUP_LABEL_OVERRIDE + "</body>")


__all__ = ["build_ui_bundle", "main", "render_workbench", "write_ui"]

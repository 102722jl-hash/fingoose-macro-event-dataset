"""Restore the industry interaction post-processing after the Q&A render override."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_001 import build_ui_bundle
from fingoose_company_impact_qa_ui_v2_impl_002 import render_workbench as _render_v2


INDUSTRY_INTERACTION_OVERRIDE = r"""
<script>
function bindQaIndustryIntegration(event){
  document.querySelectorAll('[data-industry-tier]').forEach(function(button){button.onclick=function(){
    state.industryTier=button.dataset.industryTier;
    renderMain();
    requestAnimationFrame(function(){const group=document.querySelector('[data-industry-group="'+state.industryTier+'"]');if(group)group.scrollIntoView({behavior:'smooth',block:'start'})});
  }});
  document.querySelectorAll('[data-industry-mapping],[data-industry-detail]').forEach(function(button){button.onclick=function(){
    const mappingId=button.dataset.industryMapping||button.dataset.industryDetail;
    const impact=industryImpact(event,mappingId);
    state.industryMappingId=mappingId;
    state.industryTier=impact?impact.impact_tier:state.industryTier;
    state.industryId=impact?impact.sw1_id:null;
    if(button.dataset.industryDetail)state.transmissionMode='industry';
    state.companyId=null;
    renderMain();
    requestAnimationFrame(function(){const detail=document.querySelector('.industry-detail');if(detail)detail.scrollIntoView({behavior:'smooth',block:'start'})});
  }});
  document.querySelectorAll('[data-industry-company]').forEach(function(button){button.onclick=function(){
    state.companyId=button.dataset.industryCompany;
    renderMain();
    requestAnimationFrame(function(){const grid=document.querySelector('.company-grid');if(grid)grid.scrollIntoView({behavior:'smooth',block:'start'})});
  }});
}
const qaRenderMainWithSections=renderMain;
renderMain=function(){
  qaRenderMainWithSections();
  const event=currentEvent();
  const section=document.getElementById('industries');
  if(section&&!section.querySelector('.industry-detail'))section.insertAdjacentHTML('beforeend',industryDetail(event));
  bindQaIndustryIntegration(event);
};
renderMain();
</script>
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    return _render_v2(bundle).replace(
        "</body>", INDUSTRY_INTERACTION_OVERRIDE + "</body>"
    )


def write_ui(
    root: Path,
    output_root: Path,
    *,
    qa_root: Path,
    candidate_root: Path | None = None,
    industry_root: Path | None = None,
    industry_overlay_root: Path | None = None,
) -> dict[str, Any]:
    bundle = build_ui_bundle(
        root,
        qa_root=qa_root,
        candidate_root=candidate_root,
        industry_root=industry_root,
        industry_overlay_root=industry_overlay_root,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "ui_data_bundle.js").write_text(
        "window.FINGOOSE_COMPANY_IMPACT_V2="
        + json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    (output_root / "index.html").write_text(
        render_workbench(bundle), encoding="utf-8"
    )
    return bundle["summary"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--industry", type=Path, required=True)
    parser.add_argument("--industry-overlay", type=Path)
    parser.add_argument("--qa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    def resolve(path: Path | None) -> Path | None:
        if path is None:
            return None
        return path if path.is_absolute() else root / path

    summary = write_ui(
        root,
        resolve(args.output),
        qa_root=resolve(args.qa),
        candidate_root=resolve(args.candidate),
        industry_root=resolve(args.industry),
        industry_overlay_root=resolve(args.industry_overlay),
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = ["build_ui_bundle", "main", "render_workbench", "write_ui"]

"""Keep industry research interactions stable across full workbench rerenders."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from fingoose_company_impact_qa_ui_v2_impl_009 import build_ui_bundle
from fingoose_company_impact_qa_ui_v2_impl_009 import render_workbench as _render_v9


DELEGATED_INTERACTIONS = r"""
<script>
if(!window.__industryResearchDelegated){
  window.__industryResearchDelegated=true;
  document.addEventListener('click',function(event){
    const evidenceButton=event.target.closest('.closure-evidence-button:not(.missing)');
    if(evidenceButton){
      document.querySelectorAll('.closure-evidence-entry.highlight').forEach(function(row){row.classList.remove('highlight')});
      const target=document.getElementById(closureDomId(evidenceButton.dataset.closureEvidenceId));
      if(target){target.classList.add('highlight');target.scrollIntoView({behavior:'smooth',block:'center'})}
      return;
    }
    const stepButton=event.target.closest('[data-closure-node-step-target]');
    if(stepButton){
      const target=document.querySelector('[data-closure-node-step="'+stepButton.dataset.closureNodeStepTarget+'"]');
      if(target)target.scrollIntoView({behavior:'smooth',block:'center'});
      return;
    }
    const industryButton=event.target.closest('[data-matrix-industry]');
    if(industryButton){
      state.industryMappingId=industryButton.dataset.matrixIndustry;
      state.industryTier=industryButton.dataset.matrixTier;
      state.transmissionMode='industry';
      renderMain();
      const target=document.querySelector('.research-closure');
      if(target)target.scrollIntoView({block:'start'});
      return;
    }
    const companyButton=event.target.closest('[data-matrix-company]');
    if(companyButton){
      state.companyId=companyButton.dataset.matrixCompany;
      renderMain();
      const target=document.getElementById('companies');
      if(target)target.scrollIntoView({block:'start'});
    }
  });
}
</script>
"""


def render_workbench(bundle: Mapping[str, Any]) -> str:
    return _render_v9(bundle).replace("</body>", DELEGATED_INTERACTIONS + "</body>")


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
    (output_root / "index.html").write_text(render_workbench(bundle), encoding="utf-8")
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


if __name__ == "__main__":
    raise SystemExit(main())

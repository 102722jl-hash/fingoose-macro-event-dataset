
const DATA=JSON.parse(document.getElementById("workbench-data").textContent);
const windowPoints=["T-1","T0","D1","D3","D5","D20"];
const escapeMap={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"};
function splitIds(value){return (value||"").split("|").filter(Boolean)}
function storyStepsForNode(view,nodeId){
  return [...view.querySelectorAll(".story-step")].filter(story=>splitIds(story.dataset.evidenceNodeIds).includes(nodeId));
}
function pathCardsForIds(view,ids){
  const wanted=new Set(ids); return [...view.querySelectorAll(".path-card")].filter(path=>wanted.has(path.dataset.pathId));
}
function marketCardsForIds(view,ids){
  const wanted=new Set(ids); return [...view.querySelectorAll(".market-card")].filter(card=>wanted.has(card.dataset.seriesId));
}
function setStoryDrawer(story,expanded){
  const header=story.querySelector(".story-head"),drawer=story.querySelector(".story-drawer");
  header?.setAttribute("aria-expanded",expanded?"true":"false"); if(drawer)drawer.hidden=!expanded;
}
function closeStoryDrawers(view,except=null){
  view.querySelectorAll(".story-step").forEach(story=>{if(story!==except)setStoryDrawer(story,false)});
}
function clearVisualSelection(view){
  view.querySelectorAll(".story-step,.timeline-node,.path-card,.market-card").forEach(item=>item.classList.remove("selected"));
}
function updateContext(view,label,kind){
  const context=view.querySelector(".context"); if(!context)return;
  context.innerHTML='当前选择：<strong></strong> · '+kind+'；高亮仅表示关联，不改变证据或候选路径状态。';
  context.querySelector("strong").textContent=label;
}
function selectEvent(eventId){
  document.querySelectorAll("[data-event-view]").forEach(view=>view.classList.toggle("hidden",view.dataset.eventView!==eventId));
  document.querySelectorAll("[data-event-id]").forEach(link=>link.classList.toggle("active",link.dataset.eventId===eventId));
  document.getElementById("event-sidebar").classList.remove("open");
  const view=document.querySelector('[data-event-view="'+CSS.escape(eventId)+'"]');
  const story=view?.querySelector(".story-step.selected")||view?.querySelector(".story-step");
  if(story)selectStoryStep(story.dataset.storyStepId);
  window.scrollTo({top:0,behavior:"smooth"});
}
function selectStoryStep(stepId){
  const story=document.querySelector('[data-story-step-id="'+CSS.escape(stepId)+'"]'); if(!story)return;
  const view=story.closest("[data-event-view]"); clearVisualSelection(view); closeStoryDrawers(view,story);
  story.classList.add("selected"); setStoryDrawer(story,true);
  const evidenceIds=splitIds(story.dataset.evidenceNodeIds);
  const pathIds=splitIds(story.dataset.pathIds);
  const seriesIds=splitIds(story.dataset.seriesIds);
  view.querySelectorAll(".timeline-node").forEach(node=>node.classList.toggle("selected",evidenceIds.includes(node.dataset.nodeId)));
  pathCardsForIds(view,pathIds).forEach(path=>path.classList.add("selected"));
  view.querySelectorAll(".market-card").forEach(card=>card.classList.toggle("selected",seriesIds.includes(card.dataset.seriesId)));
  const title=story.querySelector("h3")?.textContent||stepId;
  updateContext(view,title,"已联动证据节点、候选路径与行情序列");
}
function selectTimelineNode(nodeId){
  const button=document.querySelector('[data-node-id="'+CSS.escape(nodeId)+'"]'); if(!button)return;
  const view=button.closest("[data-event-view]"); clearVisualSelection(view); closeStoryDrawers(view);
  button.classList.add("selected");
  const stories=storyStepsForNode(view,nodeId); stories.forEach(story=>story.classList.add("selected"));
  if(stories[0])setStoryDrawer(stories[0],true);
  const storyPathIds=stories.flatMap(story=>splitIds(story.dataset.pathIds));
  const directPaths=[...view.querySelectorAll(".path-card")].filter(path=>path.dataset.anchorNodeId===nodeId);
  const paths=[...new Set([...pathCardsForIds(view,storyPathIds),...directPaths])]; paths.forEach(path=>path.classList.add("selected"));
  const seriesIds=stories.flatMap(story=>splitIds(story.dataset.seriesIds));
  marketCardsForIds(view,seriesIds).forEach(card=>card.classList.add("selected"));
  const detail=view.querySelector(".node-detail"), card=button.querySelector(".node-card"), linked=paths.map(path=>path.dataset.pathId).join("、")||"当前节点没有已激活路径";
  detail.innerHTML='<div class="eyebrow">当前选择 · '+nodeId+'</div><h3>'+card.querySelector("h3").textContent+'</h3><p>'+card.querySelector("p").textContent+'</p><div class="boundary">证据状态：'+card.querySelector("em").textContent+'。原文与证据边界可在节点卡片中展开。</div><dl><dt>对应事件步骤</dt><dd>'+(stories.map(story=>story.querySelector("h3").textContent).join("、")||"待建立叙事映射")+'</dd><dt>对应传导路径</dt><dd>'+linked+'</dd></dl>';
  updateContext(view,nodeId,"已反向定位事件步骤，并联动候选路径与行情序列");
  (paths[0]||stories[0])?.scrollIntoView({behavior:"smooth",block:"center"});
}
function activatePath(pathId){const path=document.querySelector('[data-path-id="'+CSS.escape(pathId)+'"]');if(!path)return;path.closest("[data-event-view]").querySelectorAll(".path-card").forEach(item=>item.classList.remove("selected"));path.classList.add("selected");path.scrollIntoView({behavior:"smooth",block:"center"})}
document.getElementById("mobile-menu").onclick=()=>document.getElementById("event-sidebar").classList.toggle("open");
const initialStory=document.querySelector("[data-event-view]:not(.hidden) .story-step");
if(initialStory)selectStoryStep(initialStory.dataset.storyStepId);

"""從 build/graph.json 產生單頁互動譜系圖 viewer.html(可直接發佈為 artifact)。
用 vis-network(cdnjs)畫可點節點;點節點看它的關係、出處、可信度、狀態。
程式產生、資料內嵌、單檔可攜。設計:不殺雞用牛刀,用現成成熟的圖視覺化套件。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
G = json.loads((ROOT / "build/graph.json").read_text(encoding="utf-8"))

nodes = [{"id": n["id"], "label": n.get("name_zh", n["id"]),
          "type": n.get("type", "concept"), "cent": n.get("centrality", 0)}
         for n in G["nodes"]]
edges = [{"from": e["source"], "to": e["target"], "kind": e.get("kind", ""),
          "claim": e.get("claim", ""), "evidence": e.get("evidence", ""),
          "ref": e.get("source_ref", ""), "tier": e.get("source_tier", ""),
          "conf": e.get("confidence", 0), "status": e.get("status", "")}
         for e in G["links"]]
DATA = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)

TEMPLATE = r"""<title>觀看的座標 譜系地圖</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;600;700&display=swap">
<style>
  /* 版面:全螢幕圖 + 右側(窄螢幕改底部)詳情面板 */
  :root{
    --bg:#eef0f1; --surface:#ffffff; --fg:#1b1f24; --muted:#5c646d; --line:#d7dce1;
    --accent:#2f6f6b;
    --person:#2f6f6b; --work:#3b6ea5; --concept:#b4681a; --event:#7a5ea8; --institution:#3f7d4e;
    --auto:#3f7d4e; --review:#b4681a;
    --font:"Noto Sans TC",system-ui,-apple-system,sans-serif;
  }
  @media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
    --bg:#15181b; --surface:#1e2226; --fg:#e8eaed; --muted:#99a1aa; --line:#2d343b;
    --accent:#5fb0a8;
    --person:#5fb0a8; --work:#6fa3d6; --concept:#d79a52; --event:#a98fd0; --institution:#6bbf7e;
    --auto:#6bbf7e; --review:#d79a52; color-scheme:dark;
  }}
  :root[data-theme="dark"]{
    --bg:#15181b; --surface:#1e2226; --fg:#e8eaed; --muted:#99a1aa; --line:#2d343b;
    --accent:#5fb0a8;
    --person:#5fb0a8; --work:#6fa3d6; --concept:#d79a52; --event:#a98fd0; --institution:#6bbf7e;
    --auto:#6bbf7e; --review:#d79a52; color-scheme:dark;
  }
  html,body{height:100%}
  *{box-sizing:border-box}
  #app{height:100%;display:flex;flex-direction:column;background:var(--bg);color:var(--fg);
    font-family:var(--font);font-size:14px}
  header{flex:0 0 auto;background:var(--surface);border-bottom:1px solid var(--line);
    padding:10px 16px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px}
  header h1{margin:0;font-size:16px;font-weight:700}
  header .sub{font-size:12px;color:var(--muted)}
  .legend{display:flex;flex-wrap:wrap;gap:4px 12px;margin-left:auto;font-size:12px;color:var(--muted)}
  .legend span{display:inline-flex;align-items:center;gap:5px}
  .dot{width:10px;height:10px;border-radius:50%;flex:0 0 auto}
  #main{flex:1;display:flex;min-height:0}
  #net{flex:1;min-width:0;min-height:0}
  #panel{flex:0 0 320px;max-width:42vw;background:var(--surface);border-left:1px solid var(--line);
    overflow-y:auto;padding:16px}
  #panel h2{margin:0 0 4px;font-size:18px}
  #panel .ptype{font-size:12px;color:var(--muted);margin-bottom:12px}
  .rel{border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin-bottom:10px}
  .rel .top{display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:4px}
  .rel .arrow{font-weight:600;cursor:pointer}
  .rel .arrow:hover{color:var(--accent);text-decoration:underline}
  .rel .badge{font-size:11px;font-weight:600;border-radius:99px;padding:2px 8px;white-space:nowrap}
  .b-auto{background:color-mix(in srgb,var(--auto) 18%,transparent);color:var(--auto)}
  .b-review{background:color-mix(in srgb,var(--review) 18%,transparent);color:var(--review)}
  .rel .claim{font-size:13px;line-height:1.5}
  .rel .meta{font-size:11.5px;color:var(--muted);margin-top:5px}
  .hint{color:var(--muted);font-size:13px;line-height:1.6}
  @media(max-width:640px){
    #main{flex-direction:column}
    #panel{flex:0 0 auto;max-width:none;max-height:44%;border-left:none;border-top:1px solid var(--line)}
  }
</style>
<div id="app">
  <header>
    <div>
      <h1>觀看的座標 · 譜系地圖</h1>
      <div class="sub">NTU Challengers｜攝影論述 AI Agent　點節點看關係與出處</div>
    </div>
    <div class="legend" id="legend"></div>
  </header>
  <div id="main">
    <div id="net"></div>
    <aside id="panel"><p class="hint">點任一個節點,這裡會列出它的關係、主張、出處、可信度與狀態(自動入圖 / 待人工判斷)。拖曳可移動,滾輪縮放。</p></aside>
  </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/vis-network.min.js"></script>
<script>
const DATA = /*__DATA__*/;
const css = k => getComputedStyle(document.documentElement).getPropertyValue(k).trim();
const TYPES = {person:"人物", work:"著作/期刊", concept:"概念", event:"事件", institution:"館所"};
function colorOf(t){return css("--"+t) || css("--concept");}

const byId = {}; DATA.nodes.forEach(n=>byId[n.id]=n);
const nodesDS = new vis.DataSet(DATA.nodes.map(n=>({ id:n.id, label:n.label, shape:"dot", value: 4 + n.cent*60 })));
const edgesDS = new vis.DataSet(DATA.edges.map((e,i)=>({ id:i, from:e.from, to:e.to, arrows:"to", dashes: e.status==="review" })));

const container = document.getElementById("net");
const net = new vis.Network(container, {nodes:nodesDS, edges:edgesDS}, {
  physics:{stabilization:true, barnesHut:{gravitationalConstant:-6000, springLength:130, avoidOverlap:0.4}},
  interaction:{hover:true, tooltipDelay:200},
  nodes:{borderWidth:1.5, scaling:{min:6,max:34}}
});

function applyTheme(){
  // 依目前主題(深/淺)重算顏色,使用者切換主題即時更新
  nodesDS.update(DATA.nodes.map(n=>({ id:n.id,
    color:{background:colorOf(n.type), border:colorOf(n.type)},
    font:{color:css("--fg"), size:15, face:"'Noto Sans TC', sans-serif"} })));
  edgesDS.update(DATA.edges.map((e,i)=>({ id:i,
    color:{color: e.status==="review"? css("--review"): css("--muted"), opacity:0.75},
    width: e.status==="review"?1:1.6 })));
  document.getElementById("legend").innerHTML =
    Object.keys(TYPES).map(t=>`<span><i class="dot" style="background:${colorOf(t)}"></i>${TYPES[t]}</span>`).join("")
    + `<span><i class="dot" style="background:${css('--auto')}"></i>入圖</span>`
    + `<span><i class="dot" style="background:${css('--review')}"></i>待判斷</span>`;
}
applyTheme();
try{
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyTheme);
  new MutationObserver(applyTheme).observe(document.documentElement, {attributes:true, attributeFilter:["data-theme"]});
}catch(e){}

const KIND = {influence:"影響了", critique:"批判了", extend:"延伸自", belongs_to:"屬於", contrast:"對照於", discusses:"討論了",
  translate:"翻譯了", study:"研究了", review:"評論了", interpret:"詮釋了", exhibit:"展出了"};
const panel = document.getElementById("panel");
function nm(id){return byId[id]? byId[id].label : id;}

function showNode(id){
  const n = byId[id]; if(!n) return;
  const outE = DATA.edges.filter(e=>e.from===id);
  const inE  = DATA.edges.filter(e=>e.to===id);
  let html = `<h2>${n.label}</h2><div class="ptype">${TYPES[n.type]||n.type}　中心性 ${n.cent}</div>`;
  const render = (e, dir)=>{
    const other = dir==="out"? e.to : e.from;
    const verb = KIND[e.kind]||e.kind;
    const txt = dir==="out"? `→ ${nm(other)}` : `← ${nm(other)}`;
    const badge = e.status==="review"? '<span class="badge b-review">待判斷</span>':'<span class="badge b-auto">入圖</span>';
    return `<div class="rel"><div class="top"><span class="arrow" data-id="${other}">${txt}（${verb}）</span>${badge}</div>`
      + `<div class="claim">${e.claim||""}</div>`
      + `<div class="meta">可信度 ${e.conf}　來源層 ${e.tier}　出處 ${e.ref}${e.evidence? "　· "+e.evidence : ""}</div></div>`;
  };
  if(outE.length) html += `<div class="ptype" style="margin:6px 0">由此出發（${outE.length}）</div>` + outE.map(e=>render(e,"out")).join("");
  if(inE.length)  html += `<div class="ptype" style="margin:10px 0 6px">指向此處（${inE.length}）</div>` + inE.map(e=>render(e,"in")).join("");
  if(!outE.length && !inE.length) html += `<p class="hint">這個節點目前還沒有關係(待連結)。</p>`;
  panel.innerHTML = html;
  panel.querySelectorAll(".arrow").forEach(a=>a.onclick=()=>{const t=a.dataset.id; net.selectNodes([t]); net.focus(t,{scale:1.1,animation:true}); showNode(t);});
}
net.on("click", p=>{ if(p.nodes.length) showNode(p.nodes[0]); });
</script>
"""

(ROOT / "build/viewer.html").write_text(TEMPLATE.replace("/*__DATA__*/", DATA), encoding="utf-8")
print("viewer.html 產生,節點", len(nodes), "關係", len(edges))

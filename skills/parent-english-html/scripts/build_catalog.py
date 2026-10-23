# -*- coding: utf-8 -*-
"""从 tools/series.json 生成 outputs/亲子英语/index.html（总目录）。

目录页设计（搜索 + 分类/年龄段/难度筛选 + 封面卡）与 outputs/series/index.html 一致。
哪些篇"已上线"由文件系统判断：outputs/亲子英语/<slug>/index.html 存在即为已上线。
用法: python tools/build_catalog.py
"""
import io, json, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, ".."))
SERIES = os.path.join(BASE, "series.json")
MAN = json.load(io.open(SERIES, encoding="utf-8"))
OUT_DIR = os.path.join(ROOT, "outputs", "亲子英语")
OUT = os.path.join(OUT_DIR, "index.html")

TPL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>亲子英语 · 场景口语成长计划</title>
<style>
:root{
  --bg:#fbf7f2; --card:#fff; --ink:#2c2a27; --muted:#75706a; --faint:#9a948d;
  --line:#ece4d9; --line2:#f5f0e9;
  --accent:#e0784f; --accent-soft:#fdeee6; --accent-ink:#b8542c;
  --blue:#dbe9fb; --blue-b:#9cc4f0; --blue-ink:#2f5f96;
  --green:#dcf1e3; --green-b:#a8dcbd;
  --shadow:0 1px 2px rgba(60,45,30,.05),0 5px 16px rgba(60,45,30,.06);
  --r:13px;
}
@media(prefers-color-scheme:dark){
  :root{
    --bg:#1b1917; --card:#242220; --ink:#ece7e0; --muted:#a9a29a; --faint:#8a837b;
    --line:#37332f; --line2:#2c2926;
    --accent:#e08a63; --accent-soft:#3a2a22; --accent-ink:#f0a882;
    --blue:#22303f; --blue-b:#4a7ba8; --blue-ink:#9fc6ee;
    --green:#223528; --green-b:#5d9c74;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 5px 16px rgba(0,0,0,.25);
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:"PingFang SC","Microsoft YaHei","Hiragino Sans GB",system-ui,-apple-system,sans-serif;
  font-size:15px;line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:1000px;margin:0 auto;padding:0 20px 60px}
a{color:inherit}

.hero{padding:46px 0 22px}
.hero h1{margin:0 0 8px;font-size:27px;letter-spacing:.5px}
.hero .sub{color:var(--muted);font-size:14.5px;margin:0}
.hero .tags{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
.tag{font-size:12px;padding:3px 10px;border-radius:999px;background:var(--line2);
  border:1px solid var(--line);color:var(--muted)}

.base-card{margin-top:22px;background:var(--blue);border:1px solid var(--blue-b);
  border-left:5px solid var(--blue-b);border-radius:var(--r);padding:16px 20px}
.base-card .bt{font-weight:700;color:var(--blue-ink);margin-bottom:8px;font-size:15px}
.base-card p{font-size:14.5px;margin:0 0 8px}
.base-card p:last-child{margin-bottom:0}
.base-card b{color:var(--blue-ink)}
.base-card .hl{background:color-mix(in srgb,var(--blue-b) 30%,transparent);
  color:var(--blue-ink);font-weight:700;padding:1px 7px;border-radius:6px}
.base-card .path{background:color-mix(in srgb,var(--blue-b) 22%,transparent);
  padding:2px 8px;border-radius:7px;font-weight:600}

/* 我的学习：统计 + 星星罐 */
.mine{margin-top:46px;position:relative;display:grid;grid-template-columns:auto 1fr;
  gap:22px;align-items:center;background:var(--card);border:1px solid var(--line);
  border-radius:var(--r);padding:18px 24px;box-shadow:var(--shadow)}
.mine .pbox{width:100px;position:relative}
.mine .jar svg{display:block;width:100px;height:auto;overflow:visible}
.mine .pcap{font-size:11.5px;color:var(--faint);text-align:center;margin-top:6px;white-space:nowrap}
.mine .pbar{height:5px;margin:6px 4px 0;border-radius:99px;background:var(--line2);
  border:1px solid var(--line);overflow:hidden}
.mine .pbar i{display:block;height:100%;width:0;border-radius:99px;
  background:linear-gradient(90deg,#ffd96b,#f3a52a);transition:width .5s ease}
.mine .mbody{min-width:0}
.mine .mttl{display:flex;align-items:center;gap:10px;margin-bottom:10px;
  font-size:13.5px;font-weight:700;color:var(--ink)}
.mine .mtoday{margin-left:auto;font-size:12px;font-weight:600;color:var(--faint);
  border:1px solid var(--line);background:var(--line2);border-radius:999px;
  padding:3px 12px;white-space:nowrap;transition:background .25s,border-color .25s}
.mine .mtoday.ok{background:var(--green);border-color:var(--green-b);color:var(--ink)}
.mine .stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stat{background:var(--line2);border:1px solid var(--line);border-radius:11px;padding:9px 13px}
.stat .k2{font-size:11.5px;color:var(--faint);line-height:1.5;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis}
.stat .v{font-size:22px;font-weight:700;line-height:1.28}
.stat .v small{font-size:12px;font-weight:400;color:var(--muted);margin-left:1px}
.bubble{position:absolute;left:16px;top:0;transform:translateY(-100%) scale(.85);
  transform-origin:26px 100%;
  background:var(--accent);color:#fff;font-size:12.5px;font-weight:600;line-height:1.4;
  padding:7px 12px;border-radius:12px;white-space:nowrap;opacity:0;pointer-events:none;
  transition:opacity .35s ease,transform .35s ease;box-shadow:0 4px 14px rgba(224,120,79,.3);z-index:3}
.bubble::after{content:"";position:absolute;left:26px;bottom:-5px;
  border:6px solid transparent;border-top-color:var(--accent);border-bottom:0}
.bubble.show{opacity:1;transform:translateY(-100%) scale(1)}
/* 星星罐动效 */
.jar g.bottle{transform-box:fill-box;transform-origin:50% 100%}
.jar.pop g.bottle{animation:jarpop .8s ease}
@keyframes jarpop{0%,100%{transform:scale(1)}45%{transform:scale(1.045)}}
.jar .star{transform-box:fill-box;transform-origin:center}
.jar .star.drop{animation:stardrop .9s cubic-bezier(.25,1.35,.5,1) both}
@keyframes stardrop{0%{opacity:0;transform:translateY(-42px) scale(.2) rotate(-60deg)}
  55%{opacity:1}100%{opacity:1;transform:none}}
.jar .spark{transform-box:fill-box;transform-origin:center;
  animation:twinkle 2.8s ease-in-out infinite}
@keyframes twinkle{0%,100%{opacity:.1;transform:scale(.5) rotate(0deg)}
  50%{opacity:.95;transform:scale(1) rotate(24deg)}}
.jar .shine{opacity:.32;transition:opacity .7s ease}
.jar.full .shine{opacity:1}
@media(max-width:600px){
  .mine{grid-template-columns:1fr;padding:16px}
  .mine .pbox{width:100px;margin:0 auto}
  .mine .mttl{justify-content:center}
  .mine .mtoday{margin-left:6px}
  .mine .stats{grid-template-columns:1fr 1fr}
}

h2.sec{font-size:17px;margin:34px 0 4px;display:flex;align-items:baseline;gap:10px}
h2.sec small{font-weight:400;font-size:12.5px;color:var(--faint)}

.tools{margin-top:16px;display:flex;flex-direction:column;gap:10px}
.search{position:relative}
.search input{width:100%;padding:10px 14px 10px 38px;font-size:14px;color:var(--ink);
  background:var(--card);border:1px solid var(--line);border-radius:11px;outline:none;
  transition:border-color .15s}
.search input:focus{border-color:var(--accent)}
.search .ico{position:absolute;left:13px;top:50%;transform:translateY(-50%);
  font-size:14px;color:var(--faint);pointer-events:none}
.filters{display:flex;flex-direction:column;gap:8px}
.frow{display:flex;align-items:flex-start;gap:10px}
.frow .lab{flex:0 0 58px;font-size:12.5px;color:var(--faint);padding-top:5px}
.chips{display:flex;gap:7px;flex-wrap:wrap}
.chip{font-size:12.5px;padding:4px 12px;border-radius:999px;cursor:pointer;user-select:none;
  background:var(--card);border:1px solid var(--line);color:var(--muted);
  transition:all .13s ease}
.chip:hover{border-color:var(--accent);color:var(--accent-ink)}
.chip.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-ink);font-weight:700}
.empty{margin-top:26px;text-align:center;color:var(--faint);font-size:14px;padding:30px 0;
  border:1px dashed var(--line);border-radius:var(--r);display:none}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:16px}
.sc{display:block;text-decoration:none;background:var(--card);border:1px solid var(--line);
  border-radius:var(--r);overflow:hidden;box-shadow:var(--shadow);
  transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}
.sc:hover{transform:translateY(-3px);border-color:var(--accent);
  box-shadow:0 3px 14px rgba(224,120,79,.16)}
.sc .cov{position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--line2)}
.sc .cov img{width:100%;height:100%;object-fit:cover;display:block;
  transition:transform .3s ease}
.sc:hover .cov img{transform:scale(1.04)}
.sc .no{position:absolute;top:10px;left:10px;font-size:12px;font-weight:700;color:#fff;
  background:rgba(40,32,25,.55);backdrop-filter:blur(4px);border-radius:7px;padding:1px 9px}
.sc .ok{position:absolute;top:10px;right:10px;font-size:11.5px;font-weight:700;color:#fff;
  background:var(--green-b);border-radius:7px;padding:1px 9px;box-shadow:0 1px 6px rgba(0,0,0,.18)}
.sc .ok.doing{background:var(--card);color:var(--accent-ink);border:1px solid var(--accent)}
.sc .body{padding:12px 15px 13px}
.sc h3{margin:0;font-size:16.5px}
.sc .en{color:var(--muted);font-size:12.5px;margin:1px 0 4px}
.sc .by{color:var(--faint);font-size:11.5px;margin:0 0 9px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sc .by::before{content:"来源 YouTube "}
.sc .meta{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:9px}
.sc .meta span{font-size:11.5px;padding:2px 8px;border-radius:999px;
  background:var(--line2);border:1px solid var(--line);color:var(--muted)}
.bar{height:6px;border-radius:99px;background:var(--line2);overflow:hidden;margin-bottom:6px}
.bar i{display:block;height:100%;border-radius:99px;background:var(--green-b);width:0;transition:width .4s}
.bar.full i{background:var(--accent)}
.sc .pr{display:flex;justify-content:space-between;align-items:center;font-size:12px;color:var(--faint)}
.sc .go{color:var(--accent-ink);font-weight:700;font-size:13px}

.sc.soon{opacity:.62;pointer-events:none}
.sc.soon .go{color:var(--faint)}

footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);
  font-size:12.5px;color:var(--faint);line-height:1.75}
footer b{color:var(--muted)}

@media(max-width:600px){
  .hero{padding:30px 0 16px}
  .hero h1{font-size:22px}
  .grid{grid-template-columns:1fr}
  .frow{flex-wrap:wrap;gap:6px}
  .frow .lab{flex-basis:100%;padding-top:0}
}
@media print{
  .tools{display:none}
  .grid{grid-template-columns:1fr}
  .sc{break-inside:avoid;box-shadow:none}
}
</style>
</head>
<body>
<div class="wrap">

  <div class="hero">
    <h1>亲子英语 · 场景口语成长计划</h1>
    <p class="sub">真实场景的原声 + 逐句精听 + 妈妈能直接说的句子。挑一个场景点进去，从今天开始说。</p>
    <div class="tags">
      <span class="tag">真实原声</span>
      <span class="tag">逐句精听</span>
      <span class="tag">可打卡</span>
      <span class="tag">可收藏复习</span>
      <span class="tag">离线可用</span>
    </div>
  </div>

  <div class="base-card">
    <div class="bt">怎么用</div>
    <p><span class="hl">懒人妈妈</span>：进任意一篇，直接翻到 <b>Part 4 场景常用句</b>，挑 2 句当天对宝宝说就够了。</p>
    <p><span class="hl">想系统学</span>：<span class="path">全篇原声听一遍 → 逐句精听 → 跟读 3 遍 → 对宝宝说 → 回来打勾</span>，每篇分 3 天，每天 5 分钟。</p>
    <p>每篇结构一致：听原声 → 逐句精听 → 学词汇 → 学句子 → 练一练 → 避开中式英语（涉及文化背景的篇目另加「文化贴士」）。</p>
  </div>

  <div class="mine" id="mine">
    <div class="pbox">
      <div class="bubble" id="bubble"></div>
      <div class="jar" id="jar"></div>
      <div class="pcap" id="jcap">还没有星星 🌟</div>
      <div class="pbar"><i id="jbar"></i></div>
    </div>
    <div class="mbody">
      <div class="mttl"><span>我的学习</span><span class="mtoday" id="sToday">今日还没打卡</span></div>
      <div class="stats">
        <div class="stat"><div class="k2">🎬 已学习场景</div><div class="v" id="sScene">0 <small>个</small></div></div>
        <div class="stat"><div class="k2">💬 已掌握句子</div><div class="v" id="sSent">0 <small>句</small></div></div>
        <div class="stat"><div class="k2">📅 已学习</div><div class="v" id="sDay">0 <small>天</small></div></div>
      </div>
    </div>
  </div>

  <h2 class="sec">场景目录 <small id="cnt"></small></h2>

  <div class="tools">
    <div class="search">
      <span class="ico">🔍</span>
      <input id="q" type="search" placeholder="搜场景名 / 英文名 / 来源频道，如：起床、bath、Vanessa…" autocomplete="off">
    </div>
    <div class="filters" id="filters"></div>
  </div>

  <div class="grid" id="grid"></div>
  <div class="empty" id="empty">没有符合条件的场景，换个筛选条件试试 🌷</div>

  <footer>
    <p><b>关于进度：</b>卡片上的进度条是该场景的「精听进度」，旁边是已掌握的场景句数量；单词打卡不计入。每完成一个场景，上面的星星罐就多一颗星。记录只存在这台设备的浏览器里，换设备 / 换浏览器 / 清缓存都会归零，不会上传，也不会跨设备同步。</p>
    <p><b>关于更新：</b>新场景会陆续加进这个目录，链接不变，随时回来看。</p>
    <p><b>关于素材：</b>视频与英文原文来自 YouTube 上各位创作者（频道名标在每张卡片上），版权归原作者所有。这里只做了剪辑、重配中英字幕和知识点整理，仅作亲子英语学习用途，不作任何商业使用。</p>
    <p style="margin-top:10px">关注我，不错过新场景 🌱</p>
  </footer>

</div>

<script>
/* ========== 系列数据：由 tools/build_catalog.py 从 series.json 生成，别手改 ========== */
const SERIES=%SERIES%;

const STAR=n=>'★'.repeat(n||0);
const grid=document.getElementById('grid');

const state={q:'',cat:'全部',age:'全部',diff:'全部',prog:'全部'};
const DIFF_LABELS={'全部':'全部','1':'★☆☆ 入门','2':'★★☆ 进阶','3':'★★★ 挑战'};
const PROG_LABELS={'全部':'全部','done':'✓ 已完成','doing':'⏳ 进行中','todo':'○ 未开始'};

const uniq=key=>[...new Set(SERIES.map(s=>s[key]))];
/* 分类顺序固定按这份清单走；清单里有、但当前没有课的分类不显示 */
const CAT_ORDER=['生活起居','日常出行','情绪社交','游戏玩耍','学习认知','安全事项','节日文化'];
const CATS=CAT_ORDER.filter(c=>SERIES.some(s=>s.cat===c));
const groups=[
  {key:'cat', label:'分类', opts:['全部',...CATS]},
  {key:'age', label:'年龄段', opts:['全部',...uniq('age')]},
  {key:'diff',label:'难度', opts:['全部','1','2','3'].filter(v=>v==='全部'||SERIES.some(s=>s.diff===+v))},
  {key:'prog',label:'进度', opts:['全部','doing','todo','done']}
];
const filtersEl=document.getElementById('filters');
groups.forEach(g=>{
  const row=document.createElement('div'); row.className='frow';
  row.innerHTML='<span class="lab">'+g.label+'</span>';
  const chips=document.createElement('div'); chips.className='chips';
  g.opts.forEach(opt=>{
    const c=document.createElement('span');
    c.className='chip'+(String(state[g.key])===String(opt)?' on':'');
    c.textContent=g.key==='diff'?DIFF_LABELS[String(opt)]
                :(g.key==='prog'?PROG_LABELS[opt]:opt);
    c.onclick=()=>{
      state[g.key]=opt;
      chips.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
      c.classList.add('on');
      render();
    };
    chips.appendChild(c);
  });
  row.appendChild(chips); filtersEl.appendChild(row);
});

document.getElementById('q').addEventListener('input',e=>{state.q=e.target.value.trim().toLowerCase();render();});

function readProgress(slug){
  try{ const raw=localStorage.getItem('xhs.progress.'+slug); return raw?JSON.parse(raw):null; }
  catch(e){ return null; }
}

/* ========== 我的学习：统计口径 ==========
   只认「精听进度」(Part 2 Day 打卡) 与「已掌握句子」(Part 4 场景句打卡)，
   单词打卡不计入。场景完成 = 精听全部打完 或 场景句全部打完。 */
function readDays(){
  try{ const a=JSON.parse(localStorage.getItem('xhs.days')||'[]'); return Array.isArray(a)?a:[]; }
  catch(e){ return []; }
}
function todayStr(){
  const d=new Date();
  return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
function myStats(){
  const t=todayStr();
  let scenes=0,sents=0,today=false;
  SERIES.forEach(s=>{
    if(!s.url) return;
    const p=readProgress(s.slug); if(!p) return;
    if(p.complete) scenes++;
    sents+=(p.scene||0);
    if(p.ts){
      const d=new Date(p.ts);
      const ds=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
      if(ds===t) today=true;
    }
  });
  return {today, scenes, sents, days:readDays().length};
}

/* ========== 星星罐 ==========
   每完成一个场景 = 一颗彩星落进罐子，随机大小 / 颜色 / 角度、互相堆叠。
   位置用「按索引的稳定伪随机」（jarRnd），所以新增星星不会打乱已有的布局。
   罐子容量固定 JAR_CAP，满了只点亮光晕 —— 课程加到几十上百课也不会「画不完」。 */
const JAR_CAP=30;
const STAR_COLORS=['#f9c74f','#78c6e8','#79d6a4','#f9a8c9','#b3a1e6','#f8a05c'];
function jarRnd(i,salt){ const x=Math.sin(i*127.1+salt*311.7)*43758.5453; return x-Math.floor(x); }
function starPts(cx,cy,r){
  const p=[];
  for(let i=0;i<10;i++){
    const rr=(i%2)?r*0.45:r, a=-Math.PI/2+i*Math.PI/5;
    p.push((cx+rr*Math.cos(a)).toFixed(1)+','+(cy+rr*Math.sin(a)).toFixed(1));
  }
  return p.join(' ');
}
function sparkPts(cx,cy,r){
  const k=r*0.28;
  return [[cx,cy-r],[cx+k,cy-k],[cx+r,cy],[cx+k,cy+k],[cx,cy+r],[cx-k,cy+k],[cx-r,cy],[cx-k,cy-k]]
    .map(p=>p[0].toFixed(1)+','+p[1].toFixed(1)).join(' ');
}
function starAt(i){
  const COLS=5, CX=53;
  const row=Math.floor(i/COLS), col=i%COLS;
  const spread=1-row*0.06;                       /* 越往上堆得越窄，像一颗颗垒上去 */
  const x=CX+((col-(COLS-1)/2)/((COLS-1)/2))*25*spread+(jarRnd(i,1)-0.5)*9;
  const y=121-row*13+(jarRnd(i,2)-0.5)*10;       /* 行距 13、抖动 ±5 → 行与行会互相压住 */
  return {
    x:x, y:y,
    r:5.6*(0.62+jarRnd(i,3)*0.62),               /* 大小随机 0.62~1.24 */
    rot:(jarRnd(i,4)-0.5)*68,                    /* 角度随机 ±34° */
    c:STAR_COLORS[Math.floor(jarRnd(i,5)*STAR_COLORS.length)%STAR_COLORS.length]
  };
}
function jarSVG(stars,animateLast){
  stars=Math.max(0,Math.floor(stars||0));
  const shown=Math.min(stars,JAR_CAP);
  const place=(p,extra)=>' points="'+starPts(p.x,p.y,p.r)+'"'+extra
    +' transform="rotate('+p.rot.toFixed(1)+' '+p.x.toFixed(1)+' '+p.y.toFixed(1)+')"';
  let pile='';
  for(let i=0;i<shown;i++){
    const p=starAt(i);
    pile+='<g class="star'+(animateLast&&i===shown-1?' drop':'')+'">'
      +'<polygon fill="'+p.c+'"'+place(p,'')+'/></g>';
  }
  if(shown<JAR_CAP){   /* 虚星 = 下一颗要去的位置；罐子空时给 3 个，别让人觉得罐子是坏的 */
    const end=(shown===0)?Math.min(2,JAR_CAP-1):shown;
    for(let k=shown;k<=end;k++){
      const g=starAt(k); g.r=5.4;          /* 虚星尺寸固定，别随机成一小撮虚线看不清 */
      pile+='<polygon fill="none" stroke="#c9b48a" stroke-width="1.3"'
        +' stroke-linejoin="round" stroke-dasharray="2.4 2.4" opacity=".6"'
        +place(g,'')+'/>';
    }
  }
  let sparks='';
  for(let i=0;i<6;i++){
    sparks+='<polygon class="spark" style="animation-delay:'+(jarRnd(i,14)*2.8).toFixed(2)+'s"'
      +' points="'+sparkPts(22+jarRnd(i,11)*62,36+jarRnd(i,12)*74,2.0+jarRnd(i,13)*2.4)
      +'" fill="#ffe9a8"/>';
  }
  return '<svg viewBox="0 0 106 142" role="img" aria-label="星星罐">'
    +'<defs><radialGradient id="jarGlow">'
    +'<stop offset="0" stop-color="#ffd96b" stop-opacity=".5"/>'
    +'<stop offset=".55" stop-color="#ffd96b" stop-opacity=".16"/>'
    +'<stop offset="1" stop-color="#ffd96b" stop-opacity="0"/>'
    +'</radialGradient><linearGradient id="jarGlass" x1="0" y1="0" x2="0" y2="1">'
    +'<stop offset="0" stop-color="#fffdf9"/><stop offset="1" stop-color="#f0e0c9"/>'
    +'</linearGradient></defs>'
    +'<circle class="shine" cx="53" cy="84" r="60" fill="url(#jarGlow)"/>'
    +'<g class="bottle">'
    +'<rect x="34" y="4" width="38" height="14" rx="5" fill="#8b6a52"/>'
    +'<rect x="35.5" y="5.6" width="35" height="3" rx="1.5" fill="#a68468" opacity=".55"/>'
    +'<path d="M40 18 L66 18 L70 25 L36 25 Z" fill="url(#jarGlass)" stroke="#fff" stroke-width="1.6"/>'
    +'<rect x="9" y="24" width="88" height="110" rx="25" fill="url(#jarGlass)" stroke="#fff" stroke-width="2"/>'
    +pile
    +'<path d="M14 46 Q10.5 78 14 112" stroke="#fff" stroke-width="3.2" stroke-linecap="round" fill="none" opacity=".8"/>'
    +sparks
    +'</g></svg>';
}
const PRAISE=['+1 颗星，收进罐子啦 ⭐','你是最棒的妈妈！','今天也开口啦，厉害 🌟',
  '宝宝会记得你今天说的每一句 💛','罐子又满了一点点 ✨','坚持的样子最好看 🌟',
  '这一句，宝宝今天一定听懂了 🍼'];
function showBubble(){
  const b=document.getElementById('bubble'); if(!b) return;
  b.textContent=PRAISE[Math.floor(Math.random()*PRAISE.length)];
  setTimeout(()=>b.classList.add('show'),320);
  setTimeout(()=>b.classList.remove('show'),4800);
}
function updateMine(){
  const s=myStats();
  const jar=document.getElementById('jar');
  const cap=document.getElementById('jcap');
  const bar=document.getElementById('jbar');
  const el={scene:document.getElementById('sScene'),sent:document.getElementById('sSent'),
            day:document.getElementById('sDay'),today:document.getElementById('sToday')};
  if(!jar) return;

  /* 只在「今天第一次打卡」或「新收集一颗星」时庆祝一次 */
  let seen={};
  try{ Object.assign(seen,JSON.parse(localStorage.getItem('xhs.jar')||'{}')); }catch(e){}
  const t=todayStr();
  const firstToday=!!s.today && seen.d!==t;
  const newStar=s.scenes>(seen.s||0);

  jar.innerHTML=jarSVG(s.scenes,newStar);
  el.scene.innerHTML=s.scenes+' <small>个</small>';
  el.sent.innerHTML=s.sents+' <small>句</small>';
  el.day.innerHTML=s.days+' <small>天</small>';
  el.today.classList.toggle('ok',!!s.today);
  el.today.textContent=s.today?'✅ 今日已打卡':'今日还没打卡';
  if(cap) cap.textContent=s.scenes?('已收集 '+s.scenes+' 颗 ⭐'):'还没有星星 🌟';
  if(bar) bar.style.width=Math.min(100,s.scenes/JAR_CAP*100)+'%';
  jar.classList.toggle('full',s.scenes>=JAR_CAP);

  if(newStar){ jar.classList.remove('pop'); void jar.offsetWidth; jar.classList.add('pop'); }
  if(firstToday||newStar) showBubble();
  if(s.today) seen.d=t;
  seen.s=s.scenes;
  try{ localStorage.setItem('xhs.jar',JSON.stringify(seen)); }catch(e){}
}
/* 进度三态：已完成 / 进行中 / 未完成 —— 与目录卡片进度条同一口径 */
function progressState(slug){
  const p=readProgress(slug);
  if(!p) return 'todo';
  if(p.complete) return 'done';
  const started=(p.listen||0)>0||(p.scene||0)>0;
  return started?'doing':'todo';
}
function matches(s){
  if(state.cat!=='全部'&&s.cat!==state.cat) return false;
  if(state.age!=='全部'&&s.age!==state.age) return false;
  if(state.diff!=='全部'&&s.diff!==+state.diff) return false;
  if(state.prog!=='全部'&&progressState(s.slug)!==state.prog) return false;
  if(state.q){
    const hay=(s.zh+' '+s.en+' '+s.cat+' '+s.age+' '+(s.by||'')).toLowerCase();
    if(!hay.includes(state.q)) return false;
  }
  return true;
}
function render(){
  grid.innerHTML='';
  const list=SERIES.filter(matches);
  list.forEach(item=>{
    const p=readProgress(item.slug);
    const pct=(p&&p.listenTotal)?Math.round((p.listen||0)/p.listenTotal*100):0;
    const sDone=(p&&p.scene)||0;
    const started=pct>0||sDone>0;
    const ok=!!(p&&p.complete);
    const a=document.createElement('a');
    a.className='sc'+(item.url?'':' soon');
    a.href=item.url||'javascript:void 0';
    a.innerHTML=
      '<div class="cov"><img loading="lazy" src="'+item.cover+'" alt="'+item.zh+'">'+
      '<span class="no">'+item.n+'</span>'+
      (ok?'<span class="ok">✓ 已完成</span>'
          :(started?'<span class="ok doing">⏳ 进行中</span>':''))+'</div>'+
      '<div class="body">'+
      '<h3>'+item.zh+'</h3>'+
      '<div class="en">'+item.en+'</div>'+
      '<div class="by" title="来源：YouTube '+item.by+'">'+item.by+'</div>'+
      '<div class="meta"><span>'+item.cat+'</span><span>'+item.age+'</span><span>'+STAR(item.diff)+'</span></div>'+
      '<div class="bar'+(ok?' full':'')+'"><i style="width:'+pct+'%"></i></div>'+
      '<div class="pr"><span>'+(started?('精听 '+pct+'% · 已掌握 '+sDone+' 句'):'还没开始')+'</span>'+
      (item.url?'<span class="go">进入 →</span>':'<span class="go">即将上线</span>')+'</div>'+
      '</div>';
    grid.appendChild(a);
  });
  document.getElementById('empty').style.display=list.length?'none':'block';
  const filtered=(state.q!=='')||state.cat!=='全部'||state.age!=='全部'
    ||state.diff!=='全部'||state.prog!=='全部';
  const live=SERIES.filter(s=>s.url).length;
  document.getElementById('cnt').textContent=filtered
    ? ('符合条件 '+list.length+' / '+SERIES.length+' 篇')
    : ('共 '+SERIES.length+' 篇 · 已上线 '+live+' 篇 · 持续更新');
}
render();
updateMine();
/* 从课程页返回时（bfcache / 切标签页回来）刷新一下统计和星星罐 */
window.addEventListener('pageshow',e=>{ if(e.persisted){ render(); updateMine(); } });
document.addEventListener('visibilitychange',()=>{ if(!document.hidden){ render(); updateMine(); } });
</script>
</body>
</html>
"""


def jstr(s):
    """JS 字符串字面量转义"""
    return (s.replace("\\", "\\\\").replace("'", "\\'")
             .replace("\n", "\\n").replace("\r", ""))


def main():
    items = []
    for L in MAN["lessons"]:
        slug = L["slug"]
        done = os.path.isfile(os.path.join(OUT_DIR, slug, "index.html"))
        cover_png = L.get("image") or ""
        # 封面统一走 covers/NN.jpg（由 make_covers.py 生成）
        cover = "covers/%s.jpg" % L["n"]
        if cover_png and not os.path.isfile(os.path.join(ROOT, "outputs", "亲子英语", cover)):
            cover = "covers/%s.jpg" % L["n"]  # 即使缺文件也让前端渲染占位
        items.append({
            "n": L["n"],
            "slug": slug,
            "zh": L["zh"],
            "en": L["en"],
            "by": L.get("by", ""),
            "cover": cover,
            "cat": L.get("cat", "日常生活"),
            "age": L.get("age", "1–2 岁"),
            "diff": L.get("diff", 2),
            "url": "%s/index.html" % slug if done else "",
        })
    js = "[\n" + ",\n".join(
        "  { n:'%s', slug:'%s', zh:'%s', en:'%s', by:'%s', cover:'%s', cat:'%s', age:'%s', diff:%d, url:'%s' }"
        % (i["n"], i["slug"], jstr(i["zh"]), jstr(i["en"]), jstr(i["by"]), i["cover"],
           jstr(i["cat"]), jstr(i["age"]), i["diff"], i["url"])
        for i in items) + "\n]"
    html = TPL.replace("%SERIES%", js)
    io.open(OUT, "w", encoding="utf-8").write(html)
    live = sum(1 for i in items if i["url"])
    print("written", OUT, len(html), "chars; 上线 %d / %d" % (live, len(items)))


if __name__ == "__main__":
    main()

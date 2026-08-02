#!/usr/bin/env python3
"""Generate pd-scheduler-detail.drawio - PD Separation Scheduler with DP selection and KV notification."""
OUT = []
def emit(s): OUT.append(s)

def esc(text):
    text = text.replace('\n', '___NL___')
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    text = text.replace('___NL___', '&#xa;')
    return text

def box(id_, x, y, w, h, label="", style="", fs=11, fst=0, fc="", align="center", fill="", sw=""):
    s = f'rounded=1;html=1;whiteSpace=wrap;{style}'
    if fill: s += f';fillColor={fill}'
    if sw: s += f';strokeWidth={sw}'
    if fs != 11: s += f';fontSize={fs}'
    if fst: s += f';fontStyle={fst}'
    if fc: s += f';fontColor={fc}'
    s += f';align={align}'
    emit(f'<mxCell id="{id_}" value="{esc(label)}" style="{s}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

def diamond(id_, x, y, w, h, label="", style="", fs=11, fc="", fill=""):
    s = f'rhombus;html=1;whiteSpace=wrap;{style}'
    if fill: s += f';fillColor={fill}'
    if fs != 11: s += f';fontSize={fs}'
    if fc: s += f';fontColor={fc}'
    s += ';align=center'
    emit(f'<mxCell id="{id_}" value="{esc(label)}" style="{s}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

def text(id_, x, y, w, h, label, fs=10, fst=0, fc="", align="center"):
    s = f'text;html=1;fontSize={fs}'
    if fst: s += f';fontStyle={fst}'
    if fc: s += f';fontColor={fc}'
    s += f';align={align}'
    emit(f'<mxCell id="{id_}" value="{esc(label)}" style="{s}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

def container(id_, x, y, w, h, fill, stroke, dashed=False, sw="2"):
    d = ';dashed=1' if dashed else ''
    emit(f'<mxCell id="{id_}" value="" style="rounded=1;html=1;whiteSpace=wrap;fillColor={fill};strokeColor={stroke};strokeWidth={sw}{d};" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

def edge(id_, src, tgt, sc, sw="1.5", pts=None, dashed=False, ex=None, ey=None, enx=None, eny=None):
    d = ';dashed=1' if dashed else ''
    exits = f';exitX={ex};exitY={ey}' if ex is not None else ''
    entrys = f';entryX={enx};entryY={eny}' if enx is not None else ''
    style = f'edgeStyle=orthogonalEdgeStyle;endArrow=classic;html=1;strokeColor={sc};strokeWidth={sw}{d}{exits}{entrys}'
    pts_str = ''
    if pts:
        pts_str = '<Array as="points">' + ''.join(f'<mxPoint x="{p[0]}" y="{p[1]}"/>' for p in pts) + '</Array>'
    emit(f'<mxCell id="{id_}" style="{style}" edge="1" parent="1" source="{src}" target="{tgt}"><mxGeometry relative="1" as="geometry">{pts_str}</mxGeometry></mxCell>')

# ============================================================
emit('<mxfile host="app.diagrams.net" modified="2026-08-02" agent="draw.io">')
emit('  <diagram name="PD-Scheduler" id="pds">')
emit('    <mxGraphModel dx="1800" dy="1600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1860" pageHeight="1900">')
emit('      <root>')
emit('        <mxCell id="0"/>')
emit('        <mxCell id="1" parent="0"/>')

# === PAGE TITLE ===
text("t0", 500, 5, 860, 32, "PD Separation - Scheduler + DP Selection + KV Notification Flow", fs=22, fst=1, fc="#1A237E")

# ============================================================
# SECTION 0: DP SELECTION (top of diagram)
# ============================================================
container("dpBox", 20, 45, 1820, 125, "#F3E5F5", "#7B1FA2", sw="1.5")
text("dpT", 750, 48, 400, 20, "Request Entry & DP Load Balancing (score = waiting x 4 + running)", fs=14, fst=1, fc="#7B1FA2")

# API Server
box("api", 60, 75, 150, 40, "API Server\n(Front-end)", fill="#E1BEE7", fc="#7B1FA2", fs=10)
# DPCoordinator
box("dpC", 260, 75, 200, 40, "DPCoordinator\nStats: [waiting, running] per DP", fill="#E1BEE7", fc="#7B1FA2", fs=10)
# LB Selection
box("lb", 510, 75, 250, 40, "DP LB: min(score) per request\nscore = waiting x 4 + running", fill="#E1BEE7", fc="#7B1FA2", fs=10)
# Arrow API→DPC
edge("a1", "api", "dpC", "#7B1FA2", ex=1, ey=0.5, enx=0, eny=0.5)
# Arrow DPC→LB (stats publish)
edge("a2", "dpC", "lb", "#7B1FA2", ex=1, ey=0.5, enx=0, eny=0.5)

# P DP selection
box("pDp", 830, 72, 180, 48, "P-side DP chosen\n→ route to kv_producer", fill="#BBDEFB", fc="#1565C0", fs=10)
# D DP selection (for decode)
box("dDp", 1050, 72, 180, 48, "D-side DP chosen\n→ route to kv_consumer", fill="#FFE0B2", fc="#E65100", fs=10)
# Arrow LB→P DP
edge("a3", "lb", "pDp", "#7B1FA2", ex=1, ey=0.5, enx=0, eny=0.5)
# Arrow LB→D DP
edge("a4", "lb", "dDp", "#7B1FA2", ex=1, ey=0.5, enx=0, eny=0.5,
     pts=[[790,95],[1020,95]])

# Policy note
text("lbNote", 1280, 78, 300, 36, "External LB mode: no stats, front-end\nroutes by its own policy (e.g. round-robin)", fs=9, fc="#7B1FA2", align="left")
# Chinese DP annotation
text("cnDp", 1290, 118, 540, 16, "中文说明: 前端API Server根据DPCoordinator发布的各DP实例[waiting, running]统计，计算 score=waitingx4+running，选最小score的DP路由请求", fs=8, fc="#6A1B9A", align="left")

# ============================================================
# MAIN CONTAINERS
# ============================================================
container("Pbx", 20, 185, 910, 1380, "#E3F2FD", "#1565C0")
container("Dbx", 950, 185, 890, 1380, "#FFF3E0", "#E65100")

# Side titles
text("Ptt", 170, 193, 260, 26, "Prefill Node (kv_producer)", fs=17, fst=1, fc="#1565C0")
text("Dtt", 1080, 193, 280, 26, "Decode Node (kv_consumer)", fs=17, fst=1, fc="#E65100")
# Chinese subtitles for P/D roles
text("cnPtt", 60, 222, 400, 16, "P节点职责: 接收请求→Prefill分块计算→KV Cache Transfer到D节点→释放KV块  |  token_budget=8192, 大块prefill", fs=8, fc="#1565C0", align="left")
text("cnDtt", 970, 222, 500, 16, "D节点职责: 接收P传来的KV→Decode逐token生成(每步1token)→返回结果  |  token_budget=512, 很少耗尽", fs=8, fc="#E65100", align="left")

# ============================================================
# P-SIDE: SCHEDULER ENTRY
# ============================================================
box("p0", 220, 235, 360, 44, "schedule()  token_budget=8192", fill="#BBDEFB", fc="#1976D2")
diamond("p1", 320, 310, 155, 52, "PAUSED_ALL?", fill="#FFF9C4", fc="#F9A825")
box("p1y", 520, 315, 95, 42, "Return Empty", fill="#FFCDD2", fc="#C62828", fs=10)
text("p1L1", 485, 320, 22, 14, "Yes", fs=10, fst=1, fc="#C62828")

# P-side Phase 1
container("pp1bx", 40, 395, 420, 390, "#E8EAF6", "#3949AB", dashed=True)
text("pp1t", 55, 400, 220, 20, "Phase 1: RUNNING (prefill requests)", fs=13, fst=1, fc="#3949AB")
# Chinese Phase 1 note
text("cnPh1", 55, 418, 380, 14, "阶段1中文: 遍历正在运行的prefill请求，跳过不需要新块的，计算num_new，分配KV块，成功→进入scheduled；失败→抢占", fs=7.5, fc="#283593", align="left")

box("p2", 140, 432, 185, 34, "Iterate self.running", fill="#C5CAE9", fc="#3949AB")
diamond("p3", 140, 492, 185, 66, "Skip?\nmax_tokens? eligible?", fill="#FFF9C4", fc="#F9A825", fs=9)
box("p3y", 370, 508, 68, 32, "Skip", fill="#E0E0E0", fc="#9E9E9E", fs=10)
text("p3L1", 335, 518, 18, 14, "Yes", fs=9, fc="#9E9E9E")
box("p4", 70, 588, 290, 54, "num_new = tokens_with_spec - computed,\nclip threshold/budget/maxlen", fill="#C5CAE9", fc="#3949AB", fs=10)
text("p4L1", 275, 565, 18, 14, "No", fs=9, fst=1, fc="#2E7D32")
box("p5", 145, 670, 142, 36, "allocate_slots()", fill="#A5D6A7", fc="#388E3C", fs=10)
diamond("p6", 150, 735, 120, 46, "Success?", fill="#FFF9C4", fc="#F9A825", fs=10)

# Phase 2
container("pp2bx", 40, 805, 375, 565, "#E8F5E9", "#2E7D32", dashed=True)
text("pp2t", 55, 810, 220, 20, "Phase 2: WAITING requests", fs=13, fst=1, fc="#2E7D32")
# Chinese Phase 2 note
text("cnPh2", 55, 828, 360, 14, "阶段2中文: 从等待队列取请求→检查本地PrefixCache+远端KV→计算num_new→分配KV块→成功则加入running；失败则break", fs=7.5, fc="#1B5E20", align="left")

box("p7", 55, 845, 210, 42, "Add to scheduled_running,\nbudget -= tokens", fill="#A5D6A7", fc="#388E3C", fs=9)
text("p7L1", 225, 785, 15, 14, "Yes", fs=9, fst=1, fc="#2E7D32")
box("p8", 55, 920, 230, 54, "waiting non-empty &\nbudget>0 & running<max_seqs", fill="#C8E6C9", fc="#388E3C", fs=10)
box("p9", 55, 1005, 170, 36, "peek request", fill="#C8E6C9", fc="#388E3C", fs=10)
box("p10", 55, 1075, 245, 84, "Check:\n1.Local PrefixCache\n2.Remote KV(PD)\nnum_computed=local+remote", fill="#C8E6C9", fc="#388E3C", fs=10)
box("p11", 55, 1190, 225, 36, "num_new = tokens - computed, clip", fill="#C8E6C9", fc="#388E3C", fs=10)
box("p12", 85, 1258, 140, 36, "allocate_slots()", fill="#A5D6A7", fc="#388E3C", fs=10)
box("p13y", 55, 1325, 155, 36, "OK: add to running", fill="#A5D6A7", fc="#388E3C", fs=10)
box("p13n", 275, 1260, 95, 32, "Fail: break", fill="#FFCDD2", fc="#C62828", fs=10)
text("p13L1", 150, 1305, 14, 14, "Y", fs=9, fst=1, fc="#2E7D32")
text("p13L2", 242, 1240, 14, 14, "N", fs=9, fst=1, fc="#C62828")

# Preemption on P (theoretical, rare)
container("prebx_p", 485, 700, 420, 390, "#FFEBEE", "#C62828", dashed=True)
text("pret_p", 580, 706, 250, 20, "Preemption (theoretical on P, KV full)", fs=12, fst=1, fc="#C62828")
text("cnPret_p", 505, 728, 380, 14, "P侧抢占(极少): KV仅在prefill分块期间暂存，完成后立即transfer释放", fs=7.5, fc="#C62828", align="left")
diamond("pr0_p", 600, 738, 155, 52, "FCFS or Priority?", fill="#FFCDD2", fc="#C62828", fs=11)
box("pr1_p", 505, 815, 145, 46, "FCFS: running.pop()", fill="#FFCDD2", fc="#C62828", fs=10)
box("pr2_p", 760, 812, 145, 50, "Priority:\nmax(running, ...)", fill="#FFCDD2", fc="#C62828", fs=10)
box("pr3_p", 505, 890, 400, 65, "Result: free blocks, num_computed=0,\nPREEMPTED, prepend waiting", fill="#FFCDD2", fc="#C62828", fs=10)
diamond("pr4_p", 630, 980, 140, 45, "Is current?", fill="#FFCDD2", fc="#C62828", fs=10)
box("pr5_p", 505, 1050, 140, 35, "break", fill="#FFCDD2", fc="#C62828", fs=10)
box("pr6_p", 760, 1050, 140, 35, "retry allocate", fill="#C8E6C9", fc="#388E3C", fs=10)
text("pr5L1_p", 512, 1010, 14, 14, "Y", fs=9, fc="#C62828")
text("pr6L1_p", 845, 1010, 14, 14, "N", fs=9, fc="#2E7D32")

# P summary note
box("psum", 485, 1355, 415, 55, "P-Scheduler: Prefill chunked at threshold.\nKV transferred to D after prefill complete.\nPreemption rare: KV released after each transfer.", fill="#E3F2FD", fc="#1565C0", fs=10, align="left")

# ============================================================
# P-SIDE EDGES
# ============================================================
edge("p0e1", "p0", "p1", "#1565C0", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p1e2", "p1", "p1y", "#C62828", ex=1, ey=0.5, enx=0, eny=0.5)
edge("p2e1", "p1", "p2", "#3949AB", ex=0.5, ey=1, enx=0.5, eny=0)
text("p2L1", 445, 388, 18, 14, "No", fs=9, fst=1, fc="#2E7D32")
edge("p3e1", "p2", "p3", "#3949AB", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p3e2", "p3", "p3y", "#9E9E9E", ex=1, ey=0.5, enx=0, eny=0.5)
edge("p4e1", "p3", "p4", "#3949AB", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p5e1", "p4", "p5", "#388E3C", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p6e1", "p5", "p6", "#388E3C", ex=0.5, ey=1, enx=0.5, eny=0)
# p6 Yes → p7
edge("p7e1", "p6", "p7", "#388E3C", ex=0.5, ey=1, enx=1, eny=0.5,
     pts=[[270,780],[270,866]])
# p6 No → pr0 (preemption)
edge("pr0e1_p", "p6", "pr0_p", "#C62828", "2", ex=1, ey=0.5, enx=0.5, eny=0,
     pts=[[310,758],[310,720],[678,720]])
text("pr0L1_p", 365, 725, 18, 14, "No", fs=9, fst=1, fc="#C62828")
# Preemption edges
edge("pr1e1_p", "pr0_p", "pr1_p", "#C62828", ex=0, ey=0.5, enx=0.5, eny=0,
     pts=[[560,764],[560,800],[578,800]])
edge("pr2e1_p", "pr0_p", "pr2_p", "#C62828", ex=1, ey=0.5, enx=0.5, eny=0,
     pts=[[780,764],[780,797],[833,797]])
text("pr1L1_p", 518, 780, 35, 14, "FCFS", fs=9)
text("pr2L1_p", 810, 780, 20, 14, "Pri", fs=9)
edge("pr3e1_p", "pr1_p", "pr3_p", "#C62828", "1.2", ex=0.5, ey=1, enx=0.25, eny=0)
edge("pr3e2_p", "pr2_p", "pr3_p", "#C62828", "1.2", ex=0.5, ey=1, enx=0.75, eny=0)
edge("pr4e1_p", "pr3_p", "pr4_p", "#C62828", "1.2", ex=0.5, ey=1, enx=0.5, eny=0)
edge("pr5e1_p", "pr4_p", "pr5_p", "#C62828", "1.2", ex=0, ey=0.5, enx=0.5, eny=0,
     pts=[[590,1002],[590,1030],[575,1030]])
edge("pr6e1_p", "pr4_p", "pr6_p", "#388E3C", "1.2", ex=1, ey=0.5, enx=0.5, eny=0,
     pts=[[810,1002],[810,1030],[830,1030]])
# Retry edge (P, rare) - go outside right, avoid crossing pret_p title
edge("prx_p", "pr6_p", "p5", "#388E3C", "1.2", dashed=True, ex=0.5, ey=1, enx=1, eny=0.5,
     pts=[[830,1105],[915,1105],[915,688],[307,688]])
text("prxL1_p", 865,1113, 28,14, "retry", fs=9, fst=1, fc="#388E3C")

# Phase 2 edges
edge("p8e1", "p7", "p8", "#2E7D32", ex=0, ey=0.5, enx=0.5, eny=0,
     pts=[[30,866],[30,910],[170,910]])
edge("p9e1", "p8", "p9", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p10e1", "p9", "p10", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p11e1", "p10", "p11", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p12e1", "p11", "p12", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p13e1", "p12", "p13y", "#388E3C", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p13e2", "p12", "p13n", "#C62828", ex=1, ey=0.5, enx=0, eny=0.5)

# ============================================================
# D-SIDE: SCHEDULER ENTRY
# ============================================================
box("d0", 1150, 235, 360, 44, "schedule()  token_budget=512 (rarely exhausted)", fill="#FFE0B2", fc="#F57F17")

# D-side Phase 1
container("dp1bx", 970, 310, 850, 125, "#FFF8E1", "#F57F17", dashed=True)
text("dp1t", 985, 315, 320, 20, "Phase 1: RUNNING (all Decode, 1 token/req)", fs=13, fst=1, fc="#E65100")
text("cnDph1", 985, 333, 800, 14, "D-阶段1中文: 所有RUNNING请求都是Decode，每请求只需1个新token的KV块，token_budget=512几乎不会耗尽，直接分配即可", fs=7.5, fc="#E65100", align="left")
box("d1", 1120, 345, 350, 55, "Iterate: num_new=1, allocate(1,lookahead),\nbudget -= 1", fill="#FFE0B2", fc="#F57F17", fs=10)

# D-side Phase 2
container("dp2bx", 970, 460, 860, 925, "#E8F5E9", "#2E7D32", dashed=True)
text("dp2t", 985, 465, 400, 20, "Phase 2: WAITING (PD-specific async KV load + local)", fs=13, fst=1, fc="#2E7D32")
text("cnDph2", 985, 482, 830, 16, "D-阶段2中文: 先检查WAITING_FOR_REMOTE_KVS(等finished_recving→promote); 再检查do_remote_prefill(有→PD async路径→WAITING_FOR_REMOTE_KVS不消耗budget; 无→本地PrefixCache路径)", fs=7.5, fc="#1B5E20", align="left")

box("d2", 1190, 498, 250, 40, "peek from waiting/\nskipped_waiting", fill="#C8E6C9", fc="#388E3C", fs=10)
diamond("d3", 1200, 568, 210, 78, "Status is\nWAITING_FOR_REMOTE_KVS?", fill="#FFF9C4", fc="#F9A825", fs=9)
diamond("d4", 1460, 568, 155, 62, "finished_recving?", fill="#FFF9C4", fc="#F9A825", fs=9)
text("d4L1", 1420, 590, 65, 14, "Yes(KV wait)", fs=9, fst=1, fc="#E65100")
box("d5", 1660, 558, 130, 65, "Promote:\ncache_blocks()\n-> WAITING", fill="#A5D6A7", fc="#388E3C", fs=10)
box("d6", 1730, 660, 100, 42, "Blocked:\nskip", fill="#FFF9C4", fc="#F9A825", fs=10)
text("d5L1", 1620, 590, 14, 14, "Y", fs=9, fst=1, fc="#2E7D32")
text("d6L1", 1550, 640, 14, 14, "N", fs=9, fst=1, fc="#F57F17")
diamond("d7", 1200, 678, 210, 80, "kv_transfer_params\nhas do_remote_prefill?", fill="#FFF9C4", fc="#F9A825", fs=9)
text("d7L1", 1285, 665, 110, 14, "No(normal WAITING)", fs=9, fst=1, fc="#2E7D32")
box("d8", 1460, 678, 270, 78, "PD async:\nget_num_new_matched_tokens()\n-> async=True, allocate(ext_tokens,\ndelay_cache=True)", fill="#FFCC80", fc="#E65100", fs=10)
text("d8L1", 1420, 710, 18, 14, "Yes", fs=9, fst=1, fc="#E65100")
box("d9", 1460, 792, 270, 62, "Enter wait:\nWAITING_FOR_REMOTE_KVS\nnum_computed=ext_tokens,\nNOT consume token_budget!", fill="#FFCC80", fc="#E65100", fs=10)
box("d10", 990, 805, 235, 62, "Normal(local):\nPrefixCache, allocate\nnum_new=tokens-computed\n->running", fill="#C8E6C9", fc="#388E3C", fs=10)
text("d10L1", 985, 715, 18, 14, "No", fs=9, fst=1, fc="#2E7D32")
box("dend", 1240, 1180, 270, 52, "Build SchedulerOutput +\nkv_connector_metadata", fill="#FFE0B2", fc="#F57F17")

# D summary
box("dsum", 990, 1270, 560, 85, "D-Scheduler: WAITING_FOR_REMOTE_KVS: no forward pass, no budget consumed.\nPromote on finished_recving signal from Worker. Heartbeat 5s / lease 30s to P.\nKV load failure: recompute (reset num_computed) or fail_immediately.\nBudget rarely exhausted (1 token/req).", fill="#FFF3E0", fc="#E65100", fs=10, align="left")

# ============================================================
# D-SIDE EDGES
# ============================================================
edge("d0e1", "d0", "d1", "#F57F17", ex=0.5, ey=1, enx=0.5, eny=0)
edge("d2e1", "d1", "d2", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("d4e1", "d3", "d4", "#F9A825", ex=1, ey=0.5, enx=0, eny=0.5)
edge("d7e1", "d3", "d7", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("d5e1", "d4", "d5", "#388E3C", ex=1, ey=0.5, enx=0, eny=0.5)
edge("d6e1", "d4", "d6", "#F9A825", ex=0.5, ey=1, enx=0.5, eny=0,
     pts=[[1537,650],[1780,650]])
edge("d8e1", "d7", "d8", "#E65100", ex=1, ey=0.5, enx=0, eny=0.5)
edge("d10e1", "d7", "d10", "#2E7D32", ex=0, ey=0.5, enx=0.5, eny=0,
     pts=[[1160,718],[1160,790],[1107,790]])
edge("d9e1", "d8", "d9", "#E65100", ex=0.5, ey=1, enx=0.5, eny=0)
edge("dende1", "d10", "dend", "#F57F17", "2", ex=0.5, ey=1, enx=0.25, eny=0,
     pts=[[1107,900],[1310,900]])
edge("dende2", "d9", "dend", "#F57F17", ex=0.5, ey=1, enx=0.75, eny=0,
     pts=[[1595,900],[1442,900]])
text("dendeL", 1460, 905, 85, 14, "after async load", fs=9, fst=1, fc="#F57F17")

# ============================================================
# SECTION: KV TRANSFER & NOTIFICATION (middle, cross P-D)
# ============================================================
container("kvBox", 430, 1115, 520, 230, "#E0F2F1", "#00695C", sw="1.5")
text("kvT", 550, 1120, 300, 20, "KV Transfer & D-side Notification Flow", fs=13, fst=1, fc="#00695C")
text("cnKv", 445, 1138, 490, 14, "KV传输中文: P完成prefill→request_finished()→KV通过RDMA/NIXL传输到D→D Worker收到后发finished_recving信号→D Scheduler下一轮调度时promote到WAITING→RUNNING开始decode", fs=7.5, fc="#004D40", align="left")

# P-side: prefill complete → transfer
box("kv1", 445, 1150, 220, 48, "P: Prefill complete\n_connector_finished()\n-> request_finished()", fill="#B2DFDB", fc="#00695C", fs=10)
# Transfer channels
box("kv2", 685, 1148, 110, 25, "KV Transfer\n(RDMA/NIXL)", fill="#80CBC4", fc="#004D40", fs=9)
box("kv3", 805, 1148, 130, 25, "Metadata Sync\n(ZMQ/API Server)", fill="#80CBC4", fc="#004D40", fs=9)
# D-side: receive → notify scheduler
box("kv4", 685, 1190, 250, 52, "D Worker: start_load_kv()\n-> wait_for_layer_load()\n-> finished_recving signal", fill="#B2DFDB", fc="#00695C", fs=10)
# Scheduler notification
box("kv5", 685, 1260, 250, 48, "D Scheduler:\n_update_from_kv_xfer_finished()\n-> finished_recving_kv_req_ids.add()", fill="#B2DFDB", fc="#00695C", fs=10)
# Promotion
box("kv6", 685, 1325, 250, 12, "", fill="none", fc="none", fs=1)
text("kv6t", 685, 1315, 250, 20, "Next schedule(): promote to WAITING → RUNNING", fs=10, fst=1, fc="#00695C")

# Edges
edge("kve1", "kv1", "kv2", "#00695C", ex=1, ey=0.5, enx=0, eny=0.5)
edge("kve2", "kv1", "kv3", "#00695C", ex=1, ey=0.25, enx=0, eny=0.5,
     pts=[[680,1162],[800,1162],[800,1160]])
edge("kve3", "kv2", "kv4", "#00695C", ex=0.5, ey=1, enx=0.25, eny=0)
edge("kve4", "kv3", "kv4", "#00695C", ex=0.5, ey=1, enx=0.75, eny=0)
edge("kve5", "kv4", "kv5", "#00695C", ex=0.5, ey=1, enx=0.5, eny=0)

# Heartbeat (D→P)
box("hb", 445, 1325, 200, 20, "Heartbeat: D→P, 5s interval, 30s lease", fill="#FFECB3", fc="#E65100", fs=9)
edge("hbe", "hb", "kv1", "#E65100", "1", dashed=True, ex=0, ey=0.5, enx=0.5, eny=1,
     pts=[[430,1335],[430,1200]])

# Arrow from P-side finish to KV box
edge("p2kv", "p13y", "kv1", "#00695C", "1.5", ex=1, ey=0.5, enx=0, eny=0.5,
     pts=[[250,1343],[400,1343],[400,1174],[435,1174]])

# ============================================================
# D-SIDE PREEMPTION (main preemption scenario)
# ============================================================
container("prebx", 970, 1370, 850, 180, "#FFEBEE", "#C62828", dashed=True)
text("pret", 1270, 1375, 300, 20, "Preemption (D-side: KV full, main scenario)", fs=12, fst=1, fc="#C62828")
text("cnPret", 990, 1390, 830, 14, "D侧抢占(主要): 每个decode请求持有全部历史KV，每步+1token持续增长直到EOS；KV满时allocate_slots()失败→选受害者(FCFS pop最后/ Priority max优先级最低)→释放块,num_computed=0→放回waiting头部", fs=7.5, fc="#C62828", align="left")
text("preNote", 990, 1405, 830, 140, "D-side Preemption Flow (same as P):\nallocate_slots() fails for RUNNING decode request -> select victim (FCFS pop last / Priority max)\n-> _preempt_request(): free blocks, num_computed=0, PREEMPTED, prepend waiting\n-> retry allocate; if victim == self -> break (cannot schedule)\nD-side preemption is common: each decode req holds all historical KV, growing 1t/step until EOS.\nP-side preemption is rare: KV held only during prefill chunk, released after transfer to D.",
          fs=9, fc="#C62828", align="left")

# ============================================================
# STATE MACHINE
# ============================================================
container("smbx", 400, 1570, 600, 195, "#FAFAFA", "#BDBDBD")
text("smt", 580, 1575, 220, 22, "Request State Machine (请求状态机)", fs=14, fst=1)

# Box positions: 2-row layout with clean spacing
# Row 1: WAITING(420) ---> RUNNING(650) ---> FINISHED(870)
# Row 2: WAITING_FOR_REMOTE_KVS(420)  PREEMPTED(650)
box("smw", 420, 1608, 120, 42, "WAITING\n(等待调度)", fill="#FFF9C4", fc="#F9A825", fs=11, fst=1)
box("smr", 650, 1608, 120, 42, "RUNNING\n(正在执行)", fill="#C8E6C9", fc="#388E3C", fs=11, fst=1)
box("smf", 870, 1608, 100, 42, "FINISHED\n(已完成)", fill="#E0E0E0", fc="#9E9E9E", fs=11, fst=1)
box("smkv", 420, 1680, 170, 42, "WAITING_FOR\n_REMOTE_KVS\n(等待远端KV)", fill="#BBDEFB", fc="#1976D2", fs=8, fst=1)
box("smp", 650, 1680, 120, 42, "PREEMPTED\n(被抢占)", fill="#FFCDD2", fc="#C62828", fs=10, fst=1)

# Edges: top row horizontal, down to bottom row, bottom row cross
# smw → smr (调度, horizontal)
edge("sme1", "smw", "smr", "#388E3C", ex=1, ey=0.5, enx=0, eny=0.5)
# smr → smf (完成, horizontal)
edge("sme6", "smr", "smf", "#9E9E9E", ex=1, ey=0.5, enx=0, eny=0.5)

# smr → smp (KV满, vertical down)
edge("sme2", "smr", "smp", "#C62828", ex=0.5, ey=1, enx=0.5, eny=0)

# smw → smkv (远端prefill, vertical down)
edge("sme4", "smw", "smkv", "#1976D2", ex=0.5, ey=1, enx=0.5, eny=0)

# smp → smw (回到队首): left→down→left→up, outside smkv
edge("sme3", "smp", "smw", "#F9A825", ex=0, ey=0.5, enx=0.5, eny=1,
     pts=[[610,1701],[610,1745],[385,1745],[385,1650],[480,1650]])

# smkv → smw (KV就绪): right→up→right, enter smw from right
edge("sme5", "smkv", "smw", "#1976D2", ex=1, ey=0.5, enx=1, eny=0.5,
     pts=[[610,1701],[610,1629]])

# Labels
text("sme1L", 575,1613, 42,14, "调度", fs=9)
text("sme6L", 775,1613, 30,14, "完成", fs=9)
text("sme2L", 720,1648, 38,14, "KV满", fs=9)
text("sme4L", 505,1658, 65,14, "远端prefill", fs=9)
text("sme3L", 402,1735, 65,14, "回到队首", fs=9)
text("sme5L", 618,1665, 42,14, "KV就绪", fs=9)

# Arrow from DP box to P/D entry - route below dpBox first
edge("dp2p", "pDp", "p0", "#1565C0", "1.5", ex=0.5, ey=1, enx=0.5, eny=0,
     pts=[[920,180],[450,180],[400,225]])
edge("dp2d", "dDp", "d0", "#E65100", "1.5", ex=0.5, ey=1, enx=0.5, eny=0,
     pts=[[1140,180],[1330,180],[1330,225]])

# === XML footer ===
emit('      </root>')
emit('    </mxGraphModel>')
emit('  </diagram>')
emit('</mxfile>')

with open('/home/qiutm/claude_workspace/vllm-learning-path/03-调度与KV缓存/diagrams/pd-scheduler-detail.drawio', 'w') as f:
    f.write('\n'.join(OUT))

print(f"Generated {len([l for l in OUT if '<mxCell' in l])} mxCell elements")
print("Done!")

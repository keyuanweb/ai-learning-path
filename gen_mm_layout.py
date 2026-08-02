#!/usr/bin/env python3
"""Generate PD multimodal scheduling diagram."""
OUT = []
def emit(s): OUT.append(s)

def esc(text):
    text = text.replace('\n', '___NL___')
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    text = text.replace('___NL___', '&#xa;')
    return text

def box(id_, x, y, w, h, label, style="", fs=11, fst=0, fc="", align="center", fill="", sw=""):
    s = f'rounded=1;html=1;whiteSpace=wrap;{style}'
    if fill: s += f';fillColor={fill}'
    if sw: s += f';strokeWidth={sw}'
    if fs != 11: s += f';fontSize={fs}'
    if fst: s += f';fontStyle={fst}'
    if fc: s += f';fontColor={fc}'
    s += f';align={align}'
    emit(f'<mxCell id="{id_}" value="{esc(label)}" style="{s}" vertex="1" parent="1"><mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')

def diamond(id_, x, y, w, h, label, style="", fs=11, fc="", fill=""):
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
    if pts: pts_str = '<Array as="points">' + ''.join(f'<mxPoint x="{p[0]}" y="{p[1]}"/>' for p in pts) + '</Array>'
    emit(f'<mxCell id="{id_}" style="{style}" edge="1" parent="1" source="{src}" target="{tgt}"><mxGeometry relative="1" as="geometry">{pts_str}</mxGeometry></mxCell>')

# ============================================================
emit('<mxfile host="app.diagrams.net" modified="2026-08-02" agent="draw.io">')
emit('  <diagram name="MM-PD-Scheduling" id="mmpd">')
emit('    <mxGraphModel dx="1800" dy="1400" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1860" pageHeight="1720">')
emit('      <root>')
emit('        <mxCell id="0"/>')
emit('        <mxCell id="1" parent="0"/>')

# === TITLE ===
text("t0", 350, 5, 1160, 30, "PD Separation - Multimodal (Vision/Language) Encoder Scheduling + EC Connector Flow", fs=20, fst=1, fc="#1A237E")

# ============================================================
# SECTION 0: MM Request Entry (top)
# ============================================================
container("reqBox", 20, 42, 1820, 140, "#F3E5F5", "#7B1FA2", sw="1.5")
text("reqT", 700, 45, 460, 20, "Multimodal Request Entry: mm_features[{image, video, audio}] per Request", fs=14, fst=1, fc="#7B1FA2")

box("mmReq", 60, 75, 280, 50, "Request arrives with mm_features[]\nEach: identifier(hash), position(offset,length),\nnum_embeds, data (image tensor/audio/etc)", fill="#E1BEE7", fc="#7B1FA2", fs=10, align="left")
box("encBudget", 720, 75, 280, 50, "Encoder Compute Budget:\nmax_num_encoder_input_tokens\n(per scheduling step)", fill="#E1BEE7", fc="#7B1FA2", fs=10)
box("encCache", 1050, 75, 280, 50, "Encoder Cache:\nencoder_cache_size (max tokens)\nCached mm_hash → embedding reference", fill="#E1BEE7", fc="#7B1FA2", fs=10)
box("ecRole", 1380, 75, 430, 50, "EC Connector (PD): is_ec_producer (P: runs encoder, sends)\nis_ec_consumer (D: receives encoder outputs, loads async)", fill="#E1BEE7", fc="#7B1FA2", fs=10, align="left")

# CN - fs=16, wrapped to 2 lines
text("cnReq", 60, 125, 1740, 52, "多模态请求携带mm_features(图片/视频/音频)，每个feature有唯一hash标识、\n在序列中的位置、embedding数量；调度时需检查编码器计算预算和缓存空间", fs=16, fc="#6A1B9A", align="left")

# ============================================================
# MAIN CONTAINERS: P-side and D-side
# ============================================================
container("Pbx", 20, 195, 910, 750, "#E3F2FD", "#1565C0")
container("Dbx", 950, 195, 890, 750, "#FFF3E0", "#E65100")

text("Ptt", 50, 198, 280, 20, "P Node (ec_producer + kv_producer)", fs=13, fst=1, fc="#1565C0")
text("Dtt", 980, 198, 280, 20, "D Node (ec_consumer + kv_consumer)", fs=13, fst=1, fc="#E65100")

# ============================================================
# P-SIDE: Encoder Execution + EC Transfer
# ============================================================
container("pEncBox", 35, 228, 425, 340, "#E8EAF6", "#3949AB", dashed=True)
text("pEncT", 50, 233, 350, 18, "P: Encoder Execution (vision/audio model)", fs=13, fst=1, fc="#3949AB")

# P encoder flow
box("p1", 55, 263, 180, 38, "schedule():\nCheck encoder_inputs", fill="#C5CAE9", fc="#3949AB", fs=10)
box("p2", 55, 328, 180, 38, "_try_schedule_encoder_inputs()\nFind MM items in token window", fill="#C5CAE9", fc="#3949AB", fs=10)
diamond("p3", 90, 393, 150, 52, "Budget OK?\nCache space?", fill="#FFF9C4", fc="#F9A825", fs=10)
box("p4", 55, 476, 180, 44, "Run Encoder Forward\n(produce embeddings)\n→ save to local cache", fill="#A5D6A7", fc="#388E3C", fs=10)

text("cnPenc", 50, 538, 400, 50, "P节点负责运行视觉/音频编码器\n→产生embedding→存入EncoderCache\n→通过EC Connector传输给D", fs=16, fc="#283593", align="left")

# EC Connector on P side
container("ecPBox", 485, 228, 420, 340, "#E0F2F1", "#00695C", dashed=True)
text("ecPT", 500, 233, 350, 18, "EC Connector (P=Producer): Encoder Output Transfer", fs=13, fst=1, fc="#00695C")

box("ecP1", 505, 263, 185, 38, "Encoder complete:\nregister encoder outputs", fill="#B2DFDB", fc="#00695C", fs=10)
box("ecP2", 505, 328, 185, 38, "request_finished():\nmark for async send to D", fill="#B2DFDB", fc="#00695C", fs=10)
box("ecP3", 505, 393, 185, 38, "Worker: save_ec_layer()\n→ transfer via shared mem", fill="#80CBC4", fc="#004D40", fs=10)
box("ecP4", 505, 476, 185, 44, "get_finished():\nreport finished_sending\n→ free encoder cache", fill="#80CBC4", fc="#004D40", fs=10)

text("cnEcP", 500, 538, 400, 50, "P侧编码器完成后→EC Connector\n异步传输encoder outputs到D\n→类似KV Transfer但传输的是encoder embeddings", fs=16, fc="#004D40", align="left")

# P edges
edge("p1e", "p1", "p2", "#3949AB", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p2e", "p2", "p3", "#3949AB", ex=0.5, ey=1, enx=0.5, eny=0)
edge("p3y", "p3", "p4", "#388E3C", ex=0.5, ey=1, enx=0.5, eny=0)
text("p3yL", 150, 453, 14, 14, "Y", fs=9, fc="#2E7D32")
# P encoder → EC connector
edge("p2ec", "p4", "ecP1", "#00695C", ex=1, ey=0.5, enx=0, eny=0.5, pts=[[280,498],[490,498],[490,282]])
edge("ecP1e", "ecP1", "ecP2", "#00695C", ex=0.5, ey=1, enx=0.5, eny=0)
edge("ecP2e", "ecP2", "ecP3", "#00695C", ex=0.5, ey=1, enx=0.5, eny=0)
edge("ecP3e", "ecP3", "ecP4", "#00695C", ex=0.5, ey=1, enx=0.5, eny=0)

# ============================================================
# P-SIDE: Scheduler Phase 1&2 with MM (lower part)
# ============================================================
container("pSchedBox", 35, 610, 870, 340, "#E8F5E9", "#2E7D32", dashed=True)
text("pSchedT", 50, 615, 400, 18, "P Scheduler: MM-aware scheduling (Phase 1 RUNNING + Phase 2 WAITING)", fs=13, fst=1, fc="#2E7D32")

# Scheduler MM flow
box("ps1", 55, 645, 200, 38, "For each request in running/waiting:\nhas_encoder_inputs?", fill="#C8E6C9", fc="#388E3C", fs=10)
diamond("ps2", 105, 708, 160, 52, "has MM inputs\nin token window?", fill="#FFF9C4", fc="#F9A825", fs=10)
box("ps3", 55, 788, 200, 46, "_try_schedule_encoder_inputs():\n1.Check local cache (mm_hash)\n2.Check remote EC cache\n3.Check encoder_budget\n4.EncoderCacheManager.allocate()", fill="#C8E6C9", fc="#388E3C", fs=10)

# Budget/cache full handling
box("ps4", 310, 645, 230, 52, "If budget/cache insufficient:\n→ clip num_new_tokens to before MM item\n→ OR set num_new_tokens=0 (blocked by prefix)", fill="#FFCDD2", fc="#C62828", fs=10)
box("ps5", 310, 728, 230, 52, "disable_chunked_mm_input:\n→ don't split MM item across steps\n→ roll back to before MM item", fill="#FFCDD2", fc="#C62828", fs=10)
box("ps6", 310, 810, 230, 46, "After scheduling:\n→ encoder_compute_budget -= embeds\n→ EncoderCacheManager.allocate()\n→ ECConnector.update_state_after_alloc()", fill="#C8E6C9", fc="#388E3C", fs=10)

# P Scheduler edges
edge("ps1e", "ps1", "ps2", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("ps2y", "ps2", "ps3", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
text("ps2yL", 160, 768, 14, 14, "Y", fs=9, fc="#2E7D32")

# CN - fs=16
text("cnPs", 55, 865, 830, 75, "多模态请求调度时需额外检查:\n①token窗口内是否有mm_features ②encoder cache是否已缓存(命中则跳过)\n③EC Connector远端缓存(有则异步加载) ④encoder compute budget是否充足\n不足则裁剪num_new_tokens到MM item之前", fs=16, fc="#1B5E20", align="left")

# ============================================================
# D-SIDE: EC Consumer + Scheduler
# ============================================================
container("dSchedBox", 965, 228, 860, 640, "#E8F5E9", "#2E7D32", dashed=True)
text("dSchedT", 980, 233, 500, 18, "D Scheduler: MM-aware with remote EC cache check (Phase 1 + Phase 2)", fs=13, fst=1, fc="#2E7D32")

# D scheduler entry
box("ds0", 985, 268, 250, 38, "schedule():\nencoder_compute_budget = max_encoder_tokens", fill="#FFE0B2", fc="#F57F17", fs=10)
box("ds1", 985, 333, 250, 44, "Phase 1 (RUNNING Decode):\nEach req needs 1 decode token;\nIf has pending MM inputs → check", fill="#FFE0B2", fc="#F57F17", fs=10)
box("ds2", 985, 406, 280, 54, "Phase 2 (WAITING): peek request\n→ _try_schedule_encoder_inputs()\n→ for each MM item in window:", fill="#C8E6C9", fc="#388E3C", fs=10)

# Decision tree for each MM item
diamond("ds3", 1020, 486, 200, 56, "In local\nEncoderCache?\n(mm_hash hit)", fill="#FFF9C4", fc="#F9A825", fs=10)
box("ds3y", 1280, 490, 140, 40, "Skip encoding\n(already done)", fill="#E0E0E0", fc="#9E9E9E", fs=10)
diamond("ds4", 1020, 570, 200, 56, "In remote\nEC cache?\n(ECConnector\n.has_cache_item)", fill="#FFF9C4", fc="#F9A825", fs=10)
box("ds4y", 1280, 576, 180, 44, "Load async from P:\nno budget consumed\n→ external_load_encoder_input", fill="#FFCC80", fc="#E65100", fs=10)
diamond("ds5", 1020, 656, 200, 56, "Budget OK?\nCache space\navailable?", fill="#FFF9C4", fc="#F9A825", fs=10)
box("ds5y", 1280, 660, 180, 44, "Schedule encoding:\nallocate cache slot\nbudget -= num_embeds", fill="#A5D6A7", fc="#388E3C", fs=10)
box("ds5n", 1020, 740, 200, 44, "Budget/cache full:\nclip num_new_tokens to\nbefore this MM item\n(or set to 0 if blocked)", fill="#FFCDD2", fc="#C62828", fs=10)

# D executor
box("ds6", 985, 808, 280, 44, "After scheduling:\n→ encoder forward pass (local MM)\n→ ECConnector.start_load_ec() (remote)\n→ merge embeddings with text tokens", fill="#FFE0B2", fc="#F57F17", fs=10)

# D edges
edge("ds0e", "ds0", "ds1", "#F57F17", ex=0.5, ey=1, enx=0.5, eny=0)
edge("ds1e", "ds1", "ds2", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("ds2e", "ds2", "ds3", "#2E7D32", ex=0.5, ey=1, enx=0.5, eny=0)
edge("ds3yL", "ds3", "ds3y", "#9E9E9E", ex=1, ey=0.5, enx=0, eny=0.5)
text("ds3L", 1185, 503, 14, 14, "Y", fs=9, fc="#9E9E9E")
edge("ds3n", "ds3", "ds4", "#F9A825", ex=0.5, ey=1, enx=0.5, eny=0)
text("ds3nL", 1110, 553, 14, 14, "N", fs=9, fc="#F57F17")
edge("ds4yL", "ds4", "ds4y", "#E65100", ex=1, ey=0.5, enx=0, eny=0.5)
text("ds4L", 1185, 588, 14, 14, "Y", fs=9, fc="#E65100")
edge("ds4n", "ds4", "ds5", "#F9A825", ex=0.5, ey=1, enx=0.5, eny=0)
text("ds4nL", 1110, 640, 14, 14, "N", fs=9, fc="#F57F17")
edge("ds5yL", "ds5", "ds5y", "#388E3C", ex=1, ey=0.5, enx=0, eny=0.5)
text("ds5L", 1185, 676, 14, 14, "Y", fs=9, fc="#2E7D32")
edge("ds5nL", "ds5", "ds5n", "#C62828", ex=0.5, ey=1, enx=0.5, eny=0)
text("ds5nT", 1120, 726, 14, 14, "N", fs=9, fc="#C62828")

# CN D-side - fs=16
text("cnDs", 985, 860, 820, 75, "多模态在D侧调度时额外检查:\n①本地EncoderCache是否命中(已处理过)\n②EC Connector远端是否有缓存(P已编码好的)\n③encoder budget是否充足；任一不满足→裁剪num_new_tokens暂缓调度", fs=16, fc="#1B5E20", align="left")

# ============================================================
# CROSS: EC Transfer Channel (between P and D)
# ============================================================
container("ecXfer", 460, 960, 940, 130, "#E0F2F1", "#00695C", sw="1.5")
text("ecXferT", 750, 965, 360, 18, "EC Transfer: P(Producer) → D(Consumer) Encoder Output Transfer", fs=13, fst=1, fc="#00695C")

box("ecX1", 480, 995, 200, 50, "P Worker: save_ec_layer()\n→ shared memory / RDMA\n→ transfer encoder embeddings", fill="#B2DFDB", fc="#00695C", fs=10)
box("ecX2", 730, 995, 200, 50, "D Worker: start_load_ec()\n→ wait_for_layer_load()\n→ merge into decoder input", fill="#B2DFDB", fc="#00695C", fs=10)
box("ecX3", 980, 995, 200, 50, "EC Connector Metadata sync\nvia API Server (like KV)\nremote_ec_cache lookup", fill="#80CBC4", fc="#004D40", fs=10)
box("ecX4", 1230, 995, 150, 50, "get_finished():\nfinished_recving\nfinished_sending", fill="#80CBC4", fc="#004D40", fs=10)

edge("ecXe1", "ecX1", "ecX2", "#00695C", ex=1, ey=0.5, enx=0, eny=0.5)
edge("ecXe2", "ecX1", "ecX3", "#00695C", ex=1, ey=0.25, enx=0, eny=0.5, pts=[[695,1007],[735,1007],[735,1020]])
edge("ecXe3", "ecX2", "ecX4", "#00695C", ex=1, ey=0.5, enx=0, eny=0.5)

text("cnEcX", 480, 1050, 900, 50, "类似KV Transfer但传输的是encoder embeddings而非KV cache\nP侧运行编码器产生embedding→通过EC Connector传给D\nD侧调度时检查远端缓存(ECConnector.has_cache_item)，有则异步加载", fs=16, fc="#004D40", align="left")

# ============================================================
# BOTTOM: Encoder Cache & Budget Lifecycle
# ============================================================
container("lifeBox", 20, 1110, 1820, 220, "#FFF3E0", "#E65100", sw="1.5")
text("lifeT", 700, 1115, 460, 20, "Encoder Cache & Budget Lifecycle + MM-aware Token Budget Interaction", fs=14, fst=1, fc="#E65100")

# Encoder Cache Manager
box("lf1", 40, 1150, 260, 75, "EncoderCacheManager:\n- check_and_update_cache(mhash)→bool\n- can_allocate(budget, embeds)→bool\n- allocate(req, input_id)\n- free(req) / free_encoder_input(req,id)\n- cache_size from config", fill="#FFE0B2", fc="#E65100", fs=10, align="left")

# Budget flow
box("lf2", 340, 1150, 260, 75, "Encoder Compute Budget per step:\n= max_num_encoder_input_tokens\nDecremented as MM inputs scheduled.\nWhen 0 → no more MM items this step.\ncompute_mm_encoder_budget() sets initial.", fill="#FFE0B2", fc="#E65100", fs=10, align="left")

# Token budget interaction
box("lf3", 640, 1150, 280, 75, "Token Budget vs Encoder Budget:\nToken budget = max_num_batched_tokens\ncontrols total tokens/step (text+MM)\nEncoder budget controls how many\nencoder tokens can be processed.\nBoth independently constrain scheduling.", fill="#FFE0B2", fc="#E65100", fs=10, align="left")

# PD interaction summary
box("lf4", 960, 1150, 270, 75, "PD EC Interaction:\nP: produces encoder outputs, sends via EC\nD: checks local cache → remote EC cache\n→ loads async from P (like KV async)\nEC cache hit on D = no budget consumed\n(same as KV prefix cache hit)", fill="#FFE0B2", fc="#E65100", fs=10, align="left")

# Modes
box("lf5", 1270, 1150, 280, 75, "Encoder Modes:\n- disable_chunked_mm_input: don't split\n  MM item across steps (roll back)\n- Encoder-Decoder: all inputs at pos=0\n- Decoder-only(VLM): MM items inline\n- EC Connector: remote cache for PD", fill="#FFE0B2", fc="#E65100", fs=10, align="left")

# Edge from D scheduler to lifecycle - route around ecXfer to the RIGHT
edge("d2life", "ds6", "lf4", "#E65100", ex=0.5, ey=1, enx=0.5, eny=0,
     pts=[[1125,864],[1415,864],[1415,1110]])

# ============================================================
# STATE MACHINE: MM Request States
# ============================================================
container("smbx", 340, 1320, 1180, 130, "#FAFAFA", "#BDBDBD")
text("smt", 780, 1325, 300, 20, "Multimodal Request Encoder State Transitions", fs=14, fst=1)

box("sm1", 360, 1363, 160, 38, "MM Item Pending\n(not yet encoded)", fill="#FFF9C4", fc="#F9A825", fs=10)
box("sm2", 600, 1363, 180, 38, "MM Item Scheduled\n(encoder forward queued)", fill="#BBDEFB", fc="#1976D2", fs=10)
box("sm3", 860, 1363, 180, 38, "MM Item Cached\n(embedding in cache)", fill="#C8E6C9", fc="#388E3C", fs=10)
box("sm4", 1120, 1363, 180, 38, "MM Item Loaded Async\n(from remote EC cache)", fill="#FFCC80", fc="#E65100", fs=10)

edge("sm1e", "sm1", "sm2", "#1976D2", ex=1, ey=0.5, enx=0, eny=0.5)
edge("sm2e", "sm2", "sm3", "#388E3C", ex=1, ey=0.5, enx=0, eny=0.5)
edge("sm1r", "sm1", "sm4", "#E65100", ex=0.5, ey=1, enx=0, eny=0.5, pts=[[440,1405],[440,1425],[1120,1425],[1120,1382]])
edge("sm4r", "sm4", "sm3", "#388E3C", ex=0, ey=0.5, enx=0.5, eny=1, pts=[[1090,1382],[1090,1405],[950,1405],[950,1401]])

text("sm1L", 525,1368, 14,14, "调度", fs=9)
text("sm2L", 780,1368, 14,14, "完成", fs=9)
text("sm1rL", 485,1415, 50,14, "远端缓存", fs=9)
text("sm4rL", 1030,1410, 50,14, "加载完成", fs=9)

# ============================================================
# ============================================================
emit('      </root>')
emit('    </mxGraphModel>')
emit('  </diagram>')
emit('</mxfile>')

with open('/home/qiutm/claude_workspace/vllm-learning-path/03-调度与KV缓存/diagrams/pd-mm-scheduling.drawio', 'w') as f:
    f.write('\n'.join(OUT))

print(f"Generated {len([l for l in OUT if '<mxCell' in l])} mxCell elements")
print("Done!")

#!/usr/bin/env python3
"""Generate K8s production deployment architecture Draw.io diagram."""
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

OUTPUT = "k8s-learning-path/diagrams/k8s-production-deployment-architecture.drawio"

def add_vertex(root, cid, parent, value, style_str, x, y, w, h):
    cell = ET.SubElement(root, "mxCell", id=cid, parent=parent, value=value,
                         vertex="1", style=style_str)
    ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w),
                  height=str(h), **{"as": "geometry"})
    return cell

def add_edge(root, cid, parent, source, target, value, style_str):
    cell = ET.SubElement(root, "mxCell", id=cid, parent=parent, source=source,
                         target=target, value=value, edge="1", style=style_str)
    ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})
    return cell

# --- Build model ---
M = ET.Element("mxGraphModel", dx="1550", dy="1050", grid="1", gridSize="10",
               guides="1", tooltips="1", connect="1", arrows="1", fold="1",
               page="1", pageScale="1", pageWidth="1600", pageHeight="1120")
root = ET.SubElement(M, "root")
ET.SubElement(root, "mxCell", id="0")
ET.SubElement(root, "mxCell", id="1", parent="0")

nid = [2]
def nxt(): v = str(nid[0]); nid[0] += 1; return v

# Style shorthands
S_CONTAINER = "container=1;collapsible=0;whiteSpace=wrap;html=1"
S_RECT      = "rounded=0;whiteSpace=wrap;html=1"
S_ROUNDED   = "rounded=1;whiteSpace=wrap;html=1"
S_CLOUD     = "ellipse=;shape=cloud;whiteSpace=wrap;html=1"
S_ACTOR     = "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0"
S_CYLINDER  = "shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=15"
S_EDGE      = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=classic;strokeWidth=1.5"
S_EDGE_DASH = S_EDGE + ";dashed=1;dashPattern=5 5"
S_EDGE_DOT  = S_EDGE + ";dashed=1;dashPattern=3 3"

CP_BG, CP_FG = "#e1d5e7", "#9673a6"
WK_BG, WK_FG = "#d5e8d4", "#82b366"
CL_BG, CL_FG = "#f5f5f5", "#666666"
GW_BG, GW_FG = "#f8cecc", "#b85450"
SV_BG, SV_FG = "#dae8fc", "#6c8ebf"
DB_BG, DB_FG = "#fff2cc", "#d6b656"
CA_BG, CA_FG = "#ffe6cc", "#d79b00"

def s(base, **kw):
    return base + ";" + ";".join(f"{k}={v}" for k, v in kw.items())

# ===== EXTERNAL USERS =====
b_id   = nxt()  # 2
a_id   = nxt()  # 3
dns_id = nxt()  # 4
add_vertex(root, b_id,   "1", "浏览器",   s(S_ACTOR, fillColor="#d5e8d4", strokeColor="#82b366", strokeWidth="2"), 300, 15, 30, 55)
add_vertex(root, a_id,   "1", "移动 APP",  s(S_ACTOR, fillColor="#d5e8d4", strokeColor="#82b366", strokeWidth="2"), 530, 15, 30, 55)
add_vertex(root, dns_id, "1", "DNS\napi.example.com → VIP", s(S_CLOUD, fillColor="#e1d5e7", strokeColor="#9673a6", strokeWidth="2", fontSize="12"), 670, 8, 190, 70)

# ===== K8s CLUSTER =====
k8s_id = nxt()  # 5
add_vertex(root, k8s_id, "1", "Kubernetes 集群 (生产环境)",
           s(S_CONTAINER, fillColor=CL_BG, strokeColor=CL_FG, strokeWidth="2", fontSize="16", fontStyle="1"),
           25, 100, 1500, 910)

# ---- Control Plane ----
cp_id = nxt()  # 6
add_vertex(root, cp_id, k8s_id, "控制面节点 (Control Plane) — 3 节点高可用",
           s(S_CONTAINER, fillColor=CP_BG, strokeColor=CP_FG, strokeWidth="1.5", fontSize="13", fontStyle="1"),
           20, 30, 1460, 115)

api_id = nxt(); etcd_id = nxt(); sched_id = nxt(); ctrl_id = nxt()  # 7-10
add_vertex(root, api_id,   cp_id, "API Server\n集群统一入口",       s(S_RECT, fillColor="#ffffff", strokeColor=CP_FG, strokeWidth="1.5", fontSize="11"), 20, 38, 325, 58)
add_vertex(root, etcd_id,  cp_id, "etcd\nRaft 共识存储",           s(S_RECT, fillColor="#ffffff", strokeColor=CP_FG, strokeWidth="1.5", fontSize="11"), 370, 38, 325, 58)
add_vertex(root, sched_id, cp_id, "Scheduler\nPod 调度",           s(S_RECT, fillColor="#ffffff", strokeColor=CP_FG, strokeWidth="1.5", fontSize="11"), 720, 38, 325, 58)
add_vertex(root, ctrl_id,  cp_id, "Controller Manager\n状态 reconcile", s(S_RECT, fillColor="#ffffff", strokeColor=CP_FG, strokeWidth="1.5", fontSize="11"), 1070, 38, 325, 58)

# ---- Worker Nodes ----
wk_id = nxt()  # 11
add_vertex(root, wk_id, k8s_id, "工作节点 (Worker Nodes) — ≥3 节点，运行业务负载",
           s(S_CONTAINER, fillColor=WK_BG, strokeColor=WK_FG, strokeWidth="1.5", fontSize="13", fontStyle="1"),
           20, 165, 1460, 720)

# Row 1 — Ingress (full width)
ingress_id = nxt()  # 12
add_vertex(root, ingress_id, wk_id, "Nginx Ingress Controller  |  TLS 终止  |  域名路由  |  限流",
           s(S_RECT, fillColor=GW_BG, strokeColor=GW_FG, strokeWidth="2", fontSize="12", fontStyle="1"),
           20, 25, 1420, 55)

# === LEFT SIDEBAR: ConfigMap + Secret ===
cm_id = nxt(); secret_id = nxt()  # 13, 14
add_vertex(root, cm_id, wk_id, "ConfigMap\n应用配置",
           s(S_ROUNDED, fillColor="#f5f5f5", strokeColor="#999999", strokeWidth="1.5", fontSize="11"),
           20, 118, 180, 52)
add_vertex(root, secret_id, wk_id, "Secret\n密钥 · 证书",
           s(S_ROUNDED, fillColor="#f8cecc", strokeColor="#b85450", strokeWidth="1.5", fontSize="11"),
           20, 190, 180, 52)

# Row 2 — Frontend
fe_svc_id = nxt(); fe_deploy_id = nxt()  # 15, 16
add_vertex(root, fe_svc_id, wk_id, "Frontend Service\n(ClusterIP :80)",
           s(S_ROUNDED, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="1.5", fontSize="11"),
           440, 118, 180, 52)
add_vertex(root, fe_deploy_id, wk_id, "Frontend Deployment\nReact SPA · 副本:3",
           s(S_RECT, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="1.5", fontSize="11"),
           660, 118, 200, 52)

# Row 3 — API Gateway
gw_svc_id = nxt(); gw_deploy_id = nxt()  # 17, 18
add_vertex(root, gw_svc_id, wk_id, "API Gateway Service\n(ClusterIP :80)",
           s(S_ROUNDED, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="1.5", fontSize="11"),
           440, 213, 180, 52)
add_vertex(root, gw_deploy_id, wk_id, "API Gateway Deployment\n认证 · 限流 · 路由 · 副本:3",
           s(S_RECT, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="1.5", fontSize="11"),
           660, 213, 225, 52)

# Row 4 — HPA + PDB (centered above microservices)
hpa_id = nxt(); pdb_id = nxt()  # 19, 20
add_vertex(root, hpa_id, wk_id, "HPA 弹性伸缩\nCPU 70% → 3~20 副本",
           s(S_ROUNDED, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="1.5", fontSize="11"),
           620, 313, 210, 52)
add_vertex(root, pdb_id, wk_id, "PodDisruptionBudget\n最少可用 2 副本",
           s(S_ROUNDED, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="1.5", fontSize="11"),
           860, 313, 220, 52)

# Row 5 — Three Microservices
user_id = nxt(); order_id = nxt(); prod_id = nxt()  # 21, 22, 23
add_vertex(root, user_id,  wk_id, "用户服务\nDeployment + Service · 副本:3",
           s(S_RECT, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="2", fontSize="12", fontStyle="1"),
           220, 408, 370, 75)
add_vertex(root, order_id, wk_id, "订单服务\nDeployment + Service · 副本:3",
           s(S_RECT, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="2", fontSize="12", fontStyle="1"),
           625, 408, 370, 75)
add_vertex(root, prod_id,  wk_id, "商品服务\nDeployment + Service · 副本:3",
           s(S_RECT, fillColor=SV_BG, strokeColor=SV_FG, strokeWidth="2", fontSize="12", fontStyle="1"),
           1030, 408, 370, 75)

# Row 6 — Data Stores
redis_id = nxt(); pg_id = nxt()  # 24, 25
add_vertex(root, redis_id, wk_id, "Redis\nStatefulSet · 哨兵模式",
           s(S_CYLINDER, fillColor=CA_BG, strokeColor=CA_FG, strokeWidth="2", fontSize="12", fontStyle="1"),
           370, 545, 215, 75)
add_vertex(root, pg_id, wk_id, "PostgreSQL\nStatefulSet · 主从复制",
           s(S_CYLINDER, fillColor=DB_BG, strokeColor=DB_FG, strokeWidth="2", fontSize="12", fontStyle="1"),
           810, 545, 215, 75)

# ===== EDGES =====
# Traffic flow (solid) — top-down
add_edge(root, nxt(), "1", b_id,   dns_id,      "HTTPS",           S_EDGE)
add_edge(root, nxt(), "1", a_id,   dns_id,      "HTTPS",           S_EDGE)
add_edge(root, nxt(), "1", dns_id, ingress_id,  "DNS → VIP",       S_EDGE)
add_edge(root, nxt(), "1", ingress_id, fe_svc_id,   "路由 /",      S_EDGE)
add_edge(root, nxt(), "1", fe_svc_id,  fe_deploy_id, "",           S_EDGE)
add_edge(root, nxt(), "1", fe_deploy_id, gw_svc_id, "/api/*",     S_EDGE)
add_edge(root, nxt(), "1", gw_svc_id,   gw_deploy_id, "",          S_EDGE)
add_edge(root, nxt(), "1", gw_deploy_id, user_id,  "/api/user/*",  S_EDGE)
add_edge(root, nxt(), "1", gw_deploy_id, order_id, "/api/order/*", S_EDGE)
add_edge(root, nxt(), "1", gw_deploy_id, prod_id,  "/api/product/*", S_EDGE)

# Data access (solid) — down
add_edge(root, nxt(), "1", user_id,  pg_id,    "读写", S_EDGE)
add_edge(root, nxt(), "1", user_id,  redis_id, "缓存", S_EDGE)
add_edge(root, nxt(), "1", order_id, pg_id,    "读写", S_EDGE)
add_edge(root, nxt(), "1", prod_id,  redis_id, "缓存", S_EDGE)

# Config/Secret injection (dashed) — left sidebar → rightward
add_edge(root, nxt(), "1", cm_id,     fe_deploy_id, "注入", S_EDGE_DASH)
add_edge(root, nxt(), "1", cm_id,     gw_deploy_id, "注入", S_EDGE_DASH)
add_edge(root, nxt(), "1", secret_id, gw_deploy_id, "注入", S_EDGE_DASH)
add_edge(root, nxt(), "1", secret_id, user_id,      "注入", S_EDGE_DASH)

# HPA auto-scaling (dotted) — downward to microservices
add_edge(root, nxt(), "1", hpa_id, user_id,  "自动扩缩", S_EDGE_DOT)
add_edge(root, nxt(), "1", hpa_id, order_id, "自动扩缩", S_EDGE_DOT)
add_edge(root, nxt(), "1", hpa_id, prod_id,  "自动扩缩", S_EDGE_DOT)

# Control Plane → Worker
add_edge(root, nxt(), "1", api_id, ingress_id, "管理 / 调度", S_EDGE_DASH)

# ===== BUILD XML =====
mxfile = ET.Element("mxfile", host="app.diagrams.net", modified="2026-08-09",
                    agent="draw.io")
diagram = ET.SubElement(mxfile, "diagram", id="k8s-arch", name="K8s 生产部署架构")
diagram.append(M)

raw = minidom.parseString(ET.tostring(mxfile, encoding="unicode")).toprettyxml(indent="  ")

os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "w", encoding="utf-8") as f:
    wrote = False
    for line in raw.split("\n"):
        if not wrote:
            if line.strip().startswith("<mxfile"):
                wrote = True
                f.write(line + "\n")
        elif line.strip():
            f.write(line + "\n")

print(f"Generated: {OUTPUT}")
print(f"Total elements: {nid[0] - 1}")

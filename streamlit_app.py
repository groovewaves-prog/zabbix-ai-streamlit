"""
Zabbix AI Assistant - Streamlit版
share.streamlit.io 対応
"""

import streamlit as st
import json
import os
import re
import hashlib
from datetime import datetime, timedelta
import random
import requests

# ==================== ページ設定 ====================
st.set_page_config(
    page_title="Zabbix AI Assistant",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== カスタムCSS ====================
st.markdown("""
<style>
    /* ヘッダー・フッター非表示 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* クイックアクションボタン */
    [data-testid="stSidebar"] .stButton > button {
        background-color: #1f77b4;
        color: white;
        font-weight: bold;
        border: none;
        border-radius: 5px;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background-color: #1565c0;
    }
    
    /* ステータスカード */
    .status-card {
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 5px;
    }
    .status-ok { background-color: #d4edda; border-left: 4px solid #28a745; }
    .status-warn { background-color: #fff3cd; border-left: 4px solid #ffc107; }
    .status-error { background-color: #f8d7da; border-left: 4px solid #dc3545; }
</style>
""", unsafe_allow_html=True)

# ==================== データ管理 ====================

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

@st.cache_data
def load_topology():
    """トポロジーデータを読み込む"""
    topology_path = os.path.join(DATA_DIR, "topology.json")
    if os.path.exists(topology_path):
        with open(topology_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

@st.cache_data
def load_mock_data():
    """モックデータを読み込む"""
    mock_path = os.path.join(DATA_DIR, "mock_data.json")
    if os.path.exists(mock_path):
        with open(mock_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"hosts": {}, "alerts": [], "metrics_history": {}, "maintenance": {}}

def get_hosts():
    """ホスト一覧を取得"""
    data = load_mock_data()
    return data.get("hosts", {})

def get_alerts():
    """アラート一覧を取得"""
    data = load_mock_data()
    return data.get("alerts", [])

def get_server_status_summary():
    """サーバーステータスのサマリーを取得"""
    hosts = get_hosts()
    alerts = get_alerts()
    
    alert_hosts = set(a["host"] for a in alerts if a["severity"] == "high")
    warning_hosts = set(a["host"] for a in alerts if a["severity"] == "warning")
    
    ok_count = 0
    warn_count = 0
    error_count = 0
    
    for host_id, host in hosts.items():
        if host_id in alert_hosts:
            error_count += 1
        elif host_id in warning_hosts:
            warn_count += 1
        else:
            ok_count += 1
    
    return {
        "ok": ok_count,
        "warning": warn_count,
        "error": error_count,
        "total": len(hosts)
    }

def get_hosts_by_condition(metric: str, operator: str, value: float) -> list:
    """条件に合うホストを取得"""
    hosts = get_hosts()
    results = []
    for host_id, host in hosts.items():
        if metric in host.get("metrics", {}):
            current_value = host["metrics"][metric]
            match = False
            if operator == ">" and current_value > value:
                match = True
            elif operator == ">=" and current_value >= value:
                match = True
            elif operator == "<" and current_value < value:
                match = True
            elif operator == "<=" and current_value <= value:
                match = True
            elif operator == "=" and current_value == value:
                match = True
            if match:
                results.append({"host_id": host_id, **host, "current_value": current_value})
    return sorted(results, key=lambda x: x["current_value"], reverse=True)

def get_hosts_by_status(status: str) -> list:
    """ステータス別にホストを取得"""
    hosts = get_hosts()
    alerts = get_alerts()
    
    alert_hosts = {a["host"]: a for a in alerts if a["severity"] == "high"}
    warning_hosts = {a["host"]: a for a in alerts if a["severity"] == "warning"}
    
    results = []
    for host_id, host in hosts.items():
        if status == "error" and host_id in alert_hosts:
            results.append({"host_id": host_id, **host, "alert": alert_hosts[host_id]})
        elif status == "warning" and host_id in warning_hosts and host_id not in alert_hosts:
            results.append({"host_id": host_id, **host, "alert": warning_hosts[host_id]})
        elif status == "ok" and host_id not in alert_hosts and host_id not in warning_hosts:
            results.append({"host_id": host_id, **host})
        elif status == "all":
            host_status = "error" if host_id in alert_hosts else "warning" if host_id in warning_hosts else "ok"
            results.append({"host_id": host_id, **host, "status": host_status})
    return results

def get_host_metrics(host_id: str) -> dict:
    """ホストのメトリクスを取得"""
    hosts = get_hosts()
    if host_id in hosts:
        return hosts[host_id].get("metrics", {})
    return {}

def generate_metrics_history(host_id: str, metric: str, hours: int = 24) -> list:
    """メトリクス履歴を生成（モック）"""
    hosts = get_hosts()
    base_value = hosts.get(host_id, {}).get("metrics", {}).get(metric, 50)
    history = []
    now = datetime.now()
    
    for i in range(hours * 6):
        timestamp = now - timedelta(minutes=10 * (hours * 6 - i))
        hour = timestamp.hour
        if 14 <= hour <= 16:
            spike = random.uniform(20, 40)
        else:
            spike = 0
        value = base_value + random.uniform(-10, 10) + spike
        value = max(0, min(100, value))
        history.append({
            "timestamp": timestamp,
            "value": round(value, 1)
        })
    return history

def generate_zabbix_config(topology: dict) -> dict:
    """トポロジーからZabbix設定を生成"""
    config = {
        "host_groups": [],
        "hosts": [],
        "templates": [],
        "triggers": [],
        "dependencies": []
    }
    
    layers = set()
    vendors = set()
    locations = set()
    ha_groups = set()
    
    for host_id, host_data in topology.items():
        layers.add(f"Layer{host_data['layer']}")
        if host_data.get("metadata", {}).get("vendor"):
            vendors.add(host_data["metadata"]["vendor"])
        if host_data.get("metadata", {}).get("location"):
            locations.add(host_data["metadata"]["location"])
        if host_data.get("redundancy_group"):
            ha_groups.add(host_data["redundancy_group"])
            
    config["host_groups"] = [
        *[{"name": f"Network/{layer}", "type": "layer"} for layer in sorted(layers)],
        *[{"name": f"Vendor/{vendor}", "type": "vendor"} for vendor in vendors],
        *[{"name": f"Location/{loc}", "type": "location"} for loc in locations],
        *[{"name": f"HA_Groups/{group}", "type": "ha"} for group in ha_groups]
    ]
    
    template_map = {
        ("Cisco", "ROUTER"): ["Template Cisco IOS-XE SNMP", "Template ICMP Ping"],
        ("Cisco", "SWITCH"): ["Template Cisco Catalyst SNMP", "Template ICMP Ping"],
        ("Juniper", "FIREWALL"): ["Template Juniper SRX SNMP", "Template ICMP Ping"],
        ("default", "ACCESS_POINT"): ["Template Generic SNMP AP", "Template ICMP Ping"],
    }
    
    for host_id, host_data in topology.items():
        vendor = host_data.get("metadata", {}).get("vendor", "default")
        device_type = host_data.get("type", "unknown")
        
        templates = template_map.get((vendor, device_type), 
                    template_map.get(("default", device_type), ["Template ICMP Ping"]))
        
        groups = [f"Network/Layer{host_data['layer']}"]
        if vendor != "default":
            groups.append(f"Vendor/{vendor}")
        if host_data.get("metadata", {}).get("location"):
            groups.append(f"Location/{host_data['metadata']['location']}")
        if host_data.get("redundancy_group"):
            groups.append(f"HA_Groups/{host_data['redundancy_group']}")
        
        host_config = {
            "host_id": host_id,
            "name": host_id,
            "groups": groups,
            "templates": templates,
            "tags": [
                {"tag": "layer", "value": str(host_data["layer"])},
                {"tag": "type", "value": device_type},
            ],
            "macros": {}
        }
        
        if vendor != "default":
            host_config["tags"].append({"tag": "vendor", "value": vendor})
        if host_data.get("metadata", {}).get("model"):
            host_config["tags"].append({"tag": "model", "value": host_data["metadata"]["model"]})
        if host_data.get("metadata", {}).get("hw_inventory", {}).get("psu_count"):
            host_config["macros"]["{$PSU_COUNT}"] = host_data["metadata"]["hw_inventory"]["psu_count"]
            
        config["hosts"].append(host_config)
        
        if host_data.get("parent_id"):
            config["dependencies"].append({
                "host": host_id,
                "depends_on": host_data["parent_id"],
                "type": "parent"
            })
    
    for host_id, host_data in topology.items():
        device_type = host_data.get("type", "unknown")
        
        config["triggers"].append({
            "host": host_id,
            "name": f"{host_id} is unreachable",
            "expression": f"nodata(/{host_id}/icmp.ping,5m)=1",
            "severity": "high" if host_data["layer"] <= 2 else "average"
        })
        
        if device_type in ["ROUTER", "SWITCH", "FIREWALL"]:
            config["triggers"].append({
                "host": host_id,
                "name": f"{host_id} CPU usage is high",
                "expression": f"last(/{host_id}/system.cpu.util)>80",
                "severity": "warning"
            })
            
        if host_data.get("redundancy_group"):
            config["triggers"].append({
                "host": host_id,
                "name": f"HA Failover detected - {host_id}",
                "expression": f"change(/{host_id}/ha.role,1h)<>0",
                "severity": "warning"
            })
    
    return config

# ==================== コマンドキャッシュ ====================

def get_cache_key(intent: str) -> str:
    return hashlib.md5(intent.lower().strip().encode()).hexdigest()

def get_command_cache():
    if "command_cache" not in st.session_state:
        st.session_state.command_cache = {}
    return st.session_state.command_cache

def set_command_cache(intent: str, command: dict):
    cache = get_command_cache()
    key = get_cache_key(intent)
    cache[key] = {
        "intent": intent,
        "command": command,
        "created_at": datetime.now().isoformat(),
        "use_count": 1
    }

def get_cached_command(intent: str):
    cache = get_command_cache()
    key = get_cache_key(intent)
    if key in cache:
        cache[key]["use_count"] += 1
        return cache[key]["command"]
    return None

# ==================== 設定表示ヘルパー ====================

def display_config_summary(config: dict):
    """設定を人が読みやすい形式で表示"""
    import pandas as pd
    
    tab1, tab2 = st.tabs(["📊 サマリー表示", "📄 JSON表示"])
    
    with tab1:
        st.subheader("🏷️ ホストグループ")
        if config.get("host_groups"):
            groups_df = pd.DataFrame(config["host_groups"])
            st.dataframe(groups_df, use_container_width=True, hide_index=True)
        
        st.subheader("🖥️ ホスト設定")
        if config.get("hosts"):
            hosts_data = []
            for host in config["hosts"]:
                hosts_data.append({
                    "ホスト名": host.get("host_id", ""),
                    "グループ": ", ".join(host.get("groups", [])),
                    "テンプレート": ", ".join(host.get("templates", [])),
                })
            hosts_df = pd.DataFrame(hosts_data)
            st.dataframe(hosts_df, use_container_width=True, hide_index=True)
        
        st.subheader("⚡ トリガー")
        if config.get("triggers"):
            triggers_data = []
            for trigger in config["triggers"]:
                triggers_data.append({
                    "ホスト": trigger.get("host", ""),
                    "トリガー名": trigger.get("name", ""),
                    "重要度": trigger.get("severity", ""),
                })
            triggers_df = pd.DataFrame(triggers_data)
            st.dataframe(triggers_df, use_container_width=True, hide_index=True)
        
        st.subheader("🔗 依存関係")
        if config.get("dependencies"):
            deps_data = []
            for dep in config["dependencies"]:
                deps_data.append({
                    "ホスト": dep.get("host", ""),
                    "依存先": dep.get("depends_on", ""),
                    "タイプ": dep.get("type", ""),
                })
            deps_df = pd.DataFrame(deps_data)
            st.dataframe(deps_df, use_container_width=True, hide_index=True)
    
    with tab2:
        st.json(config)

# ==================== サーバー情報ダイアログ ====================

def show_server_info_dialog():
    """サーバー情報ダイアログを表示"""
    import pandas as pd
    
    st.subheader("📊 サーバー情報")
    
    tab_a, tab_b, tab_c = st.tabs([
        "📈 サマリー＋条件検索", 
        "🎯 カード形式ダッシュボード", 
        "❓ クイック質問"
    ])
    
    # === タブA: サマリー＋条件検索 ===
    with tab_a:
        summary = get_server_status_summary()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🟢 正常", f"{summary['ok']}台")
        with col2:
            st.metric("🟡 警告", f"{summary['warning']}台")
        with col3:
            st.metric("🔴 異常", f"{summary['error']}台")
        with col4:
            st.metric("📊 合計", f"{summary['total']}台")
        
        st.divider()
        
        # クイックフィルター
        st.write("**🔍 クイックフィルター**")
        qf_col1, qf_col2, qf_col3, qf_col4 = st.columns(4)
        with qf_col1:
            if st.button("🔴 異常のみ", key="filter_error", use_container_width=True):
                st.session_state.server_filter = "error"
        with qf_col2:
            if st.button("🟡 警告以上", key="filter_warn", use_container_width=True):
                st.session_state.server_filter = "warning_up"
        with qf_col3:
            if st.button("🟢 正常のみ", key="filter_ok", use_container_width=True):
                st.session_state.server_filter = "ok"
        with qf_col4:
            if st.button("📋 全て表示", key="filter_all", use_container_width=True):
                st.session_state.server_filter = "all"
        
        st.divider()
        
        # カスタム条件検索
        st.write("**🎛️ カスタム条件検索**")
        cond_col1, cond_col2, cond_col3, cond_col4 = st.columns([2, 1, 1, 1])
        with cond_col1:
            metric = st.selectbox("メトリクス", ["cpu", "memory", "disk"], key="search_metric")
        with cond_col2:
            operator = st.selectbox("条件", [">", ">=", "<", "<=", "="], key="search_op")
        with cond_col3:
            value = st.number_input("値(%)", min_value=0, max_value=100, value=80, key="search_value")
        with cond_col4:
            st.write("")  # スペーサー
            st.write("")
            search_clicked = st.button("🔍 検索", key="custom_search", use_container_width=True)
        
        # 結果表示
        if search_clicked:
            st.session_state.server_filter = "custom"
            st.session_state.custom_search = {"metric": metric, "operator": operator, "value": value}
        
        if "server_filter" in st.session_state:
            st.divider()
            filter_type = st.session_state.server_filter
            
            if filter_type == "custom" and "custom_search" in st.session_state:
                cs = st.session_state.custom_search
                results = get_hosts_by_condition(cs["metric"], cs["operator"], cs["value"])
                st.write(f"**検索結果: {cs['metric']} {cs['operator']} {cs['value']}%**")
            elif filter_type == "error":
                results = get_hosts_by_status("error")
                st.write("**🔴 異常サーバー一覧**")
            elif filter_type == "warning_up":
                results = get_hosts_by_status("error") + get_hosts_by_status("warning")
                st.write("**🟡 警告以上のサーバー一覧**")
            elif filter_type == "ok":
                results = get_hosts_by_status("ok")
                st.write("**🟢 正常サーバー一覧**")
            else:
                results = get_hosts_by_status("all")
                st.write("**📋 全サーバー一覧**")
            
            if results:
                display_data = []
                for r in results:
                    row = {
                        "ホスト": r["host_id"],
                        "タイプ": r.get("type", "-"),
                    }
                    if "current_value" in r:
                        row["値"] = f"{r['current_value']:.1f}%"
                    if "status" in r:
                        status_map = {"ok": "🟢", "warning": "🟡", "error": "🔴"}
                        row["状態"] = status_map.get(r["status"], "-")
                    if "alert" in r:
                        row["アラート"] = r["alert"].get("message", "-")
                    metrics = r.get("metrics", {})
                    if metrics:
                        row["CPU"] = f"{metrics.get('cpu', '-')}%" if isinstance(metrics.get('cpu'), (int, float)) else "-"
                        row["メモリ"] = f"{metrics.get('memory', '-')}%" if isinstance(metrics.get('memory'), (int, float)) else "-"
                    display_data.append(row)
                st.dataframe(pd.DataFrame(display_data), use_container_width=True, hide_index=True)
            else:
                st.info("該当するサーバーはありません")
    
    # === タブB: カード形式ダッシュボード ===
    with tab_b:
        hosts = get_hosts()
        alerts = get_alerts()
        
        # メトリクス別カウント
        cpu_high = len([h for h in hosts.values() if h.get("metrics", {}).get("cpu", 0) > 80])
        mem_high = len([h for h in hosts.values() if h.get("metrics", {}).get("memory", 0) > 80])
        disk_high = len([h for h in hosts.values() if h.get("metrics", {}).get("disk", 0) > 80])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 💻 CPU")
            if cpu_high > 0:
                st.error(f"高負荷: {cpu_high}台")
            else:
                st.success("すべて正常")
            if st.button("詳細を見る", key="cpu_detail"):
                st.session_state.card_detail = "cpu"
        
        with col2:
            st.markdown("### 🧠 メモリ")
            if mem_high > 0:
                st.error(f"高負荷: {mem_high}台")
            else:
                st.success("すべて正常")
            if st.button("詳細を見る", key="mem_detail"):
                st.session_state.card_detail = "memory"
        
        with col3:
            st.markdown("### 💾 ディスク")
            if disk_high > 0:
                st.warning(f"注意: {disk_high}台")
            else:
                st.success("すべて正常")
            if st.button("詳細を見る", key="disk_detail"):
                st.session_state.card_detail = "disk"
        
        col4, col5 = st.columns(2)
        with col4:
            st.markdown("### ⚡ アラート")
            high_alerts = len([a for a in alerts if a["severity"] == "high"])
            warn_alerts = len([a for a in alerts if a["severity"] == "warning"])
            if high_alerts > 0:
                st.error(f"重大: {high_alerts}件")
            if warn_alerts > 0:
                st.warning(f"警告: {warn_alerts}件")
            if high_alerts == 0 and warn_alerts == 0:
                st.success("アラートなし")
            if st.button("詳細を見る", key="alert_detail"):
                st.session_state.card_detail = "alerts"
        
        with col5:
            st.markdown("### 📊 全体サマリー")
            summary = get_server_status_summary()
            st.write(f"🟢 正常: {summary['ok']}台")
            st.write(f"🟡 警告: {summary['warning']}台")
            st.write(f"🔴 異常: {summary['error']}台")
        
        # 詳細表示
        if "card_detail" in st.session_state:
            st.divider()
            detail = st.session_state.card_detail
            if detail in ["cpu", "memory", "disk"]:
                results = get_hosts_by_condition(detail, ">", 80)
                st.write(f"**{detail.upper()} 80%超えのサーバー**")
                if results:
                    for r in results:
                        st.write(f"- {r['host_id']}: {r['current_value']:.1f}%")
                else:
                    st.info("該当なし")
            elif detail == "alerts":
                st.write("**アラート一覧**")
                for a in alerts:
                    icon = "🔴" if a["severity"] == "high" else "🟡"
                    st.write(f"{icon} **{a['host']}**: {a['message']}")
    
    # === タブC: クイック質問 ===
    with tab_c:
        st.write("**🔍 何を知りたいですか？**")
        
        quick_questions = [
            ("💻 CPU高負荷のサーバー", "cpu", ">", 80),
            ("🧠 メモリ不足のサーバー", "memory", ">", 80),
            ("💾 ディスク容量警告のサーバー", "disk", ">", 70),
            ("🔴 異常状態のサーバー", "error", None, None),
            ("📋 全サーバーの状態一覧", "all", None, None),
        ]
        
        for label, metric, op, val in quick_questions:
            if st.button(label, key=f"qq_{metric}", use_container_width=True):
                if op and val:
                    results = get_hosts_by_condition(metric, op, val)
                    st.session_state.quick_question_result = {
                        "label": label,
                        "results": results,
                        "type": "condition"
                    }
                else:
                    results = get_hosts_by_status(metric)
                    st.session_state.quick_question_result = {
                        "label": label,
                        "results": results,
                        "type": "status"
                    }
        
        st.divider()
        
        # 特定サーバーの詳細
        st.write("**🎯 特定サーバーの詳細**")
        hosts = get_hosts()
        selected_host = st.selectbox("サーバーを選択", [""] + list(hosts.keys()), key="select_host")
        if selected_host:
            metrics = get_host_metrics(selected_host)
            host_info = hosts.get(selected_host, {})
            
            st.write(f"**{selected_host}** ({host_info.get('type', '-')})")
            if metrics:
                mcol1, mcol2, mcol3 = st.columns(3)
                with mcol1:
                    cpu = metrics.get('cpu', '-')
                    st.metric("CPU", f"{cpu}%" if isinstance(cpu, (int, float)) else cpu)
                with mcol2:
                    mem = metrics.get('memory', '-')
                    st.metric("メモリ", f"{mem}%" if isinstance(mem, (int, float)) else mem)
                with mcol3:
                    disk = metrics.get('disk', '-')
                    st.metric("ディスク", f"{disk}%" if isinstance(disk, (int, float)) else disk)
        
        st.divider()
        
        # 自由入力
        st.write("**💬 または自由に質問:**")
        free_query = st.text_input("例: メモリ70%以上のサーバー", key="free_query")
        if st.button("質問する", key="ask_free") and free_query:
            st.session_state.pending_message = free_query
            st.rerun()
        
        # クイック質問結果表示
        if "quick_question_result" in st.session_state:
            st.divider()
            qr = st.session_state.quick_question_result
            st.write(f"**{qr['label']} の結果:**")
            if qr["results"]:
                for r in qr["results"]:
                    if "current_value" in r:
                        st.write(f"- {r['host_id']}: {r['current_value']:.1f}%")
                    elif "status" in r:
                        status_map = {"ok": "🟢", "warning": "🟡", "error": "🔴"}
                        st.write(f"- {status_map.get(r['status'], '')} {r['host_id']}")
                    else:
                        st.write(f"- {r['host_id']}")
            else:
                st.info("該当するサーバーはありません")

# ==================== LLM連携 ====================

# サニタイズ対象のパターン
SENSITIVE_PATTERNS = [
    # パスワード関連
    (r'(password|passwd|pass|pw)\s*[=:]\s*["\']?[\w\S]+["\']?', r'\1=***REDACTED***'),
    (r'(パスワード|暗証番号)\s*[=:：]\s*[\w\S]+', r'\1=***REDACTED***'),
    
    # APIキー・シークレット
    (r'(api[_-]?key|apikey|secret[_-]?key|access[_-]?key)\s*[=:]\s*["\']?[\w\-]+["\']?', r'\1=***REDACTED***', re.IGNORECASE),
    (r'(bearer|token|jwt)\s+[\w\-\.]+', r'\1 ***REDACTED***', re.IGNORECASE),
    
    # 認証情報
    (r'(auth|credential|secret)\s*[=:]\s*["\']?[\w\S]+["\']?', r'\1=***REDACTED***', re.IGNORECASE),
    
    # クレジットカード番号（16桁の数字、スペースやハイフン区切り含む）
    (r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b', '***CARD-REDACTED***'),
    
    # SSN（米国社会保障番号）
    (r'\b(\d{3}[\s\-]?\d{2}[\s\-]?\d{4})\b', '***SSN-REDACTED***'),
    
    # 日本のマイナンバー（12桁）
    (r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})\b', '***MYNUMBER-REDACTED***'),
    
    # Basic認証ヘッダー
    (r'(Basic\s+)[A-Za-z0-9+/=]+', r'\1***REDACTED***', re.IGNORECASE),
    
    # AWS認証情報
    (r'(AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}', '***AWS-KEY-REDACTED***'),
    (r'(aws[_-]?secret[_-]?access[_-]?key)\s*[=:]\s*[\w/+=]+', r'\1=***REDACTED***', re.IGNORECASE),
    
    # 秘密鍵（PEM形式）
    (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?PRIVATE\s+KEY-----', '***PRIVATE-KEY-REDACTED***'),
    
    # データベース接続文字列
    (r'(mysql|postgres|mongodb|redis)://[^\s]+', r'\1://***REDACTED***', re.IGNORECASE),
]

def sanitize_message(message: str) -> tuple[str, list[str]]:
    """
    メッセージから秘密情報を除去する
    
    Returns:
        tuple: (サニタイズ済みメッセージ, 検出された秘密情報の種類リスト)
    """
    sanitized = message
    detected = []
    
    for pattern_tuple in SENSITIVE_PATTERNS:
        if len(pattern_tuple) == 3:
            pattern, replacement, flags = pattern_tuple
            regex = re.compile(pattern, flags)
        else:
            pattern, replacement = pattern_tuple
            regex = re.compile(pattern, re.IGNORECASE)
        
        if regex.search(sanitized):
            # 検出された秘密情報の種類を記録
            if 'password' in pattern.lower() or 'passwd' in pattern.lower() or 'パスワード' in pattern:
                detected.append("パスワード")
            elif 'api' in pattern.lower() or 'secret' in pattern.lower() or 'token' in pattern.lower():
                detected.append("APIキー/トークン")
            elif 'card' in replacement.lower():
                detected.append("クレジットカード番号")
            elif 'ssn' in replacement.lower():
                detected.append("社会保障番号")
            elif 'mynumber' in replacement.lower():
                detected.append("マイナンバー")
            elif 'aws' in pattern.lower():
                detected.append("AWS認証情報")
            elif 'private' in replacement.lower():
                detected.append("秘密鍵")
            elif 'mysql' in pattern.lower() or 'postgres' in pattern.lower():
                detected.append("データベース接続情報")
            else:
                detected.append("認証情報")
            
            sanitized = regex.sub(replacement, sanitized)
    
    # 重複を除去
    detected = list(set(detected))
    
    return sanitized, detected

def call_gemini(user_message: str) -> dict:
    """Google AI Studio APIを呼び出す（エラー時はモック応答）"""
    
    # ★ サニタイズ処理
    sanitized_message, detected_secrets = sanitize_message(user_message)
    
    # 秘密情報が検出された場合、警告をセッションに保存
    if detected_secrets:
        st.session_state.sanitize_warning = detected_secrets
    
    api_key = ""
    try:
        if hasattr(st, 'secrets') and "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
    except:
        pass
    
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY", "")
    
    if not api_key:
        return generate_mock_response(sanitized_message)  # サニタイズ済みを使用
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-12b-it:generateContent?key={api_key}"
        
        system_prompt = """あなたはZabbix監視システムのAIアシスタントです。
ユーザーの意図を解析し、以下のJSON形式で応答してください:
{"intent": "意図", "action": "アクション名", "parameters": {パラメータ}}

アクション: generate_config, set_maintenance, search_hosts, get_metrics, get_alerts, show_graph"""
        
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nユーザー: {sanitized_message}"}]}],  # サニタイズ済みを使用
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }
        
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
    except requests.exceptions.Timeout:
        pass  # タイムアウトはモック応答にフォールバック
    except Exception as e:
        pass  # その他エラーもモック応答にフォールバック
    
    return generate_mock_response(sanitized_message)  # サニタイズ済みを使用

def generate_mock_response(user_message: str) -> dict:
    """パターンマッチングによるモック応答"""
    message_lower = user_message.lower()
    
    if "トポロジー" in message_lower and ("設定" in message_lower or "監視" in message_lower):
        return {"intent": "トポロジーからZabbix設定を生成", "action": "generate_config", "parameters": {}}
    
    if "メンテナンス" in message_lower:
        host_match = re.search(r'([A-Z][A-Z0-9_-]+)', user_message)
        host_id = host_match.group(1) if host_match else "WAN_ROUTER_01"
        time_match = re.search(r'(\d+)\s*(分|時間|hour|min)', message_lower)
        duration = 60
        if time_match:
            duration = int(time_match.group(1))
            if "時間" in time_match.group(2) or "hour" in time_match.group(2):
                duration *= 60
        return {"intent": f"{host_id}をメンテナンスモードに設定", "action": "set_maintenance", "parameters": {"host_id": host_id, "duration_minutes": duration}}
    
    # CPU/メモリ/ディスク検索
    for metric_ja, metric_en in [("cpu", "cpu"), ("メモリ", "memory"), ("ディスク", "disk")]:
        if metric_ja in message_lower:
            threshold_match = re.search(r'(\d+)\s*%?', user_message)
            threshold = int(threshold_match.group(1)) if threshold_match else 80
            operator = ">"
            if "以下" in message_lower or "未満" in message_lower:
                operator = "<"
            elif "以上" in message_lower:
                operator = ">="
            return {"intent": f"{metric_en}{threshold}%{operator}のホストを検索", "action": "search_hosts", "parameters": {"metric": metric_en, "operator": operator, "value": threshold}}
    
    if "メトリクス" in message_lower or "状態" in message_lower or "情報" in message_lower:
        host_match = re.search(r'([A-Z][A-Z0-9_-]+)', user_message)
        if host_match:
            return {"intent": f"{host_match.group(1)}のメトリクスを取得", "action": "get_metrics", "parameters": {"host_id": host_match.group(1)}}
    
    if "アラート" in message_lower or "障害" in message_lower or "問題" in message_lower:
        return {"intent": "現在のアラート一覧を取得", "action": "get_alerts", "parameters": {}}
    
    if "グラフ" in message_lower or "推移" in message_lower or "トレンド" in message_lower:
        host_match = re.search(r'([A-Z][A-Z0-9_-]+)', user_message)
        host_id = host_match.group(1) if host_match else "WAN_ROUTER_01"
        metric = "cpu" if "cpu" in message_lower else "memory" if "メモリ" in message_lower else "cpu"
        return {"intent": f"{host_id}の{metric}グラフを表示", "action": "show_graph", "parameters": {"host_id": host_id, "metric": metric, "hours": 24}}
    
    # サーバー情報
    if "サーバー" in message_lower:
        return {"intent": "サーバー情報を表示", "action": "show_server_info", "parameters": {}}
    
    return {"intent": "不明", "action": "unknown", "parameters": {"original_query": user_message}}

# ==================== メッセージ処理 ====================

def process_message(user_message: str) -> dict:
    """メッセージを処理して応答を生成"""
    
    cached = get_cached_command(user_message)
    if cached:
        response = cached
        is_cached = True
    else:
        response = call_gemini(user_message)
        is_cached = False
        if response.get("action") != "unknown":
            set_command_cache(user_message, response)
    
    action = response.get("action", "unknown")
    params = response.get("parameters", {})
    
    result = {"response": response, "cached": is_cached}
    
    if action == "generate_config":
        topology = load_topology()
        if not topology:
            result["message"] = "❌ トポロジーデータがありません。サイドバーからアップロードしてください。"
        else:
            config = generate_zabbix_config(topology)
            result["config"] = config
            result["message"] = f"""✅ Zabbix設定を生成しました：
• ホスト: {len(config['hosts'])}台
• ホストグループ: {len(config['host_groups'])}個
• トリガー: {len(config['triggers'])}個
• 依存関係: {len(config['dependencies'])}件"""
            
    elif action == "set_maintenance":
        host_id = params.get("host_id", "不明")
        duration = params.get("duration_minutes", 60)
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration)
        
        if "maintenance" not in st.session_state:
            st.session_state.maintenance = {}
        st.session_state.maintenance[host_id] = {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration": duration
        }
        
        result["message"] = f"""✅ {host_id}をメンテナンスモードに設定しました
• 開始: {start_time.strftime('%Y-%m-%d %H:%M')}
• 終了: {end_time.strftime('%Y-%m-%d %H:%M')}
• 期間: {duration}分"""
        result["maintenance"] = st.session_state.maintenance[host_id]
        
    elif action == "search_hosts":
        metric = params.get("metric", "cpu")
        operator = params.get("operator", ">")
        value = params.get("value", 80)
        
        hosts = get_hosts_by_condition(metric, operator, value)
        result["hosts"] = hosts
        
        if hosts:
            host_list = "\n".join([f"• {h['host_id']}: {h['current_value']:.1f}%" for h in hosts])
            result["message"] = f"🔍 {len(hosts)}台見つかりました：\n{host_list}"
        else:
            result["message"] = f"✅ 条件に合うホストはありません（{metric} {operator} {value}%）"
            
    elif action == "get_metrics":
        host_id = params.get("host_id")
        metrics = get_host_metrics(host_id)
        
        if metrics:
            result["metrics"] = metrics
            metrics_lines = []
            for k, v in metrics.items():
                if isinstance(v, float):
                    metrics_lines.append(f"• {k}: {v:.1f}%")
                else:
                    metrics_lines.append(f"• {k}: {v}")
            result["message"] = f"📊 {host_id}のメトリクス：\n" + "\n".join(metrics_lines)
        else:
            result["message"] = f"❌ ホスト {host_id} が見つかりません"
            
    elif action == "get_alerts":
        alerts = get_alerts()
        result["alerts"] = alerts
        
        if alerts:
            alert_list = "\n".join([
                f"{'🔴' if a['severity']=='high' else '🟡'} {a['host']}: {a['message']}" 
                for a in alerts
            ])
            result["message"] = f"⚠️ {len(alerts)}件のアラート：\n{alert_list}"
        else:
            result["message"] = "✅ 現在アラートはありません"
            
    elif action == "show_graph":
        host_id = params.get("host_id", "WAN_ROUTER_01")
        metric = params.get("metric", "cpu")
        hours = params.get("hours", 24)
        
        history = generate_metrics_history(host_id, metric, hours)
        result["graph_data"] = history
        result["host_id"] = host_id
        result["metric"] = metric
        
        if history:
            peak = max(history, key=lambda x: x["value"])
            result["message"] = f"📈 {host_id}の{metric}推移（過去{hours}時間）\nピーク: {peak['value']:.1f}% ({peak['timestamp'].strftime('%H:%M')})"
        else:
            result["message"] = f"❌ {host_id}の{metric}データがありません"
    
    elif action == "show_server_info":
        result["message"] = "📊 サーバー情報ダイアログを開きます"
        result["show_server_dialog"] = True
    else:
        result["message"] = f"""🤔 「{user_message}」の意図を理解できませんでした。

以下のような質問をお試しください：
• トポロジーで監視設定して
• CPU80%超えてるサーバー教えて
• WAN_ROUTER_01のメトリクス見せて
• 現在のアラート教えて
• CORE_SW_01のCPU推移をグラフで"""
    
    return result

# ==================== UI ====================

def main():
    # ヘッダー
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🖥️ Zabbix AI Assistant")
        st.caption("Powered by gemma-3-12b-it | Demo Mode")
    with col2:
        st.markdown(f"🟢 Online | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    st.divider()
    
    # サイドバー
    with st.sidebar:
        st.header("⚡ クイックアクション")
        
        if st.button("📊 サーバー情報を見る", key="quick_server_info", use_container_width=True):
            st.session_state.show_server_dialog = True
        
        if st.button("🔧 トポロジーで監視設定", key="quick_topology", use_container_width=True):
            st.session_state.pending_message = "トポロジーで監視設定して"
        
        if st.button("⚠️ 現在のアラート確認", key="quick_alert", use_container_width=True):
            st.session_state.pending_message = "現在のアラート教えて"
        
        if st.button("🛠️ メンテナンス設定", key="quick_maintenance", use_container_width=True):
            st.session_state.show_maintenance_dialog = True
        
        if st.button("📈 グラフ表示", key="quick_graph", use_container_width=True):
            st.session_state.show_graph_dialog = True
        
        st.divider()
        
        # トポロジーアップロード
        st.header("📁 トポロジーアップロード")
        uploaded_file = st.file_uploader("JSONファイルを選択", type=["json"], key="topology_upload")
        
        if uploaded_file:
            try:
                new_topology = json.load(uploaded_file)
                os.makedirs(DATA_DIR, exist_ok=True)
                with open(os.path.join(DATA_DIR, "topology.json"), "w", encoding="utf-8") as f:
                    json.dump(new_topology, f, ensure_ascii=False, indent=2)
                st.success(f"✅ {len(new_topology)}台のデバイスを読み込みました")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"❌ 読み込みエラー: {e}")
        
        st.divider()
        
        # キャッシュ情報
        st.header("💾 コマンドキャッシュ")
        cache = get_command_cache()
        st.caption(f"{len(cache)}件のコマンドをキャッシュ中")
        if st.button("キャッシュクリア", use_container_width=True):
            st.session_state.command_cache = {}
            st.success("キャッシュをクリアしました")
        
        st.divider()
        
        # チャット履歴クリア
        if st.button("🗑️ チャット履歴クリア", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    
    # === ダイアログ表示 ===
    
    # サーバー情報ダイアログ
    if st.session_state.get("show_server_dialog"):
        with st.expander("📊 サーバー情報", expanded=True):
            show_server_info_dialog()
            if st.button("閉じる", key="close_server_dialog"):
                st.session_state.show_server_dialog = False
                st.rerun()
    
    # メンテナンス設定ダイアログ
    if st.session_state.get("show_maintenance_dialog"):
        with st.expander("🛠️ メンテナンス設定", expanded=True):
            hosts = get_hosts()
            selected_host = st.selectbox("対象ホスト", list(hosts.keys()), key="maint_host")
            duration = st.number_input("期間（分）", min_value=1, max_value=1440, value=60, key="maint_duration")
            if st.button("設定する", key="set_maintenance"):
                st.session_state.pending_message = f"{selected_host}を{duration}分メンテナンスモードに"
                st.session_state.show_maintenance_dialog = False
                st.rerun()
            if st.button("キャンセル", key="cancel_maintenance"):
                st.session_state.show_maintenance_dialog = False
                st.rerun()
    
    # グラフ表示ダイアログ
    if st.session_state.get("show_graph_dialog"):
        with st.expander("📈 グラフ表示", expanded=True):
            hosts = get_hosts()
            selected_host = st.selectbox("対象ホスト", list(hosts.keys()), key="graph_host")
            metric = st.selectbox("メトリクス", ["cpu", "memory", "disk"], key="graph_metric")
            if st.button("表示する", key="show_graph"):
                st.session_state.pending_message = f"{selected_host}の{metric}推移をグラフで"
                st.session_state.show_graph_dialog = False
                st.rerun()
            if st.button("キャンセル", key="cancel_graph"):
                st.session_state.show_graph_dialog = False
                st.rerun()
    
    # チャット履歴の初期化
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": """こんにちは！Zabbix AI アシスタントです。

以下のようなことができます：
• トポロジーからの自動監視設定
• メンテナンスモードの設定
• メトリクスの確認
• アラートの確認
• グラフ表示

何かお手伝いしましょうか？"""
            }
        ]
    
    # チャット履歴の表示
    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # ユーザーメッセージの場合、編集・コピーボタン
            if message["role"] == "user":
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])
                with btn_col1:
                    if st.button("📋", key=f"copy_{idx}", help="コピー"):
                        st.session_state.clipboard = message["content"]
                        st.toast("コピーしました")
                with btn_col2:
                    if st.button("✏️", key=f"edit_{idx}", help="編集して再送信"):
                        st.session_state.edit_message = message["content"]
            
            # 追加データの表示
            if "data" in message:
                data = message["data"]
                
                if "graph_data" in data and data["graph_data"]:
                    import pandas as pd
                    df = pd.DataFrame(data["graph_data"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                    st.line_chart(df["value"], use_container_width=True)
                
                if "config" in data:
                    with st.expander("📋 生成された設定を表示", expanded=True):
                        display_config_summary(data["config"])
                
                if "hosts" in data and data["hosts"]:
                    for host in data["hosts"]:
                        severity_color = "🔴" if host["current_value"] > 90 else "🟡" if host["current_value"] > 80 else "🟢"
                        st.markdown(f"{severity_color} **{host['host_id']}**: {host['current_value']:.1f}%")
    
    # サニタイズ警告の表示
    if "sanitize_warning" in st.session_state and st.session_state.sanitize_warning:
        warnings = st.session_state.sanitize_warning
        st.warning(f"⚠️ 秘密情報を検出したため、LLMへの送信前に削除しました: {', '.join(warnings)}")
        del st.session_state.sanitize_warning
    
    # クイックアクションからのメッセージ処理
    if "pending_message" in st.session_state:
        pending = st.session_state.pending_message
        del st.session_state.pending_message
        
        st.session_state.messages.append({"role": "user", "content": pending})
        
        with st.chat_message("user"):
            st.markdown(pending)
        
        with st.chat_message("assistant"):
            with st.spinner("処理中..."):
                result = process_message(pending)
            
            # サニタイズ警告があれば表示
            if "sanitize_warning" in st.session_state and st.session_state.sanitize_warning:
                warnings = st.session_state.sanitize_warning
                st.warning(f"🔒 秘密情報を検出・削除しました: {', '.join(warnings)}")
                del st.session_state.sanitize_warning
            
            if result.get("cached"):
                st.caption("⚡ キャッシュから応答")
            
            st.markdown(result.get("message", ""))
            
            if "graph_data" in result and result["graph_data"]:
                import pandas as pd
                df = pd.DataFrame(result["graph_data"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")
                st.line_chart(df["value"], use_container_width=True)
            
            if "config" in result:
                with st.expander("📋 生成された設定を表示", expanded=True):
                    display_config_summary(result["config"])
            
            if "hosts" in result and result["hosts"]:
                for host in result["hosts"]:
                    severity_color = "🔴" if host["current_value"] > 90 else "🟡" if host["current_value"] > 80 else "🟢"
                    st.markdown(f"{severity_color} **{host['host_id']}**: {host['current_value']:.1f}%")
            
            if result.get("show_server_dialog"):
                st.session_state.show_server_dialog = True
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.get("message", ""),
            "data": result
        })
        st.rerun()
    
    # 編集モードの入力欄
    if "edit_message" in st.session_state:
        edit_val = st.text_input("メッセージを編集:", value=st.session_state.edit_message, key="edit_input")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("送信", key="send_edit"):
                del st.session_state.edit_message
                st.session_state.pending_message = edit_val
                st.rerun()
        with col2:
            if st.button("キャンセル", key="cancel_edit"):
                del st.session_state.edit_message
                st.rerun()
    else:
        # チャット入力
        if prompt := st.chat_input("メッセージを入力... (例: CPU高いサーバー教えて)"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.markdown(prompt)
            
            with st.chat_message("assistant"):
                with st.spinner("処理中..."):
                    result = process_message(prompt)
                
                # サニタイズ警告があれば表示
                if "sanitize_warning" in st.session_state and st.session_state.sanitize_warning:
                    warnings = st.session_state.sanitize_warning
                    st.warning(f"🔒 秘密情報を検出・削除しました: {', '.join(warnings)}")
                    del st.session_state.sanitize_warning
                
                if result.get("cached"):
                    st.caption("⚡ キャッシュから応答")
                
                st.markdown(result.get("message", ""))
                
                if "graph_data" in result and result["graph_data"]:
                    import pandas as pd
                    df = pd.DataFrame(result["graph_data"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                    st.line_chart(df["value"], use_container_width=True)
                
                if "config" in result:
                    with st.expander("📋 生成された設定を表示", expanded=True):
                        display_config_summary(result["config"])
                
                if "hosts" in result and result["hosts"]:
                    for host in result["hosts"]:
                        severity_color = "🔴" if host["current_value"] > 90 else "🟡" if host["current_value"] > 80 else "🟢"
                        st.markdown(f"{severity_color} **{host['host_id']}**: {host['current_value']:.1f}%")
                
                if result.get("show_server_dialog"):
                    st.session_state.show_server_dialog = True
            
            st.session_state.messages.append({
                "role": "assistant",
                "content": result.get("message", ""),
                "data": result
            })

if __name__ == "__main__":
    main()

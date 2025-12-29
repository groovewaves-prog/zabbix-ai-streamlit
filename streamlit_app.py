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
    /* ダークテーマ風 */
    .stApp {
        background-color: #0a0e14;
        color: #f0f0f0;
    }
    
    /* 全体のテキスト色を明るく */
    .stApp, .stApp p, .stApp span, .stApp div, .stApp li {
        color: #f0f0f0 !important;
    }
    
    /* サイドバー */
    [data-testid="stSidebar"] {
        background-color: #151b23;
    }
    [data-testid="stSidebar"] * {
        color: #f0f0f0 !important;
    }
    
    /* チャットメッセージ */
    .stChatMessage {
        background-color: #1e2630;
        border-radius: 10px;
        padding: 10px;
    }
    .stChatMessage p, .stChatMessage span, .stChatMessage div {
        color: #f0f0f0 !important;
    }
    
    /* マークダウンテキスト */
    .stMarkdown, .stMarkdown p, .stMarkdown span {
        color: #f0f0f0 !important;
    }
    
    /* キャプション */
    .stCaption, small {
        color: #b0b0b0 !important;
    }
    
    /* メトリクスカード */
    .metric-card {
        background: linear-gradient(135deg, #1e2630, #151b23);
        border-radius: 10px;
        padding: 15px;
        margin: 5px 0;
        border-left: 3px solid #00ff9d;
    }
    
    /* アラートカード */
    .alert-high {
        border-left: 3px solid #ff4757;
    }
    .alert-warning {
        border-left: 3px solid #ffc107;
    }
    
    /* ボタン */
    .stButton > button {
        background: linear-gradient(135deg, #00ff9d, #00b8ff);
        color: #0a0e14 !important;
        font-weight: bold;
        border: none;
    }
    
    /* コードブロック */
    .stCodeBlock {
        background-color: #0a0e14 !important;
    }
    
    /* ヘッダー非表示 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* タイトルスタイル */
    .main-title {
        background: linear-gradient(135deg, #00ff9d, #00b8ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2em;
        font-weight: bold;
    }
    
    /* キャッシュバッジ */
    .cache-badge {
        background: #ffc107;
        color: #0a0e14;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 12px;
        margin-left: 10px;
    }
    
    /* 入力欄 */
    .stTextInput input, .stChatInput input, .stChatInput textarea {
        color: #f0f0f0 !important;
        background-color: #1e2630 !important;
    }
    
    /* expander */
    .streamlit-expanderHeader {
        color: #f0f0f0 !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== データ管理 ====================

# データディレクトリのパス
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

def get_hosts_by_condition(metric: str, operator: str, value: float) -> list:
    """条件に合うホストを取得"""
    hosts = get_hosts()
    results = []
    for host_id, host in hosts.items():
        if metric in host.get("metrics", {}):
            current_value = host["metrics"][metric]
            if operator == ">" and current_value > value:
                results.append({"host_id": host_id, **host, "current_value": current_value})
            elif operator == "<" and current_value < value:
                results.append({"host_id": host_id, **host, "current_value": current_value})
            elif operator == "=" and current_value == value:
                results.append({"host_id": host_id, **host, "current_value": current_value})
    return sorted(results, key=lambda x: x["current_value"], reverse=True)

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
    
    for i in range(hours * 6):  # 10分間隔
        timestamp = now - timedelta(minutes=10 * (hours * 6 - i))
        hour = timestamp.hour
        # 14時頃に急上昇するパターン
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
    
    # ホストグループ生成
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
    
    # テンプレートマッピング
    template_map = {
        ("Cisco", "ROUTER"): ["Template Cisco IOS-XE SNMP", "Template ICMP Ping"],
        ("Cisco", "SWITCH"): ["Template Cisco Catalyst SNMP", "Template ICMP Ping"],
        ("Juniper", "FIREWALL"): ["Template Juniper SRX SNMP", "Template ICMP Ping"],
        ("default", "ACCESS_POINT"): ["Template Generic SNMP AP", "Template ICMP Ping"],
    }
    
    # ホスト設定生成
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
        
        # 依存関係設定
        if host_data.get("parent_id"):
            config["dependencies"].append({
                "host": host_id,
                "depends_on": host_data["parent_id"],
                "type": "parent"
            })
    
    # トリガー生成
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
    """キャッシュキーを生成"""
    return hashlib.md5(intent.lower().strip().encode()).hexdigest()

def get_command_cache():
    """コマンドキャッシュを取得"""
    if "command_cache" not in st.session_state:
        st.session_state.command_cache = {}
    return st.session_state.command_cache

def set_command_cache(intent: str, command: dict):
    """コマンドをキャッシュに保存"""
    cache = get_command_cache()
    key = get_cache_key(intent)
    cache[key] = {
        "intent": intent,
        "command": command,
        "created_at": datetime.now().isoformat(),
        "use_count": 1
    }

def get_cached_command(intent: str):
    """キャッシュからコマンドを取得"""
    cache = get_command_cache()
    key = get_cache_key(intent)
    if key in cache:
        cache[key]["use_count"] += 1
        return cache[key]["command"]
    return None

# ==================== LLM連携 ====================

def call_gemini(user_message: str) -> dict:
    """Google AI Studio APIを呼び出す"""
    api_key = st.secrets.get("GOOGLE_API_KEY", "") if hasattr(st, 'secrets') else os.getenv("GOOGLE_API_KEY", "")
    
    if not api_key:
        return generate_mock_response(user_message)
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-12b-it:generateContent?key={api_key}"
        
        system_prompt = """あなたはZabbix監視システムのAIアシスタントです。
ユーザーの意図を解析し、以下のJSON形式で応答してください:
{"intent": "意図", "action": "アクション名", "parameters": {パラメータ}}

アクション: generate_config, set_maintenance, search_hosts, get_metrics, get_alerts, show_graph"""
        
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nユーザー: {user_message}"}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }
        
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        st.warning(f"API呼び出しエラー: {e}")
    
    return generate_mock_response(user_message)

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
    
    if "cpu" in message_lower and ("高い" in message_lower or "超え" in message_lower or ">" in message_lower):
        threshold_match = re.search(r'(\d+)\s*%?', user_message)
        threshold = int(threshold_match.group(1)) if threshold_match else 80
        return {"intent": f"CPU{threshold}%超えのホストを検索", "action": "search_hosts", "parameters": {"metric": "cpu", "operator": ">", "value": threshold}}
    
    if "メトリクス" in message_lower or "状態" in message_lower:
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
    
    return {"intent": "不明", "action": "unknown", "parameters": {"original_query": user_message}}

# ==================== メイン処理 ====================

def process_message(user_message: str) -> tuple:
    """メッセージを処理して応答を生成"""
    
    # キャッシュチェック
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
    else:
        result["message"] = """🤔 すみません、意図を理解できませんでした。
        
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
        st.markdown('<p class="main-title">🖥️ Zabbix AI Assistant</p>', unsafe_allow_html=True)
        st.caption("Powered by gemma-3-12b-it | Demo Mode")
    with col2:
        st.markdown(f"🟢 Online | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    st.divider()
    
    # サイドバー
    with st.sidebar:
        st.header("⚡ クイックアクション")
        
        quick_actions = [
            "トポロジーで監視設定して",
            "CPU80%超えてるサーバー教えて",
            "WAN_ROUTER_01を30分メンテナンスに",
            "現在のアラート教えて",
            "CORE_SW_01のCPU推移をグラフで"
        ]
        
        for action in quick_actions:
            if st.button(action, key=f"quick_{action}", use_container_width=True):
                st.session_state.pending_message = action
        
        st.divider()
        
        # トポロジーアップロード
        st.header("📁 トポロジーアップロード")
        uploaded_file = st.file_uploader("JSONファイルを選択", type=["json"], key="topology_upload")
        
        if uploaded_file:
            try:
                new_topology = json.load(uploaded_file)
                # ファイルに保存
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
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # 追加データの表示
            if "data" in message:
                data = message["data"]
                
                # グラフ表示
                if "graph_data" in data and data["graph_data"]:
                    import pandas as pd
                    df = pd.DataFrame(data["graph_data"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"])
                    df = df.set_index("timestamp")
                    st.line_chart(df["value"], use_container_width=True)
                
                # 設定プレビュー
                if "config" in data:
                    with st.expander("📋 生成された設定を表示"):
                        st.json(data["config"])
                
                # ホスト一覧
                if "hosts" in data and data["hosts"]:
                    for host in data["hosts"]:
                        severity_color = "🔴" if host["current_value"] > 90 else "🟡" if host["current_value"] > 80 else "🟢"
                        st.markdown(f"{severity_color} **{host['host_id']}**: {host['current_value']:.1f}%")
    
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
            
            # キャッシュバッジ
            if result.get("cached"):
                st.markdown("⚡ **Cached**", help="キャッシュから応答しました")
            
            st.markdown(result.get("message", ""))
            
            # グラフ表示
            if "graph_data" in result and result["graph_data"]:
                import pandas as pd
                df = pd.DataFrame(result["graph_data"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")
                st.line_chart(df["value"], use_container_width=True)
            
            # 設定プレビュー
            if "config" in result:
                with st.expander("📋 生成された設定を表示"):
                    st.json(result["config"])
            
            # ホスト一覧
            if "hosts" in result and result["hosts"]:
                for host in result["hosts"]:
                    severity_color = "🔴" if host["current_value"] > 90 else "🟡" if host["current_value"] > 80 else "🟢"
                    st.markdown(f"{severity_color} **{host['host_id']}**: {host['current_value']:.1f}%")
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.get("message", ""),
            "data": result
        })
        st.rerun()
    
    # チャット入力
    if prompt := st.chat_input("メッセージを入力... (例: CPU高いサーバー教えて)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("処理中..."):
                result = process_message(prompt)
            
            if result.get("cached"):
                st.markdown("⚡ **Cached**", help="キャッシュから応答しました")
            
            st.markdown(result.get("message", ""))
            
            if "graph_data" in result and result["graph_data"]:
                import pandas as pd
                df = pd.DataFrame(result["graph_data"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df = df.set_index("timestamp")
                st.line_chart(df["value"], use_container_width=True)
            
            if "config" in result:
                with st.expander("📋 生成された設定を表示"):
                    st.json(result["config"])
            
            if "hosts" in result and result["hosts"]:
                for host in result["hosts"]:
                    severity_color = "🔴" if host["current_value"] > 90 else "🟡" if host["current_value"] > 80 else "🟢"
                    st.markdown(f"{severity_color} **{host['host_id']}**: {host['current_value']:.1f}%")
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": result.get("message", ""),
            "data": result
        })

if __name__ == "__main__":
    main()

import streamlit as st
import pandas as pd
import os

# Refresh QIANFAN env vars from Windows registry (bypass stale terminal env)
def _refresh_qianfan_env():
    try:
        import winreg
        user_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Environment')
        for var_name in ['QIANFAN_ACCESS_KEY', 'QIANFAN_SECRET_KEY']:
            try:
                val, _ = winreg.QueryValueEx(user_key, var_name)
                os.environ[var_name] = val
            except FileNotFoundError:
                pass
        winreg.CloseKey(user_key)
        # Clear old-style vars to prevent SDK confusion
        os.environ.pop('QIANFAN_AK', None)
        os.environ.pop('QIANFAN_SK', None)
    except Exception:
        pass

_refresh_qianfan_env()
import io
from src.document_parser import get_document_content
from src.ai_engine import extract_by_headers
from src.logic_engine import align_multi_values, merge_results
from src.database import (
    init_db, save_extraction, get_all_extractions, 
    save_template, get_all_templates, delete_template,
    get_setting, update_setting,
    save_custom_model, get_all_custom_models, delete_custom_model
)
from src.formula_engine import process_computed_columns
import tkinter as tk
from tkinter import filedialog

# Initialize DB on start
init_db()

st.set_page_config(
    page_title="Data_Flow 通用表格提取助手", 
    layout="wide",
    page_icon="⚙️"  # Using gear icon for engineering context
)

# Custom CSS for Premium UI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --primary: #1a73e8;
        --primary-hover: #1765cc;
        --secondary: #5f6368;
        --success: #1e8e3e;
        --warning: #f9ab00;
        --bg-main: #f8f9fa;
        --card-bg: #ffffff;
        --text-main: #202124;
        --text-secondary: #5f6368;
        --border: #dadce0;
        --radius: 12px;
        --shadow: 0 1px 3px 0 rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15);
    }

    .stApp {
        background-color: var(--bg-main) !important;
        font-family: 'Inter', sans-serif;
    }

    /* Typography */
    h1, h2, h3, h4, h5, h6, p, label {
        color: var(--text-main) !important;
        font-weight: 500;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--card-bg) !important;
        border-right: 1px solid var(--border);
    }

    /* Cards & Containers */
    .stExpander, .stTabs, [data-testid="stForm"] {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3) !important;
        padding: 10px;
        margin-bottom: 20px;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox div {
        border-radius: 8px !important;
        border: 1px solid var(--border) !important;
        background-color: white !important;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        border: 1px solid var(--border) !important;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
        border-color: var(--primary) !important;
    }

    .stButton > button[kind="primary"] {
        background-color: var(--primary) !important;
        color: white !important;
        border: none !important;
    }

    /* Step Indicators */
    .step-header {
        display: flex;
        align-items: center;
        margin-bottom: 1rem;
        padding: 0.5rem 0;
        border-bottom: 2px solid var(--primary);
        width: fit-content;
    }
    .step-number {
        background-color: var(--primary);
        color: white;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        justify-content: center;
        align-items: center;
        margin-right: 10px;
        font-weight: bold;
    }
    .step-title {
        font-size: 1.2rem;
        font-weight: 600;
        color: var(--primary);
    }

    /* Status Widget Rotation */
    [data-testid="stStatusWidget"] div div::before {
        content: '⚙️';
        display: inline-block;
        animation: spin 2s linear infinite;
        margin-right: 8px;
    }
    @keyframes spin { 100% { transform: rotate(360deg); } }

</style>
""", unsafe_allow_html=True)

st.title("⚡ Data_Flow")
st.markdown("<p style='font-size: 1.1rem; color: #5f6368; margin-top: -15px;'>智能表格提取助手：让文档数据触手可及</p>", unsafe_allow_html=True)
st.markdown("---")

# ── Sidebar ──────────────────────────────────────────────────
st.sidebar.header("⚙️ 设置")

# Fetch custom models
custom_models_cfg = get_all_custom_models()
custom_provider_names = [m['provider_name'] for m in custom_models_cfg]

# Model Provider Choice
provider = st.sidebar.radio("选择模型来源", [
    "Ollama (本地)", 
    "DeepSeek (线上)", 
    "Moonshot (线上)",
    "智谱 AI (线上)",
    "火山引擎 (线上)",
    "腾讯云 (线上)",
    "硅基流动 (线上)",
    "商汤 MINIMAX (线上)",
    "阿里云通义 (线上)",
    "百度智能云 (线上)",
    "Agnes AI (线上)"
] + custom_provider_names)

if provider == "Ollama (本地)":
    def get_ollama_models():
        import requests
        try:
            response = requests.get("http://127.0.0.1:11434/api/tags", timeout=3)
            if response.status_code == 200:
                return [m['name'] for m in response.json().get('models', [])]
        except Exception:
            pass
        return []

    available_models = get_ollama_models()
    if not available_models:
        st.sidebar.warning("⚠️ 未检测到 Ollama 或模型列表为空")
        available_models = ["deepseek-r1:7b", "llama3.1"]

    model_name = st.sidebar.selectbox("选择 AI 模型", available_models, index=0)
    api_key = None
    base_url = None

elif provider == "DeepSeek (线上)":
    # DeepSeek API - read from environment only
    model_name = st.sidebar.selectbox("选择 DeepSeek 模型", ["deepseek-chat", "deepseek-reasoner"])
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    base_url = "https://api.deepseek.com"
    if api_key:
        st.sidebar.success("✅ 已检测到 DEEPSEEK_API_KEY 环境变量")
    else:
        st.sidebar.error("❌ 未检测到 DEEPSEEK_API_KEY 环境变量")
        st.sidebar.info("请在系统环境变量中设置 DEEPSEEK_API_KEY")

elif provider == "Moonshot (线上)":
    model_name = st.sidebar.selectbox("选择 Moonshot 模型", ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"])
    api_key = os.environ.get("MOONSHOT_API_KEY", "")
    base_url = "https://api.moonshot.cn/v1"
    if api_key:
        st.sidebar.success("✅ 已检测到 MOONSHOT_API_KEY")
    else:
        st.sidebar.error("❌ 未检测到 MOONSHOT_API_KEY")
        st.sidebar.info("请在系统环境变量中设置 MOONSHOT_API_KEY")

elif provider == "智谱 AI (线上)":
    model_name = st.sidebar.selectbox("选择智谱模型", ["glm-4", "glm-4-flash", "glm-4-air", "glm-3-turbo"])
    api_key = os.environ.get("ZHIPUAI_API_KEY", "")
    base_url = None
    if api_key:
        st.sidebar.success("✅ 已检测到 ZHIPUAI_API_KEY")
    else:
        st.sidebar.error("❌ 未检测到 ZHIPUAI_API_KEY")
        st.sidebar.info("请在系统环境变量中设置 ZHIPUAI_API_KEY")

elif provider == "火山引擎 (线上)":
    st.sidebar.markdown("### 🌋 火山引擎 (豆包大模型)")
    
    # Added templates for common models to guide the user
    volc_model_type = st.sidebar.selectbox("选择模型类型", [
        "豆包 (Doubao) - 通用", 
        "豆包 (Doubao) - 视觉理解",
        "其他自定义模型"
    ])
    
    volc_region = st.sidebar.selectbox("选择地域 (Region)", ["华北 2 (北京)", "华东 2 (上海)"])
    region_map = {
        "华北 2 (北京)": "cn-beijing",
        "华东 2 (上海)": "cn-shanghai"
    }
    base_url = f"https://ark.{region_map[volc_region]}.volces.com/api/v3"

    env_endpoint_id = os.environ.get("VOLCENGINE_ENDPOINT_ID", "").strip()
    model_name = st.sidebar.text_input(
        "输入接入点 ID (Endpoint ID)", 
        value=env_endpoint_id,
        placeholder="例如: ep-20240501...", 
        help="请注意：填写控制台中显示的【接入点 ID】（通常包含随机字符），而不是您起的【接入点名称】。"
    ).strip()
    
    api_key = os.environ.get("VOLCENGINE_API_KEY", "").strip()
    
    if api_key:
        st.sidebar.success("✅ 已检测到 VOLCENGINE_API_KEY")
    else:
        st.sidebar.error("❌ 未检测到 VOLCENGINE_API_KEY")
        st.sidebar.info("请在系统环境变量中设置 VOLCENGINE_API_KEY")

elif provider == "腾讯云 (线上)":
    model_name = st.sidebar.selectbox("选择混元模型", ["hunyuan-pro", "hunyuan-standard", "hunyuan-lite"])
    
    # Check env vars
    env_sid = os.environ.get("TENCENT_SECRET_ID", "").strip()
    env_skey = os.environ.get("TENCENT_SECRET_KEY", "").strip()
    env_appid = os.environ.get("TENCENT_APP_ID", "").strip()
    
    # AppID Input (Required for Hunyuan)
    app_id_input = st.sidebar.text_input(
        "输入腾讯云 AppID", 
        value=env_appid,
        placeholder="例如: 1251234567",
        help="请登录腾讯云控制台，在【账号信息】或【API 密钥管理】页面获取"
    ).strip()
    
    api_key = env_sid
    secret_key = env_skey
    base_url = None
    
    # We will pass app_id via environment as the engine reads it from there
    if app_id_input:
        os.environ["TENCENT_APP_ID"] = app_id_input
    
    if api_key and secret_key and app_id_input:
        st.sidebar.success("✅ 验证信息已就绪")
    else:
        st.sidebar.error("❌ 验证信息不完整")
        if not app_id_input:
            st.sidebar.info("请输入腾讯云 AppID")
        if not (api_key and secret_key):
            st.sidebar.info("请在系统环境变量中设置 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY")

elif provider == "硅基流动 (线上)":
    model_name = st.sidebar.selectbox("选择模型", [
        "deepseek-ai/DeepSeek-V3", 
        "deepseek-ai/DeepSeek-R1",
        "Qwen/Qwen2.5-72B-Instruct",
        "internlm/internlm2_5-7b-chat"
    ])
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    base_url = "https://api.siliconflow.cn/v1"
    if api_key:
        st.sidebar.success("✅ 已检测到 SILICONFLOW_API_KEY")
    else:
        st.sidebar.error("❌ 未检测到 SILICONFLOW_API_KEY")
        st.sidebar.info("请在系统环境变量中设置 SILICONFLOW_API_KEY")

elif provider == "商汤 MINIMAX (线上)":
    model_name = st.sidebar.selectbox("选择模型", ["abab6.5-chat", "abab6.5s-chat", "abab6-chat"])
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    base_url = "https://api.minimax.chat/v1"
    if api_key:
        st.sidebar.success("✅ 已检测到 MINIMAX_API_KEY")
    else:
        st.sidebar.error("❌ 未检测到 MINIMAX_API_KEY")
        st.sidebar.info("请在系统环境变量中设置 MINIMAX_API_KEY")

elif provider == "阿里云通义 (线上)":
    model_name = st.sidebar.selectbox("选择通义模型", ["qwen-plus", "qwen-turbo", "qwen-max"])
    api_key = os.environ.get("DASHSCOPE_API_KEY", "")
    base_url = None  # Alibaba uses different API structure
    if api_key:
        st.sidebar.success("✅ 已检测到 DASHSCOPE_API_KEY 环境变量")
    else:
        st.sidebar.error("❌ 未检测到 DASHSCOPE_API_KEY 环境变量")
        st.sidebar.info("请在系统环境变量中设置 DASHSCOPE_API_KEY")

elif provider == "Agnes AI (线上)":
    model_name = st.sidebar.selectbox("选择模型", ["Agnes-2.0-Flash", "Agnes-1.5-Flash", "agnes-image-20-flash", "agnes-video-v20"])
    api_key = os.environ.get("AGNES_API_KEY", "sk-wNaxpTaBkIrOnoXX7azJrkm8d8oVLYDWVTK7VHkqoA4OGhjq")
    base_url = "https://apihub.agnes-ai.com/v1"
    st.sidebar.success("✅ Agnes AI 已就绪")

elif provider in custom_provider_names:
    cfg = next(m for m in custom_models_cfg if m['provider_name'] == provider)
    model_name = st.sidebar.selectbox(f"选择 {provider} 模型", cfg['model_names'])
    api_key = cfg['api_key']
    base_url = cfg['base_url']
    st.sidebar.success(f"✅ 已加载自定义配置: {provider}")

if st.sidebar.button("刷新模型列表"):
    st.rerun()

st.sidebar.markdown("---")
# ── Custom Model Management ──
st.sidebar.header("🛠️ 自定义模型管理")
with st.sidebar.expander("➕ 添加/管理自定义模型"):
    with st.form("custom_model_form"):
        new_p_name = st.text_input("供应商名称", placeholder="例如: MyDeepSeek")
        new_base_url = st.text_input("Base URL", placeholder="https://api.deepseek.com")
        new_api_key = st.text_input("API Key", type="password")
        new_models_str = st.text_area("模型名称 (逗号分隔)", placeholder="deepseek-chat, deepseek-reasoner")
        
        if st.form_submit_button("保存自定义模型"):
            if new_p_name and new_base_url and new_api_key and new_models_str:
                m_list = [m.strip() for m in new_models_str.split(",") if m.strip()]
                if save_custom_model(new_p_name, new_base_url, new_api_key, m_list):
                    st.success(f"✅ 已保存 {new_p_name}")
                    st.rerun()
                else:
                    st.error("保存失败，名称可能已存在")
            else:
                st.warning("请填全所有信息")
    
    if custom_models_cfg:
        st.markdown("---")
        st.write("**已添加模型:**")
        for m in custom_models_cfg:
            c1, c2 = st.columns([3, 1])
            c1.write(f"{m['provider_name']}")
            if c2.button("🗑️", key=f"del_cm_{m['id']}"):
                delete_custom_model(m['id'])
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("📜 历史记录")
if st.sidebar.button("查看历史数据"):
    history = get_all_extractions()
    if history:
        for record in history[:10]:
            with st.sidebar.expander(f"#{record['id']} - {record['created_at'][:16]}"):
                st.write(f"**表头**: {', '.join(record['headers'])}")
                st.write(f"**来源文件**: {', '.join(record['source_files'])}")
                st.write(f"**行数**: {len(record['data'])}")
    else:
        st.sidebar.write("暂无历史数据")


# ── Main Section ─────────────────────────────────────────────

# Step 1: User defines table headers
st.markdown('<div class="step-header"><div class="step-number">1</div><div class="step-title">定义表头</div></div>', unsafe_allow_html=True)

# --- Template Management ---
with st.expander("📁 模板中心 - 加载或保存常用表头"):
    tabs = st.tabs(["加载模板", "保存为新模板", "管理模板"])
    
    with tabs[0]: # Load Template
        all_templates = get_all_templates()
        if all_templates:
            template_names = [t['name'] for t in all_templates]
            selected_tpl_name = st.selectbox("选择要加载的模板", ["-- 请选择 --"] + template_names)
            
            if selected_tpl_name != "-- 请选择 --":
                selected_tpl = next(t for t in all_templates if t['name'] == selected_tpl_name)
                st.info(f"模板说明: {selected_tpl['template_description'] or '无'}")
                if st.button("🚀 加载此模板"):
                    # Clear existing headers in session state first
                    for key in list(st.session_state.keys()):
                        if key.startswith("header_") or key.startswith("desc_"):
                            del st.session_state[key]
                    
                    # Set new header count and values
                    st.session_state.num_headers = len(selected_tpl['headers'])
                    for i, (h, d) in enumerate(zip(selected_tpl['headers'], 
                                                  [selected_tpl['header_descriptions'].get(h, "") for h in selected_tpl['headers']])):
                        st.session_state[f"header_{i}"] = h
                        st.session_state[f"desc_{i}"] = d
                    st.success(f"✅ 成功加载模板: {selected_tpl_name}")
                    st.rerun()
        else:
            st.write("暂无保存的模板")
            
    with tabs[1]: # Save Template
        if st.button("📋 确认当前待保存数据"):
            st.session_state.prepare_save = True
            
        if st.session_state.get('prepare_save', False):
            # Get active headers
            active_headers = []
            active_desc = {}
            for i in range(st.session_state.get('num_headers', 8)):
                h = st.session_state.get(f"header_{i}", "")
                if h:
                    active_headers.append(h)
                    d = st.session_state.get(f"desc_{i}", "")
                    active_desc[h] = d # Save even if empty string
            
            if not active_headers:
                st.warning("请先在下方输入一些表头内容再保存为模板")
                st.session_state.prepare_save = False
            else:
                with st.form("save_template_form"):
                    st.write(f"即将保存 {len(active_headers)} 个字段及其说明")
                    new_tpl_name = st.text_input("模板名称", placeholder="例如：工程结算模板")
                    new_tpl_desc = st.text_area("模板说明", placeholder="简要说明该模板的用途")
                    
                    col_s1, col_s2 = st.columns(2)
                    if col_s1.form_submit_button("💾 确认保存"):
                        if not new_tpl_name:
                            st.error("请输入模板名称")
                        else:
                            if save_template(new_tpl_name, active_headers, active_desc, new_tpl_desc or ""):
                                st.success(f"✅ 模板 '{new_tpl_name}' 已保存")
                                st.session_state.prepare_save = False
                                st.rerun()
                            else:
                                st.error("保存失败，可能名称已存在")
                    if col_s2.form_submit_button("取消"):
                        st.session_state.prepare_save = False
                        st.rerun()

    with tabs[2]: # Manage/Edit Template
        if all_templates:
            # Check if we are currently editing
            editing_id = st.session_state.get('editing_tpl_id', None)
            
            for t in all_templates:
                if editing_id == t['id']:
                    st.markdown(f"### ✏️ 正在编辑: {t['name']}")
                    
                    # Initialize edit state if not present
                    if 'edit_headers' not in st.session_state:
                        st.session_state.edit_headers = t['headers'].copy()
                        st.session_state.edit_header_descs = t['header_descriptions'].copy()
                        st.session_state.edit_tpl_name = t['name']
                        st.session_state.edit_tpl_desc = t['template_description'] or ""

                    edit_name = st.text_input("模板名称", value=st.session_state.edit_tpl_name, key="edit_tpl_name_input")
                    edit_tpl_desc = st.text_area("模板整体说明", value=st.session_state.edit_tpl_desc, key="edit_tpl_desc_input")
                    
                    st.write("**字段及说明编辑:**")
                    
                    # Use a copy of the list to iterate to avoid issues when deleting
                    current_headers = st.session_state.edit_headers
                    new_headers = []
                    new_descs = {}
                    
                    for i in range(len(current_headers)):
                        h = current_headers[i]
                        d = st.session_state.edit_header_descs.get(h, "")
                        
                        c1, c2, c3 = st.columns([2, 3, 0.5])
                        h_val = c1.text_input(f"字段 {i+1}", value=h, key=f"edit_h_{t['id']}_{i}")
                        d_val = c2.text_area(f"说明 {i+1}", value=d, key=f"edit_d_{t['id']}_{i}", height=70)
                        
                        if c3.button("🗑️", key=f"edit_del_{t['id']}_{i}"):
                            # Remove this header from the list
                            st.session_state.edit_headers.pop(i)
                            # Update session state values from inputs before rerun to keep other changes
                            # Note: we need to sync current inputs to session state here if we want to preserve them
                            st.session_state.edit_tpl_name = edit_name
                            st.session_state.edit_tpl_desc = edit_tpl_desc
                            st.rerun()
                            
                        if h_val:
                            new_headers.append(h_val)
                            new_descs[h_val] = d_val
                            
                    if st.button("➕ 添加字段", key=f"edit_add_{t['id']}"):
                        st.session_state.edit_headers.append(f"新字段_{len(st.session_state.edit_headers)+1}")
                        st.session_state.edit_tpl_name = edit_name
                        st.session_state.edit_tpl_desc = edit_tpl_desc
                        st.rerun()

                    col_e1, col_e2 = st.columns(2)
                    if col_e1.button("💾 保存修改", key=f"edit_save_{t['id']}", type="primary"):
                        if not edit_name:
                            st.error("请输入模板名称")
                        elif not new_headers:
                            st.error("至少需要保留一个字段")
                        else:
                            if save_template(edit_name, new_headers, new_descs, edit_tpl_desc):
                                if edit_name != t['name']:
                                    delete_template(t['id'])
                                st.success("✅ 修改已保存")
                                # Clear states
                                del st.session_state.editing_tpl_id
                                del st.session_state.edit_headers
                                del st.session_state.edit_header_descs
                                del st.session_state.edit_tpl_name
                                del st.session_state.edit_tpl_desc
                                st.rerun()
                            else:
                                st.error("保存失败，可能名称已存在")
                                
                    if col_e2.button("取消", key=f"edit_cancel_{t['id']}"):
                        del st.session_state.editing_tpl_id
                        if 'edit_headers' in st.session_state: del st.session_state.edit_headers
                        if 'edit_header_descs' in st.session_state: del st.session_state.edit_header_descs
                        if 'edit_tpl_name' in st.session_state: del st.session_state.edit_tpl_name
                        if 'edit_tpl_desc' in st.session_state: del st.session_state.edit_tpl_desc
                        st.rerun()
                    st.markdown("---")
                else:
                    col_t1, col_t2, col_t3 = st.columns([3, 1, 1])
                    col_t1.write(f"**{t['name']}** ({len(t['headers'])} 列)")
                    if col_t2.button("✏️ 编辑", key=f"edit_btn_{t['id']}"):
                        st.session_state.editing_tpl_id = t['id']
                        st.rerun()
                    if col_t3.button("🗑️", key=f"del_tpl_{t['id']}"):
                        delete_template(t['id'])
                        st.success(f"已删除模板: {t['name']}")
                        st.rerun()
        else:
            st.write("暂无保存的模板")

st.caption('每列一个表头字段，可选填写表头说明以提升提取精度。序号列自动生成，无需输入。')

# Initialize session state for dynamic columns
if 'num_headers' not in st.session_state:
    st.session_state.num_headers = 8  # Default 8 columns

# Add column button
col_add, col_reset = st.columns([1, 5])
with col_add:
    if st.button("➕ 增加一列", use_container_width=True):
        st.session_state.num_headers += 1
        st.rerun()

# Create dynamic column inputs
headers = []
header_descriptions = {}

st.markdown("**表头输入：**")
cols = st.columns(min(st.session_state.num_headers, 4))  # Max 4 columns per row for readability

for i in range(st.session_state.num_headers):
    col_idx = i % 4
    with cols[col_idx]:
        header = st.text_input(
            f"列 {i+1}",
            key=f"header_{i}",
            placeholder=f"表头 {i+1}",
            label_visibility="visible"
        )
        if header:
            headers.append(header)
            
            # Description field directly below header
            desc = st.text_area(
                f"说明 {i+1}",
                key=f"desc_{i}",
                placeholder="(可选) 详细说明该字段含义",
                height=80,
                label_visibility="collapsed"
            )
            if desc:
                header_descriptions[header] = desc
    
    # Create new row after every 4 columns
    if (i + 1) % 4 == 0 and i + 1 < st.session_state.num_headers:
        cols = st.columns(min(st.session_state.num_headers - (i + 1), 4))

# Save to session state
st.session_state.header_descriptions = header_descriptions

st.markdown("---")

# Step 2: Upload files
st.markdown('<div class="step-header"><div class="step-number">2</div><div class="step-title">上传文件</div></div>', unsafe_allow_html=True)
st.caption("支持格式：Word, PDF, TXT, Excel, Markdown, CSV, PowerPoint")
uploaded_files = st.file_uploader(
    "上传需要提取数据的文件",
    type=["docx", "pdf", "txt", "xlsx", "xls", "md", "csv", "pptx", "ppt"],
    accept_multiple_files=True
)

st.markdown("---")

# Step 3: Process
st.markdown('<div class="step-header"><div class="step-number">3</div><div class="step-title">提取数据</div></div>', unsafe_allow_html=True)

if not headers:
    st.warning("请先在上方输入表头")
elif not uploaded_files:
    st.warning("请上传至少一个文件")
elif provider != "Ollama (本地)" and not api_key:
    st.warning(f"请在系统环境变量中设置 API Key")
else:
    st.success(f"已就绪：{len(headers)} 个表头 × {len(uploaded_files)} 个文件")

    if st.button("🔍 开始智能提取", type="primary"):
        progress_bar = st.progress(0)
        status_text = st.empty()

        all_extracted = []
        source_files = []

        for i, uploaded_file in enumerate(uploaded_files):
            status_text.text(f"正在处理: {uploaded_file.name} ...")

            # Save file temporarily to parse
            temp_path = os.path.join("data", uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            try:
                # 1. Parse document content
                content = get_document_content(temp_path)

                # 2. AI extraction based on user-defined headers
                status_text.text(f"正在用 AI 提取数据: {uploaded_file.name} ...")
                # Determine provider name for AI engine
                provider_name = "Ollama"
                secret_key = None  # For Baidu only
                
                if provider == "DeepSeek (线上)":
                    provider_name = "DeepSeek"
                elif provider == "Moonshot (线上)":
                    provider_name = "Moonshot"
                elif provider == "智谱 AI (线上)":
                    provider_name = "Zhipu"
                elif provider == "火山引擎 (线上)":
                    provider_name = "Volcengine"
                elif provider == "腾讯云 (线上)":
                    provider_name = "Hunyuan"
                    secret_key = os.environ.get("TENCENT_SECRET_KEY", "")
                elif provider == "硅基流动 (线上)":
                    provider_name = "SiliconFlow"
                elif provider == "商汤 MINIMAX (线上)":
                    provider_name = "MINIMAX"
                elif provider == "阿里云通义 (线上)":
                    provider_name = "Alibaba"
                elif provider == "百度智能云 (线上)":
                    provider_name = "Baidu"
                    secret_key = os.environ.get("QIANFAN_SECRET_KEY", "")
                elif provider == "Agnes AI (线上)":
                    provider_name = "Agnes"
                
                # Get header descriptions from session state
                header_descriptions = st.session_state.get("header_descriptions", {})
                
                extracted = extract_by_headers(
                    content, 
                    headers, 
                    model_name=model_name,
                    provider=provider_name,
                    api_key=api_key,
                    base_url=base_url,
                    secret_key=secret_key,
                    header_descriptions=header_descriptions
                )

                # Add source file info to extracted data
                extracted["来源文件"] = uploaded_file.name
                all_extracted.append(extracted)
                source_files.append(uploaded_file.name)

            except Exception as e:
                st.error(f"处理 {uploaded_file.name} 时出错: {str(e)}")
                # Add empty extraction on error
                empty = {h: None for h in headers}
                empty["来源文件"] = uploaded_file.name
                all_extracted.append(empty)
                source_files.append(uploaded_file.name)

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            progress_bar.progress((i + 1) / len(uploaded_files))

        status_text.text("✅ 处理完成！")

        # Align and merge multi-value results
        # Include "来源文件" as an extra column
        full_headers = headers + ["来源文件"]
        all_rows = merge_results(all_extracted, full_headers)
        
        # Process computed columns if any header descriptions define formulas
        header_descriptions = st.session_state.get("header_descriptions", {})
        if header_descriptions and all_rows:
            status_text.text("正在计算计算列...")
            all_rows = process_computed_columns(headers, header_descriptions, all_rows)

        # Save to session state
        st.session_state.results = all_rows
        st.session_state.result_headers = full_headers
        st.session_state.source_files = source_files

# ── Display Results ──────────────────────────────────────────

if "results" in st.session_state and st.session_state.results:
    st.markdown("---")
    st.subheader("📊 提取结果")
    st.caption("A1 = 序号 | 表头横向排列 | 您可以直接编辑表格内容")

    result_headers = st.session_state.result_headers
    display_columns = ["序号"] + result_headers

    df = pd.DataFrame(st.session_state.results)
    # Ensure column order
    df = df[[c for c in display_columns if c in df.columns]]

    edited_df = st.data_editor(df, num_rows="dynamic", width="stretch")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    # Archive to database
    if col1.button("✅ 确认归档"):
        rows_to_save = edited_df.to_dict(orient="records")
        header_descriptions = st.session_state.get("header_descriptions", {})
        save_extraction(
            headers=result_headers,
            rows=rows_to_save,
            source_files=st.session_state.get("source_files", []),
            header_descriptions=header_descriptions
        )
        st.success("✅ 数据已成功归档到本地数据库")

    # Export as Excel
    if col2.button("📥 导出 Excel"):
        # 1. Get last export path from DB
        last_dir = get_setting("last_export_dir", os.path.expanduser("~"))
        
        # 2. Open tkinter dialog
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Bring dialog to front
        
        file_path = filedialog.asksaveasfilename(
            initialdir=last_dir,
            initialfile="data_flow_export.xlsx",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            parent=root,
            title="选择保存位置"
        )
        
        root.destroy()
        
        if file_path:
            try:
                # 3. Save file directly
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    edited_df.to_excel(writer, index=False, sheet_name='提取结果')
                
                # 4. Save path to DB
                new_dir = os.path.dirname(file_path)
                update_setting("last_export_dir", new_dir)
                
                st.success(f"✅ 文件已成功导出至: {file_path}")
            except Exception as e:
                st.error(f"❌ 导出失败: {str(e)}")
        else:
            st.info("已取消导出")

    # Clear results
    if col3.button("🗑️ 清空结果"):
        st.session_state.results = []
        st.session_state.result_headers = []
        st.session_state.source_files = []
        st.rerun()

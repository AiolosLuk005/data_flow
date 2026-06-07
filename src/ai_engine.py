from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
import re
import json


def extract_by_headers(text: str, headers: list[str], 
                       model_name: str = "deepseek-r1:7b",
                       provider: str = "Ollama",
                       base_url: str = None,
                       api_key: str = None,
                       secret_key: str = None,
                       header_descriptions: dict = None):
    """
    Use LLM to extract data from document text based on user-defined table headers.

    Args:
        text: The document text content.
        headers: A list of table header names provided by the user.
        model_name: The model name to use.
        provider: "Ollama", "DeepSeek", "Alibaba", or "Baidu".
        base_url: Custom API base URL (optional).
        api_key: API key for online provider (optional).
        secret_key: Secret key for Baidu Qianfan (optional).
        header_descriptions: Optional dict mapping header names to detailed descriptions.

    Returns:
        A dict where keys are header names and values are extracted data
        (str or list[str] for multiple matches).
    """
    import os
    # --- Windows Environment Variable Force-Refresh ---
    if os.name == 'nt':
        try:
            import winreg
            env_vars_to_refresh = [
                'MOONSHOT_API_KEY', 'ZHIPUAI_API_KEY', 'VOLCENGINE_API_KEY',
                'VOLCENGINE_ENDPOINT_ID', 'TENCENT_SECRET_ID', 'TENCENT_SECRET_KEY',
                'TENCENT_APP_ID', 'SILICONFLOW_API_KEY', 'MINIMAX_API_KEY',
                'DASHSCOPE_API_KEY', 'QIANFAN_ACCESS_KEY', 'QIANFAN_SECRET_KEY',
                'DEEPSEEK_API_KEY'
            ]
            # Search logic: check User first, then System
            paths = [
                (winreg.HKEY_CURRENT_USER, r'Environment'),
                (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
            ]
            for hkey, path in paths:
                try:
                    with winreg.OpenKey(hkey, path) as key:
                        for var_name in env_vars_to_refresh:
                            try:
                                val, _ = winreg.QueryValueEx(key, var_name)
                                os.environ[var_name] = val
                            except FileNotFoundError:
                                pass
                except Exception:
                    pass
        except Exception:
            pass

    if provider in ["DeepSeek", "Moonshot", "Volcengine", "SiliconFlow", "MINIMAX", "Agnes"] or (base_url and api_key):
        # OpenAI-compatible API providers (including custom ones)
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError(
                f"{provider} 功能需要安装 langchain-openai。\n"
                "请在终端运行: pip install langchain-openai"
            )
        
        # Default base URLs if not provided
        default_urls = {
            "DeepSeek": "https://api.deepseek.com",
            "Moonshot": "https://api.moonshot.cn/v1",
            "Volcengine": "https://ark.cn-beijing.volces.com/api/v3",
            "SiliconFlow": "https://api.siliconflow.cn/v1",
            "MINIMAX": "https://api.minimax.chat/v1",
            "Agnes": "https://apihub.agnes-ai.com/v1"
        }
        url = base_url or default_urls.get(provider)
        
        # Defensive stripping and validation
        env_key_name = f"{provider.upper()}_API_KEY" if provider in default_urls else "CUSTOM_API_KEY"
        current_api_key = (api_key or os.environ.get(env_key_name, "")).strip()
        if current_api_key.startswith("Bearer "):
            current_api_key = current_api_key.replace("Bearer ", "").strip()
        
        llm = ChatOpenAI(
            model=model_name,
            temperature=0,
            base_url=url,
            api_key=current_api_key,
            model_kwargs={"response_format": {"type": "json_object"}} if "r1" not in model_name.lower() else {}
        )
    
    elif provider == "Hunyuan":
        # Tencent Hunyuan
        try:
            from langchain_community.chat_models import ChatHunyuan
        except ImportError:
            raise ImportError(
                "腾讯混元功能需要安装 langchain-community。\n"
                "请在终端运行: pip install langchain-community"
            )
        
        import os
        # Use provided keys or fallback to env
        sid = (api_key or os.environ.get("TENCENT_SECRET_ID", "")).strip()
        skey = (secret_key or os.environ.get("TENCENT_SECRET_KEY", "")).strip()
        appid = os.environ.get("TENCENT_APP_ID", "").strip()
        
        llm = ChatHunyuan(
            model=model_name,
            hunyuan_secret_id=sid,
            hunyuan_secret_key=skey,
            hunyuan_app_id=appid,
            temperature=0.01
        )
    
    elif provider == "Zhipu":
        # Zhipu AI (GLM)
        try:
            from langchain_community.chat_models import ChatZhipuAI
        except ImportError:
            raise ImportError(
                "智谱AI功能需要安装 langchain-community 和 zhipuai。\n"
                "请在终端运行: pip install langchain-community zhipuai"
            )
        llm = ChatZhipuAI(
            model=model_name,
            api_key=api_key,
            temperature=0.01
        )
    
    elif provider == "Alibaba":
        # Alibaba Cloud (通义千问) uses DashScope API
        try:
            from langchain_community.chat_models import ChatTongyi
        except ImportError:
            raise ImportError(
                "阿里云通义功能需要安装 langchain-community。\n"
                "请在终端运行: pip install langchain-community dashscope"
            )
        # ChatTongyi expects the API key via DASHSCOPE_API_KEY env or parameter
        import os
        os.environ["DASHSCOPE_API_KEY"] = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        llm = ChatTongyi(
            model=model_name,
            temperature=0,
            # Request JSON output (tongyi supports structured output modes)
            model_kwargs={"result_format": "message"}
        )
    elif provider == "Baidu":
        # Baidu Qianfan via IAM Access Key + Secret Key
        try:
            from langchain_community.chat_models import QianfanChatEndpoint
        except ImportError:
            raise ImportError(
                "百度智能云千帆功能需要安装 langchain-community 和 qianfan。\n"
                "请在终端运行: pip install langchain-community qianfan"
            )
        import os
        
        # Provider-specific logic will use os.environ which we refreshed at the top
        
        # Override with explicit params if provided
        s_ak = (api_key or os.environ.get("QIANFAN_ACCESS_KEY", "")).strip()
        s_sk = (secret_key or os.environ.get("QIANFAN_SECRET_KEY", "")).strip()
        
        if s_ak:
            os.environ["QIANFAN_ACCESS_KEY"] = s_ak
        if s_sk:
            os.environ["QIANFAN_SECRET_KEY"] = s_sk
        
        # Clear old-style env vars to prevent SDK confusion
        os.environ.pop("QIANFAN_AK", None)
        os.environ.pop("QIANFAN_SK", None)
        
        llm = QianfanChatEndpoint(
            model=model_name,
            temperature=0.01,
        )
    
    else:
        # Default to Ollama
        url = base_url or "http://127.0.0.1:11434"
        llm = ChatOllama(model=model_name, temperature=0, base_url=url, format="json")

    # ── Stage 1: Chunk and Search ─────────────────────────────
    from src.document_parser import chunk_text, search_relevant_chunks
    
    # Filter out computed columns (handled by formula_engine, not LLM)
    from src.formula_engine import FormulaParser
    formula_parser = FormulaParser()
    extraction_headers = []
    for h in headers:
        desc = (header_descriptions or {}).get(h, "")
        if not formula_parser.is_computed_column(desc):
            extraction_headers.append(h)
    
    # If all headers are computed, nothing to extract
    if not extraction_headers:
        return {h: None for h in headers}
    
    # Provider-specific limits (ERNIE 8K models have smaller context windows)
    if provider == "Baidu":
        max_text_len = 3000   # ~1500 tokens for Chinese text
        top_k_chunks = 3
    elif provider == "Ollama":
        # Local models perform better with slightly less context to avoid "losing the middle"
        max_text_len = 5000
        top_k_chunks = 4
    else:
        max_text_len = 8000
        top_k_chunks = 5
    
    # Chunk the document
    chunks = chunk_text(text, chunk_size=1500, overlap=300)
    
    # Find most relevant chunks
    relevant_chunks = search_relevant_chunks(
        chunks, extraction_headers, header_descriptions, top_k=top_k_chunks
    )
    
    # Assemble focused text from relevant chunks
    focused_text = "\n\n---\n\n".join(relevant_chunks)
    
    # Safety trim based on provider limits
    if len(focused_text) > max_text_len:
        focused_text = focused_text[:max_text_len]

    # --- Prepare Headers String ---
    header_descriptions = header_descriptions or {}
    headers_list = []
    for h in extraction_headers:
        if h in header_descriptions and header_descriptions[h]:
            headers_list.append(f"  - {h}\n    说明: {header_descriptions[h]}")
        else:
            headers_list.append(f"  - {h}")
    headers_str = "\n".join(headers_list)

    # --- Optimized Prompt Engineering ---
    is_reasoning_model = "r1" in model_name.lower()
    
    if provider == "Ollama":
        # Specific prompt for local models: More concise + explicit schema + few-shot
        system_prompt = (
            "你是一个高效的数据提取专家。请从提供的文档片段中提取信息并以 JSON 格式输出。\n"
            "### 提取规则：\n"
            "1. 严格对应表头名称，不要修改 key。\n"
            "2. 如果信息不存在，value 设为 null。\n"
            "3. 如果表头有说明，请务必遵守。\n"
            "4. 输出必须是纯 JSON，不要包含任何解释性文字。\n"
        )
        
        if is_reasoning_model:
            system_prompt += "5. 你是推理模型，请在 <think> 标签内进行分析，但在 <think> 之外只输出最终的 JSON 对象。\n"
        
        # Use placeholders {headers} and {text} instead of pre-interpolating with f-string
        # Escaping curly braces for LangChain ChatPromptTemplate: 
        # {{ and }} become literal { and } in the final prompt.
        user_prompt = (
            "### 示例：\n"
            "表头：项目名称, 投资额\n"
            "文本：建设年产20万吨水泥厂，总投资5000万元。\n"
            "输出：{{\"项目名称\": \"年产20万吨水泥厂\", \"投资额\": \"5000万元\"}}\n\n"
            "### 当前待处理任务：\n"
            "表头列表：\n{headers}\n\n"
            "文档片段：\n{text}\n\n"
            "请直接输出结果 JSON："
        )
    else:
        # Prompt for powerful online models
        system_prompt = (
            "你是一个专业的数据提取助手。你的任务是根据表头列表，从文档中**精确提取**对应的信息。\n\n"
            "⚠️ 关键原则：先分析，再提取。\n\n"
            "请严格按照以下步骤操作：\n\n"
            "**第一步：分析上下文**\n"
            "找出数值出现的关键词（如：送审、核定、静态、动态等）。\n\n"
            "**第二步：逐个匹配表头**\n"
            "根据表头说明中的限定词，在文档中定位最正确的数据。如表头要求“送审”，则忽略“核定”的数据。\n\n"
            "**第三步：输出 JSON**\n"
            "  - 你的最终输出必须是且仅是一个合法的 JSON 对象。\n"
            "  - JSON 的 key 必须与表头名称完全一致。\n"
            "  - 提取数值时保留单位。"
        )
        user_prompt = (
            "以下是表头列表：\n{headers}\n\n"
            "以下是文档内容：\n{text}\n\n"
            "请执行提取任务并输出 JSON："
        )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt)
    ])

    chain = prompt | llm

    try:
        response = chain.invoke({"headers": headers_str, "text": focused_text})
        raw_content = response.content if hasattr(response, 'content') else str(response)

        # --- Robust JSON Extraction ---
        # 1. Strip <think> blocks if present
        content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()

        # 2. Extract potential JSON string
        json_str = ""
        # Try markdown code fences first (non-greedy)
        json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
        if json_block_match:
            json_str = json_block_match.group(1).strip()
        else:
            # Fallback: Find the first { and the last }
            first_brace = content.find('{')
            last_brace = content.rfind('}')
            if first_brace != -1 and last_brace != -1:
                json_str = content[first_brace : last_brace + 1]
            else:
                json_str = content

        # 3. Parse with extra data handling
        try:
            # First try direct load
            result = json.loads(json_str)
        except json.JSONDecodeError:
            # If "Extra data", use raw_decode to pick the first valid object
            try:
                decoder = json.JSONDecoder()
                result, _ = decoder.raw_decode(json_str)
            except Exception as e:
                # If still failing, re-raise to be caught by main try block
                raise ValueError(f"无法从响应中解析 JSON。原始内容: {content[:100]}...")

        # Ensure all headers exist in result (fill missing with None)
        for h in headers:
            if h not in result:
                result[h] = None

        return result

    except Exception as e:
        print(f"AI Extraction failed for {model_name}: {e}")
        # Return empty template on failure
        return {h: None for h in headers}


if __name__ == "__main__":
    pass

# Data_Flow 代码修改任务

## 背景
Data_Flow (`D:\Data-Lab\Data_flow`) 是一个从电力工程 docx 文档中提取表格数据的 Streamlit 应用。经过 Hermes 测试发现，当前代码有 4 个问题需要修复。

## 修改任务（按优先级）

### 任务 1：[严重] Chunking 遗漏文档首段
**文件**: `src/document_parser.py`
**函数**: `search_relevant_chunks()`

**问题**: 关键词评分机制导致文档第一段（含项目名称+评审日期）被过滤。

**修改**: 在函数返回前，检查 `chunks[0]` 是否已在结果中，不存在则强制插入开头。
保持原有评分逻辑不变，只加几行代码。

**期望效果**: 传入 chunks=[chunkA, chunkB, ...], headers=[...]，
如果 chunks[0] 不在 top_k 结果中，插入到结果最前面。

### 任务 2：[中] DeepSeek/AI 模型 prompt 优化
**文件**: `src/ai_engine.py`
**位置**: `extract_by_headers()` 函数中在线模型的 system_prompt (第273-287行)

**问题**: 当前 prompt 没有指导模型从电力工程投资估算表的"合计行"查找数据。

**修改**: 在 system_prompt 末尾添加：
```
5. 投资金额必须在【投资估算汇总表】或【投资估算对比表】的"合计"行查找。
6. "送审动态投资"列在"送审"表头下，"审定动态投资"列在"审定"表头下。
7. "送审静态投资"和"审定静态投资"在投资估算汇总表的对应列查找。
8. 取合计行的数据，不要取分项数据。
```

### 任务 3：[中] max_text_len 放宽
**文件**: `src/ai_engine.py`
**位置**: 第207-215行

**问题**: DeepSeek 限制 max_text_len=8000，部分文档达 38000 字被截断。

**修改**: 
```python
if provider == "Baidu":
    max_text_len = 3000
elif provider == "Ollama":
    max_text_len = 5000
else:
    max_text_len = 30000  # 从 8000 改为 30000，利用 DeepSeek 的长上下文
```

### 任务 4：[低] 项目名称清洗
**文件**: `app.py`
**位置**: `merge_results()` 调用之后（约第728行），`st.session_state.results` 赋值之前

**问题**: 提取的项目名称带"可行性研究报告评审意见"等冗余后缀。

**修改**: 在 merge_results 之后添加清洗：
```python
import re
for row in all_rows:
    if "项目名称" in row and row["项目名称"]:
        name = row["项目名称"]
        # 清洗冗余后缀
        name = re.sub(r'(可行性研究)?报告评审意见$', '', name)
        name = re.sub(r'评审意见$', '', name)
        row["项目名称"] = name.strip()
```

## 验证方法
运行测试脚本验证修改效果：
```bash
cd /d/Data-Lab/Data_flow/tests
/D/Data-Lab/Data_flow/Data_Flow_Dist/bin/python.exe test_extraction.py
```

## 模型选择说明
- 默认使用 Ollama 本地模型（qwen3.5:9b）
- 可在左侧栏切换为 gemma4:12b 或 DeepSeek (线上)
- DeepSeek 需设置环境变量 `DEEPSEEK_API_KEY`

## 已打开的文件
- `src/document_parser.py`
- `src/ai_engine.py`
- `app.py`

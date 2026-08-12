#!/usr/bin/env python
"""Test Data_flow extraction with DeepSeek API on all 9 projects, compare with sample."""
import os, sys, time, json, re

# Configure stdout to use UTF-8 to prevent UnicodeEncodeError on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PYTHON = r"D:\Data-Lab\Data_flow\Data_Flow_Dist\bin\python.exe"
sys.path.insert(0, r"D:\Data-Lab\Data_flow")

# Read DeepSeek key from environment (set in bash)
deepseek_key = os.environ.get("MY_DEEPSEEK_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
use_ollama = False
if not deepseek_key:
    print("WARNING: No DeepSeek API key found. Falling back to local Ollama (gemma4:12b) for testing.")
    use_ollama = True
else:
    os.environ["DEEPSEEK_API_KEY"] = deepseek_key

from src.document_parser import get_document_content

# Monkey-patch chunking to always include first chunk (has project name and review date)
import src.document_parser as dp
original_search = dp.search_relevant_chunks
def patched_search(chunks, headers, header_descriptions=None, top_k=5):
    result = original_search(chunks, headers, header_descriptions, top_k)
    if chunks and chunks[0] not in result:
        result.insert(0, chunks[0])
    return result[:top_k]
dp.search_relevant_chunks = patched_search

# Target columns for extraction (A, C, H, I, J, K)
headers = [
    "项目名称", 
    "可研评审时间", 
    "可研估算送审动态投资", 
    "可研估算审定动态投资", 
    "可研估算送审静态投资", 
    "可研估算审定静态投资"
]

header_descriptions = {
    "项目名称": "项目的完整名称，从文档开头第一行提取，不要自己编造",
    "可研评审时间": "可行性研究报告评审会议的召开日期，提取第一段中的日期，格式YYYY-MM-DD",
    "可研估算送审动态投资": "送审的可研估算动态投资金额，在投资估算汇总表或对比表的合计行中找'送审动态投资'或'送审'列的值，单位为万元",
    "可研估算审定动态投资": "审定的可研估算动态投资金额，在投资估算汇总表或对比表的合计行中找'审定动态投资'或'审定'列的值，单位为万元",
    "可研估算送审静态投资": "送审的可研估算静态投资金额，在投资估算汇总表的合计行找'静态投资'列，单位为万元",
    "可研估算审定静态投资": "审定的可研估算静态投资金额，在投资估算汇总表的合计行找'审定静态投资'或对应列，单位为万元"
}

from src.ai_engine import extract_by_headers

# Input files
base_input = r"D:\PowerGrid AI Workspace\data\work_materials\001_input_评审意见\001_可行性研究评审意见"
files = sorted([f for f in os.listdir(base_input) if f.endswith(".docx") and not f.startswith("~$")])

print(f"Found {len(files)} files to process:")
for f in files:
    project_name = f.replace("可行性研究报告评审意见.docx", "").strip()
    print(f"  - {project_name}")

# Run extraction
all_results = []
for idx, filename in enumerate(files):
    filepath = os.path.join(base_input, filename)
    project_name = filename.replace("可行性研究报告评审意见.docx", "").strip()
    
    print(f"\n{'='*60}")
    print(f"[{idx+1}/{len(files)}] {project_name}")
    print(f"{'='*60}")
    
    try:
        content = get_document_content(filepath)
        print(f"  Doc length: {len(content)} chars")
        
        start = time.time()
        if use_ollama:
            result = extract_by_headers(
                content, headers,
                model_name="gemma4:12b",
                provider="Ollama",
                api_key=None,
                base_url="http://127.0.0.1:11434",
                header_descriptions=header_descriptions
            )
        else:
            result = extract_by_headers(
                content, headers,
                model_name="deepseek-chat",
                provider="DeepSeek",
                api_key=deepseek_key,
                base_url="https://api.deepseek.com",
                header_descriptions=header_descriptions
            )
        elapsed = time.time() - start
        
        result["来源文件"] = filename
        all_results.append(result)
        
        for h in headers:
            val = result.get(h)
            print(f"  {h}: {val}")
        print(f"  ⏱ {elapsed:.1f}s")
        
    except Exception as e:
        print(f"  ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        result = {h: None for h in headers}
        result["来源文件"] = filename
        all_results.append(result)

print(f"\n\n{'='*60}")
print("ALL RESULTS SUMMARY")
print(f"{'='*60}")
print(json.dumps(all_results, ensure_ascii=False, indent=2))

# Compare with sample
sample_path = r"D:\PowerGrid AI Workspace\data\work_materials\002_process_信息提取\001_可行性研究评审数据 - 样本.xlsx"
import pandas as pd
df_sample = pd.read_excel(sample_path, sheet_name="Sheet1", header=0)
print(f"\n\n{'='*60}")
print("COMPARISON WITH SAMPLE")
print(f"{'='*60}")

for idx, filename in enumerate(files):
    proj_name = filename.replace("可行性研究报告评审意见.docx", "").strip()
    match_row = df_sample[df_sample["项目名称"].str.contains(proj_name[:6], na=False)]
    
    print(f"\n--- {proj_name} ---")
    result = all_results[idx]
    
    if match_row.empty:
        print(f"  ⚠️  No matching project in sample")
        continue
    
    row = match_row.iloc[0]
    
    # Compare: 项目名称
    ai_name = result.get("项目名称", "")
    sample_name = row["项目名称"]
    if ai_name and sample_name:
        # Remove whitespace differences
        ai_clean = ai_name.replace(" ", "").replace("　", "")
        sample_clean = str(sample_name).replace(" ", "").replace("　", "")
        match_pct = sum(1 for a, b in zip(ai_clean, sample_clean) if a == b) / max(len(sample_clean), 1) * 100 if sample_clean else 0
        if match_pct < 60:
            print(f"  ⚠️ 项目名称偏差: AI='{ai_name}' vs 样本='{sample_name}' (匹配度{match_pct:.0f}%)")
        else:
            print(f"  ✅ 项目名称: {ai_name}")
    
    # Compare date
    ai_date = result.get("可研评审时间", "")
    sample_date = str(row["可研评审时间"])[:10] if pd.notna(row["可研评审时间"]) else ""
    if ai_date and sample_date:
        if ai_date[:10] == sample_date[:10]:
            print(f"  ✅ 可研评审时间: {ai_date}")
        else:
            print(f"  ⚠️ 可研评审时间偏差: AI='{ai_date}' vs 样本='{sample_date}'")
    elif not ai_date:
        print(f"  ❌ 可研评审时间: 未提取 (样本='{sample_date}')")
    
    # Compare investment amounts
    inv_fields = [
        ("可研估算送审动态投资", "可研估算送审动态投资"),
        ("可研估算审定动态投资", "可研估算审定动态投资"),
        ("可研估算送审静态投资", "可研估算送审静态投资"),
        ("可研估算审定静态投资", "可研估算审定静态投资"),
    ]
    for ai_field, sample_field in inv_fields:
        ai_val = result.get(ai_field, "")
        sample_val = str(row[sample_field]) if pd.notna(row[sample_field]) else ""
        # Normalize: remove units, spaces
        import re as _re
        ai_num = _re.sub(r'[^\d.￥万元]', '', str(ai_val or ""))
        sample_num = _re.sub(r'[^\d.]', '', str(sample_val))
        try:
            ai_f = float(ai_num) if ai_num else None
        except:
            ai_f = None
        try:
            sample_f = float(sample_num) if sample_num else None
        except:
            sample_f = None
        if ai_f and sample_f:
            diff_pct = abs(ai_f - sample_f) / sample_f * 100 if sample_f else 0
            if diff_pct < 2:
                print(f"  ✅ {ai_field}: AI={ai_val} | 样本={sample_val}")
            else:
                print(f"  ⚠️ {ai_field}偏差{diff_pct:.1f}%: AI={ai_val} vs 样本={sample_val}")
        elif not ai_f:
            print(f"  ❌ {ai_field}: 未提取 (样本='{sample_val}')")

print(f"\n{'='*60}")
print("TEST COMPLETE")
print(f"{'='*60}")

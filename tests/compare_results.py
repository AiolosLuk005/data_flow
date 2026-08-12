#!/usr/bin/env python
"""Compare already-extracted results with sample."""
import os, json, re, sys

import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)

# The extraction results from the test
results = [
    {"项目名称": "110千伏千叶输变电工程可行性研究报告", "可研评审时间": "2026-05-20", "可研估算送审动态投资": "14305.25万元", "可研估算审定动态投资": "12832.88万元", "可研估算送审静态投资": "14061.20万元", "可研估算审定静态投资": "12614.08万元", "来源": "110千伏千叶输变电工程"},
    {"项目名称": "110千伏名美（易为）输变电工程（电气分册）可行性研究报告评审意见", "可研评审时间": "2026-03-13", "可研估算送审动态投资": "11768.34万元", "可研估算审定动态投资": "8854.52万元", "可研估算送审静态投资": "11571.97万元", "可研估算审定静态投资": "8705.90万元", "来源": "110千伏名美（易为）输变电工程（电气分册）"},
    {"项目名称": "110千伏文冲站扩建第三台主变工程可行性研究报告评审意见", "可研评审时间": "2026-01-30", "可研估算送审动态投资": "2002.21万元", "可研估算审定动态投资": "2135.29万元", "可研估算送审静态投资": "1982.18万元", "可研估算审定静态投资": "2114.70万元", "来源": "110千伏文冲站扩建第三台主变工程"},
    {"项目名称": "110千伏榄核扩建主变工程", "可研评审时间": "2026-03-20", "可研估算送审动态投资": "3372.81万元", "可研估算审定动态投资": "3530.28万元", "可研估算送审静态投资": "3331.6万元", "可研估算审定静态投资": "3487.29万元", "来源": "110千伏榄核扩建主变工程"},
    {"项目名称": "110千伏长隆输变电工程（电气分册）", "可研评审时间": "2026-03-16", "可研估算送审动态投资": "9459.35万元", "可研估算审定动态投资": "9373.04万元", "可研估算送审静态投资": "9297.19万元", "可研估算审定静态投资": "9212.23万元", "来源": "110千伏长隆输变电工程(电气分册)"},
    {"项目名称": "220千伏环西输变电工程（第三分册）", "可研评审时间": "2025-11-20", "可研估算送审动态投资": "20310.03万元", "可研估算审定动态投资": "18799.33万元", "可研估算送审静态投资": "19944.69万元", "可研估算审定静态投资": "18461.15万元", "来源": "220千伏环西输变电工程（第三分册）"},
    {"项目名称": "220千伏西部输变电工程（第一分册）", "可研评审时间": "2026-04-08", "可研估算送审动态投资": "99987.90万元", "可研估算审定动态投资": "86957.41万元", "可研估算送审静态投资": "98356.27万元", "可研估算审定静态投资": "85534.47万元", "来源": "220千伏西部输变电工程（第一分册）"},
    {"项目名称": "傍海（番南）站配套220千伏线路工程（第二分册）", "可研评审时间": "2026-05-25", "可研估算送审动态投资": "50363.73万元", "可研估算审定动态投资": "48306.64万元", "可研估算送审静态投资": "49429.05万元", "可研估算审定静态投资": "47410.84万元", "来源": "傍海（番南）站配套220千伏线路工程（第二分册）"},
    {"项目名称": "广州恒运新型混合储能示范电站项目配套间隔工程", "可研评审时间": "2026-02-03", "可研估算送审动态投资": "483.14万元", "可研估算审定动态投资": "473.27万元", "可研估算送审静态投资": "478.27万元", "可研估算审定静态投资": "468.47万元", "来源": "广州恒运新型混合储能示范电站项目配套间隔工程"},
]

sample_path = r"D:\PowerGrid AI Workspace\data\work_materials\002_process_信息提取\001_可行性研究评审数据 - 样本.xlsx"
df_sample = pd.read_excel(sample_path, sheet_name="Sheet1", header=0)

def extract_num(s):
    """Extract numeric value from string like '14305.25万元'"""
    if not s:
        return None
    m = re.search(r'(\d+\.?\d*)', str(s))
    return float(m.group(1)) if m else None

def parse_date(s):
    """Parse date from various formats"""
    if not s:
        return ""
    s = str(s).strip()
    # Clean up: "2026-05-25 00:00:00" -> "2026-05-25"
    s = s[:10]
    return s

print("=" * 150)
print(f"{'项目名称':<30} {'字段':<25} {'AI提取值':<20} {'样本值':<20} {'结果':<8} {'偏差%':<8}")
print("=" * 150)

total_fields = 0
correct_fields = 0

for r in results:
    proj = r["来源"]
    sample_row = None
    for i, row in df_sample.iterrows():
        sn = str(row["项目名称"]).replace(" ", "").replace("　", "")
        pn = proj.replace(" ","").replace("　","")
        # Fuzzy match: first 8 chars
        if sn[:8] == pn[:8]:
            sample_row = row
            break
    
    if sample_row is None:
        continue
    
    # Compare fields
    fields_to_check = [
        ("项目名称", r["项目名称"], str(sample_row["项目名称"]), "match_name"),
        ("可研评审时间", r["可研评审时间"], str(sample_row["可研评审时间"])[:10] if pd.notna(sample_row["可研评审时间"]) else "", "match_exact"),
        ("可研估算送审动态投资", r["可研估算送审动态投资"], str(sample_row.get("可研估算送审动态投资", "")), "match_num"),
        ("可研估算审定动态投资", r["可研估算审定动态投资"], str(sample_row.get("可研估算审定动态投资", "")), "match_num"),
        ("可研估算送审静态投资", r["可研估算送审静态投资"], str(sample_row.get("可研估算送审静态投资", "")), "match_num"),
        ("可研估算审定静态投资", r["可研估算审定静态投资"], str(sample_row.get("可研估算审定静态投资", "")), "match_num"),
    ]
    
    for field, ai_val, sample_val, match_type in fields_to_check:
        total_fields += 1
        ai_s = str(ai_val).replace("万元", "").strip()
        sample_s = str(sample_val).replace("万元", "").replace(".0", "").strip()
        
        if match_type == "match_name":
            # Fuzzy compare project name
            ai_clean = ai_val.replace(" ", "")
            sample_clean = sample_val.replace(" ", "")
            if ai_clean == sample_clean:
                status = "✅"
                correct_fields += 1
                pct = ""
            elif ai_clean[:8] == sample_clean[:8]:
                status = "⚠️"
                pct = ""
            else:
                status = "❌"
                pct = ""
        elif match_type == "match_exact":
            if ai_s == sample_s:
                status = "✅"
                correct_fields += 1
                pct = ""
            else:
                status = "❌"
                pct = ""
        elif match_type == "match_num":
            ai_n = extract_num(ai_val)
            sample_n = extract_num(sample_val)
            if ai_n and sample_n:
                diff = abs(ai_n - sample_n) / sample_n * 100
                if diff < 0.5:
                    status = "✅"
                    correct_fields += 1
                    pct = f"{diff:.2f}%"
                elif diff < 2:
                    status = "⚠️"
                    pct = f"{diff:.2f}%"
                else:
                    status = "❌"
                    pct = f"{diff:.2f}%"
            else:
                status = "❓"
                pct = f"AI={ai_val} S={sample_val}"
        
        proj_short = proj[:28]
        print(f"{proj_short:<30} {field:<25} {ai_s[:18]:<20} {sample_s[:18]:<20} {status:<8} {pct:<8}")

print("=" * 150)
print(f"\n总计: {total_fields} 个字段, 正确: {correct_fields} 个 ({correct_fields/total_fields*100:.1f}%)")

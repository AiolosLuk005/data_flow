def align_multi_values(extracted_data: dict, headers: list[str]) -> list[dict]:
    """
    Align extracted data into rows for table display.

    If any header has a list value, expand into multiple rows.
    Non-list values are repeated across all rows.

    Args:
        extracted_data: Dict with header names as keys, values are str/list/None.
        headers: The ordered list of user-defined headers.

    Returns:
        A list of dicts, each representing one table row (with "序号" column).
    """
    # Determine the maximum number of rows needed
    max_rows = 1
    for h in headers:
        val = extracted_data.get(h)
        if isinstance(val, list):
            max_rows = max(max_rows, len(val))

    rows = []
    for i in range(max_rows):
        row = {"序号": i + 1}
        for h in headers:
            val = extracted_data.get(h)
            if isinstance(val, list):
                row[h] = val[i] if i < len(val) else ""
            elif val is None:
                row[h] = ""
            else:
                row[h] = str(val)
        rows.append(row)

    return rows


def merge_results(all_extracted: list[dict], headers: list[str]) -> list[dict]:
    """
    Merge extraction results from multiple files into a single row list.

    Each file's extraction is expanded via align_multi_values, then all rows
    are concatenated and re-numbered sequentially.

    Args:
        all_extracted: List of extracted dicts (one per file).
        headers: The ordered list of user-defined headers.

    Returns:
        A combined list of row dicts with sequential "序号".
    """
    all_rows = []
    for extracted in all_extracted:
        rows = align_multi_values(extracted, headers)
        all_rows.extend(rows)

    # Re-number sequentially
    for i, row in enumerate(all_rows):
        row["序号"] = i + 1

    return all_rows


if __name__ == "__main__":
    # Quick test
    test_data = {
        "项目名称": ["项目A", "项目B"],
        "投资金额": "1000万",
        "建设单位": "XX公司"
    }
    test_headers = ["项目名称", "投资金额", "建设单位"]
    result = align_multi_values(test_data, test_headers)
    for r in result:
        print(r)

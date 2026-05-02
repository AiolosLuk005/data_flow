import re
from typing import Dict, Any, List, Optional


class FormulaParser:
    """Parse and evaluate formulas for computed columns."""
    
    def __init__(self):
        # Pattern to detect computed column syntax: "计算列 = formula"
        self.computed_pattern = re.compile(r'^计算列\s*=\s*(.+)$', re.IGNORECASE)
    
    def is_computed_column(self, description: str) -> bool:
        """Check if a column description defines a computed column."""
        if not description:
            return False
        return bool(self.computed_pattern.match(description.strip()))
    
    def extract_formula(self, description: str) -> Optional[str]:
        """Extract the formula from a computed column description."""
        match = self.computed_pattern.match(description.strip())
        if match:
            return match.group(1).strip()
        return None
    
    def parse_number(self, value: Any) -> Optional[float]:
        """
        Parse a value to a number, handling Chinese units.
        
        Examples:
            "1200万元" -> 12000000.0
            "35.5公里" -> 35.5
            "1.2亿" -> 120000000.0
            "3500" -> 3500.0
        """
        if value is None or value == "":
            return None
        
        # Convert to string
        value_str = str(value).strip()
        
        # Handle empty or null strings
        if not value_str or value_str.lower() in ['null', 'none', 'nan']:
            return None
        
        # Remove common currency/unit symbols
        value_str = value_str.replace('元', '').replace('¥', '').replace('$', '')
        value_str = value_str.replace('公里', '').replace('km', '').replace('米', '')
        value_str = value_str.replace(',', '')  # Remove thousand separators
        
        # Handle Chinese number units
        multiplier = 1.0
        if '亿' in value_str:
            multiplier = 100000000
            value_str = value_str.replace('亿', '')
        elif '万' in value_str:
            multiplier = 10000
            value_str = value_str.replace('万', '')
        elif '千' in value_str:
            multiplier = 1000
            value_str = value_str.replace('千', '')
        
        # Try to parse the remaining number
        try:
            number = float(value_str.strip())
            return number * multiplier
        except (ValueError, TypeError):
            return None
    
    def evaluate_formula(self, formula: str, row_data: Dict[str, Any]) -> Optional[float]:
        """
        Evaluate a formula against row data.
        
        Args:
            formula: The formula string, e.g., "静态投资 + 动态投资"
            row_data: Dictionary of column values for this row
        
        Returns:
            Computed result or None if evaluation fails
        """
        # Replace column names with their values
        eval_expr = formula
        
        # Track which columns are referenced
        referenced_columns = []
        
        # Sort columns by length (longest first) to avoid partial matches
        sorted_columns = sorted(row_data.keys(), key=len, reverse=True)
        
        for col_name in sorted_columns:
            if col_name in eval_expr:
                referenced_columns.append(col_name)
                value = self.parse_number(row_data[col_name])
                
                # If any referenced value is None, return None
                if value is None:
                    return None
                
                # Replace column name with its numeric value
                # Use regex word boundary to avoid partial replacements
                pattern = re.escape(col_name)
                eval_expr = re.sub(f'(?<![\\w]){pattern}(?![\\w])', str(value), eval_expr)
        
        # Check if we have any column references left (unknown columns)
        # If so, the formula is invalid
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', eval_expr)
        if chinese_chars:
            print(f"Warning: Unknown column names in formula: {chinese_chars}")
            return None
        
        # Evaluate the expression
        try:
            # Only allow safe mathematical operations
            allowed_chars = set('0123456789+-*/()., ')
            if not all(c in allowed_chars for c in eval_expr):
                print(f"Warning: Formula contains invalid characters: {eval_expr}")
                return None
            
            result = eval(eval_expr, {"__builtins__": {}}, {})
            return float(result)
        except Exception as e:
            print(f"Error evaluating formula '{formula}': {e}")
            return None
    
    def format_result(self, value: Optional[float], reference_column: Optional[str] = None,
                     row_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Format a computed result with appropriate units.
        
        If a reference column is provided, try to match its units.
        """
        if value is None:
            return ""
        
        # Check if reference column has units
        if reference_column and row_data:
            ref_value = str(row_data.get(reference_column, ""))
            
            # Detect units in reference value
            if '万元' in ref_value or '万' in ref_value:
                return f"{value / 10000:.2f}万元"
            elif '亿元' in ref_value or '亿' in ref_value:
                return f"{value / 100000000:.2f}亿元"
            elif '千元' in ref_value or '千' in ref_value:
                return f"{value / 1000:.2f}千元"
            elif '元' in ref_value:
                return f"{value:.2f}元"
            elif '公里' in ref_value or 'km' in ref_value.lower():
                return f"{value:.2f}公里"
        
        # Default: return as-is with 2 decimal places
        return f"{value:.2f}"


def process_computed_columns(headers: List[str], 
                            header_descriptions: Dict[str, str],
                            rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process computed columns for all rows.
    
    Args:
        headers: List of all column headers
        header_descriptions: Dict mapping headers to their descriptions
        rows: List of row data dictionaries
    
    Returns:
        Updated rows with computed columns filled in
    """
    parser = FormulaParser()
    
    # Identify computed columns
    computed_columns = {}
    for header in headers:
        desc = header_descriptions.get(header, "")
        if parser.is_computed_column(desc):
            formula = parser.extract_formula(desc)
            if formula:
                computed_columns[header] = formula
    
    # If no computed columns, return as-is
    if not computed_columns:
        return rows
    
    # Process each row
    for row in rows:
        for col_name, formula in computed_columns.items():
            # Compute the value
            result = parser.evaluate_formula(formula, row)
            
            # Format and store the result
            if result is not None:
                # Try to match units from the first referenced column
                formatted = parser.format_result(result, None, row)
                row[col_name] = formatted
            else:
                row[col_name] = None
    
    return rows

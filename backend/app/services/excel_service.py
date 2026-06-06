"""Excel parsing service for node imports."""
import openpyxl
from typing import List, Tuple, Dict, Any
from io import BytesIO


REQUIRED_COLUMNS = ["nombre", "latitud", "longitud"]
MAX_ROWS = 10_000
VALID_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def validate_mime_type(mime_type: str) -> None:
    """Validate that the file is an .xlsx file by MIME type."""
    if mime_type != VALID_MIME_TYPE:
        raise ValueError("UNSUPPORTED_FILE_TYPE")


def parse_nodes_xlsx(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parse an .xlsx file containing node data.
    
    Args:
        file_bytes: Raw bytes of the .xlsx file
        
    Returns:
        Tuple of (valid_rows, errors)
        - valid_rows: List of dicts with keys: nombre, latitud, longitud, tipo
        - errors: List of dicts with keys: row, field, message
    """
    valid_rows = []
    errors = []
    
    try:
        workbook = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True)
        sheet = workbook.active
    except Exception as e:
        errors.append({"row": 0, "field": "file", "message": f"Invalid .xlsx file: {str(e)}"})
        return valid_rows, errors
    
    # Get headers from first row
    headers = []
    for cell in sheet[1]:
        headers.append(cell.value)
    
    # Validate required columns
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in headers]
    if missing_columns:
        errors.append({
            "row": 0, 
            "field": "columns", 
            "message": f"Missing required columns: {', '.join(missing_columns)}. Required: {', '.join(REQUIRED_COLUMNS)}"
        })
        return valid_rows, errors
    
    # Map column names to indices
    col_indices = {col: headers.index(col) for col in REQUIRED_COLUMNS}
    tipo_idx = headers.index("tipo") if "tipo" in headers else None
    
    row_num = 1  # 1-indexed for user-friendly error messages (header is row 1)
    
    for row in sheet.iter_rows(min_row=2, values_only=True):
        row_num += 1
        
        # Check row limit
        if row_num > MAX_ROWS + 1:
            errors.append({
                "row": row_num,
                "field": "row_count",
                "message": f"Maximum {MAX_ROWS} rows allowed. File has more rows."
            })
            break
        
        # Skip completely empty rows
        if all(cell is None for cell in row):
            continue
        
        row_errors = []
        
        # Parse required fields
        nombre = row[col_indices["nombre"]]
        latitud = row[col_indices["latitud"]]
        longitud = row[col_indices["longitud"]]
        
        # Validate nombre
        if not nombre or not str(nombre).strip():
            row_errors.append({"row": row_num, "field": "nombre", "message": "Nombre is required"})
        else:
            nombre = str(nombre).strip()
        
        # Validate latitud
        if latitud is None:
            row_errors.append({"row": row_num, "field": "latitud", "message": "Latitud is required"})
        else:
            try:
                lat = float(latitud)
                if lat < -90 or lat > 90:
                    row_errors.append({"row": row_num, "field": "latitud", "message": "Latitud must be between -90 and 90"})
                else:
                    latitud = lat
            except (ValueError, TypeError):
                row_errors.append({"row": row_num, "field": "latitud", "message": "Latitud must be a valid number"})
        
        # Validate longitud
        if longitud is None:
            row_errors.append({"row": row_num, "field": "longitud", "message": "Longitud is required"})
        else:
            try:
                lng = float(longitud)
                if lng < -180 or lng > 180:
                    row_errors.append({"row": row_num, "field": "longitud", "message": "Longitud must be between -180 and 180"})
                else:
                    longitud = lng
            except (ValueError, TypeError):
                row_errors.append({"row": row_num, "field": "longitud", "message": "Longitud must be a valid number"})
        
        # Parse optional tipo
        tipo = "city"
        if tipo_idx is not None and tipo_idx < len(row):
            tipo_val = row[tipo_idx]
            if tipo_val and str(tipo_val).strip():
                tipo_str = str(tipo_val).strip().lower()
                if tipo_str in ("city", "tower", "datacenter"):
                    tipo = tipo_str
                else:
                    row_errors.append({"row": row_num, "field": "tipo", "message": "Tipo must be 'city', 'tower', or 'datacenter'"})
        
        if row_errors:
            errors.extend(row_errors)
        else:
            valid_rows.append({
                "nombre": nombre,
                "latitud": latitud,
                "longitud": longitud,
                "tipo": tipo
            })
    
    return valid_rows, errors
# =====================================
# utils/exports.py — funzioni di esportazione (Excel + PDF)
# =====================================
from io import BytesIO
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from utils.formatting import fmt_date, safe_text
from utils.pdf_builder import SHTPDF


# =====================================
# 📘 ESPORTAZIONE IN EXCEL
# =====================================
def export_excel_contratti(df_ct, sel_id, rag_soc):
    """Esporta i contratti di un cliente in formato Excel A4 orizzontale con stile professionale."""
    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    # ✅ colonne principali
    headers = [
        "NumeroContratto", "DataInizio", "DataFine", "Durata",
        "DescrizioneProdotto", "NOL_FIN", "NOL_INT", "TotRata",
        "CopieBN", "EccBN", "CopieCol", "EccCol", "Stato"
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = f"Contratti {rag_soc}"

    # Titolo principale
    ws.merge_cells("A1:M1")
    title = ws["A1"]
    title.value = f"Contratti Cliente: {rag_soc}"
    title.font = Font(size=14, bold=True, color="2563EB")
    title.alignment = Alignment(horizontal="center", vertical="center")

    # Riga di intestazione (blu SHT)
    ws.append(headers)
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="2563EB")
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin")
    )

    # Applica stile all'intestazione
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=2, column=i)
        c.font = head_font
        c.fill = head_fill
        c.alignment = center
        c.border = thin

    # Righe di dati
    for _, row in disp.iterrows():
        ws.append([str(row.get(h, "")) for h in headers])
        stato = str(row.get("Stato", "")).lower()
        r_idx = ws.max_row

        for j in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=j)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin
            # Riga colorata se "chiuso"
            if stato == "chiuso":
                cell.fill = PatternFill("solid", fgColor="FFCDD2")

    # ✅ Larghezze perfette per A4 orizzontale
    col_widths = [18, 14, 14, 10, 35, 14, 14, 14, 12, 12, 12, 12, 14]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Congela riga intestazione
    ws.freeze_panes = "A3"

    # Imposta layout stampa A4 orizzontale
    ws.page_setup.orientation = ws.ORIENTATION_LANDSCAPE
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_margins.left = 0.4
    ws.page_margins.right = 0.4
    ws.page_margins.top = 0.6
    ws.page_margins.bottom = 0.6
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    # Esporta come bytes
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


# =====================================
# 📗 ESPORTAZIONE IN PDF
# =====================================
def export_pdf_contratti(df_ct, sel_id, rag_soc):
    """Esporta i contratti di un cliente in PDF usando il layout SHTPDF."""
    disp = df_ct[df_ct["ClienteID"].astype(str) == str(sel_id)].copy()
    disp["DataInizio"] = disp["DataInizio"].apply(fmt_date)
    disp["DataFine"] = disp["DataFine"].apply(fmt_date)

    headers = [
        "NumeroContratto", "DataInizio", "DataFine",
        "Durata", "DescrizioneProdotto", "TotRata", "Stato"
    ]
    widths = [30, 25, 25, 20, 95, 25, 25]  # proporzioni perfette per A4 landscape

    pdf = SHTPDF(title=f"Contratti Cliente: {rag_soc}")
    pdf.add_page()
    pdf.table_header(headers, widths)

    for _, r in disp.iterrows():
        stato = str(r.get("Stato", "")).lower()
        row_data = [str(r.get(h, "")) for h in headers]
        pdf.table_row(row_data, widths, wrap_index=headers.index("DescrizioneProdotto"), stato=stato)

    return pdf.output(dest="S").encode("latin-1", errors="replace")

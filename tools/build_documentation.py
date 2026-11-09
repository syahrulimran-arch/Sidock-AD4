from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "documentation" / "SIDock_AD4_Software_Documentation_v0.7.1.md"
OUTPUT = ROOT / "documentation" / "SIDock_AD4_Software_Documentation_v0.7.1.docx"

NAVY = "1F4E78"
PALE_BLUE = "EEF4F8"
LIGHT_BORDER = "D9D9D9"
BLACK = RGBColor(0, 0, 0)
WHITE = RGBColor(255, 255, 255)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), LIGHT_BORDER)


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    marker = OxmlElement("w:tblHeader")
    marker.set(qn("w:val"), "true")
    tr_pr.append(marker)


def set_font(run, name: str = "Arial", size: float | None = None) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)


def add_inline(paragraph, text: str, color: RGBColor = BLACK, size: float | None = None) -> None:
    pieces = re.split(r"(\*\*.*?\*\*|`.*?`)", text)
    for piece in pieces:
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            run = paragraph.add_run(piece[2:-2])
            run.bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            run = paragraph.add_run(piece[1:-1])
            set_font(run, "Courier New", 9.0 if size is None else size)
        else:
            run = paragraph.add_run(piece)
        run.font.color.rgb = color
        if not (piece.startswith("`") and piece.endswith("`")):
            set_font(run, "Arial", size)


def add_page_field(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, text, end):
        run._r.append(element)
    set_font(run, "Arial", 8.5)


def configure_styles(document: Document) -> None:
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.12

    title = document.styles["Title"]
    title.font.name = "Arial"
    title._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    title._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    title.font.size = Pt(27)
    title.font.bold = True
    title.font.color.rgb = BLACK
    title.paragraph_format.space_after = Pt(14)
    title_ppr = title._element.get_or_add_pPr()
    title_border = title_ppr.find(qn("w:pBdr"))
    if title_border is not None:
        title_ppr.remove(title_border)

    for style_name, size, before, after in (
        ("Heading 1", 17, 16, 8),
        ("Heading 2", 13, 12, 5),
        ("Heading 3", 11, 9, 4),
    ):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = BLACK
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    for style_name in ("List Bullet", "List Number"):
        style = document.styles[style_name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(10.5)
        style.font.color.rgb = BLACK
        style.paragraph_format.space_after = Pt(3)


def configure_section(section) -> None:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.68)
    section.left_margin = Inches(0.78)
    section.right_margin = Inches(0.78)
    section.header_distance = Inches(0.32)
    section.footer_distance = Inches(0.32)


def add_header_footer(section) -> None:
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.text = "SIDock AD4 Software Documentation"
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.runs[0]
    set_font(run, "Arial", 8.2)
    run.font.color.rgb = RGBColor(90, 90, 90)

    footer = section.footer
    table = footer.add_table(rows=1, cols=2, width=Inches(6.94))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(4.6)
    table.columns[1].width = Inches(2.34)
    left = table.cell(0, 0).paragraphs[0]
    left.paragraph_format.space_after = Pt(0)
    run = left.add_run("SIDock AD4 0.7.1")
    set_font(run, "Arial", 8.5)
    run.font.color.rgb = RGBColor(90, 90, 90)
    right = table.cell(0, 1).paragraphs[0]
    right.paragraph_format.space_after = Pt(0)
    add_page_field(right)


def parse_table(lines: list[str]) -> tuple[list[str], list[list[str]]]:
    def row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = row(lines[0])
    data = [row(line) for line in lines[2:]]
    return headers, data


def add_table(document: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    set_repeat_table_header(table.rows[0])

    all_rows = [headers, *rows]
    max_lengths = []
    for col in range(len(headers)):
        maximum = max(len(item[col]) if col < len(item) else 0 for item in all_rows)
        max_lengths.append(max(8, min(48, maximum)))
    total_weight = sum(max_lengths)
    widths = [6.82 * weight / total_weight for weight in max_lengths]

    for index, heading in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.width = Inches(widths[index])
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        set_cell_margins(cell)
        set_cell_shading(cell, NAVY)
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(0)
        add_inline(paragraph, heading, WHITE, 8.5)
        for run in paragraph.runs:
            run.bold = True

    for row_index, values in enumerate(rows, start=1):
        cells = table.add_row().cells
        for col_index, cell in enumerate(cells):
            cell.width = Inches(widths[col_index])
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_margins(cell)
            if row_index % 2 == 0:
                set_cell_shading(cell, PALE_BLUE)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            value = values[col_index] if col_index < len(values) else ""
            add_inline(paragraph, value, BLACK, 8.4)
    document.add_paragraph().paragraph_format.space_after = Pt(1)


def add_code_block(document: Document, lines: list[str]) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.left_indent = Inches(0.22)
    paragraph.paragraph_format.right_indent = Inches(0.12)
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(8)
    paragraph.paragraph_format.line_spacing = 1.0
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), "F2F2F2")
    paragraph._p.get_or_add_pPr().append(shading)
    run = paragraph.add_run("\n".join(lines))
    set_font(run, "Courier New", 8.3)
    run.font.color.rgb = BLACK


def build() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    lines = markdown.splitlines()

    document = Document()
    configure_styles(document)
    configure_section(document.sections[0])
    document.core_properties.title = "SIDock AD4 Software Documentation"
    document.core_properties.subject = "User manual scientific guidance technical reference and release guide"
    document.core_properties.author = "Dr Syahrul Imran"
    document.core_properties.keywords = "SIDock AD4 AutoDock4 AutoGrid virtual screening docking"

    cover = document.sections[0]
    cover.different_first_page_header_footer = True
    paragraph = document.add_paragraph(style="Title")
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_before = Pt(78)
    title_border = paragraph._p.get_or_add_pPr().find(qn("w:pBdr"))
    if title_border is not None:
        paragraph._p.get_or_add_pPr().remove(title_border)
    paragraph.add_run("SIDock AD4 Software Documentation")

    subtitle = document.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(34)
    run = subtitle.add_run("User Manual Scientific Guidance Technical Reference and Release Guide")
    set_font(run, "Arial", 14)
    run.bold = True
    run.font.color.rgb = BLACK

    identity = document.add_paragraph()
    identity.paragraph_format.line_spacing = 1.35
    add_inline(identity, "Streamlined Interface for Docking with AutoDock4\n", BLACK, 12)
    add_inline(identity, "Version 0.7.1\n", BLACK, 12)
    add_inline(identity, "64-bit Windows 10 version 1809 or newer and Windows 11", BLACK, 12)

    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(88)
    developer = document.add_paragraph()
    add_inline(developer, "Developed by Dr Syahrul Imran\nDocument date 11 September 2026", BLACK, 10.5)

    document.add_page_break()
    section = document.sections[0]
    add_header_footer(section)

    # Skip the Markdown cover block and start with Document Purpose.
    start = next(index for index, line in enumerate(lines) if line == "## Document Purpose")
    lines = lines[start:]

    index = 0
    paragraph_buffer: list[str] = []
    in_code = False
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_buffer
        if not paragraph_buffer:
            return
        text = " ".join(item.strip() for item in paragraph_buffer).strip()
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_inline(paragraph, text)
        paragraph_buffer = []

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                add_code_block(document, code_lines)
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not line.strip():
            flush_paragraph()
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|\s*[-:]+", lines[index + 1]):
            flush_paragraph()
            table_lines = [line, lines[index + 1]]
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                table_lines.append(lines[index])
                index += 1
            headers, rows = parse_table(table_lines)
            add_table(document, headers, rows)
            continue
        heading_match = re.match(r"^(#{2,4})\s+(.+)$", line)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1)) - 1
            heading = heading_match.group(2).replace("`", "")
            paragraph = document.add_paragraph(style=f"Heading {min(level, 3)}")
            if level == 1 and re.match(r"^\d+\s", heading):
                paragraph.paragraph_format.page_break_before = True
            add_inline(paragraph, heading)
            index += 1
            continue
        if line.startswith("- "):
            flush_paragraph()
            paragraph = document.add_paragraph(style="List Bullet")
            add_inline(paragraph, line[2:].strip())
            index += 1
            continue
        number_match = re.match(r"^(\d+)\.\s+(.+)$", line)
        if number_match:
            flush_paragraph()
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.left_indent = Inches(0.28)
            paragraph.paragraph_format.first_line_indent = Inches(-0.18)
            paragraph.paragraph_format.space_after = Pt(3)
            add_inline(paragraph, f"{number_match.group(1)}. {number_match.group(2)}")
            index += 1
            continue
        paragraph_buffer.append(line)
        index += 1

    flush_paragraph()

    for paragraph in document.paragraphs:
        for run in paragraph.runs:
            if run.font.name is None:
                set_font(run, "Arial")
            if paragraph.style.name.startswith("Heading") or paragraph.style.name == "Title":
                run.font.color.rgb = BLACK

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()

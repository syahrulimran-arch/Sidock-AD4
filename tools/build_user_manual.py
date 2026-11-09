from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "documentation" / "SIDock_AD4_User_Manual_v0.7.1.docx"
SETUP_SCREENSHOT = ROOT.parent / "upload" / "7a4f8930-afb4-493c-8a05-8eaf4ea9e28f.png"
CHECK_SCREENSHOT = ROOT.parent / "upload" / "0f58eb9b-fc5e-4d23-9c2d-ac4f060720f1.png"

NAVY = "1F4E78"
PALE_BLUE = "EEF4F8"
LIGHT_BORDER = "D9D9D9"
BLACK = RGBColor(0, 0, 0)
WHITE = RGBColor(255, 255, 255)


def set_font(run, name: str = "Arial", size: float = 10.5, color=BLACK) -> None:
    run.font.name = name
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:ascii"), name)
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = color


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd")
        tc_pr.append(shading)
    shading.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=90, start=110, bottom=90, end=110) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
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
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "single")
        node.set(qn("w:sz"), "4")
        node.set(qn("w:color"), LIGHT_BORDER)


def keep_with_next(paragraph) -> None:
    paragraph.paragraph_format.keep_with_next = True


def add_page_number(paragraph) -> None:
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
    run._r.extend([begin, instr, separate, text, end])


def add_header_footer(section) -> None:
    header = section.header
    hp = header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hr = hp.add_run("SIDock AD4 User Manual")
    set_font(hr, size=8.5, color=RGBColor(90, 90, 90))

    footer = section.footer
    table = footer.add_table(rows=1, cols=3, width=Inches(7.0))
    table.autofit = False
    widths = (Inches(2.6), Inches(1.8), Inches(2.6))
    for cell, width in zip(table.rows[0].cells, widths):
        cell.width = width
    left, center, right = table.rows[0].cells
    left.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.LEFT
    center.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    right.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
    lr = left.paragraphs[0].add_run("SIDock AD4 0.7.1")
    set_font(lr, size=8.5, color=RGBColor(90, 90, 90))
    add_page_number(center.paragraphs[0])
    rr = right.paragraphs[0].add_run("Dr Syahrul Imran")
    set_font(rr, size=8.5, color=RGBColor(90, 90, 90))
    for cell in table.rows[0].cells:
        cell._tc.get_or_add_tcPr().append(OxmlElement("w:tcBorders"))


def configure_styles(document: Document) -> None:
    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = BLACK
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.08

    title = styles["Title"]
    title.font.name = "Arial"
    title._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    title._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    title.font.size = Pt(30)
    title.font.bold = True
    title.font.color.rgb = BLACK
    title.paragraph_format.space_after = Pt(14)
    title_border = title._element.get_or_add_pPr().find(qn("w:pBdr"))
    if title_border is not None:
        title._element.get_or_add_pPr().remove(title_border)

    for name, size, before, after in (
        ("Heading 1", 19, 8, 8),
        ("Heading 2", 13, 9, 4),
        ("Heading 3", 11, 7, 3),
    ):
        style = styles[name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = BLACK
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.keep_with_next = True

    caption = styles["Caption"]
    caption.font.name = "Arial"
    caption._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    caption._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    caption.font.size = Pt(9)
    caption.font.italic = True
    caption.font.color.rgb = RGBColor(70, 70, 70)


def add_text(document: Document, text: str, *, bold_lead: str | None = None) -> None:
    paragraph = document.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        lead = paragraph.add_run(bold_lead)
        set_font(lead)
        lead.bold = True
        body = paragraph.add_run(text[len(bold_lead):])
        set_font(body)
    else:
        run = paragraph.add_run(text)
        set_font(run)


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(3)
        run = paragraph.add_run(item)
        set_font(run)


def add_steps(document: Document, items: list[tuple[str, str]]) -> None:
    for index, (lead, body) in enumerate(items, start=1):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.left_indent = Inches(0.2)
        paragraph.paragraph_format.first_line_indent = Inches(-0.2)
        number = paragraph.add_run(f"{index}. ")
        set_font(number)
        number.bold = True
        first = paragraph.add_run(lead)
        set_font(first)
        first.bold = True
        rest = paragraph.add_run(body)
        set_font(rest)


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths: list[float], mono_columns: set[int] | None = None) -> None:
    mono_columns = mono_columns or set()
    table = document.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for index, (cell, header, width) in enumerate(zip(table.rows[0].cells, headers, widths)):
        cell.width = Inches(width)
        set_cell_shading(cell, NAVY)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        paragraph = cell.paragraphs[0]
        run = paragraph.add_run(header)
        set_font(run, size=9, color=WHITE)
        run.bold = True
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for column, (cell, value, width) in enumerate(zip(cells, values, widths)):
            cell.width = Inches(width)
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            if row_index % 2:
                set_cell_shading(cell, PALE_BLUE)
            paragraph = cell.paragraphs[0]
            run = paragraph.add_run(value)
            set_font(run, name="Consolas" if column in mono_columns else "Arial", size=8.2 if column in mono_columns else 9)
    set_table_borders(table)
    document.add_paragraph().paragraph_format.space_after = Pt(1)


def add_screenshot(document: Document, path: Path, width: float, caption: str, description: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    inline = run.add_picture(str(path), width=Inches(width))
    doc_pr = inline._inline.docPr
    doc_pr.set("title", caption)
    doc_pr.set("descr", description)
    cap = document.add_paragraph(caption, style="Caption")
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER


def section_page(document: Document, title: str) -> None:
    document.add_page_break()
    document.add_heading(title, level=1)


def build() -> Path:
    if not SETUP_SCREENSHOT.is_file() or not CHECK_SCREENSHOT.is_file():
        raise FileNotFoundError("Required SIDock screenshots are missing.")

    document = Document()
    configure_styles(document)
    section = document.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(0.72)
    section.bottom_margin = Inches(0.72)
    section.left_margin = Inches(0.72)
    section.right_margin = Inches(0.72)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.3)
    section.different_first_page_header_footer = True
    add_header_footer(section)

    # Cover
    title = document.add_paragraph(style="Title")
    title.paragraph_format.space_before = Pt(80)
    title_border = title._p.get_or_add_pPr().find(qn("w:pBdr"))
    if title_border is not None:
        title._p.get_or_add_pPr().remove(title_border)
    title.add_run("SIDock AD4 User Manual")
    subtitle = document.add_paragraph()
    subtitle.paragraph_format.space_after = Pt(34)
    sr = subtitle.add_run("First Time Setup and Virtual Screening Workflow")
    set_font(sr, size=15)
    sr.bold = True
    identity = document.add_paragraph()
    for value in (
        "Streamlined Interface for Docking with AutoDock4\n",
        "Version 0.7.1\n",
        "64-bit Windows 10 version 1809 or newer and Windows 11",
    ):
        run = identity.add_run(value)
        set_font(run, size=12)
    document.add_paragraph().paragraph_format.space_after = Pt(80)
    developer = document.add_paragraph()
    dr = developer.add_run("Developed by Dr Syahrul Imran\nUser manual dated 11 September 2026")
    set_font(dr, size=10.5)

    section_page(document, "How to Use This Manual")
    add_text(document, "This manual takes a first-time user from initial tool configuration through receptor and ligand preparation, AutoDock4 screening, result analysis, and receptor-ligand complex download. Follow the numbered steps in sequence for a new installation.")
    document.add_heading("Workflow at a Glance", level=2)
    add_steps(document, [
        ("Configure tool paths. ", "Enter the AutoGrid4, AutoDock4, MGLTools Python, and AutoDockTools receptor-preparation paths. Check the setup, then save the paths."),
        ("Create a project. ", "Choose a writable project folder. SIDock stores all inputs, logs, docking files, and reports there."),
        ("Prepare the receptor and grid. ", "Select the correct receptor mode, prepare the receptor, and define the docking box."),
        ("Prepare ligands. ", "Import SDF, MOL, or MOL2 files and run geometry preparation and Meeko conversion."),
        ("Run screening. ", "Set AutoDock4 search parameters, start the run, and monitor completion."),
        ("Review results. ", "Open the HTML report, inspect rankings and contacts, and download receptor-ligand complex PDB files."),
    ])
    document.add_heading("Before You Begin", level=2)
    add_bullets(document, [
        "Install SIDock AD4 v0.7.1 on 64-bit Windows 10 version 1809 or newer, or Windows 11.",
        "Install AutoDock 4.2.6 and MGLTools 1.5.7 if the AutoDockTools receptor mode will be used.",
        "Use a project location where the current Windows account has permission to create and modify files.",
        "The paths in this manual match the standard installations shown by the developer. If your software was installed elsewhere, use Browse to select the actual file.",
    ])

    section_page(document, "Step 1 Configure Tool Paths")
    add_text(document, "Complete this setup the first time SIDock is started. Open the Project tab and locate the External tools section. The entries are saved for later sessions after the setup check succeeds.")
    add_screenshot(
        document, SETUP_SCREENSHOT, 7.0,
        "Figure 1  Project tab before first-time tool configuration",
        "SIDock AD4 Project tab showing the project folder and external tool path fields.",
    )
    add_text(document, "Use the Browse buttons to select the executable or script files. Selecting the file is safer than typing a long path manually.", bold_lead="Use the Browse buttons")

    section_page(document, "Step 1 Enter the Required Paths")
    add_text(document, "Enter or browse to the following full file paths. These are file paths, not only folder names.")
    add_table(document, ["SIDock field", "Required value", "Instruction"], [
        ["AutoGrid4 executable", "C:/Program Files (x86)/The Scripps Research Institute/Autodock/4.2.6/autogrid4.exe", "Browse to autogrid4.exe"],
        ["AutoDock4 executable", "C:/Program Files (x86)/The Scripps Research Institute/Autodock/4.2.6/autodock4.exe", "Browse to autodock4.exe"],
        ["Meeko ligand command", "Bundled Meeko (automatic)", "Leave unchanged"],
        ["Meeko receptor command", "Bundled Meeko (automatic)", "Leave unchanged"],
        ["Open Babel executable", "Bundled Open Babel", "Leave unchanged"],
        ["MGLTools Python executable", "C:/Program Files (x86)/MGLTools-1.5.7/python.exe", "Browse to python.exe"],
        ["AutoDockTools prepare_receptor4.py", "C:/Program Files (x86)/MGLTools-1.5.7/Lib/site-packages/AutoDockTools/Utilities24/prepare_receptor4.py", "Browse to prepare_receptor4.py"],
    ], [1.7, 3.75, 1.55], mono_columns={1})
    add_text(document, "Important. Keep both Meeko fields set to Bundled Meeko (automatic) and Open Babel set to Bundled Open Babel. Do not point a Meeko field to SIDock.exe; doing so can reopen the main application instead of running ligand or receptor preparation.", bold_lead="Important.")
    document.add_heading("If your installation path is different", level=2)
    add_text(document, "The Program Files (x86) paths above are examples from the intended installation. If AutoDock or MGLTools is installed in another location, use Browse and select the matching executable or prepare_receptor4.py file there. Do not copy a path that does not exist on the computer.")

    section_page(document, "Step 1 Check and Save the Tool Setup")
    add_steps(document, [
        ("Click Check tool setup. ", "SIDock tests AutoGrid4, AutoDock4, bundled Open Babel, and both bundled Meeko preparation modules."),
        ("Review the tool-check window. ", "Every displayed required entry should begin with OK. The resolved file location is shown beside applicable tools."),
        ("Correct any missing entry. ", "Close the check window, browse to the correct file, and run Check tool setup again. Do not proceed while a required entry is reported as missing."),
        ("Save the verified paths. ", "When all displayed entries report OK, click OK to close the check window and then click Save tool paths on the Project tab."),
    ])
    add_screenshot(
        document, CHECK_SCREENSHOT, 4.5,
        "Figure 2  Successful tool setup check",
        "SIDock tool check window showing OK results for AutoGrid4, AutoDock4, bundled Open Babel, and bundled Meeko.",
    )
    add_text(document, "The tool-check window does not list the optional MGLTools paths. Those paths are used when Treated PDB - AutoDockTools is selected during receptor preparation. If you plan to use that mode, make sure both MGLTools files entered above exist.")

    section_page(document, "Step 2 Create or Open a Project")
    add_steps(document, [
        ("Choose the project folder. ", "Click Browse beside Folder and select an empty or new writable folder for the screening study."),
        ("Create a new project. ", "Click Create project. SIDock creates project.json and the receptor, ligand, grid, docking, log, result, and analysis subfolders."),
        ("Resume an existing project when needed. ", "Select the folder containing project.json and click Open existing. SIDock restores the saved receptor, ligand, grid, docking, and analysis settings."),
    ])
    add_text(document, "Use one project folder for one receptor and one defined screening setup. Keep the whole folder when archiving or transferring the work because report links are relative to this folder.", bold_lead="Use one project folder")
    document.add_heading("Project folder recommendations", level=2)
    add_bullets(document, [
        "Use a short, descriptive name without confidential identifiers when the project will be shared.",
        "Avoid read-only folders, removable drives that disconnect, and network locations with unstable access.",
        "Do not manually rename generated subfolders while SIDock is open.",
        "Back up the complete project after a successful screen and analysis.",
    ])

    section_page(document, "Step 3 Prepare the Receptor")
    add_text(document, "Open the Receptor grid tab. Select the input mode that matches the receptor file and the level of preparation already completed.")
    add_table(document, ["Receptor mode", "Use this mode when"], [
        ["Raw PDB - prepare and validate with Meeko", "The starting file is a conventional protein PDB compatible with Meeko templates."],
        ["Treated PDB - AutoDockTools", "A curated PDB, including HEM or metal-containing systems, should be processed using MGLTools prepare_receptor4.py."],
        ["Treated PDB - preserve structure with Open Babel", "A user-curated PDB should undergo minimal rigid conversion while retaining the supplied geometry."],
        ["Prepared PDBQT - use directly", "The receptor was prepared externally and its atom types, charges, hydrogens, and retained residues are already correct."],
    ], [2.7, 4.3])
    add_steps(document, [
        ("Select the receptor file. ", "Browse to the PDB or PDBQT required by the selected mode."),
        ("Set cleanup options. ", "Choose a protein chain if needed. Decide whether to remove crystallographic waters and other HETATM records. Enter retained residue names for required cofactors or metals."),
        ("Prepare the receptor. ", "Run receptor preparation and read the completion message. If the process fails, open the named log file before changing the receptor or preparation mode."),
    ])
    add_text(document, "For HEM, metal centers, nonstandard residues, missing residues, unusual protonation states, or covalent cofactors, confirm the chemistry manually. Automated receptor preparation cannot determine the scientifically correct model for every system.", bold_lead="For HEM, metal centers")

    section_page(document, "Step 4 Define the Grid Box")
    add_text(document, "The grid box defines where AutoDock4 searches. It must cover the intended binding site and leave enough space for the ligand to move, but should not include unnecessary receptor volume.")
    add_table(document, ["Method", "Procedure", "Best use"], [
        ["Manual coordinates", "Enter X, Y, and Z center coordinates, even point counts, and grid spacing.", "A known pocket center or a previously validated grid."],
        ["Box from reference ligand", "Select an isolated bound ligand in PDB or PDBQT format. SIDock calculates the box with padding.", "A co-crystallized ligand extracted from the receptor."],
        ["Box from bound ligand in receptor", "Enter the bound-ligand residue name and optional receptor chain.", "The original receptor PDB still contains the bound ligand."],
    ], [1.7, 3.3, 2.0])
    add_text(document, "Do not use the complete receptor as the reference-ligand file. Its dimensions can exceed AutoGrid's maximum 126 points per axis. Extract the bound ligand into a separate coordinate file instead.", bold_lead="Do not use the complete receptor")
    document.add_heading("Grid checks before screening", level=2)
    add_bullets(document, [
        "Confirm that the center lies inside the intended pocket.",
        "Confirm that each point count is even and does not exceed 126.",
        "Inspect the physical dimensions produced by the point counts and spacing.",
        "Use a consistent grid when compounds will be compared in one ranking table.",
    ])

    section_page(document, "Step 5 Import and Prepare Ligands")
    add_text(document, "Open the Ligands tab and select an SDF, MOL, or MOL2 source. A multi-molecule SDF is processed one record at a time. SIDock sanitizes filenames and preserves a preparation audit for every ligand.")
    add_steps(document, [
        ("Add ligand files. ", "Browse to the source file or files. Check that molecule names and structures are correct before preparation."),
        ("Choose geometry options. ", "Keep Generate 3D coordinates when missing enabled for two-dimensional inputs. Keep Optimize or minimize geometry enabled unless a justified externally optimized geometry will be used."),
        ("Select the force field. ", "MMFF94 is the general starting choice for supported organic molecules. MMFF94s and UFF should be selected only when scientifically appropriate."),
        ("Set conformers and iterations. ", "The default is 10 conformers and 500 maximum minimization iterations per conformer. These are upper limits, so a converged minimization may finish quickly."),
        ("Prepare ligands. ", "SIDock generates or evaluates conformers, accepts only converged candidates, keeps the lowest-energy converged conformer, and sends it to bundled Meeko for PDBQT preparation."),
    ])
    document.add_heading("Check the ligand audit", level=2)
    add_bullets(document, [
        "Status should report convergence and successful PDBQT preparation.",
        "Initial and final energies must be finite; the final energy should not increase beyond numerical tolerance.",
        "Coordinate RMSD and energy change show whether the geometry actually moved during minimization.",
        "geometry_summary.csv records the method, conformers attempted and converged, selected conformer, energies, displacement, elapsed time, and errors.",
    ])

    section_page(document, "Step 6 Run AutoGrid4 and AutoDock4")
    add_text(document, "Open the Screen results tab after the receptor, grid, and ligand PDBQT files are ready.")
    add_table(document, ["Setting", "Default", "Purpose"], [
        ["GA runs per ligand", "10", "Number of independent Lamarckian genetic algorithm runs."],
        ["Maximum evaluations", "2,500,000", "Search-evaluation ceiling for each run."],
        ["Parallel AutoDock processes", "Based on CPU count", "Number of ligand jobs that can run concurrently."],
        ["Top poses for contact analysis", "20", "Number of ranked ligands receiving receptor-contact annotation."],
    ], [2.1, 1.6, 3.3])
    add_steps(document, [
        ("Review the settings. ", "Use the same search settings for compounds that will be compared. Increasing runs and evaluations increases computational time."),
        ("Start the screen. ", "SIDock runs AutoGrid4 once, generates a DPF for every ligand, and runs AutoDock4 jobs up to the selected parallel limit."),
        ("Monitor completion. ", "Progress and messages are displayed in the interface. Detailed standard output and errors are written to project log files."),
        ("Handle interruption. ", "Cancel requests preserve completed DLG files. Retry failed only skips ligands with an existing parseable binding energy and submits failed or missing jobs again."),
    ])

    section_page(document, "Step 7 Review and Download Results")
    add_text(document, "SIDock automatically analyzes available DLG files when docking finishes. Click Analyze existing results to rebuild the analysis without rerunning docking.")
    add_table(document, ["Report section", "What it provides"], [
        ["Binding-energy ranking", "Best AutoDock energy, ligand efficiency, heavy-atom count, run, cluster rank, cluster size, and best-pose complex controls."],
        ["Compound comparison", "Energy, ligand-efficiency, and cluster-support ranks plus the transparent consensus score."],
        ["AutoDock clusters", "Cluster membership, best energy, and mean energy when usable cluster information exists in the DLG."],
        ["Receptor contacts", "Distance-based residue contacts for the selected number of top-ranked poses."],
    ], [2.2, 4.8])
    document.add_heading("Open or download a binding pose with the receptor", level=2)
    add_steps(document, [
        ("Find the ligand row. ", "Use either the Binding-energy ranking or Compound comparison table in analysis/report.html."),
        ("Click Open complex. ", "SIDock opens the visualization-ready PDB containing the complete prepared receptor together with the selected best-pose ligand."),
        ("Click Download PDB. ", "Save the same receptor-ligand complex as a PDB file for Discovery Studio, PyMOL, ChimeraX, or another compatible viewer."),
    ])
    add_text(document, "Complex files are stored in analysis/complexes. The ligand is written as residue LIG in chain L. Ligand-only PDBQT poses remain in analysis/poses for AutoDock-specific inspection and auditing.", bold_lead="Complex files")
    add_text(document, "The Open complex action depends on the computer's browser and PDB file association. If the browser displays the PDB as text, use Download PDB and open the downloaded file in the preferred molecular viewer.")

    section_page(document, "Interpretation and Data Management")
    document.add_heading("Interpreting the ranking", level=2)
    add_bullets(document, [
        "More negative AutoDock binding energy ranks higher under the selected docking model.",
        "Ligand efficiency is the negative binding energy divided by ligand heavy-atom count; it is a screening descriptor, not an experimental measurement.",
        "The SIDock consensus score weights binding energy at 65 percent, ligand efficiency at 25 percent, and cluster support at 10 percent. Missing metrics are excluded and remaining weights are renormalized.",
        "Contact labels are geometry-based screening annotations. They are not energetic decomposition and do not replace manual pose inspection.",
        "Docking results should be treated as hypotheses for experimental or higher-level computational validation, not direct proof of potency or selectivity.",
    ])
    document.add_heading("Important project outputs", level=2)
    add_table(document, ["Location", "Contents"], [
        ["results/results.csv", "Basic result collection and run status."],
        ["analysis/report.html", "Self-contained interactive analysis report."],
        ["analysis/ranking.csv", "Binding-energy ranking and pose/complex paths."],
        ["analysis/comparison.csv", "Consensus and component ranking data."],
        ["analysis/clusters.csv", "Parsed AutoDock cluster summary."],
        ["analysis/contacts.csv", "Residue-level geometry-based contact annotations."],
        ["analysis/poses", "Ligand-only best-pose PDBQT files."],
        ["analysis/complexes", "Prepared receptor plus best-pose ligand PDB files."],
        ["logs and docking/dlg", "Command logs and original AutoDock DLG files for auditing."],
    ], [2.2, 4.8], mono_columns={0})

    section_page(document, "Troubleshooting")
    add_table(document, ["Problem", "Action"], [
        ["Tool check reports AutoGrid4 or AutoDock4 missing", "Use Browse and select the exact .exe file. Repeat Check tool setup before saving."],
        ["Meeko preparation is missing", "Restore both Meeko fields to Bundled Meeko (automatic). Do not select SIDock.exe or an obsolete wrapper."],
        ["A button opens another SIDock window", "Use v0.7.1 and restore both Meeko fields to Bundled Meeko (automatic)."],
        ["AutoDockTools receptor preparation fails", "Confirm the MGLTools Python and prepare_receptor4.py paths, input structure, retained residues, and the named log file."],
        ["Receptor preparation reports file not found", "Reselect the receptor source and prepare it again. SIDock projects moved from another location may contain an obsolete input reference."],
        ["Ligand minimization appears too fast", "Read geometry_summary.csv. A converged status, finite energies, and non-increasing final energy demonstrate a completed minimization even when runtime is short."],
        ["Cluster table is empty", "Inspect the DLG for a completed clustering histogram or representative cluster records. Binding energy can still be present without usable cluster annotations."],
        ["Complex controls are missing", "Install or build v0.7.1, open the project, and click Analyze existing results to regenerate analysis/complexes and the updated report."],
        ["Open complex displays text", "Click Download PDB and open the file in a molecular-visualization program."],
        ["Windows reports api-ms-win-core-path-l1-1-0.dll missing", "The operating system is unsupported. Use 64-bit Windows 10 version 1809 or newer, or Windows 11."],
    ], [2.45, 4.55])

    section_page(document, "First Run Completion Checklist")
    add_bullets(document, [
        "AutoGrid4 executable selected and reported OK.",
        "AutoDock4 executable selected and reported OK.",
        "Meeko ligand and receptor commands remain Bundled Meeko (automatic) and report OK.",
        "Open Babel remains Bundled Open Babel and reports OK.",
        "MGLTools Python executable path entered when the AutoDockTools receptor mode will be used.",
        "AutoDockTools prepare_receptor4.py path entered when the AutoDockTools receptor mode will be used.",
        "Check tool setup completed before Save tool paths was clicked.",
        "A writable, self-contained project folder was created.",
        "Receptor preparation mode and retained cofactors or metals were reviewed scientifically.",
        "The grid box covers the intended binding pocket.",
        "Ligand geometry and PDBQT preparation audits were checked.",
        "AutoDock4 search settings were recorded and applied consistently.",
        "The HTML report, CSV files, DLG files, poses, complexes, and logs were archived together.",
    ])
    document.add_heading("Recommended study record", level=2)
    add_text(document, "For reproducibility, record the SIDock, AutoGrid4, and AutoDock4 versions; receptor source and preparation mode; retained waters, cofactors, and metals; ligand preparation settings; force field; conformer count; grid center and dimensions; GA runs and evaluations; ranking rule; validation controls; and the molecular viewer used for pose inspection.")
    document.add_heading("End of Manual", level=2)
    add_text(document, "SIDock AD4 0.7.1  Streamlined Interface for Docking with AutoDock4  Developed by Dr Syahrul Imran")

    document.core_properties.title = "SIDock AD4 User Manual"
    document.core_properties.subject = "First-time setup and virtual screening workflow for SIDock AD4 0.7.1"
    document.core_properties.author = "Dr Syahrul Imran"
    document.core_properties.keywords = "SIDock AD4, AutoDock4, AutoGrid4, virtual screening, user manual"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(build())

from astropy.table import Table
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patheffects import withStroke
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib as mpl

# =============================
# USER CONFIGURATION SECTION
# =============================
# Adjust these values to tweak layout without touching the code below.

# Outer borders (white margins outside the perforated rectangles)
BORDER_TOP_MM = 10     # mm
BORDER_BOTTOM_MM = 10  # mm
BORDER_LEFT_MM = 15    # mm
BORDER_RIGHT_MM = 15   # mm

# Tag count per page (perforation layout)
ROWS_PER_PAGE = 5
COLS_PER_PAGE = 2

# Adjust to scale tag size inside each perforated zone
TAG_SCALE = 1.00   # 1.00 = default; <1 shrinks tag slightly, >1 grows it

# Padding inside each name tag image (affects artwork inset)
TAG_PADDING_FRAC = 0.02   # fraction of width/height
# =============================
# END USER CONFIG SECTION
# =============================

# Progress bar (tqdm) with graceful fallback if not installed
try:
    from tqdm import tqdm  # type: ignore
except Exception:
    def tqdm(iterable, **kwargs):
        return iterable

# plt.rcParams['font.family'] = 'Times New Roman'  # closest to Cambria
# or:
plt.rcParams['font.family'] = 'Georgia'

# Load the background once
bg_path = "Name_Tag_Image.png"
bg_path = "Name_Tag_Image_HiRes.png"
bg_img = Image.open(bg_path).convert("RGB")

# Base font sizes (will be auto-fitted)
NAME_FS_START, NAME_FS_MIN = 14, 8
AFFIL_FS_START, AFFIL_FS_MIN = 10, 4
PRONOUN_FS = 8

# A4 paper dimensions in inches
A4_WIDTH_IN, A4_HEIGHT_IN = 8.27, 11.69
## Name tag grid layout (rows x columns per page)
# (Now configured in the USER CONFIGURATION SECTION above)

# Layout tuning
WSPACE, HSPACE = 0.05, 0.1  # spacing between name tags
OUTPUT_DPI = 300  # output resolution for saved PDFs
WIFI_NAME = "Fort Scratchley"
WIFI_PASSWORD = "Fort!2300"
WIFI_FS = 10  # font size for WiFi and Password text

# Load the consolidated CSV of attendees with pronouns
tab = Table.read(
    "Name_Badge_List.csv",
    format="ascii.csv",
    guess=False,
    fast_reader=False,
    encoding="utf-8-sig",
)

# Column resolver that tolerates curly quotes and minor header variants
def pick_column(table, candidates):
    # direct match
    for c in candidates:
        if c in table.colnames:
            return c
    # try normalizing curly apostrophes to straight
    normal_map = {col.replace("\u2019", "'"): col for col in table.colnames}
    for c in candidates:
        if c in normal_map:
            return normal_map[c]
    # try case-insensitive match
    lower_map = {col.lower(): col for col in table.colnames}
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    raise KeyError(f"None of {candidates} found in columns: {table.colnames}")

# Resolve columns with support for both old and new formats
# Name can be a single column OR split as First_Name + Last_Name
first_col = last_col = None
try:
    name_col = pick_column(tab, ["name", "Name", "Presenter's Full Name", "Presenter’s Full Name", "Full Name"])
except KeyError:
    name_col = None
    # New CSV uses split columns
    first_col = pick_column(tab, ["First_Name", "First Name", "Given_Name", "Given Name"])
    last_col  = pick_column(tab, ["Last_Name", "Last Name", "Surname", "Family_Name", "Family Name"])

# Affiliation header variants
affil_col = pick_column(tab, ["affil", "Affiliation", "Institute", "Institution"])

# Pronouns header variants
try:
    pronoun_col = pick_column(tab, ["pronoun", "Pronoun", "Pronouns"])
except KeyError:
    pronoun_col = None

def compose_name(i: int) -> str:
    """Return display name for row i using either a single name column or First/Last."""
    if name_col is not None:
        return str(tab[name_col][i]).strip()
    # Build from first/last; tolerate missing pieces
    first = str(tab[first_col][i]).strip() if first_col in tab.colnames else ""
    last  = str(tab[last_col][i]).strip() if last_col in tab.colnames else ""
    full = f"{first} {last}".strip()
    return full

def normalise_pronoun(val: object) -> str:
    """Return a clean pronoun string, or '' if it's effectively empty."""
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return ""
    # normalise en/em dashes to hyphen
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    s_low = s.lower()
    empties = {"", "-", "--", "---", "—", "–", "n/a", "na", "none", "null", "nil", "no pronouns", "prefer not to say"}
    return "" if s_low in empties else s

def break_line(text, max_chars=60):
    """Break long text into two lines.
    Priority 1: break at '/'
    Priority 2: break at last space before limit
    Returns original text if short enough."""
    if len(text) <= max_chars:
        return text
    if '/' in text:
        parts = text.split('/', 1)
        return parts[0].strip() + "\n" + parts[1].strip()
    # fallback: break at last space before limit
    cut = text.rfind(' ', 0, max_chars)
    if cut == -1:
        return text  # no safe break
    return text[:cut].strip() + "\n" + text[cut:].strip()

def _axis_pixel_width(ax):
    # Get the axis width in display pixels
    renderer = ax.figure.canvas.get_renderer()
    return ax.get_window_extent(renderer=renderer).width

def draw_name_tag(ax, bg_img, name, affil, pronoun=""):
    # Inset padding to avoid print clipping
    height, width = bg_img.size[1], bg_img.size[0]
    pad_frac = TAG_PADDING_FRAC
    pad_x = width * pad_frac
    pad_y = height * pad_frac

    ax.imshow(
        bg_img,
        extent=(pad_x, width - pad_x, height - pad_y, pad_y)
    )


    # Ensure a renderer exists for measurements
    ax.figure.canvas.draw_idle()
    ax.figure.canvas.flush_events()
    axis_px = _axis_pixel_width(ax)
    max_text_px = axis_px * 0.86   # horizontal padding so text doesn't hit the edges

    pronoun = normalise_pronoun(pronoun)
    has_pronoun = pronoun != ""

    # Add a white outline for better readability
    stroke_effect = withStroke(linewidth=3, foreground=(1, 1, 1, 0.8))

    # --- NAME positioning (Aldo baseline) ---
    name_text = break_line(name, max_chars=22)
    name_y = height * 0.25

    # Invisible rendering to measure text height
    probe = ax.text(
        width/2, name_y, name_text,
        ha="center", va="top",
        fontsize=NAME_FS_START, weight="bold",
        linespacing=1.0, alpha=0
    )
    ax.figure.canvas.draw()
    renderer = ax.figure.canvas.get_renderer()
    bb = probe.get_window_extent(renderer=renderer)
    probe.remove()

    # Convert pixel height to image-space y-offset using AXIS height (not full figure)
    axis_bbox = ax.get_window_extent(renderer=renderer)
    px_to_img = height / axis_bbox.height
    name_height_img = bb.height * px_to_img

    # Aldo baseline spacing
    gap_after_name = height * 0.030
    pronoun_y = name_y + name_height_img + gap_after_name
    gap_after_pronoun = height * 0.105
    affil_y = pronoun_y + gap_after_pronoun

    # --- NAME (fixed font size with line break) ---
    ax.text(
        width/2,
        name_y,
        name_text,
        ha="center",
        va="top",     # ensure multi-line names expand downward, not upward
        fontsize=NAME_FS_START,
        weight="bold",
        color="black",
        linespacing=1.0,
        path_effects=[stroke_effect]
    )

    # --- PRONOUN (fixed style, appears only if present) ---
    if has_pronoun:
        ax.text(width / 2, pronoun_y, str(pronoun).strip(), ha="center", va="top",
                fontsize=PRONOUN_FS, color="black", path_effects=[stroke_effect])

    # --- AFFILIATION (fixed font size with line break) ---
    affil_text = break_line(affil, max_chars=50)
    ax.text(width/2, affil_y, affil_text, ha="center", va="top",
            fontsize=AFFIL_FS_START, color="black",
            path_effects=[stroke_effect])

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)

    ax.axis("off")

# Helper to chunk the table into pages of N entries
PER_PAGE = ROWS_PER_PAGE * COLS_PER_PAGE  # 5 rows x 2 cols

def paginate_indices(n_items, per_page=PER_PAGE):
    for start in range(0, n_items, per_page):
        yield range(start, min(start + per_page, n_items))


# Loop over all names, rendering 5x2 per page
page_iter = list(paginate_indices(len(tab), PER_PAGE))
#page_iter = page_iter[:1]  # Only render the first page for layout testing

# --- Diagnostics for consolidated CSV ---
try:
    all_names = [compose_name(i) for i in range(len(tab))]
    print(f"[diagnostic] Total entries: {len(all_names)}")
    if pronoun_col is not None:
        cleaned = [normalise_pronoun(x) for x in tab[pronoun_col]]
        with_pron = sum(1 for x in cleaned if x)
        print(f"[diagnostic] With pronouns: {with_pron}")
        print(f"[diagnostic] Without pronouns: {len(all_names) - with_pron}")
    else:
        print("[diagnostic] No pronoun column found")
except Exception as e:
    print(f"[diagnostic] Failed to run diagnostics: {e}. Columns present: {tab.colnames}")

# Combined multi-page PDF writer
combined_pdf_path = "name_tags_all_pages.pdf"
pdf_combined = PdfPages(combined_pdf_path)

for p_idx, idx_range in enumerate(tqdm(page_iter, desc="Pages", unit="page"), start=1):
    #fig, axes = plt.subplots(ROWS_PER_PAGE, COLS_PER_PAGE, figsize=(A4_WIDTH_IN, A4_HEIGHT_IN))
    #axes = axes.flatten()
    fig = plt.figure(figsize=(A4_WIDTH_IN, A4_HEIGHT_IN))

    # Convert mm borders to page-fractions
    PAGE_WIDTH_MM = 210.0
    PAGE_HEIGHT_MM = 297.0

    border_top = BORDER_TOP_MM / PAGE_HEIGHT_MM
    border_bottom = BORDER_BOTTOM_MM / PAGE_HEIGHT_MM
    border_left = BORDER_LEFT_MM / PAGE_WIDTH_MM
    border_right = BORDER_RIGHT_MM / PAGE_WIDTH_MM

    # Compute tag size in fractions, then apply scaling
    tag_h = ((1.0 - border_top - border_bottom) / ROWS_PER_PAGE) * TAG_SCALE
    tag_w = ((1.0 - border_left - border_right) / COLS_PER_PAGE) * TAG_SCALE

    # Build grid (5 rows x 2 cols) with symmetric top/bottom margins
    axes = []
    for r in range(ROWS_PER_PAGE):
        # bottom from top border downward
        bottom = 1 - border_top - (r+1)*tag_h
        for c in range(COLS_PER_PAGE):
            left = border_left + c * tag_w
            ax = fig.add_axes([left, bottom, tag_w, tag_h])
            axes.append(ax)

    # Fill this page
    for ax, i in zip(axes, list(idx_range)):
        name  = compose_name(i)
        affil = str(tab[affil_col][i]).strip()
        pron = ""
        if pronoun_col is not None:
            val = tab[pronoun_col][i]
            pron = normalise_pronoun(val)
        draw_name_tag(ax, bg_img, name, affil, pronoun=pron)

    # Any leftover axes (if last page has <10 entries)
    for ax in axes[len(list(idx_range)):]:
        ax.axis('off')

    #plt.subplots_adjust(left=0.12, right=0.88, top=0.99, bottom=0.01, wspace=WSPACE, hspace=HSPACE)

    output_pdf = f"name_tags_page_{p_idx:02d}.pdf"
    fig.set_size_inches(A4_WIDTH_IN, A4_HEIGHT_IN, forward=True)
    plt.savefig(output_pdf, format='pdf', dpi=OUTPUT_DPI)
    fig.set_size_inches(A4_WIDTH_IN, A4_HEIGHT_IN, forward=True)
    pdf_combined.savefig(fig, dpi=OUTPUT_DPI)
    print(f"Saved page {p_idx} to {output_pdf}")
    plt.close(fig)

    # --- BACK PAGE GENERATION ---
    #fig_back, axes_back = plt.subplots(ROWS_PER_PAGE, COLS_PER_PAGE, figsize=(A4_WIDTH_IN, A4_HEIGHT_IN))
    #axes_back = axes_back.flatten()
    fig_back = plt.figure(figsize=(A4_WIDTH_IN, A4_HEIGHT_IN))

    # Build grid (5 rows x 2 cols) for back page with symmetric top/bottom margins
    axes_back = []
    for r in range(ROWS_PER_PAGE):
        bottom = 1 - border_top - (r+1)*tag_h
        for c in range(COLS_PER_PAGE):
            left = border_left + c * tag_w
            ax_back = fig_back.add_axes([left, bottom, tag_w, tag_h])
            axes_back.append(ax_back)

    for ax in axes_back:
        ax.imshow(bg_img,alpha=0.4)
        height, width = bg_img.size[1], bg_img.size[0]
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)

        ax.text(width / 2, height * 0.35, "WiFi:", ha="right", va="center", fontsize=WIFI_FS, weight="bold")
        ax.text(width / 2 + 10, height * 0.35, WIFI_NAME, ha="left", va="center", fontsize=WIFI_FS)
        ax.text(width / 2, height * 0.45, "Password:", ha="right", va="center", fontsize=WIFI_FS, weight="bold")
        ax.text(width / 2 + 10, height * 0.45, WIFI_PASSWORD, ha="left", va="center", fontsize=WIFI_FS)
        ax.axis("off")

    #plt.subplots_adjust(left=0.12, right=0.88, top=0.99, bottom=0.01, wspace=WSPACE, hspace=HSPACE)

    output_back_pdf = f"name_tags_back_{p_idx:02d}.pdf"
    fig_back.set_size_inches(A4_WIDTH_IN, A4_HEIGHT_IN, forward=True)
    plt.savefig(output_back_pdf, format='pdf', dpi=OUTPUT_DPI)
    fig_back.set_size_inches(A4_WIDTH_IN, A4_HEIGHT_IN, forward=True)
    pdf_combined.savefig(fig_back, dpi=OUTPUT_DPI)
    print(f"Saved back page {p_idx} to {output_back_pdf}")
    plt.close(fig_back)

# Finalize combined PDF
pdf_combined.close()
print(f"Saved combined multi-page PDF to {combined_pdf_path}")

import subprocess
import shutil

# Optional: compress final PDF using Ghostscript if available
gs_cmd = shutil.which("gs")
if gs_cmd is not None:
    compressed_output = "name_tags_all_pages_compressed.pdf"
    try:
        subprocess.run(
            [
                gs_cmd,
                "-sDEVICE=pdfwrite",
                "-dCompatibilityLevel=1.4",
                "-dPDFSETTINGS=/prepress",
                "-dNOPAUSE",
                "-dQUIET",
                "-dBATCH",
                f"-sOutputFile={compressed_output}",
                combined_pdf_path,
            ],
            check=True
        )
        print(f"Compressed PDF saved to {compressed_output}")
    except Exception as e:
        print(f"Ghostscript compression failed: {e}")
else:
    print("Ghostscript not found — skipping PDF compression.")
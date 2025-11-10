from astropy.table import Table
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patheffects import withStroke
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib as mpl

# Progress bar (tqdm) with graceful fallback if not installed
try:
    from tqdm import tqdm  # type: ignore
except Exception:
    def tqdm(iterable, **kwargs):
        return iterable

# plt.rcParams['font.family'] = 'Times New Roman'  # closest to Cambria
# or:
plt.rcParams['font.family'] = 'Georgia'

#
# Load the background once
bg_path = "Name_Tag_Image.png"
bg_img = Image.open(bg_path).convert("RGB")

# Base font sizes (will be auto-fitted)
NAME_FS_START, NAME_FS_MIN = 28, 16
AFFIL_FS_START, AFFIL_FS_MIN = 18, 12
PRONOUN_FS = 16

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

def _axis_pixel_width(ax):
    # Get the axis width in display pixels
    renderer = ax.figure.canvas.get_renderer()
    return ax.get_window_extent(renderer=renderer).width

def _fit_fontsize(ax, text, max_px, start_fs, min_fs, **kw):
    """
    Iteratively reduce fontsize until the rendered text fits within max_px.
    Creates a temporary invisible Text to measure.
    """
    renderer = ax.figure.canvas.get_renderer()
    probe = ax.text(0.5, 0.5, text, alpha=0, **kw)
    fs = start_fs
    while fs >= min_fs:
        probe.set_fontsize(fs)
        bb = probe.get_window_extent(renderer=renderer)
        if bb.width <= max_px:
            probe.remove()
            return fs
        fs -= 1
    probe.remove()
    return min_fs

def _maybe_two_line_name(ax, name, max_px, start_fs, min_fs, **kw):
    """
    Try a single line first; if it can't fit with a reasonable size (>= min_fs),
    split into two lines (first names on line 1, family name(s) on line 2) and refit.
    Returns (text_to_draw, chosen_fontsize, used_two_lines: bool).
    """
    fs_single = _fit_fontsize(ax, name, max_px, start_fs, min_fs, **kw)
    if fs_single > min_fs:
        return name, fs_single, False
    # Two-line attempt
    parts = name.split()
    if len(parts) >= 3:
        two_line = " ".join(parts[:-1]) + "\n" + parts[-1]
    elif len(parts) == 2:
        two_line = parts[0] + "\n" + parts[1]
    else:
        two_line = name  # nothing to do
    fs_two = _fit_fontsize(ax, two_line, max_px, start_fs, min_fs, **kw)
    return two_line, fs_two, ("\n" in two_line)

def draw_name_tag(ax, bg_img, name, affil, pronoun=""):
    ax.imshow(bg_img)

    # Get image size and correct text placement using image coordinates
    height, width = bg_img.size[1], bg_img.size[0]

    # Ensure a renderer exists for measurements
    ax.figure.canvas.draw_idle()
    ax.figure.canvas.flush_events()
    axis_px = _axis_pixel_width(ax)
    max_text_px = axis_px * 0.86   # horizontal padding so text doesn't hit the edges

    pronoun = normalise_pronoun(pronoun)
    has_pronoun = pronoun != ""

    # Add a white outline for better readability
    stroke_effect = withStroke(linewidth=3, foreground=(1, 1, 1, 0.8))

    name_y = height * 0.30
    if has_pronoun:
        name_y    = height * 0.26   # move name slightly higher for more spacing
        pronoun_y = height * 0.38   # move pronoun slightly lower
        affil_y   = height * 0.54
    else:
        pronoun_y = None
        affil_y   = height * 0.50

    # If the name spills to two lines, move pronoun/affiliation a touch lower
    if has_pronoun and 'used_two_lines' in locals() and used_two_lines:
        pronoun_y = height * 0.40
        affil_y   = height * 0.56
    elif (not has_pronoun) and 'used_two_lines' in locals() and used_two_lines:
        affil_y   = height * 0.52

    # --- NAME (auto-fit, two-line if needed) ---
    name_text, name_fs, used_two_lines = _maybe_two_line_name(
        ax, name, max_text_px, NAME_FS_START, NAME_FS_MIN,
        ha="center", va="center", weight="bold", path_effects=[stroke_effect], color="black"
    )
    ax.text(width / 2, name_y, name_text, ha="center", va="center",
            fontsize=name_fs, weight="bold", color="black", path_effects=[stroke_effect])

    # --- PRONOUN (fixed style, appears only if present) ---
    if has_pronoun:
        ax.text(width / 2, pronoun_y, str(pronoun).strip(), ha="center", va="center",
                fontsize=PRONOUN_FS, color="black", path_effects=[stroke_effect])

    # --- AFFILIATION (single line, auto-fit to width) ---
    affil_fs = _fit_fontsize(
        ax, affil, max_text_px, AFFIL_FS_START, AFFIL_FS_MIN,
        ha="center", va="center", path_effects=[stroke_effect], color="black"
    )
    ax.text(width / 2, affil_y, affil, ha="center", va="center",
            fontsize=affil_fs, color="black", path_effects=[stroke_effect])

    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)

    ax.axis("off")

# Helper to chunk the table into pages of N entries
PER_PAGE = 10  # 5 rows x 2 cols

def paginate_indices(n_items, per_page=PER_PAGE):
    for start in range(0, n_items, per_page):
        yield range(start, min(start + per_page, n_items))

# Loop over all names, rendering 5x2 per page
page_iter = list(paginate_indices(len(tab), PER_PAGE))

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
    fig, axes = plt.subplots(5, 2, figsize=(16, 20))
    axes = axes.flatten()

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

    plt.subplots_adjust(left=0.12, right=0.88, top=0.99, bottom=0.01, wspace=0, hspace=0.02)

    output_pdf = f"name_tags_page_{p_idx:02d}.pdf"
    plt.savefig(output_pdf, format='pdf', bbox_inches='tight', dpi=100)
    pdf_combined.savefig(fig, bbox_inches='tight', dpi=100)
    print(f"Saved page {p_idx} to {output_pdf}")
    plt.close(fig)

# Finalize combined PDF
pdf_combined.close()
print(f"Saved combined multi-page PDF to {combined_pdf_path}")
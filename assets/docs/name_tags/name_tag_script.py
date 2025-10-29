from astropy.table import Table
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patheffects import withStroke
from matplotlib.backends.backend_pdf import PdfPages

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
bg_img = Image.open(bg_path).convert("RGB")

# Load the CSV
tab = Table.read(
    "../../data/SiN_AEW11_Information.csv",
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

name_col  = pick_column(tab, ["Presenter's Full Name", "Presenter’s Full Name", "Name", "Full Name"])
affil_col = pick_column(tab, ["Affiliation", "Institute", "Institution"])

def draw_name_tag(ax, bg_img, name, affil):
    ax.imshow(bg_img)

    # Get image size and correct text placement using image coordinates
    height, width = bg_img.size[1], bg_img.size[0]
    ax.set_xlim(0, width)
    ax.set_ylim(height, 0)

    # Add a white outline for better readability
    stroke_effect = withStroke(linewidth=3, foreground=(1, 1, 1, 0.8))  # white with alpha=0.9

    # Now text uses image pixel coordinates
    ax.text(width / 2, height * 0.30, name, ha="center", va="center",
            fontsize=24, weight="bold", color="black", path_effects=[stroke_effect])
    ax.text(width / 2, height * 0.50, affil, ha="center", va="center",
            fontsize=16, color="black", path_effects=[stroke_effect])

    ax.axis("off")

# Helper to chunk the table into pages of N entries
PER_PAGE = 10  # 5 rows x 2 cols

def paginate_indices(n_items, per_page=PER_PAGE):
    for start in range(0, n_items, per_page):
        yield range(start, min(start + per_page, n_items))

# Loop over all names, rendering 5x2 per page
page_iter = list(paginate_indices(len(tab), PER_PAGE))

# Combined multi-page PDF writer
combined_pdf_path = "name_tags_all_pages.pdf"
pdf_combined = PdfPages(combined_pdf_path)

for p_idx, idx_range in enumerate(tqdm(page_iter, desc="Pages", unit="page"), start=1):
    fig, axes = plt.subplots(5, 2, figsize=(16, 20))
    axes = axes.flatten()

    # Fill this page
    for ax, i in zip(axes, list(idx_range)):
        name  = str(tab[name_col][i]).strip()
        affil = str(tab[affil_col][i]).strip()
        draw_name_tag(ax, bg_img, name, affil)

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
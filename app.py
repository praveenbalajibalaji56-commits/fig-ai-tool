import io, re, zipfile
from pathlib import Path

import fitz
import numpy as np
import streamlit as st
from PIL import Image

st.set_page_config(page_title="FIG AI", page_icon="✂️", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1150px; padding-top: 2rem;}
.hero {padding: 1.5rem; border-radius: 18px; background: linear-gradient(120deg,#17152d,#30245b); color:white;}
.hero h1 {margin:0; font-size:2.5rem;}
.hero p {margin:.5rem 0 0; color:#ddd8f5;}
.small-muted {color:#777;}
</style>
<div class="hero">
<h1>FIG AI</h1>
<p>Find figures in research PDFs by caption. Extract clean figures without captions or excess white space.</p>
</div>
""", unsafe_allow_html=True)

CAPTION_RE = re.compile(
    r"(?im)^\s*(?:Figure|Fig\.?)\s*[\dIVX]+(?:[.\-]\d+)?\s*[:.\-]?\s*.*$"
)

def pil_from_pixmap(pix):
    mode = "RGBA" if pix.alpha else "RGB"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples).convert("RGB")

def trim_white(img, threshold=245, padding=8):
    """Trim near-white outer margins while retaining internal white areas."""
    arr = np.asarray(img.convert("RGB"))
    # Consider a pixel content if any channel is meaningfully darker than near-white.
    mask = np.min(arr, axis=2) < threshold
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return img
    x0, x1 = max(0, xs.min()-padding), min(img.width, xs.max()+padding+1)
    y0, y1 = max(0, ys.min()-padding), min(img.height, ys.max()+padding+1)
    return img.crop((x0, y0, x1, y1))

def find_captions(page):
    found = []
    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue
        text = "".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()
        if CAPTION_RE.match(text):
            found.append((fitz.Rect(block["bbox"]), text))
    return sorted(found, key=lambda x: x[0].y0)

def extract_one(page, caption_rect, all_caption_rects, scale=3.0):
    # Prefer an embedded image immediately above the caption.
    image_candidates = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 1 and "bbox" in block:
            r = fitz.Rect(block["bbox"])
            gap = caption_rect.y0 - r.y1
            overlap = max(0, min(r.x1, caption_rect.x1) - max(r.x0, caption_rect.x0))
            if -3 <= gap <= 180 and overlap > 0:
                image_candidates.append((gap, r))
    if image_candidates:
        image_rect = min(image_candidates, key=lambda x: abs(x[0]))[1]
        # Include nearby image blocks belonging to the same visual, but stop at caption.
        region = fitz.Rect(image_rect)
        for _, r in image_candidates:
            if r != image_rect and abs(r.y0 - image_rect.y0) < 150:
                region |= r
        region.y1 = min(region.y1, caption_rect.y0 - 2)
    else:
        # Fallback: crop the page area above the caption, bounded by prior caption.
        prior = [r for r in all_caption_rects if r.y1 <= caption_rect.y0 and r != caption_rect]
        top = max((r.y1 + 3 for r in prior), default=0)
        region = fitz.Rect(0, top, page.rect.width, max(top + 10, caption_rect.y0 - 2))

    region = region & page.rect
    if region.width < 20 or region.height < 20:
        return None
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), clip=region, alpha=False)
    img = pil_from_pixmap(pix)
    return trim_white(img)

def figure_name(index):
    return f"figure_{index}"

uploaded = st.file_uploader("Upload a research PDF", type=["pdf"])
if uploaded:
    raw = uploaded.getvalue()
    try:
        doc = fitz.open(stream=raw, filetype="pdf")
    except Exception as e:
        st.error(f"Could not open this PDF: {e}")
        st.stop()

    with st.spinner("Scanning PDF captions and figure regions..."):
        records = []
        for page_no, page in enumerate(doc):
            caps = find_captions(page)
            cap_rects = [x[0] for x in caps]
            for rect, caption in caps:
                img = extract_one(page, rect, cap_rects)
                if img:
                    records.append({
                        "page": page_no + 1,
                        "caption": caption,
                        "image": img,
                        "name": figure_name(len(records) + 1)
                    })

    st.success(f"Found {len(records)} captioned figure candidate(s) across {len(doc)} page(s).")
    if not records:
        st.warning("No selectable-text figure captions were detected. This first version needs text-based captions; scanned PDFs may require OCR.")
    else:
        query = st.text_input("Find a figure by caption or keyword", placeholder="e.g. system architecture, Figure 2")
        filtered = [r for r in records if query.lower() in r["caption"].lower()] if query else records

        c1, c2 = st.columns([2, 1])
        with c1:
            st.subheader(f"Figures ({len(filtered)})")
        with c2:
            st.caption("Output: figure only · caption removed · white margins trimmed")

        selected = list(filtered)
        for idx, rec in enumerate(filtered):
            with st.container(border=True):
                left, right = st.columns([1.5, 2])
                with left:
                    st.image(rec["image"], use_container_width=True)
                with right:
                    st.markdown(f"**{rec['caption']}**")
                    st.caption(f"PDF page {rec['page']}")
                    fmt = st.selectbox("Download format", ["PNG", "JPG"], key=f"fmt_{idx}")
                    buf = io.BytesIO()
                    rec["image"].save(buf, format=fmt, quality=95)
                    st.download_button("Download figure", data=buf.getvalue(),
                                       file_name=f"{rec['name']}.{fmt.lower()}",
                                       mime="image/png" if fmt == "PNG" else "image/jpeg",
                                       key=f"dl_{idx}")
                    st.caption(f"ZIP filename: {rec['name']}.png")

        if selected:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, rec in enumerate(selected, 1):
                    out = io.BytesIO()
                    rec["image"].save(out, format="PNG")
                    zf.writestr(f"{i:02d}_{rec['name']}_page_{rec['page']}.png", out.getvalue())
            st.download_button("Download all extracted figures as ZIP", zip_buf.getvalue(),
                               file_name="fig_ai_all_figures.zip",
                               mime="application/zip", type="primary")

st.divider()
st.caption("FIG AI prototype · Captions are used for matching only and are not included in exported images. Complex multi-column layouts, vector diagrams and scanned PDFs may need manual review.")

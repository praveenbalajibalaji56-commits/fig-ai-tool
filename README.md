# FIG AI — PDF Figure Extractor

A local web app prototype that scans selectable-text PDF pages for captions such as `Figure 1:` or `Fig. 2`, finds a nearby figure region, removes the caption from the output, trims outer near-white margins, and exports PNG/JPG or a ZIP.

## Run it

1. Install Python 3.10 or newer.
2. Extract this ZIP.
3. Open a terminal in the `fig_ai` folder.
4. Run:

```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

5. Open the local URL Streamlit prints (usually http://localhost:8501).

## Current prototype limitations

- Best with PDFs that contain selectable text and conventional `Figure` / `Fig.` captions.
- Scanned/image-only PDFs need OCR; this version does not yet include OCR.
- Figure-to-caption matching is heuristic. Multi-column papers, captions above figures, multi-panel figures, and vector-only diagrams may need review.
- The crop removes the caption and trims outer near-white margins, but does not guarantee perfect segmentation for every PDF.
- Uploaded PDFs are processed by the local app process; this prototype does not upload them to a hosted service.

## Production next steps

Add OCR for scanned PDFs, layout-aware figure detection, caption association across columns/pages, crop review controls, user accounts, storage policies, and deployment with authentication and upload limits.


## Updated export behavior

Figures are named sequentially as `figure_1.png`, `figure_2.png`, and so on.
The **Download all extracted figures as ZIP** button creates one ZIP containing
all figures in the current results, without captions.

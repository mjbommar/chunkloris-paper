PAPER  = main
ENGINE = lualatex
LFLAGS = -interaction=nonstopmode -halt-on-error
FIGS   = $(wildcard figures/*.pdf)
SRCS   = $(PAPER).tex sections/*.tex bib/references.bib

.PHONY: all clean watch figures distclean arxiv

all: $(PAPER).pdf

# Explicit build: lualatex -> biber -> lualatex -> lualatex.
# No -shell-escape required (no minted); arXiv builds the same way.
$(PAPER).pdf: $(SRCS) $(FIGS)
	$(ENGINE) $(LFLAGS) $(PAPER).tex
	biber $(PAPER)
	$(ENGINE) $(LFLAGS) $(PAPER).tex
	$(ENGINE) $(LFLAGS) $(PAPER).tex

# Regenerate the figure PDFs from the measurement data in ../replication,
# then copy the embedded PDFs into paper/figures/.
figures:
	cd ../replication/scripts && \
	  uv run --with matplotlib --with numpy --with seaborn python render_us_per_chunk.py && \
	  uv run --with matplotlib --with numpy --with seaborn python render_scaling.py && \
	  uv run --with matplotlib --with numpy --with seaborn python render_mode_a_vs_b.py && \
	  uv run --with matplotlib --with numpy --with seaborn python render_verdict_pie.py && \
	  uv run --with matplotlib --with numpy --with seaborn python render_ecosystem_bar.py && \
	  uv run --with matplotlib --with numpy --with seaborn python render_protocol_compare.py
	cp ../replication/figures/*.pdf figures/

# Rebuild paper whenever a source file changes.
watch:
	latexmk -$(ENGINE) -pvc -interaction=nonstopmode $(PAPER).tex

# Self-contained source tarball for arXiv upload (bundles main.bbl).
arxiv: $(PAPER).pdf
	tar czf ../chunkloris-paper-arxiv.tar.gz \
	  $(PAPER).tex $(PAPER).bbl sections/*.tex bib/references.bib \
	  figures/*.pdf figures/*.tex
	@echo "wrote ../chunkloris-paper-arxiv.tar.gz"

clean:
	rm -f *.aux *.log *.bbl *.bcf *.run.xml *.synctex.gz *-blx.bib *.out *.toc *.lof *.lot *.fls *.fdb_latexmk

distclean: clean
	rm -f $(PAPER).pdf

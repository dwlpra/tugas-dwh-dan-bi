LATEXMK := latexmk
OUT_DIR := render
LATEX_FLAGS := -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir=$(OUT_DIR)

.PHONY: all makalah slide prepare clean help

all: makalah slide

makalah: prepare
	$(LATEXMK) $(LATEX_FLAGS) Makalah.tex

slide: prepare
	$(LATEXMK) $(LATEX_FLAGS) "Slide Tugas II DWBI.tex"

prepare:
	mkdir -p $(OUT_DIR)/contents

clean:
	find $(OUT_DIR) -mindepth 1 -delete 2>/dev/null || true

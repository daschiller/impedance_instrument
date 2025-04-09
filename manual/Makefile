SRCS = $(wildcard *.md)
DEPS = $(wildcard images/*)
OUT = manual.pdf
COMMON_ARGS =
ifeq ($(V),1)
	COMMON_ARGS += --verbose
endif

.PHONY: all html pdf booklet docx clean watch

%.pdf: %.md $(DEPS)
	pandoc $(COMMON_ARGS) --pdf-engine=lualatex $< -o $@

%.html: %.md $(DEPS)
	pandoc $(COMMON_ARGS) --strip-comments -M mainfont=serif -M monofont=monospace \
		--embed-resources=true -s $< -o $@

%.docx: %.md $(DEPS)
	pandoc $(COMMON_ARGS) -t docx -s $< -o $@

all: pdf

booklet: $(OUT)
	pdfbook2 -p a4paper -o0 -i0 -t0 -b0 -n $<

html: $(patsubst %.md, %.html, $(SRCS))

pdf: $(patsubst %.md, %.pdf, $(SRCS))

docx: $(patsubst %.md, %.docx, $(SRCS))

watch:
	echo $(SRCS) | entr $(MAKE)

clean:
	rm -f *.pdf *.html *.docx

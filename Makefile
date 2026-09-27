PYTHON ?= python3
.PHONY: test summarize rtl
test:
	PYTHONPATH=diagnosis $(PYTHON) -m unittest discover -s diagnosis/tests -v
summarize:
	$(PYTHON) scripts/summarize_results.py
rtl:
	$(PYTHON) scripts/run_rtl.py

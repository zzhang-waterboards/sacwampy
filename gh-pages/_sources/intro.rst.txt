Introduction
============

Prerequisites
------------- 
Anaconda (No external libraries required). 

Git.

Usage
-----
'git clone' the repository for sacwampy. 

Add sacwampy path to PYTHONPATH (no installation required). 


Scripts
-------
**weapapi functions**: weapapi.py includes all generic functions to interact with WEAP. More details can be found in 'WEAP API Example' section.

**wsi-di related**: three modules are related to wsi-di curves:

			*calc_wsidi*: calculate existing wsi-di values.

			*wsidigenerator*: generate new curves by fitting the calculated wsi and di from calc_wsidi.

			*wsidi_main*: main script to recursively run Sacwam and generate final wsi-di curves.
			
			More details about wsi-di curve generation can be found in 'WSI-DI Curve Generation' section.

**postprocessing**: regression_testing.py compares the current run results with an archived run.

			More details about regression testing can be found in 'Regression test' section
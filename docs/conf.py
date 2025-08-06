from r2r_ctd.docker_ctl import SBEDP_IMAGE

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "r2r-ctd"
copyright = "2025, Regents of the University of California"
author = "Andrew Barna"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ["autoapi.extension", "myst_parser"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "furo"
html_static_path = ["_static"]

autoapi_dirs = ["../src"]

myst_enable_extensions = ["colon_fence", "fieldlist", "substitution"]

myst_substitutions = {"SBEDP_IMAGE": SBEDP_IMAGE}

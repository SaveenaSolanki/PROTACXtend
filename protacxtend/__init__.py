"""PROTACXtend package.

PROTACXtend is a deterministic, tool-augmented scaffold for component-aware
PROTAC design. Optional scientific dependencies such as RDKit, Pydantic,
LangGraph, LangChain, Agno, and Streamlit are integrated when installed.
"""

from protacxtend._compat import install as _install_compat

# Resolve ``synglue_agent.*`` references inside committed pickle artifacts to the
# renamed ``protacxtend.*`` package (see protacxtend/_compat.py). This is the
# ONLY intentional reference to the legacy package name in the runtime.
_install_compat()

__all__ = ["__version__"]

__version__ = "0.3.0"

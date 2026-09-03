"""SynGlue-Agent package.

SynGlue-Agent is a deterministic, tool-augmented scaffold for component-aware
PROTAC design. Optional scientific dependencies such as RDKit, Pydantic,
LangGraph, LangChain, Agno, and Streamlit are integrated when installed.
"""

from protacxtend._compat import install as _install_compat

_install_compat()  # resolve synglue_agent.* pickle references inside committed artifacts

__all__ = ["__version__"]

__version__ = "0.3.0"

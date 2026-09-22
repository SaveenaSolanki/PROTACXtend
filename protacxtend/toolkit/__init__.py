"""PROTACXtend toolkit package.

This package hosts two complementary layers:

* **Excel-backed capability registry** (:mod:`protacxtend.toolkit.registry`,
  :mod:`protacxtend.toolkit.schema`, :mod:`protacxtend.toolkit.status`) — the
  master ``Agent_Toolkit.xlsx`` view of modalities, tools, databases, packages,
  skills and agents.
* **Provisioning / detection / truth** (:mod:`protacxtend.toolkit.environments`,
  :mod:`protacxtend.toolkit.catalog`, :mod:`protacxtend.toolkit.provision`,
  :mod:`protacxtend.toolkit.bridge`, :mod:`protacxtend.toolkit.truth`) — the
  cross-environment install/verify engine and the single-source-of-truth
  workbook + markdown for tool, dataset and dependency versions.

The provisioning modules are imported lazily (via submodule imports); only the
Excel-registry API is re-exported here.
"""

from protacxtend.toolkit.registry import (
    get_agent_module,
    get_agent_modules,
    get_databases,
    get_modalities,
    get_packages,
    get_skills,
    get_tools,
    load_toolkit_registry,
    search_databases,
    search_registry,
    search_skills,
    search_tools,
    summarize_registry,
)
from protacxtend.toolkit.status import (
    classify_existing_implementation,
    detect_cli_availability,
    detect_package_availability,
    get_all_tool_statuses,
    get_tool_status,
    summarize_toolkit_status,
)

__all__ = [
    "get_agent_module",
    "get_agent_modules",
    "get_databases",
    "get_modalities",
    "get_packages",
    "get_skills",
    "get_tools",
    "load_toolkit_registry",
    "search_databases",
    "search_registry",
    "search_skills",
    "search_tools",
    "summarize_registry",
    "classify_existing_implementation",
    "detect_cli_availability",
    "detect_package_availability",
    "get_all_tool_statuses",
    "get_tool_status",
    "summarize_toolkit_status",
]

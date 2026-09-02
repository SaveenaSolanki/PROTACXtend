"""Shared OpenMP/BLAS thread bounding for PROTACXtend.

Why: sklearn HistGradientBoosting (and other numpy/BLAS users) open libgomp
parallel regions per call. On shared/loaded machines the OpenMP barrier spin
makes single-row predictions take ~10-30 s each (measured on this box at
load>40: ~11 s per HGB model vs <1 ms with a bounded pool). Thread bounding
makes inference fast, predictable, and load-immune.

Usage:
    from synglue_agent.tools.thread_limits import apply_thread_limits, bounded
    apply_thread_limits()          # call EARLY, before heavy imports
    with bounded(1):               # context-manage pools around hot loops
        model.predict(x)
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

logger = logging.getLogger("protacpilot.thread_limits")

DEFAULT_LIMIT = 4


def apply_thread_limits(limit: Optional[int] = None) -> int:
    """Set process-wide env defaults for OpenMP/BLAS/MKL thread pools.

    Must run BEFORE numpy/sklearn/torch pools initialize for full effect
    (libgomp reads these at pool creation); harmless afterwards.
    Returns the effective limit.
    """
    limit = int(limit or os.environ.get("PROTACPILOT_THREAD_LIMIT") or DEFAULT_LIMIT)
    os.environ.setdefault("OMP_NUM_THREADS", str(limit))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(limit))
    os.environ.setdefault("MKL_NUM_THREADS", str(limit))
    os.environ.setdefault("NUMEXPR_NUM_THREADS", str(limit))
    return limit


@contextmanager
def bounded(limit: int = 1, user_api: str = "openmp") -> Iterator[None]:
    """Temporarily cap a library's thread pool (openmp|blas) via threadpoolctl.

    Falls back to no-op when threadpoolctl is unavailable.
    """
    try:
        from threadpoolctl import threadpool_limits

        with threadpool_limits(limits=max(1, int(limit)), user_api=user_api):
            yield
    except Exception as exc:  # noqa: BLE001
        logger.debug("threadpool_limits unavailable (%s); running unbounded", exc)
        yield
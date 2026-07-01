from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalConfig:
    k: int = 8                            # total facts returned (incl. the 2 headline slots)
    recent_n: int = 6                     # thread messages used to build the relevance query
    k0: float = 4.0                       # blend midpoint: alpha(d) = d / (d + k0)
    common_ground_limit: int = 6
    min_common_ground_sim: float = 0.5    # drop weak "shared ground" pairs


DEFAULT_CONFIG = RetrievalConfig()

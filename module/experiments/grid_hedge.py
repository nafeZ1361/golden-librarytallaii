"""Pure Grid/Hedge planning helpers. No MT5 access and no order side effects."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class GridHedgeConfig:
    step_price: float = 0.20
    levels: int = 5

    def __post_init__(self) -> None:
        if self.step_price <= 0 or self.levels < 1:
            raise ValueError("step_price must be positive and levels must be >= 1")

def pending_levels(mid_price: float, config: GridHedgeConfig) -> dict[str, list[float]]:
    """Plan symmetric buy-stop/sell-stop levels; execution remains elsewhere."""
    if mid_price <= 0:
        raise ValueError("mid_price must be positive")
    return {
        "buy": [round(mid_price + i * config.step_price, 10) for i in range(1, config.levels + 1)],
        "sell": [round(mid_price - i * config.step_price, 10) for i in range(1, config.levels + 1)],
    }

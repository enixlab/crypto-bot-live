"""Hyperliquid exchange client — wrapper du SDK officiel.

Documentation officielle :
  https://github.com/hyperliquid-dex/hyperliquid-python-sdk
  https://hyperliquid.gitbook.io/hyperliquid-docs/

Usage :
    client = HyperliquidClient.from_env()
    client.check()                             # ping & balance
    client.place_order("LINK", is_buy=True, sz=10, limit_px=12.5, leverage=3)
    client.get_positions()
    client.close_position("LINK")
"""
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


def _lazy_import():
    """Import du SDK Hyperliquid uniquement quand nécessaire (paper mode s'en passe)."""
    from eth_account import Account  # type: ignore
    from hyperliquid.exchange import Exchange  # type: ignore
    from hyperliquid.info import Info  # type: ignore
    from hyperliquid.utils import constants  # type: ignore
    return Account, Exchange, Info, constants


@dataclass
class Position:
    coin: str
    size: float            # signé : positif=long, négatif=short
    entry_price: float
    mark_price: float
    unrealized_pnl: float
    leverage: int
    margin_used: float


class HyperliquidClient:
    """Wrapper minimal autour du SDK officiel Hyperliquid.

    Supporte testnet et mainnet. Toutes les opérations qui touchent
    au compte sont signées par l'API wallet (clé privée séparée du
    MetaMask seed). Le compte principal reste le wallet MetaMask
    qui détient les fonds — l'API wallet ne peut que trader.
    """

    def __init__(
        self,
        private_key: str,
        account_address: str,
        network: str = "testnet",
    ):
        if not private_key or not private_key.startswith("0x"):
            raise ValueError("HYPERLIQUID_PRIVATE_KEY doit commencer par 0x")
        if not account_address or not account_address.startswith("0x"):
            raise ValueError("HYPERLIQUID_ACCOUNT_ADDRESS doit commencer par 0x")

        Account, Exchange, Info, constants = _lazy_import()
        self.account_address = account_address
        self.network = network
        self.base_url = (
            constants.MAINNET_API_URL if network == "mainnet"
            else constants.TESTNET_API_URL
        )

        self._wallet = Account.from_key(private_key)
        self.info = Info(self.base_url, skip_ws=True)
        self.exchange = Exchange(
            self._wallet,
            self.base_url,
            account_address=account_address,
        )
        log.info("HyperliquidClient ready (%s, account=%s, api_wallet=%s)",
                 network, account_address[:6] + "...", self._wallet.address[:6] + "...")

    @classmethod
    def from_env(cls) -> "HyperliquidClient":
        return cls(
            private_key=os.environ["HYPERLIQUID_PRIVATE_KEY"],
            account_address=os.environ["HYPERLIQUID_ACCOUNT_ADDRESS"],
            network=os.environ.get("HYPERLIQUID_NETWORK", "testnet"),
        )

    # ===== READ =====

    def get_user_state(self) -> dict:
        return self.info.user_state(self.account_address)

    def get_balance_usdc(self) -> float:
        state = self.get_user_state()
        return float(state.get("marginSummary", {}).get("accountValue", 0))

    def get_positions(self) -> list[Position]:
        state = self.get_user_state()
        out: list[Position] = []
        for ap in state.get("assetPositions", []):
            pos = ap.get("position", {})
            size = float(pos.get("szi", 0))
            if size == 0:
                continue
            out.append(Position(
                coin=pos["coin"],
                size=size,
                entry_price=float(pos.get("entryPx", 0)),
                mark_price=float(self.get_mark_price(pos["coin"])),
                unrealized_pnl=float(pos.get("unrealizedPnl", 0)),
                leverage=int(pos.get("leverage", {}).get("value", 1)),
                margin_used=float(pos.get("marginUsed", 0)),
            ))
        return out

    def get_mark_price(self, coin: str) -> float:
        mids = self.info.all_mids()
        return float(mids.get(coin, 0))

    # ===== WRITE =====

    def set_leverage(self, coin: str, leverage: int, is_cross: bool = True) -> dict:
        """Hard cap leverage at 3x in this codebase (safety)."""
        if leverage > 3:
            raise ValueError(f"Leverage {leverage} dépasse le cap de 3x")
        return self.exchange.update_leverage(leverage, coin, is_cross)

    def place_order(
        self,
        coin: str,
        is_buy: bool,
        sz: float,
        limit_px: float,
        leverage: int = 3,
        reduce_only: bool = False,
        tif: str = "Gtc",
    ) -> dict:
        """Place un ordre limit. tif: Gtc (good til cancel), Ioc, Alo."""
        self.set_leverage(coin, leverage)
        order_type = {"limit": {"tif": tif}}
        res = self.exchange.order(coin, is_buy, sz, limit_px, order_type, reduce_only)
        log.info("place_order coin=%s side=%s sz=%s px=%s -> %s",
                 coin, "BUY" if is_buy else "SELL", sz, limit_px, res)
        return res

    def market_buy(self, coin: str, sz: float, leverage: int = 3) -> dict:
        """Approximation market via limit prix légèrement décalé."""
        mark = self.get_mark_price(coin)
        limit_px = round(mark * 1.005, 4)  # 50 bps de slippage acceptable
        return self.place_order(coin, True, sz, limit_px, leverage, tif="Ioc")

    def market_sell(self, coin: str, sz: float, leverage: int = 3) -> dict:
        mark = self.get_mark_price(coin)
        limit_px = round(mark * 0.995, 4)
        return self.place_order(coin, False, sz, limit_px, leverage, tif="Ioc")

    def close_position(self, coin: str) -> Optional[dict]:
        for pos in self.get_positions():
            if pos.coin == coin:
                # Reverse side: long → sell, short → buy
                return self.place_order(
                    coin=coin,
                    is_buy=pos.size < 0,
                    sz=abs(pos.size),
                    limit_px=self.get_mark_price(coin) * (0.995 if pos.size > 0 else 1.005),
                    leverage=pos.leverage,
                    reduce_only=True,
                    tif="Ioc",
                )
        return None

    def cancel_all_orders(self) -> dict:
        return self.exchange.cancel_all()

    # ===== SAFETY =====

    def check(self) -> dict:
        """Sanity check : ping API, vérifie balance, leverage cap."""
        balance = self.get_balance_usdc()
        positions = self.get_positions()
        result = {
            "network": self.network,
            "account": self.account_address,
            "api_wallet": self._wallet.address,
            "balance_usdc": balance,
            "open_positions": len(positions),
            "ok": balance > 0,
        }
        log.info("Hyperliquid check: %s", result)
        return result


if __name__ == "__main__":
    # Test rapide : python -m bot.core.hyperliquid_client
    import json
    from dotenv import load_dotenv
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    load_dotenv()
    client = HyperliquidClient.from_env()
    print(json.dumps(client.check(), indent=2, default=str))
    print("\n=== Positions ===")
    for p in client.get_positions():
        print(p)

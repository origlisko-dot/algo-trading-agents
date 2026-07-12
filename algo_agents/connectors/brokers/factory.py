"""Select the active paper broker: simulated (default), IBKR, or Alpaca."""
from __future__ import annotations

from algo_agents.config import get_settings
from algo_agents.connectors.base import BrokerConnector, ConnectorStatus
from algo_agents.connectors.brokers.alpaca_broker import AlpacaBroker
from algo_agents.connectors.brokers.ibkr_broker import IBKRBroker
from algo_agents.connectors.brokers.simulated_broker import SimulatedBroker
from algo_agents.observability.logging import get_logger

_log = get_logger(__name__)

_BROKERS = {
    "simulated": SimulatedBroker,
    "sim": SimulatedBroker,
    "local": SimulatedBroker,
    "ibkr": IBKRBroker,
    "alpaca": AlpacaBroker,
}


def get_paper_broker() -> BrokerConnector:
    """Return broker per PAPER_BROKER setting, or first ready broker in auto mode."""
    settings = get_settings()
    choice = settings.paper_broker.strip().lower()

    if choice in _BROKERS:
        return _BROKERS[choice]()

    if choice == "auto":
        for name in ("ibkr", "alpaca", "simulated"):
            broker = _BROKERS[name]()
            if broker.check().ok:
                _log.info("auto-selected paper broker: %s", name)
                return broker
        return SimulatedBroker()

    _log.warning("Unknown PAPER_BROKER=%s, using simulated", choice)
    return SimulatedBroker()


def broker_status(broker: BrokerConnector) -> ConnectorStatus:
    return broker.check()

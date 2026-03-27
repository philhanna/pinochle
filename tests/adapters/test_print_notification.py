# tests.adapters.test_print_notification
from pinochle.adapters.print_notification import PrintNotification
from tests.ports.test_notification_port import run_contract


def test_contract():
    """Verify the print-based notifier satisfies the shared contract."""
    run_contract(PrintNotification())

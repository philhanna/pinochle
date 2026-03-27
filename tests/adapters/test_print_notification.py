# tests.adapters.test_print_notification
from pinochle.adapters.outbound.print_notification import PrintNotification
from tests.ports.test_notification_port import run_contract


def test_contract():
    run_contract(PrintNotification())

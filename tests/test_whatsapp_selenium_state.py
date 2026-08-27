
import pytest

def test_activation_gate_requires_start_command():
    from remax_bot.whatsapp_state import ActivationGate
    g=ActivationGate()
    assert g.handle("#izmit kiralık daire#") == ("ignore", None)

def test_activation_gate_starts_and_stops():
    from remax_bot.whatsapp_state import ActivationGate
    g=ActivationGate()
    assert g.handle("#bot başlat#")[0] == "started"
    assert g.active is True
    assert g.handle("#izmit kiralık daire#") == ("query", "#izmit kiralık daire#")
    assert g.handle("#bot durdur#")[0] == "stopped"
    assert g.active is False

def test_help_only_after_activation():
    from remax_bot.whatsapp_state import ActivationGate
    g=ActivationGate()
    assert g.handle("#?")[0] == "ignore"
    g.handle("#bot başlat#")
    assert g.handle("#?") == ("query", "#?")

def test_normal_chat_is_always_ignored():
    from remax_bot.whatsapp_state import ActivationGate
    g=ActivationGate(); g.handle("#bot başlat#")
    assert g.handle("merhaba") == ("ignore", None)

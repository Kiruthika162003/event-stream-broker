from __future__ import annotations

import pytest

from relay.connectionquota import ConnectionQuota
from relay.errors import Invalid


class TestPerIp:
    def test_connections_up_to_the_per_ip_cap_are_accepted(self):
        q = ConnectionQuota(per_ip_cap=2, broker_cap=100)
        q.open("10.0.0.5")
        assert "accepted from 10.0.0.5" in q.open("10.0.0.5")

    def test_over_the_per_ip_cap_is_refused(self):
        q = ConnectionQuota(per_ip_cap=2, broker_cap=100)
        q.open("10.0.0.5")
        q.open("10.0.0.5")
        with pytest.raises(Invalid) as caught:
            q.open("10.0.0.5")
        assert "this host alone is the problem" in str(caught.value)

    def test_another_host_is_unaffected(self):
        q = ConnectionQuota(per_ip_cap=2, broker_cap=100)
        q.open("10.0.0.5")
        q.open("10.0.0.5")
        assert "accepted from 10.0.0.6" in q.open("10.0.0.6")


class TestBrokerWide:
    def test_the_broker_cap_fires_even_under_per_ip(self):
        q = ConnectionQuota(per_ip_cap=100, broker_cap=2)
        q.open("a")
        q.open("b")
        with pytest.raises(Invalid) as caught:
            q.open("c")
        assert "saturated overall" in str(caught.value)


class TestInterbrokerExempt:
    def test_interbroker_connections_skip_the_per_ip_cap(self):
        q = ConnectionQuota(per_ip_cap=1, broker_cap=100)
        q.open("peer", interbroker=True)
        assert "accepted from peer" in q.open("peer", interbroker=True)


class TestBusiest:
    def test_it_names_the_busiest_host(self):
        q = ConnectionQuota(per_ip_cap=10, broker_cap=100)
        q.open("a")
        q.open("a")
        q.open("b")
        note = q.busiest()
        assert "a holds 2/3" in note

    def test_closing_decrements(self):
        q = ConnectionQuota(per_ip_cap=10, broker_cap=100)
        q.open("a")
        q.close("a")
        assert "no connections open" in q.busiest()

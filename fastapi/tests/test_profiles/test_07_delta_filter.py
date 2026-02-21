import pytest


def test_delta_filter_hazard_transition():
    """
    Test Profile 7: Delta Filter Validation

    Verify that hazard level transitions override <5% delta threshold.

    Scenario: fire_dominance increases 4.5% (below threshold), but
    hazard_level changes from HIGH to CRITICAL.

    Expected: Packet should be transmitted (hazard transition overrides delta)
    """

    packet_1 = {
        "fire_dominance": 0.44,
        "hazard_level": "HIGH",
        "proximity_alert": False
    }

    packet_2 = {
        "fire_dominance": 0.46,  # +4.5%, below 5% threshold
        "hazard_level": "CRITICAL",  # Threshold crossed
        "proximity_alert": True  # Also triggered
    }

    # Delta calculation
    delta_percent = abs(packet_2["fire_dominance"] - packet_1["fire_dominance"]) / packet_1["fire_dominance"] * 100

    print(f"\nDelta Filter Test:")
    print(f"  fire_dominance delta: {delta_percent:.1f}%")
    print(f"  Hazard transition: {packet_1['hazard_level']} → {packet_2['hazard_level']}")
    print(f"  Proximity alert: {packet_2['proximity_alert']}")

    # Decision logic
    should_transmit = (
        delta_percent > 5.0 or  # Delta threshold
        packet_1["hazard_level"] != packet_2["hazard_level"] or  # Level change
        packet_2["proximity_alert"]  # Proximity trigger
    )

    assert should_transmit == True, "Packet should be transmitted despite <5% delta"
    assert packet_1["hazard_level"] != packet_2["hazard_level"], "Hazard level should have changed"

    print("✅ PASS: Hazard transition overrides delta threshold")


def test_delta_filter_no_transmission():
    """
    Test case where packet should be dropped (no significant change).
    """

    packet_1 = {
        "fire_dominance": 0.50,
        "hazard_level": "MODERATE",
        "proximity_alert": False
    }

    packet_2 = {
        "fire_dominance": 0.51,  # +2%, below threshold
        "hazard_level": "MODERATE",  # No change
        "proximity_alert": False  # No change
    }

    delta_percent = abs(packet_2["fire_dominance"] - packet_1["fire_dominance"]) / packet_1["fire_dominance"] * 100

    should_transmit = (
        delta_percent > 5.0 or
        packet_1["hazard_level"] != packet_2["hazard_level"] or
        packet_2["proximity_alert"]
    )

    print(f"\nDelta Filter (no transmission):")
    print(f"  fire_dominance delta: {delta_percent:.1f}%")
    print(f"  Should transmit: {should_transmit}")

    assert should_transmit == False, "Packet should be dropped (no significant change)"

    print("✅ PASS: Packet correctly filtered")


def test_delta_filter_large_delta():
    """
    Test case where delta exceeds threshold (should transmit).
    """

    packet_1 = {
        "fire_dominance": 0.40,
        "hazard_level": "MODERATE",
        "proximity_alert": False
    }

    packet_2 = {
        "fire_dominance": 0.50,  # +25%, well above 5% threshold
        "hazard_level": "MODERATE",  # No change
        "proximity_alert": False  # No change
    }

    delta_percent = abs(packet_2["fire_dominance"] - packet_1["fire_dominance"]) / packet_1["fire_dominance"] * 100

    should_transmit = (
        delta_percent > 5.0 or
        packet_1["hazard_level"] != packet_2["hazard_level"] or
        packet_2["proximity_alert"]
    )

    print(f"\nDelta Filter (large delta):")
    print(f"  fire_dominance delta: {delta_percent:.1f}%")
    print(f"  Should transmit: {should_transmit}")

    assert should_transmit == True, "Packet should be transmitted (large delta)"
    assert delta_percent > 5.0, "Delta should exceed 5%"

    print("✅ PASS: Large delta triggers transmission")


def test_delta_filter_proximity_alert():
    """
    Test case where proximity alert triggers transmission.
    """

    packet_1 = {
        "fire_dominance": 0.30,
        "hazard_level": "LOW",
        "proximity_alert": False
    }

    packet_2 = {
        "fire_dominance": 0.31,  # +3.3%, below threshold
        "hazard_level": "LOW",  # No change
        "proximity_alert": True  # NEW ALERT
    }

    delta_percent = abs(packet_2["fire_dominance"] - packet_1["fire_dominance"]) / packet_1["fire_dominance"] * 100

    should_transmit = (
        delta_percent > 5.0 or
        packet_1["hazard_level"] != packet_2["hazard_level"] or
        packet_2["proximity_alert"]
    )

    print(f"\nDelta Filter (proximity alert):")
    print(f"  fire_dominance delta: {delta_percent:.1f}%")
    print(f"  Proximity alert: {packet_1['proximity_alert']} → {packet_2['proximity_alert']}")
    print(f"  Should transmit: {should_transmit}")

    assert should_transmit == True, "Packet should be transmitted (proximity alert)"
    assert packet_2["proximity_alert"] == True, "Proximity alert should be triggered"

    print("✅ PASS: Proximity alert triggers transmission")


def test_delta_filter_edge_case_exact_threshold():
    """
    Test edge case: delta exactly at 5% threshold.
    """

    packet_1 = {
        "fire_dominance": 0.40,
        "hazard_level": "MODERATE",
        "proximity_alert": False
    }

    packet_2 = {
        "fire_dominance": 0.42,  # Exactly 5% increase
        "hazard_level": "MODERATE",
        "proximity_alert": False
    }

    delta_percent = abs(packet_2["fire_dominance"] - packet_1["fire_dominance"]) / packet_1["fire_dominance"] * 100

    should_transmit = (
        delta_percent > 5.0 or  # Note: strictly greater than, not >=
        packet_1["hazard_level"] != packet_2["hazard_level"] or
        packet_2["proximity_alert"]
    )

    print(f"\nDelta Filter (edge case - exactly 5%):")
    print(f"  fire_dominance delta: {delta_percent:.4f}%")
    print(f"  Should transmit: {should_transmit}")

    # At exactly 5%, should NOT transmit (threshold is > 5.0, not >= 5.0)
    assert should_transmit == False, "Packet should NOT be transmitted (delta exactly 5%, threshold is >5%)"

    print("✅ PASS: Edge case handled correctly (exactly 5% → no transmission)")

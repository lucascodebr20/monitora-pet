import unittest

from app.domain.zone_presence import PresenceState, TransitionType, ZonePresenceMachine


class ZonePresenceTests(unittest.TestCase):
    def test_confirms_only_after_minimum_presence(self):
        machine = ZonePresenceMachine()

        self.assertEqual(machine.observe(True, 0.7, 10, 3, 1, 5), [])
        self.assertEqual(machine.observe(True, 0.8, 12, 3, 1, 5), [])
        transitions = machine.observe(True, 0.9, 13, 3, 1, 5)

        self.assertEqual(machine.state, PresenceState.ACTIVE)
        self.assertEqual(transitions[0].type, TransitionType.CONFIRM)
        self.assertEqual(transitions[0].confidence, 0.9)

    def test_discards_short_presence(self):
        machine = ZonePresenceMachine()

        machine.observe(True, 0.8, 10, 3, 1, 5)
        transitions = machine.observe(False, 0, 12, 3, 1, 5)

        self.assertEqual(transitions, [])
        self.assertEqual(machine.state, PresenceState.OUTSIDE)

    def test_return_during_cooldown_keeps_event_active(self):
        machine = ZonePresenceMachine()
        machine.observe(True, 0.8, 10, 1, 1, 5)
        machine.observe(True, 0.8, 11, 1, 1, 5)
        machine.observe(False, 0, 13, 1, 1, 5)

        self.assertEqual(machine.state, PresenceState.COOLDOWN)
        transitions = machine.observe(True, 0.8, 14, 1, 1, 5)

        self.assertEqual(transitions, [])
        self.assertEqual(machine.state, PresenceState.ACTIVE)

    def test_finishes_after_cooldown(self):
        machine = ZonePresenceMachine()
        machine.observe(True, 0.8, 10, 1, 1, 5)
        machine.observe(True, 0.8, 11, 1, 1, 5)
        machine.observe(False, 0, 13, 1, 1, 5)
        transitions = machine.observe(False, 0, 16, 1, 1, 5)

        self.assertEqual(transitions[0].type, TransitionType.FINISH)
        self.assertEqual(machine.state, PresenceState.OUTSIDE)


if __name__ == "__main__":
    unittest.main()

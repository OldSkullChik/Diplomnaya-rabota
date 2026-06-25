from django.test import SimpleTestCase

from annotation.monitoring.cascade import omsu_decision


class MonitoringCascadeDecisionTests(SimpleTestCase):
    def test_strong_negative_score_promotes_mid_probability_negative(self):
        decision, band, weight = omsu_decision(
            0.79,
            0.85,
            0.15,
            score=-80,
        )

        self.assertEqual(decision, "negative_omsu")
        self.assertEqual(band, "strong_score_negative")
        self.assertEqual(weight, 0.75)

    def test_mid_probability_without_strong_score_stays_low_confidence(self):
        decision, band, weight = omsu_decision(
            0.79,
            0.85,
            0.15,
            score=-20,
        )

        self.assertEqual(decision, "low_confidence")
        self.assertEqual(band, "low_confidence")
        self.assertEqual(weight, 0.0)

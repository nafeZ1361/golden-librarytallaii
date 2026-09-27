import unittest
import numpy as np
import pandas as pd
from ml_signal_adapter import signal_from_positive_probability, probabilities_to_signals

class SignalAdapterTests(unittest.TestCase):
    def test_long_flat_short_boundaries(self):
        self.assertEqual(signal_from_positive_probability(0.90), 1)
        self.assertEqual(signal_from_positive_probability(0.50), 0)
        self.assertEqual(signal_from_positive_probability(0.55), 1)
        self.assertEqual(signal_from_positive_probability(0.54), 0)
        self.assertEqual(signal_from_positive_probability(0.46), 0)
        self.assertEqual(signal_from_positive_probability(0.45), -1)

    def test_invalid_probability_and_threshold(self):
        with self.assertRaises(ValueError): signal_from_positive_probability(-0.1)
        with self.assertRaises(ValueError): signal_from_positive_probability(1.1)
        with self.assertRaises(ValueError): signal_from_positive_probability(0.5, threshold=0.5)
        with self.assertRaises(ValueError): signal_from_positive_probability(0.5, threshold=1.0)

    def test_vector_mapping(self):
        self.assertEqual(probabilities_to_signals([0.2,0.5,0.6,0.9]), [-1,0,1,1])

if __name__ == "__main__":
    unittest.main()

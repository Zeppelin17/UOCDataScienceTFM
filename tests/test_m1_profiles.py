import numpy as np
import pandas as pd
import pytest

pytest.importorskip("scipy")

from tfm.m1_profiles import MIN_EXAMPLES, local_effects
from tfm.walk_forward import SIGNAL_COLUMNS


def test_local_effects_preserve_linear_slope_and_do_not_bridge_missing_intervals():
    feature, other = SIGNAL_COLUMNS
    values = np.repeat([-1.5, -.5, .5, 1.5], MIN_EXAMPLES)
    rows = pd.DataFrame({feature: values, other: values * 4})
    edges = np.arange(-2., 3.)

    def score(x):
        return 2 * x[:, 0] + 3 * x[:, 1]

    intervals, effects = local_effects(rows, feature, edges, score)
    assert intervals.examples.eq(MIN_EXAMPLES).all()
    np.testing.assert_array_equal(effects, 2 * edges)

    rows = rows.loc[rows[feature].ne(.5)]
    intervals, effects = local_effects(rows, feature, edges, score)
    assert intervals.examples.tolist() == [MIN_EXAMPLES, MIN_EXAMPLES, 0, MIN_EXAMPLES]
    np.testing.assert_array_equal(effects, [-4., -2., 0., np.nan, np.nan])

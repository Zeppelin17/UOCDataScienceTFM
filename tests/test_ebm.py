"""Aportaciones aditivas, purga y dependencia de las referencias de boosting."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("interpret.glassbox")

from tfm.boosting import RESULT_NAMES as BOOSTING_RESULTS
from tfm.data import read_result, save_result
from tfm.ebm import RESULT_NAMES, ebm_curves, fit_ebm_partition
from tfm.walk_forward import SIGNAL_COLUMNS
from test_logistic import fixture_samples


def test_ebm_adds_two_terms_and_uses_only_training_labels():
    _, _, samples = fixture_samples()
    rows = samples.loc[samples.sample_usable & samples.strategy.eq("reversal")]
    train = rows.loc[rows.target_period.lt("1949-12")]
    validation = rows.loc[rows.target_period.between("1950-01", "1950-12")]
    model, probabilities = fit_ebm_partition(train, validation, year=1950)
    _, flipped = fit_ebm_partition(train, validation.assign(label=1-validation.label), year=1950)
    np.testing.assert_array_equal(probabilities, flipped)
    x = validation[SIGNAL_COLUMNS].to_numpy(dtype=float)
    assert model.term_features_ == [(0,), (1,)]
    score = model.intercept_[0] + model.eval_terms(x).sum(axis=1)
    np.testing.assert_allclose(probabilities, 1 / (1 + np.exp(-score)), rtol=0, atol=1e-12)
    curves = ebm_curves(model, strategy="reversal", year=1950)
    assert curves.groupby("feature").examples.sum().eq(len(train)).all()
    with pytest.raises(ValueError, match="purga"):
        fit_ebm_partition(train.assign(target_period="1949-12"), validation, year=1950)


def test_republishing_boosting_invalidates_ebm_tables(tmp_path):
    table = pd.DataFrame({"prediction": [.5]})
    for name in RESULT_NAMES:
        save_result(tmp_path, name, table, {})
    save_result(tmp_path, BOOSTING_RESULTS[0], table, {})
    pd.testing.assert_frame_equal(read_result(tmp_path, BOOSTING_RESULTS[0])[0], table)
    for name in RESULT_NAMES:
        with pytest.raises(ValueError, match="secciones 37–39"):
            read_result(tmp_path, name)

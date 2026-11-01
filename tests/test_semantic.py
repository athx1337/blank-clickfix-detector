import numpy as np
import pytest

from ml.semantic import aggregate_embeddings, token_windows


def test_token_windows_preserve_tail_and_report_overflow():
    windows, truncated = token_windows(list(range(500)))
    assert windows[0] == list(range(254))
    assert windows[1][0] == 222
    assert windows[-1][-1] == 499
    assert not truncated
    windows, truncated = token_windows(list(range(3000)))
    assert len(windows) == 8 and truncated
    assert token_windows([]) == ([[]], False)


def test_normalized_window_aggregation():
    actual = aggregate_embeddings(np.array([[3., 0.], [0., 4.]]))
    np.testing.assert_allclose(actual, [2**-0.5, 2**-0.5])
    with pytest.raises(ValueError):
        aggregate_embeddings(np.array([[float('nan'), 0.]]))

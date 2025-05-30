import logging

import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class MTableGenerator:
    def __init__(self, k, p, alpha):
        # assign parameters
        self.k = k
        self.p = p
        self.alpha = alpha
        self._mtable = self._compute_mtable()

    def mtable_as_list(self):
        return [int(i) for i in self._mtable.m.tolist()]

    def mtable_as_dataframe(self):
        return self._mtable

    def m(self, k):
        if k < 1:
            msg = "Parameter k must be at least 1"
            raise ValueError(msg)

        if k > self.k:
            msg = f"Parameter k must be at most {self.k}"
            raise ValueError(msg)

        result = stats.binom.ppf(self.alpha, k, self.p)
        return 0 if result < 0 else result

    def _compute_mtable(self):
        """Computes a table containing the minimum number of protected elements
        required at each position
        """
        mtable = pd.DataFrame(columns=["m"])
        for i in range(1, self.k + 1):
            if i % 2000 == 0:
                logger.info(f"Computing m: {i:.0f} of {self.k:.0f}")
            mtable.loc[i] = [self.m(i)]
        return mtable


def compute_aux_mtable(mtable):
    """
    Stores the inverse of an mTable entry and the size of the block with respect to the inverse
    """
    if not (isinstance(mtable, pd.DataFrame)):
        msg = "Internal mtable must be a DataFrame"
        raise TypeError(msg)

    aux_mtable = pd.DataFrame(columns=["inv", "block"])
    last_m_seen = 0
    last_position = 0
    for position in range(1, len(mtable)):
        if position % 2000 == 0:
            logger.info(f"Computing m inverse: {position:.0f} of {len(mtable):.0f}")
        if mtable.at[position, "m"] == last_m_seen + 1:
            last_m_seen += 1
            aux_mtable.loc[position] = [position, position - last_position]
            last_position = position
        elif mtable.at[position, "m"] != last_m_seen:
            msg = "Inconsistent mtable"
            raise RuntimeError(msg)

    return aux_mtable

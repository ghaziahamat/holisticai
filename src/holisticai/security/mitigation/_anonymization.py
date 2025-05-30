from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


class Anonymize:
    """Anonymize
    Class for performing tailored, model-guided anonymization of training datasets for ML models.

    Parameters
    ----------
    k : int
        The privacy parameter that determines the number of records that will be indistinguishable from each
        other (when looking at the quasi identifiers). Should be at least 2.

    quasi_identifiers :  np.ndarray or list of strings or integers.
        The features that need to be minimized in case of pandas data, and indexes of features
        in case of numpy data.

    quasi_identifer_slices: list of lists of strings or integers.
        If some of the quasi-identifiers represent 1-hot encoded features that need to remain
        consistent after anonymization, provide a list containing the list of column names
        or indexes that represent a single feature.

    categorical_features : list
        The list of categorical features (if supplied, these featurtes will be one-hot encoded
        before using them to train the decision tree model).

    is_regression : bool
        Whether the model is a regression model or not (if False, assumes a classification model).
        Default is False.

    train_only_QI : bool
        The required method to train data set for anonymization. Default is
        to train the tree on all features.


    References
    ----------

    Goldsteen, Abigail, Gilad Ezov, Ron Shmelkin, Micha Moffie, and Ariel Farkash. "Anonymizing machine learning models."
    In International Workshop on Data Privacy Management, pp. 121-136. Cham: Springer International Publishing, 2021.

    """

    def __init__(
        self,
        k: int,
        quasi_identifiers: np.ndarray | list,
        features: list | None = None,
        features_names: list | None = None,
        quasi_identifer_slices: list | None = None,
        categorical_features: list | None = None,
        is_regression: bool | None = False,
        train_only_QI: bool | None = False,
    ):
        if k < 2:
            msg = "k should be a positive integer with a value of 2 or higher"
            raise ValueError(msg)
        if quasi_identifiers is None or len(quasi_identifiers) < 1:
            msg = "The list of quasi-identifiers cannot be empty"
            raise ValueError(msg)

        self.k = k
        self.quasi_identifiers = quasi_identifiers
        self.categorical_features = categorical_features
        self.is_regression = is_regression
        self.train_only_QI = train_only_QI
        self.features_names = features_names
        self.features = features
        self.quasi_identifer_slices = quasi_identifer_slices

    def anonymize(self, X_train, y_train):
        """
        Description
        -----------
        Method for performing model-guided anonymization.

        Parameters
        ----------
        X_train : np.ndarray or pandas DataFrame
            Dataset containing the training data for the model.

        y_train : np.ndarray
            The predictions of the original model on the training data.

        Returns
        -------
        The anonymized training dataset as pandas DataFrame.

        """
        if X_train.shape[1] != 0:
            self.features = list(range(X_train.shape[1]))
        else:
            msg = "No data provided"
            raise ValueError(msg)

        if self.features_names is None:
            # if no names provided, use numbers instead
            self.features_names = self.features

        if not set(self.quasi_identifiers).issubset(set(self.features_names)):
            msg = (
                "Quasi identifiers should bs a subset of the supplied features or indexes in range of "
                "the data columns"
            )
            raise ValueError(msg)
        if self.categorical_features and not set(self.categorical_features).issubset(set(self.features_names)):
            msg = (
                "Categorical features should bs a subset of the supplied features or indexes in range of "
                "the data columns"
            )
            raise ValueError(msg)

        # transform quasi identifiers to indexes
        self.quasi_identifiers = [i for i, v in enumerate(self.features_names) if v in self.quasi_identifiers]
        if self.quasi_identifer_slices:
            temp_list = []
            for qislice in self.quasi_identifer_slices:
                new_slice = [i for i, v in enumerate(self.features_names) if v in qislice]
                temp_list.append(new_slice)
            self.quasi_identifer_slices = temp_list
        if self.categorical_features:
            self.categorical_features = [i for i, v in enumerate(self.features_names) if v in self.categorical_features]

        transformed = self._anonymize(X_train.copy(), y_train)
        df = pd.DataFrame(transformed, columns=self.features_names)
        return df.astype(X_train.dtypes)

    def _anonymize(self, x, y):
        if x.shape[0] != y.shape[0]:
            msg = "x and y should have same number of rows"
            raise ValueError(msg)
        if any(x.select_dtypes(include="category").columns):
            if not self.categorical_features:
                msg = "when supplying an array with non-numeric data, categorical_features must be defined"
                raise ValueError(msg)
            x_prepared = self._modify_categorical_features(x)
        else:
            x_prepared = x
        x_anonymizer_train = x_prepared
        if self.train_only_QI:
            # build DT just on QI features
            x_anonymizer_train = x_prepared[:, self.quasi_identifiers]
        if self.is_regression:
            self._anonymizer = DecisionTreeRegressor(random_state=10, min_samples_split=2, min_samples_leaf=self.k)
        else:
            self._anonymizer = DecisionTreeClassifier(random_state=10, min_samples_split=2, min_samples_leaf=self.k)

        self._anonymizer.fit(x_anonymizer_train, y)
        cells_by_id = self._calculate_cells(x, x_anonymizer_train)
        return self._anonymize_data(x, x_anonymizer_train, cells_by_id)

    def _calculate_cells(self, x, x_anonymizer_train):
        # x is original data, x_anonymizer_train is only QIs + 1-hot encoded
        cells_by_id = {}
        leaves = []
        for node, feature in enumerate(self._anonymizer.tree_.feature):
            if feature == -2:  # leaf node
                leaves.append(node)
                hist = [int(i) for i in self._anonymizer.tree_.value[node][0]]
                # TODO we may change the method for choosing representative for cell  # noqa: TD004
                # label_hist = self.anonymizer.tree_.value[node][0]
                # label = int(self.anonymizer.classes_[np.argmax(label_hist)])
                cell = {"label": 1, "hist": hist, "id": int(node)}
                cells_by_id[cell["id"]] = cell
        self._nodes = leaves
        self._find_representatives(x, x_anonymizer_train, cells_by_id.values())
        return cells_by_id

    def _find_representatives(self, x, x_anonymizer_train, cells):
        # x is original data (always numpy), x_anonymizer_train is only QIs + 1-hot encoded
        node_ids = self._find_sample_nodes(x_anonymizer_train)
        if self.quasi_identifer_slices:
            all_one_hot_features = {feature for encoded in self.quasi_identifer_slices for feature in encoded}
        else:
            all_one_hot_features = set()
        for cell in cells:
            cell["representative"] = {}
            # get all rows in cell
            indexes = [index for index, node_id in enumerate(node_ids) if node_id == cell["id"]]
            # TODO: should we filter only those with majority label? (using hist)
            rows = x.loc[indexes]
            done = set()
            for feature in self.quasi_identifiers:  # self.quasi_identifiers are numerical indexes
                if feature not in done:
                    # deal with 1-hot encoded features
                    if feature in all_one_hot_features:
                        # find features that belong together
                        for encoded in self.quasi_identifer_slices:
                            if feature in encoded:
                                values = rows[:, encoded]
                                unique_rows, counts = np.unique(values, axis=0, return_counts=True)
                                rep = unique_rows[np.argmax(counts)]
                                for i, e in enumerate(encoded):
                                    done.add(e)
                                    cell["representative"][e] = rep[i]
                    else:  # rest of features
                        values = rows.iloc[:, feature]
                        if self.categorical_features and feature in self.categorical_features:
                            # find most common value
                            cell["representative"][feature] = Counter(values).most_common(1)[0][0]
                        else:
                            # find the mean value (per feature)
                            median = np.median(values)
                            min_value = max(values)
                            min_dist = float("inf")
                            for value in values:
                                # euclidean distance between two floating point values
                                dist = abs(value - median)
                                if dist < min_dist:
                                    min_dist = dist
                                    min_value = value
                            cell["representative"][feature] = min_value

    def _find_sample_nodes(self, samples):
        paths = self._anonymizer.decision_path(samples).toarray()
        node_set = set(self._nodes)
        return [next(iter({i for i, v in enumerate(p) if v == 1} & node_set)) for p in paths]

    def _find_sample_cells(self, samples, cells_by_id):
        node_ids = self._find_sample_nodes(samples)
        return [cells_by_id[node_id] for node_id in node_ids]

    def _anonymize_data(self, x, x_anonymizer_train, cells_by_id):
        cells = self._find_sample_cells(x_anonymizer_train, cells_by_id)
        index = 0
        dfnew = pd.DataFrame(columns=x.columns)
        for _, row in x.iterrows():
            cell = cells[index]
            index += 1
            for feature in cell["representative"]:
                row[feature] = cell["representative"][feature]
            dfnew.loc[len(dfnew)] = row
        return dfnew

    def _modify_categorical_features(self, x):
        # prepare data for DT
        used_features = self.features
        if self.train_only_QI:
            used_features = self.quasi_identifiers
        numeric_features = [f for f in self.features if f in used_features and f not in self.categorical_features]
        categorical_features = [f for f in self.categorical_features if f in used_features]
        numeric_transformer = Pipeline(steps=[("imputer", SimpleImputer(strategy="constant", fill_value=0))])

        categorical_transformer = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        preprocessor = ColumnTransformer(
            transformers=[
                ("num", numeric_transformer, numeric_features),
                ("cat", categorical_transformer, categorical_features),
            ]
        )
        return preprocessor.fit_transform(x)

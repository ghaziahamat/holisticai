from typing import Literal, overload

@overload
def load_dataset(
    dataset_name: Literal["adult"],
    protected_attribute: Literal["race", "sex"] | None = None,
    preprocessed: bool = True,
): ...
@overload
def load_dataset(
    dataset_name: Literal["law_school"],
    protected_attribute: Literal["race", "gender"] | None = None,
    preprocessed: bool = True,
): ...
@overload
def load_dataset(
    dataset_name: Literal["student_multiclass"],
    protected_attribute: Literal["sex", "address"] | None = None,
    preprocessed: bool = True,
): ...
@overload
def load_dataset(
    dataset_name: Literal["student"],
    target: Literal["G1", "G2", "G3"] | None = None,
    preprocessed: bool = True,
    protected_attribute: Literal["sex", "address"] | None = None,
): ...
@overload
def load_dataset(
    dataset_name: Literal["lastfm"],
): ...
@overload
def load_dataset(
    dataset_name: Literal["us_crime"],
    preprocessed: bool = True,
    protected_attribute: Literal["race"] | None = None,
): ...
@overload
def load_dataset(
    dataset_name: Literal["us_crime_multiclass"],
    preprocessed: bool = True,
    protected_attribute: Literal["race"] | None = None,
): ...
@overload
def load_dataset(dataset_name: Literal["clinical_records"], protected_attribute: Literal["sex"] | None = None): ...

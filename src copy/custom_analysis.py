from enum import Enum

from abc import ABC, abstractmethod


class CustomAnalysisKind(Enum):
    POINT_SCALAR = 1
    SERIES_SCALAR = 2
    NSERIES_SCALAR = 3

    POINT_SERIES = 4
    SERIES_SERIES = 5
    NSERIES_SERIES = 6

    POINT_NSERIES = 7
    SERIES_NSERIES = 8
    NSERIES_NSERIES = 9


points_required = [
    CustomAnalysisKind.POINT_SCALAR,
    CustomAnalysisKind.POINT_SERIES,
    CustomAnalysisKind.POINT_NSERIES,
]
series_required = [
    CustomAnalysisKind.SERIES_SCALAR,
    CustomAnalysisKind.SERIES_SERIES,
    CustomAnalysisKind.SERIES_NSERIES,
]
nseries_required = [
    CustomAnalysisKind.NSERIES_SCALAR,
    CustomAnalysisKind.NSERIES_SERIES,
    CustomAnalysisKind.NSERIES_NSERIES,
]


class CustomAnalysis(ABC):
    def __init__(self, kind: CustomAnalysisKind, **kwargs):
        super().__init__()
        if not isinstance(kind, CustomAnalysisKind):
            raise Exception("Expected type CustomAnalysisKind, got " + str(type(kind)))
        self.kind_obj = kind

        def is_num(obj):
            return isinstance(obj, float) or isinstance(obj, int)

        if self.kind_obj in points_required:
            assert "x" in kwargs.keys()
            assert "y" in kwargs.keys()
            assert is_num(kwargs["x"])
            assert is_num(kwargs["y"])

            self.x = kwargs["x"]
            self.y = kwargs["y"]

        if self.kind_obj in series_required:
            assert "x" in kwargs.keys()
            assert "y" in kwargs.keys()
            assert isinstance(kwargs["x"], list)
            assert len(kwargs["x"]) > 0
            assert is_num(kwargs["x"][0])
            assert isinstance(kwargs["y"], list)
            assert len(kwargs["y"]) > 0
            assert is_num(kwargs["y"][0])

            self.x = kwargs["x"]
            self.y = kwargs["y"]

    @abstractmethod
    def get(self, **kwargs):
        """
        Another abstract method with a parameter that must be implemented.
        """
        pass

    def kind(self):
        return self.kind_obj

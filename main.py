from src.smart_serial_plottter import SmartSerialPloter
from src.custom_analysis import CustomAnalysis, CustomAnalysisKind
from pprint import pprint

import logging
from PyQt5.QtWidgets import QApplication
import sys


class Scale(CustomAnalysis):
    def __init__(self, kind: CustomAnalysisKind, **kwargs):
        super().__init__(kind, **kwargs)
        self.factor = kwargs["factor"]

    def get(self):
        return self.y / self.factor


class Mean(CustomAnalysis):
    def __init__(self, kind: CustomAnalysisKind, **kwargs):
        super().__init__(kind, **kwargs)

    def get(self):
        return sum(self.y) / len(self.y)


if __name__ == "__main__":
    scale = Scale(CustomAnalysisKind.POINT_SCALAR, x=1, y=2, factor=10)
    mean = Mean(CustomAnalysisKind.SERIES_SCALAR, x=[1, 2], y=[3, 4])
    print(scale.get())
    print(mean.get())
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s", level=logging.DEBUG
    )
    app = QApplication(sys.argv)
    window = SmartSerialPloter()
    sys.exit(app.exec_())

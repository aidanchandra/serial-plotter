import multiprocessing
import time
import re
from pprint import pprint
import serial
from serial.tools.list_ports import comports
import matplotlib.pyplot as plt
import numpy as np
import random
import json
import os
import logging
import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QTextEdit,
    QLineEdit,
    QComboBox,
    QPushButton,
)
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, pyqtSignal
import random
from enum import Enum


class CustomAnalysis:
    class kind(Enum):
        POINT_SCALAR = 1
        SERIES_SCALAR = 2
        NSERIES_SCALAR = 3

        POINT_SERIES = 4
        SERIES_SERIES = 5
        NSERIES_SERIES = 6

        POINT_NSERIES = 7
        SERIES_NSERIES = 8
        NSERIES_NSERIES = 9

    def __init__(self, name: str, type: kind, function_reader, color, dasher) -> None:
        self.type = type
        self.name = name
        self.function_reader = function_reader
        self.color = color
        self.dasher = dasher
        if self.type == CustomAnalysis.kind.POINT_SCALAR:
            try:
                a = function_reader(1, 2)
                assert isinstance(a, float) or isinstance(a, int)
            except Exception as e:
                print("Malformed function for POINT_SCALAR")
                raise e
        if self.type == CustomAnalysis.kind.SERIES_SCALAR:
            try:
                a = function_reader([1, 2, 3], [4, 5, 6])  # x_array, y_array
                assert isinstance(a, float) or isinstance(a, int)
            except Exception as e:
                print("Malformed function for POINT_SCALAR")
                raise e

    def process(self):
        pass


class Message:
    def __init__(self, raw_string: str) -> None:
        self.raw_string = raw_string

    def process(self) -> dict:
        returnable = {}
        self.timestamp = self.raw_string[0 : int(self.raw_string.find("::"))]
        returnable["timestamp"] = int(self.timestamp)

        data_string_subst = self.raw_string[int(self.raw_string.find("::")) + 2 :]
        pairs = data_string_subst.split(",")
        datas = []
        statuses = []
        for pair in pairs:
            # Split each pair by colon
            name, data = pair.split(":")

            # Convert data to float and append the tuple to the result list
            if "!" in name:
                statuses.append((name, str(data)))
            else:
                datas.append((name, float(data)))

        returnable["statuses"] = statuses
        returnable["datas"] = datas

        return returnable


class Plotter:
    def __init__(self, cachesize) -> None:
        self.data = []
        self.cachesize = cachesize

    def update(self, shared_list):
        logging.basicConfig(
            format="PLOTTER: %(asctime)s - %(levelname)s - %(message)s",
            level=logging.DEBUG,
        )

        while True:
            if len(shared_list) > 0:
                self.data.append(shared_list.pop())

            if len(self.data) >= self.cachesize:
                self.data = self.data[-self.cachesize :]


class SerialReader:
    def __init__(self, cachesize, enable_logging=True) -> None:
        self.logging_flag = enable_logging
        self.messages = []
        self.cachesize = cachesize
        self.ser = None

    def get_ports(self):
        # initialize the serial monitor
        ports = serial.tools.list_ports.comports()
        ports_list = []
        for port, desc, hwid in sorted(ports):
            # print(f"{port}: {desc} [{hwid}]")
            ports_list.append([port, desc, hwid])

        return ports_list

    def _log(self, data):
        """
        Logs a dictionary to a JSON file. If the file does not exist, it creates a new file.
        If it does exist, it appends data to the existing file.

        :param data: Dictionary to be logged.
        """

        # Check if the file exists
        if os.path.exists("logging/" + self.log_instance + ".json"):
            # Read existing data
            try:
                with open("logging/" + self.log_instance + ".json", "r") as file:
                    # Read existing data, expecting it to be a dictionary
                    existing_data = json.load(file)
                    # Ensure the existing data is a dictionary
                    if not isinstance(existing_data, dict):
                        existing_data = {}
            except json.JSONDecodeError:
                # In case of a decoding error, start with an empty dictionary
                existing_data = {}
        else:
            existing_data = {}

        # Append new data
        existing_data.update(data)

        # Write data back to file
        with open("logging/" + self.log_instance + ".json", "w") as file:
            json.dump(existing_data, file, indent=4)

    def begin_read(self, shared_list, port, baud=115200, latch_timeout=10):
        logging.basicConfig(
            format="READER: %(asctime)s - %(levelname)s - %(message)s",
            level=logging.DEBUG,
        )

        self.log_instance = str(time.time()).replace(".", "-")
        self._log(
            {
                "port": str(port[0]),
                "desc": str(port[1]),
                "hwid": str(port[2]),
                "baud": str(baud),
                "t_connect": str(time.time()),
                "data": [],
            }
        )

        logging.info("Connecting to:" + str(port[0]))
        self.ser = serial.Serial(str(port[0]), baud)

        latch_attempts = 0
        logging.debug("Began read function")
        start_time = time.perf_counter()
        while True:
            if self.ser.in_waiting > 0:
                data = self.ser.readline().decode("utf-8").rstrip()
                try:
                    message = Message(str(data))
                    shared_list.append(message.process())
                    self.messages.append(str(data))
                except Exception as e:
                    logging.info("Failed %d latch attempts", latch_attempts)
                    latch_attempts += 1
                    if latch_attempts > latch_timeout:
                        logging.critical(
                            "Timeout in latching full-messages in from serial monitor"
                        )
                        raise e

            cur_time = time.perf_counter()
            ellapsed_time = cur_time - start_time
            if ellapsed_time > 5:
                logging.debug("Log-to-file heartbeat recieved")
                self._log({"data": self.messages})
                start_time = time.perf_counter()
                self.messages = []


class CustomLineEdit(QLineEdit):
    """Generic custom class for QLineEdit objects that unfocus after relevat keypresses"""

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.clearFocus()  # Remove focus from the text box


class SerialLineEdit(QLineEdit):
    """Custom class to send serial data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.parent.serial_send()
            self.clear()


class SerialPortDropdown(QComboBox):
    """Custom class for dropdowns live-updating"""

    clicked = pyqtSignal()  # TODO: no clue

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent  # Store a reference to the parent window

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.parent.get_serial_ports()
        self.clicked.emit()  # TODO: no clue


class SmartSerialPloter(QMainWindow):
    def __init__(self):
        """
        Q1  Q3
        Q2  Q4
        Q2  q%

        """
        ## Initializations
        super().__init__()
        self.clickable_items = (
            []
        )  # List of items that will be unfocused after being clicked off

        ## Main widget and layout
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left vertical layout
        left_v_layout = QVBoxLayout()
        main_layout.addLayout(left_v_layout, 1)

        # Right vertical layout
        right_v_layout = QVBoxLayout()
        main_layout.addLayout(right_v_layout, 5)

        # Each quadrant
        # Quadrant 1: Plot Info + Stop/Start (Red)
        q1 = QWidget()
        q1.setStyleSheet("background-color: grey")
        q1_layout = QVBoxLayout(q1)  # New layout for q1
        q1_baud_layout = QHBoxLayout()

        q1_label = QLabel("Baudrate:")
        self.serial_ports = SerialPortDropdown(self)
        self.baud = CustomLineEdit(self)
        q1_baud_layout.addWidget(q1_label)
        q1_baud_layout.addWidget(self.baud)

        q1_start_stop_button = QPushButton("Start")
        q1_connect_disconnect = QPushButton("Connect")
        q1_layout.addWidget(q1_start_stop_button)
        q1_layout.addWidget(q1_connect_disconnect)
        q1_layout.addWidget(self.serial_ports)
        q1_layout.addLayout(q1_baud_layout)

        self.clickable_items.append(self.serial_ports)

        q1.setMinimumSize(150, 80)

        left_v_layout.addWidget(q1, 1)

        # Quadrant 2: Various Analyses and Statuses (Green)
        q2 = QWidget()
        q2.setStyleSheet("background-color: green")
        q2_layout = QVBoxLayout(q2)
        self.analysis_text_edit = QTextEdit()
        self.analysis_text_edit.setReadOnly(True)  # Make it read-only
        q2_layout.addWidget(self.analysis_text_edit)
        q2.setMinimumSize(150, 220)
        left_v_layout.addWidget(q2, 2)

        # Quadrant 3: General Status/Name
        q3 = QWidget()
        q3.setStyleSheet("background-color: grey")
        q3_layout = QVBoxLayout(q3)  # New layout for q3
        self.q3_label = QLabel("General Status/Name")
        self.q3_text_input = (
            CustomLineEdit()
        )  # Changed to QLineEdit for a single line text box
        q3_layout.addWidget(self.q3_label)
        q3_layout.addWidget(self.q3_text_input)
        self.clickable_items.append(self.q3_text_input)

        q3.setFixedHeight(70)  # Set minimum size for q3
        right_v_layout.addWidget(q3, 1)  # Add q3 to the right layout

        # Quadrant 4: Blue with Matplotlib Plot
        self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        self.ax = self.canvas.figure.subplots()
        self.ax.plot([0, 1, 2], [2, 1, 0])  # Example plot
        self.canvas.setMinimumSize(300, 250)
        right_v_layout.addWidget(self.canvas, 3)

        # Quadrant 5: Serial Send/Receive + Reserved (Yellow)
        q5 = QWidget()
        q5.setStyleSheet("background-color: grey")
        q5_layout = QVBoxLayout(q5)  # New layout for q5
        q5_h_layout = QHBoxLayout()

        q5_button = QPushButton("Send")
        q5_button.clicked.connect(self.serial_send)
        self.q5_text_input = SerialLineEdit(
            self
        )  # Changed to QLineEdit for a single line text box
        self.serial_send_choice = QComboBox()
        self.serial_send_choice.addItems(["None", "LR", "CF", "LRCF"])
        self.serial_send_choice.setFixedWidth(80)  # Adjust the width as needed

        self.clickable_items.append(self.q5_text_input)

        q5_h_layout.addWidget(self.q5_text_input)
        q5_h_layout.addWidget(self.serial_send_choice)
        q5_h_layout.addWidget(q5_button)

        q5_layout.addLayout(q5_h_layout)
        q5.setMinimumSize(300, 60)
        q5.setFixedHeight(60)

        right_v_layout.addWidget(q5, 1)

        # Window settings
        self.setWindowTitle("Quadrant Scaling Example")
        self.resize(600, 400)

        # Timer for live updates
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_analysis_text)
        self.timer.timeout.connect(self.update_general_text)

        self.timer.start(100)  # Update every second

        self.show()

        # self.show()
        # self.custom_analyses = []
        # self.cachesize = cachesize
        # self.plotter = Plotter(self.cachesize)
        # self.reader = SerialReader(self.cachesize)

    def begin(self):
        logging.debug("Creating theads")
        manager = multiprocessing.Manager()
        shared_list = manager.list()
        # Creating processes
        serial_process = multiprocessing.Process(
            target=self.reader.begin_read,
            args=(
                shared_list,
                self.reader.get_ports()[1],
            ),
        )
        plot_process = multiprocessing.Process(
            target=self.plotter.update, args=(shared_list,)
        )

        logging.debug("Starting theads")
        # Starting processes
        serial_process.start()
        plot_process.start()

        logging.debug("Joining theads")
        # Joining processes
        serial_process.join()
        plot_process.join()

    def add_customAnalysis(self, obj: CustomAnalysis):
        self.custom_analyses.append(obj)

    def update_analysis_text(self):
        # Append new text without changing the scroll position
        current_scrollbar_position = self.analysis_text_edit.verticalScrollBar().value()
        max_scrollbar_position = self.analysis_text_edit.verticalScrollBar().maximum()
        self.analysis_text_edit.append("New update line")  # Append new text here

        # Keep the current scrollbar position unless the user is at the bottom
        if current_scrollbar_position == max_scrollbar_position:
            self.analysis_text_edit.verticalScrollBar().setValue(max_scrollbar_position)
        else:
            self.analysis_text_edit.verticalScrollBar().setValue(
                current_scrollbar_position
            )

    def update_general_text(self):
        a = random.randint(400, 500)
        b = random.randint(100, 120)
        c = random.randint(250, 300)

        self.q3_label.setText(
            "Num samples: "
            + str(a)
            + " @ "
            + str(b)
            + " hz  total t displayed: "
            + str(c)
        )

    def serial_send(self):
        print(
            "Serial Sent "
            + self.q5_text_input.text()
            + " with setting "
            + str(self.serial_send_choice.currentText())
        )  # Replace with your desired action

    def get_serial_ports(self):
        print("Clearing and adding items")
        self.serial_ports.clear()
        self.serial_ports.addItems(["a", "b"])

    def mousePressEvent(self, event):
        # Check if the click is outside q3_text_input
        for item in self.clickable_items:
            if not item.geometry().contains(event.pos()):
                item.clearFocus()
            super().mousePressEvent(event)


def average(xarr, yarr):
    return float(np.mean(yarr))


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s", level=logging.DEBUG
    )
    app = QApplication(sys.argv)
    window = SmartSerialPloter()
    sys.exit(app.exec_())

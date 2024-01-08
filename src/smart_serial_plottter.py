import multiprocessing
from pprint import pprint
from serial.tools.list_ports import comports
import matplotlib.pyplot as plt
import numpy as np
import random
import logging
import queue
import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QCheckBox,
    QWidget,
    QLabel,
    QTextEdit,
    QLineEdit,
    QComboBox,
    QPushButton,
)
from PyQt5.QtGui import QFont
import os
from PyQt5.QtCore import QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import Qt, pyqtSignal
import random
from PyQt5.QtGui import QRegExpValidator
from PyQt5.QtCore import QRegExp
from datetime import datetime


if __name__ == "__main__":
    from custom_analysis import *
    from serial_class import *
    from plotting_subclass import *

else:
    from src.custom_analysis import *
    from src.serial_class import *
    from src.plotting_subclass import *


class CustomLineEdit(QLineEdit):
    """Generic custom class for QLineEdit objects that unfocus after relevat keypresses"""

    def __init__(self, regex_pattern="", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            """
            QLineEdit {
                color: black;  /* Text color */
                background-color: white;  /* Background color */
                selection-background-color: lightblue; /* Color of highlighted text */
                selection-color: black; /* Color of text that is highlighted */
            }
        """
        )
        reg_ex = QRegExp(regex_pattern)
        validator = QRegExpValidator(reg_ex, self)
        self.setValidator(validator)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.clearFocus()  # Remove focus from the text box


class SerialLineEdit(QLineEdit):
    """Custom class to send serial data"""

    def __init__(self, regex_pattern="", parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setStyleSheet(
            """
            QLineEdit {
                color: black;  /* Text color */
                background-color: white;  /* Background color */
                selection-background-color: lightblue; /* Color of highlighted text */
                selection-color: black; /* Color of text that is highlighted */
            }
        """
        )
        reg_ex = QRegExp(regex_pattern)
        validator = QRegExpValidator(reg_ex, self)
        self.setValidator(validator)

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
        self.setStyleSheet(
            """
            QLineEdit {
                color: black;  /* Text color */
                background-color: white;  /* Background color */
                selection-background-color: lightblue; /* Color of highlighted text */
                selection-color: black; /* Color of text that is highlighted */
            }
        """
        )

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.parent.get_serial_ports()
        self.clicked.emit()  # TODO: no clue


class SmartSerialPloter(QMainWindow):
    def init_layout(self):
        ## Main widget and layout
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # Left vertical layout
        left_v_layout = QVBoxLayout()
        main_layout.addLayout(left_v_layout, 1)

        # Right vertical layout
        self.right_v_layout = QVBoxLayout()
        main_layout.addLayout(self.right_v_layout, 5)

        # Each quadrant
        # Quadrant 1: Plot Info + Stop/Start (Red)
        q1 = QWidget()
        q1.setStyleSheet("background-color: grey")
        q1_layout = QVBoxLayout(q1)  # New layout for q1
        q1_baud_layout = QHBoxLayout()

        q1_label = QLabel("Baudrate:")
        self.serial_ports = SerialPortDropdown(self)
        self.log_to_file_checkbox = QCheckBox(f"Log to file")
        self.baud = CustomLineEdit(regex_pattern="[0-9]*", parent=self)
        self.baud.setText(self.user_settings["baud"])
        q1_baud_layout.addWidget(q1_label)
        q1_baud_layout.addWidget(self.baud)

        self.q1_c_dc_button = QPushButton("Connect")
        self.q1_c_dc_button.released.connect(self.c_dc_handler)
        self.is_on = False
        # self.q1_plot_ss_button = QPushButton("Toggle View")

        # q1_connect_disconnect = QPushButton("Connect")
        q1_layout.addWidget(self.q1_c_dc_button)
        # q1_layout.addWidget(q1_connect_disconnect)
        q1_layout.addWidget(self.serial_ports)
        q1_layout.addLayout(q1_baud_layout)
        q1_layout.addWidget(self.log_to_file_checkbox)
        # q1_layout.addWidget(self.q1_plot_ss_button)

        self.clickable_items.append(self.serial_ports)

        q1.setMinimumWidth(150)
        q1.setFixedHeight(180)

        left_v_layout.addWidget(q1, 1)

        # Quadrant 2: Various Analyses and Statuses (Green)
        q2 = QWidget()
        q2.setStyleSheet("background-color: grey")
        q2_layout = QVBoxLayout(q2)
        self.analysis_text_edit = QTextEdit()
        self.analysis_text_edit.setFont(QFont("Courier New", 12))
        self.analysis_text_edit.setReadOnly(True)  # Make it read-only
        q2_layout.addWidget(self.analysis_text_edit)
        q2.setMinimumSize(150, 220)
        left_v_layout.addWidget(q2, 2)

        # Quadrant 3: General Status/Name
        q3 = QWidget()
        q3.setStyleSheet("background-color: grey")
        q3_layout = QVBoxLayout(q3)  # New layout for q3
        self.q3_label = QLabel("Click start...")
        self.q3_label.setFont(QFont("Courier New", 14))
        self.friendly_name = CustomLineEdit(
            regex_pattern=r"^[^\/:*?\"<>|\r\n]+(?=\.\w+$)", parent=self
        )  # Changed to QLineEdit for a single line text box
        q3_layout.addWidget(self.q3_label)
        q3_layout.addWidget(self.friendly_name)
        self.clickable_items.append(self.friendly_name)

        q3.setFixedHeight(70)  # Set minimum size for q3
        self.right_v_layout.addWidget(q3, 1)  # Add q3 to the right layout
        self.right_v_layout.addWidget(self.plotter, 3)

        # Quadrant 4: Blue with Matplotlib Plot
        # self.canvas = FigureCanvas(Figure(figsize=(5, 3)))
        # self.ax = self.canvas.figure.subplots()
        # self.ax.plot([0, 1, 2], [2, 1, 0])  # Example plot
        # self.canvas.setMinimumSize(300, 250)

        # Quadrant 5: Serial Send/Receive + Reserved (Yellow)
        q5 = QWidget()
        q5.setStyleSheet("background-color: grey")
        q5_layout = QVBoxLayout(q5)  # New layout for q5
        q5_h_layout = QHBoxLayout()

        serial_send_button = QPushButton("Send")
        serial_send_button.clicked.connect(self.serial_send)
        self.q5_text_input = SerialLineEdit(
            parent=self, regex_pattern=r"^[ -~]+$"
        )  # Changed to QLineEdit for a single line text box
        self.serial_line_ending = QComboBox()
        self.serial_line_ending.addItems(["None", "LR", "CF", "LRCF"])
        try:
            self.serial_line_ending.setCurrentIndex(
                int(self.user_settings["line_ending"])
            )
        except:
            logging.debug("Error setting line-ending to previous")
        self.serial_line_ending.setFixedWidth(80)  # Adjust the width as needed

        self.clickable_items.append(self.q5_text_input)

        q5_h_layout.addWidget(self.q5_text_input)
        q5_h_layout.addWidget(self.serial_line_ending)
        q5_h_layout.addWidget(serial_send_button)

        q5_layout.addLayout(q5_h_layout)
        q5.setMinimumSize(300, 60)
        q5.setFixedHeight(60)

        self.right_v_layout.addWidget(q5, 1)

        # Window settings
        self.setWindowTitle("Smart Serial Plotter")
        self.resize(600, 400)

    def __init__(self, debug=False):
        logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
        ## Initializations
        super().__init__()
        self.clickable_items = (
            []
        )  # List of items that will be unfocused after being clicked off
        self.user_settings = self._get_user_settings()
        self.serial = SerialClass(5000, verbose=True)
        self.cur_ports = []  # List of current ports
        self.read_messages = None  # Messages read from serial monitor
        self.serial_process = None  # PRocess for serial handler
        self.plot_queue = queue.Queue()
        self.local_list = []
        self.custom_analyses = []
        self.item_count = 0

        self.plotter = LivePlotter(self.plot_queue, parent=self)
        self.statuses = {}
        self.init_layout()

        # Timer for live updates
        self.ui_timer = QTimer(self)
        self.serial_timer = QTimer(self)

        self.ui_timer.timeout.connect(self.ui_callback)
        self.serial_timer.timeout.connect(self.serial_callback)

        self.ui_timer.start(100)  # Update every second
        self.data_callback_lock = False
        self.serial_timer.start(1)  # Update every second

        # Debug printing:
        if debug:
            self.debug_timer = QTimer(self)
            self.debug_timer.start(10)
            self.debug_timer.timeout.connect(self.debug_func)

        self.log_to_file_checkbox.setChecked(self.user_settings["log_to_file"])

        self.show()

        self.get_serial_ports()
        self.serial_ports.setCurrentIndex(self.user_settings["port"])

    def c_dc_handler(self):
        if self.is_on == False:  # Stopped
            self.im_too_tired_to_correctly_name_this = True
            # Start
            self.begin_serial()
            self.is_on = True

            # Get index and size of the current plotter
            plotter_index = self.right_v_layout.indexOf(self.plotter)
            plotter_size = self.plotter.size()

            # Remove and delete the current plotter
            self.right_v_layout.removeWidget(self.plotter)
            self.plotter.deleteLater()

            # Create and configure the new plotter
            self.plotter = LivePlotter(
                self.plot_queue,
                curve_keys=self.serial.rx_messages.get().as_curve_keys(),
                parent=self,
            )  # Adjust parameters as needed
            self.plotter.resize(plotter_size)  # Set the size to match the old plotter
            self.plotter.setSizePolicy(
                self.plotter.sizePolicy()
            )  # Maintain size policy if needed

            # Insert the new plotter
            self.right_v_layout.insertWidget(plotter_index, self.plotter)
            # while self.serial.rx_messages.empty:
            #     pass
            # self.plotter.toggle_start_stop()
            self.q1_c_dc_button.setText("Disconnect")

        else:  # Started
            self.is_on = False
            self.statuses = {}
            self.update_statuses_analyses()
            self.end_serial()
            self.q1_c_dc_button.setText("Connect")
            self.friendly_name.setText("")
            self.item_count = 0
            if self.plotter.is_live:
                self.plotter.toggle_start_stop()

            self.analysis_text_edit.setText("")  # Append new text here

        # Stop

    def add_customAnalysis(self, obj: CustomAnalysis):
        self.custom_analyses.append(obj)

    # -------------------------------------------------------------
    # ---------------------- Timed Functions ----------------------
    # -------------------------------------------------------------
    def debug_func(self):
        pass
        # if self.is_on:
        #     logging.debug(
        #         "Q size from serial class " + str(self.serial.rx_messages.qsize())
        #     )

    def serial_callback(self):
        """ """
        if self.is_on:
            start_time = time.perf_counter_ns()
            recieved_messages = 0
            while not self.serial.rx_messages.empty():
                if self.im_too_tired_to_correctly_name_this:
                    self.plotter.toggle_start_stop()
                self.im_too_tired_to_correctly_name_this = False
                message: RXMessage
                message = self.serial.rx_messages.get()
                # message.apply_offset(self.serial.config["t_first_message"])
                self.plot_queue.put_nowait(message)
                self.statuses.update(message.get_statuses())
                recieved_messages += 1

            # logging.debug(
            #     "Read %d messages in %f uS",
            #     recieved_messages,
            #     (time.perf_counter_ns() - start_time) / 1000,
            # )

    def ui_callback(self):
        self.update_statuses_analyses()
        self.update_plot_info()

    def update_statuses_analyses(self):
        current_scrollbar_position = self.analysis_text_edit.verticalScrollBar().value()
        max_scrollbar_position = self.analysis_text_edit.verticalScrollBar().maximum()
        # self.analysis_text_edit.append("New update line")  # Append new text here
        textline = ""

        for key in self.statuses:
            textline += key.replace("!", "") + ": "
            if self.statuses[key].lower() == "true":
                textline += (
                    "<span style='color: green;'>" + self.statuses[key] + "</span><br>"
                )
            elif self.statuses[key].lower() == "false":
                textline += (
                    "<span style='color: red;'>" + self.statuses[key] + "</span><br>"
                )
            else:
                textline += self.statuses[key] + "<br>"

        self.analysis_text_edit.setText(textline)  # Append new text here

        # Keep the current scrollbar position unless the user is at the bottom
        if current_scrollbar_position == max_scrollbar_position:
            self.analysis_text_edit.verticalScrollBar().setValue(max_scrollbar_position)
        else:
            self.analysis_text_edit.verticalScrollBar().setValue(
                current_scrollbar_position
            )

    def update_plot_info(self):
        if self.is_on:
            a = random.randint(0, 500)
            b = random.randint(0, 120)
            c = random.randint(0, 300)

            self.q3_label.setText(
                "total samples: "
                + self._safe_num_as_str(self.serial.get_n_total_messages_read(), 6)
                + " @ "
                + self._safe_num_as_str(self.serial.get_hz_rx_messages(), 6)
                + " hz   n displayed: "
                + self._safe_num_as_str(self.plotter.get_total_points(), 6)  # TODO:
            )
            # self.plotter.refresh_plot()

    # ---------------------- Serial Handling ----------------------
    def serial_send(self):
        self.serial.tx_messages.put(
            TXMessage(
                message=self.q5_text_input.text(),
                line_ending=str(self.serial_line_ending.currentText()),
            )
        )

    def get_serial_ports(self):
        self.cur_ports = self.serial.get_ports()
        logging.debug("Current serial ports: " + str(self.cur_ports))
        cur_index = self.serial_ports.currentIndex()
        self.serial_ports.clear()
        for port in self.cur_ports:
            self.serial_ports.addItem(str(port))

        try:
            self.serial_ports.setCurrentIndex(cur_index)
        except:
            logging.debug("Serial port no longer available")

    def begin_serial(self):
        enable_logging = self.log_to_file_checkbox.isChecked()
        ports = self.serial.get_ports()
        chosen_port = ports[self.serial_ports.currentIndex()]

        current_time = datetime.now()
        self.serial.config["log_name"] = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        self.serial.config["on"] = True
        self.serial.config["log_enabled"] = enable_logging
        self.serial.config["port"] = chosen_port
        self.serial.config["baud"] = int(self.baud.text())
        self.serial.config["latch_timeout"] = 50

        table = Table()
        table.add_column("Column 1")
        table.add_column("Column 2")
        table.add_row("Row 1 Data 1", "Row 1 Data 2")
        table.add_row("Row 2 Data 1", "Row 2 Data 2")
        # Start the process

        self.serial.start()

        # message: RXMessage
        # message = self.serial.rx_messages.get_nowait()
        # self.plotter.update_curve_keys(message.as_curve_keys())
        # print("reinitializing plotter class")
        # self.plotter.ui_init()

    def end_serial(self):
        self.serial.end()
        logging.debug("Serial thread ended")

    # ---------------------- Global UI Event Handling ----------------------
    def mousePressEvent(self, event):
        # Check if the click is outside q3_text_input
        for item in self.clickable_items:
            if not item.geometry().contains(event.pos()):
                item.clearFocus()
            super().mousePressEvent(event)

    def closeEvent(self, event):
        try:
            self.end_serial()
        except:
            pass
        time.sleep(0.1)
        self._dump_user_settings()
        if self.serial_process != None:
            self.serial_process.terminate()
        super().closeEvent(event)
        # self.plotter.data_generator.terminate()

    # ---------------------- User Settings and Caching ----------------------
    def _get_user_settings(self) -> dict:
        data_dict = {}
        try:
            with open("src/user_settings.json", "r") as file:
                data_dict = json.load(file)

        except FileNotFoundError:
            logging.error("File not found user_settings.json file")

            with open("src/user_settings.json", "w") as file:
                file.write("{}")

        except json.JSONDecodeError:
            logging.error("Malformed user_settings.json file")
            data_dict = {}

        if data_dict == {}:
            data_dict.update(
                {
                    "baud": 115200,
                    "port": None,
                    "line_ending": "None",
                    "log_to_file": True,
                }
            )

        return data_dict

    def _dump_user_settings(self):
        self.user_settings.update(
            {
                "baud": self.baud.text(),
                "port": self.serial_ports.currentIndex(),
                "line_ending": self.serial_line_ending.currentIndex(),
                "log_to_file": self.log_to_file_checkbox.isChecked(),
            }
        )

        with open("src/user_settings.json", "w") as file:
            json.dump(self.user_settings, file, indent=4)

    # ---------------------- Misc. ----------------------
    def _safe_num_as_str(self, number, characters):
        """
        Create a string representation of a number that limits it to a certain character count.
        If the number cannot be represented fully within the max allowed number of characters,
        it defaults to the most specific possible scientific notation using (xEn notation).
        The output string is exactly as long as 'characters', padded by zeroes when necessary.

        :param number: The input number.
        :param characters: The max allowed length of the string.
        :return: String representation of the number with specified constraints.
        """

        is_negative = number < 0
        number = abs(number)

        # Determine how many digits are needed for the integer part
        int_digits = len(str(int(number)))

        # Calculate remaining space for decimal part
        decimal_space = max(0, characters - int_digits - 1)  # -1 for the decimal point

        if int_digits + 1 <= characters:
            # Format with fixed-point notation, trimming or padding the decimal part
            formatted_number = f"{number:.{decimal_space}f}"
        else:
            # Use scientific notation
            sci_decimal_space = max(0, characters - 5)  # -5 for "e+XX."
            formatted_number = f"{number:.{sci_decimal_space}e}"

        # Ensure the string length matches 'characters'
        if len(formatted_number) > characters:
            formatted_number = formatted_number[:characters]

        # Restore the negative sign if necessary
        if is_negative:
            formatted_number = "-" + formatted_number[1:]

        return formatted_number


def average(xarr, yarr):
    return float(np.mean(yarr))


if __name__ == "__main__":
    logging.basicConfig(
        format="SPLOTTER: %(asctime)s - %(levelname)s - %(message)s",
        level=logging.DEBUG,
    )

import sys
import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QColorDialog,
)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt, QSize
import time
import random
from datetime import datetime
from multiprocessing import Process, Queue


class DataGenerator(Process):
    def __init__(self, data_queue):
        super().__init__()
        self.data_queue = data_queue
        self.active_curves = list(range(9))

    def run(self):
        a = 0
        two_pi = 2 * np.pi
        while True:
            for i in self.active_curves:
                x = datetime.now().timestamp()
                y = np.sin(a)
                self.data_queue.put((i, (x, y)))

                a += 0.01
                if a >= two_pi:
                    a -= two_pi  # Reset a to 0 after reaching 2π
            time.sleep(0.0001)


from PyQt5.QtCore import pyqtSignal


class CustomPlotWidget(pg.PlotWidget):
    sigMouseWheelScrolled = pyqtSignal(object)  # Define a custom signal

    def wheelEvent(self, event):
        super().wheelEvent(event)  # Call the original wheelEvent
        self.sigMouseWheelScrolled.emit(event)  # Emit the custom signal


class LivePlotter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        main_layout = QVBoxLayout(self)

        self.plot_widget = CustomPlotWidget()
        self.plot_widget.setMouseEnabled(x=False, y=False)
        main_layout.addWidget(self.plot_widget)
        self.legend = self.plot_widget.addLegend()

        self.max_points = 10000
        self.has_downsampled = False
        self.plot_curves = []
        self.data_generators = []
        self.displayed_data = []
        self.total_data = []
        self.cached_total_data = []
        self.data_queue = Queue()
        self.data_generator = DataGenerator(self.data_queue)
        self.data_generator.start()
        self.colors = [
            "red",
            "green",
            "blue",
            "yellow",
            "white",
            "cyan",
            "magenta",
            "orange",
            "pink",
            "purple",
        ]
        self.color_buttons = []
        self.checkboxes = []

        # Checkbox and color picker layout
        self.checkbox_container = QWidget()  # Container for the grid layout
        self.checkbox_layout = QGridLayout(
            self.checkbox_container
        )  # Set the layout to the container
        self.checkbox_container.setFixedHeight(
            90
        )  # Set the maximum height for the container
        main_layout.addLayout(self.checkbox_layout)
        self.checkbox_layout.setVerticalSpacing(1)
        self.checkbox_layout.setHorizontalSpacing(1)

        self.num_curves = 9
        for i in range(self.num_curves):
            curve_layout = QHBoxLayout()

            checkbox = QCheckBox(f"Curve {i+1}")
            font = checkbox.font()
            font.setPointSize(8)  # Smaller font size
            checkbox.setFont(font)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(
                lambda checked, idx=i: self.toggle_curve(idx, checked)
            )
            self.checkboxes.append(checkbox)
            checkbox.setFixedHeight(10)

            color_button = QPushButton()
            color_button.setStyleSheet(f"background-color: {self.colors[i]}")
            color_button.setFixedWidth(15)  # Fixed width for color buttons
            color_button.clicked.connect(lambda _, idx=i: self.open_color_picker(idx))
            self.color_buttons.append(color_button)

            curve_layout.addWidget(color_button)
            curve_layout.addWidget(checkbox)
            curve_layout.addStretch()  # Ensure tight packing

            curve_container = QWidget()
            curve_container.setLayout(curve_layout)

            self.checkbox_layout.addWidget(
                curve_container, i // 3, i % 3
            )  # Arranging curve containers

            curve = self.plot_widget.plot(pen=self.colors[i])
            self.legend.addItem(curve, f"Curve {i+1}")
            self.plot_curves.append(curve)
            self.displayed_data.append([])
            self.total_data.append([])
            self.cached_total_data.append([])

            # data_generator = DataGenerator(i, frequency=1.0 + i * 0.5)
            # data_generator.data_signal.connect(self.receive_data)
            # data_generator.start()
            # self.data_generators.append(data_generator)

            # self.data_generator = DataGenerator()
            # self.data_generator.data_signal.connect(self.receive_data)
            # self.data_generator.start()

        self.timer = QTimer()
        self.timer2 = QTimer()

        self.timer.timeout.connect(self.update_plot)
        self.timer.timeout.connect(self.process_queue)

        self.timer.start(1)
        self.timer2.start(250)
        self.timer2.timeout.connect(self.update_title)

        self.last_update = time.time()
        self.fps = 0
        self.fps_avg_n = 0

        # Crosshair Cursor
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.hLine = pg.InfiniteLine(angle=0, movable=False)
        self.plot_widget.addItem(self.vLine, ignoreBounds=True)
        self.plot_widget.addItem(self.hLine, ignoreBounds=True)
        self.mouse_label = QLabel()
        self.mouse_label.setFixedHeight(11)
        main_layout.addWidget(self.mouse_label)
        self.plot_widget.scene().sigMouseMoved.connect(self.mouse_moved)
        self.plot_widget.sigMouseWheelScrolled.connect(
            self.mouse_scrolled
        )  # Connect the custom signal

        # Buttons layout
        buttons_layout = QHBoxLayout()
        main_layout.addLayout(buttons_layout)

        # Start/Stop Button
        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.clicked.connect(self.toggle_start_stop)
        buttons_layout.addWidget(self.start_stop_button)
        # font = self.start_stop_button.font()
        # font.setPointSize(8)  # Smaller font size
        # self.start_stop_button.setFont(font)
        # self.start_stop_button.setFixedHeight(20)

        # View All/Hide All Button
        self.menu_button = QPushButton("Show Menu")
        self.menu_button.clicked.connect(self.toggle_menu)
        buttons_layout.addWidget(self.menu_button)

        # View All/Hide All Button
        self.view_all_button = QPushButton("Hide All Plots")
        self.view_all_button.clicked.connect(self.toggle_view_all)
        buttons_layout.addWidget(self.view_all_button)

        self.hide_menu = True
        self.checkbox_container.hide()
        self.hide_all = True
        self.is_live = True

        self.toggle_start_stop()
        main_layout.addWidget(self.checkbox_container)
        self.show()

    def toggle_menu(self):
        self.hide_menu = not self.hide_menu
        if self.hide_menu:
            self.menu_button.setText("Show Menu")
            self.checkbox_container.hide()
        else:
            self.menu_button.setText("Hide Menu")
            self.checkbox_container.show()

    def toggle_view_all(self):
        self.hide_all = not self.hide_all
        if self.hide_all:
            self.view_all_button.setText("Hide All Plots")
            for item in self.plot_curves:
                item.setVisible(True)
            for checkbox in self.checkboxes:
                checkbox.setChecked(True)

            self.plot_widget.autoRange()
        else:
            self.view_all_button.setText("Show All Plots")
            for item in self.plot_curves:
                item.setVisible(False)
            for checkbox in self.checkboxes:
                checkbox.setChecked(False)

    def open_color_picker(self, idx):
        color = QColorDialog.getColor()
        if color.isValid():
            self.colors[idx] = color.name()
            self.plot_curves[idx].setPen(pg.mkPen(color.name()))
            self.color_buttons[idx].setStyleSheet(f"background-color: {color.name()}")

    def toggle_curve(self, idx, checked):
        self.plot_curves[idx].setVisible(checked)

    def process_queue(self):
        while not self.data_queue.empty():
            curve_id, data_point = self.data_queue.get()
            self.receive_data(curve_id, data_point)

    def receive_data(self, curve_id, data_point):
        x, y = data_point
        if self.is_live:
            self.displayed_data[curve_id].append((x, y))
            if len(self.displayed_data[curve_id]) > 1000:
                self.displayed_data[curve_id].pop(0)
        self.total_data[curve_id].append((x, y))
        if len(self.total_data[curve_id]) > self.max_points:
            self.total_data[curve_id].pop(0)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.pan_plot("left")
        elif event.key() == Qt.Key_Right:
            self.pan_plot("right")

    def update_plot(self):
        if self.is_live:
            for i, curve in enumerate(self.plot_curves):
                x_vals, y_vals = (
                    zip(*self.displayed_data[i]) if self.displayed_data[i] else ([], [])
                )
                curve.setData(x_vals, y_vals)  # Update plot data
            self.plot_widget.autoRange()

        now = time.time()
        dt = now - self.last_update
        if dt > 0:
            self.fps += 1.0 / dt
            self.fps_avg_n += 1
            self.last_update = now

    def get_total_points(self):
        total = 0
        for list in self.total_data:
            total += len(list)
        return total

    def update_title(self):
        if self.fps_avg_n == 0:
            return
        self.setWindowTitle(
            f"Live Plotter - FPS: {(self.fps/self.fps_avg_n):.2f}, n: {self.get_total_points()}"
        )
        self.fps_avg_n = 0
        self.fps = 0

    def calculate_total_points_shown(self):
        view_range = self.plot_widget.viewRange()
        x_min, x_max = view_range[0]  # x-axis range

        total_displayed_points = 0
        for curve_data in self.total_data:
            # Count the number of points within the view range for each curve
            points_in_range = [
                point for point in curve_data if x_min <= point[0] <= x_max
            ]
            total_displayed_points += len(points_in_range)

    def mouse_scrolled(self, event):
        # if not self.is_live:
        #     view_range = self.plot_widget.viewRange()
        #     x_min, x_max = view_range[0]  # x-axis range

        #     total_displayed_points = 0
        #     for curve_data in self.displayed_data:
        #         # Count the number of points within the view range for each curve
        #         points_in_range = [
        #             point for point in curve_data if x_min <= point[0] <= x_max
        #         ]
        #         total_displayed_points += len(points_in_range)

        #     print(f"Total displayed points in view range: {total_displayed_points}")
        pass

    def closeEvent(self, event):
        self.data_generator.terminate()  # Terminate the data generator process
        event.accept()

    def mouse_moved(self, pos):
        # # Get the current view bounds
        # view_range = self.plot_widget.viewRange()

        # # If the lower X-bound is less than 0, adjust it to 0
        # if view_range[0][0] < 0:
        #     self.plot_widget.setXRange(
        #         0, view_range[0][1] - view_range[0][0], padding=0
        #     )

        mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(pos)
        self.vLine.setPos(mouse_point.x())
        self.hLine.setPos(mouse_point.y())
        time_str = datetime.fromtimestamp(mouse_point.x()).strftime(
            "%Y-%m-%d %H:%M:%S.%f"
        )
        self.mouse_label.setText(f"Time: {time_str}, Y: {mouse_point.y():.2f}")

    def toggle_start_stop(self):
        self.is_live = not self.is_live
        if self.is_live:
            self.start_stop_button.setText("Stop")
            # Resume live plotting
            for i in range(self.num_curves):
                self.plot_widget.setMouseEnabled(x=False, y=False)  # Disable scrolling
                self.displayed_data[i].clear()
        else:
            self.start_stop_button.setText("Start")
            # Freeze plot and display all data
            for i in range(self.num_curves):
                # self.cached_total_data[i] = self.total_data[i].copy()
                self.plot_widget.setMouseEnabled(x=True, y=False)  # Enable scrolling
                x_vals, y_vals = (
                    zip(*self.total_data[i]) if self.total_data[i] else ([], [])
                )
                self.plot_curves[i].setData(x_vals, y_vals)  # Set formatted (x, y) data
            self.plot_widget.autoRange()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = LivePlotter()
    sys.exit(app.exec_())

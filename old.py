import multiprocessing
import time
import re
from pprint import pprint
import serial
from serial.tools.list_ports import comports
import matplotlib.pyplot as plt
import numpy as np
import random


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
    def __init__(self, color_keys, custom_analyses) -> None:
        plt.ion()  # Set interactive mode on
        self.fig, self.ax = plt.subplots()
        self.plots = {}
        self.custom_analyses = custom_analyses

        self.x_data = []
        self.datas = {}
        self.statuses = {}

        self.all_colors = {
            "red",
            "green",
            "blue",
            "yellow",
            "purple",
            "orange",
            "cyan",
            "magenta",
            "brown",
            "black",
            "white",
        }
        self.used_colors = []
        self.status_text = None
        self.plot_info_text = None
        self.fig.subplots_adjust(left=0.3)
        self.window_length = 500  # TODO:
        self.color_keys = color_keys

    def _add_plot(self, plot_id, color):
        if plot_id not in self.plots:
            (line,) = self.ax.plot([], [], color, label=plot_id)
            self.plots[plot_id] = line
            self.ax.legend(loc="lower left")

    def _remove_plot(self, plot_id):
        if plot_id in self.plots:
            line = self.plots.pop(plot_id)
            line.remove()
            self.ax.legend(loc="lower left")
            # TODO: Color removal

    def update(self, data: list):
        for datapoint in data:  # For EACH message
            # Add all the statuses to display from the messages
            for status in datapoint["statuses"]:
                if status[0] not in self.statuses.keys():
                    self.statuses[status[0]] = []
                self.statuses[status[0]] = status[1]

            # Build our current series X
            self.x_data.append(datapoint["timestamp"])

            # For each y series and build clean dictionary
            datas = datapoint["datas"]
            for key, value in datas:
                if key not in self.datas:
                    self.datas[key] = []
                    self._add_plot(
                        key, self.color_keys[key]
                    )  # Add plot with a specified color

                self.datas[key].append(value)
                self.plots[key].set_xdata(self.x_data)
                self.plots[key].set_ydata(self.datas[key])

            custom_analysis: CustomAnalysis
            for custom_analysis in self.custom_analyses:
                print(custom_analysis.name)
                if custom_analysis.type == CustomAnalysis.kind.SERIES_SCALAR:
                    print(len(self.x_data))
                    # print(custom_analysis.function_reader(self.x_data, self.datas[key]))

        # Check if the total data points exceed the window length
        if len(self.x_data) > self.window_length:
            # Determine how many points to remove
            # num_points_to_remove = len(self.x_data) - self.window_length

            # Remove the oldest data points
            self.x_data = self.x_data[-self.window_length :]

            for key in self.datas:
                self.datas[key] = self.datas[key][-self.window_length :]
                self.plots[key].set_xdata(self.x_data)
                self.plots[key].set_ydata(self.datas[key])

            # Adjust the X-axis limits
            self.ax.set_xlim(min(self.x_data), max(self.x_data))

        self.ax.relim()  # Recompute the ax.dataLim
        self.ax.autoscale_view()  # Rescale the view

        if self.status_text:
            self.status_text.remove()
            self.plot_info_text.remove()

        text = ""
        for key in self.statuses:
            value = self.statuses[key]
            text += key[1:] + ":" + value + "\n"

        self.status_text = self.fig.text(
            0.02,
            0.5,
            text,
            ha="left",
            va="center",
            fontsize=10,
            transform=self.fig.transFigure,
        )

        def average_difference(lst):
            if len(lst) < 2:
                return 0  # No difference if the list has less than 2 elements

            differences = [abs(lst[i] - lst[i - 1]) for i in range(1, len(lst))]
            average_diff = sum(differences) / len(differences)
            return average_diff

        avg_timestamp_difference = average_difference(self.x_data) / 1000
        if avg_timestamp_difference != 0:
            hz = 1 / avg_timestamp_difference
        else:
            hz = -1
        formatted_string = f"{hz:.2f}"
        total_t_formatted = f"{len(self.x_data) * avg_timestamp_difference:.2f}"
        self.plot_info_text = self.fig.text(
            0.5,
            0.01,
            "Num samples: "
            + str(len(self.x_data))
            + " @ "
            + formatted_string
            + " hz \n total t displayed: "
            + total_t_formatted,
            ha="center",
            va="bottom",
            fontsize=10,
        )

        # Update the figure canvas
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()


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


class SmartSerialPloter:
    def __init__(self, color_keys: dict) -> None:
        self.color_keys = color_keys
        self.custom_analyses = []

    def begin(self):
        manager = multiprocessing.Manager()
        shared_list = manager.list()

        # Creating processes
        p1 = multiprocessing.Process(target=self.serial_reader, args=(shared_list,))
        p2 = multiprocessing.Process(target=self.plotter_updater, args=(shared_list,))

        # Starting processes
        p1.start()
        p2.start()

        # Joining processes
        p1.join()
        p2.join()
        pass

    def add_customAnalysis(self, obj: CustomAnalysis):
        self.custom_analyses.append(obj)

    def serial_reader(self, shared_list):
        """Function to contunially read the serial monitor"""

        # initialize the serial monitor
        ports = serial.tools.list_ports.comports()
        port_to_connect_to = None
        for port, desc, hwid in sorted(ports):
            print(f"{port}: {desc} [{hwid}]")
            if "pico" in str(desc).lower():
                port_to_connect_to = port
        ser = serial.Serial(str(port_to_connect_to), 115200)
        while True:
            if ser.in_waiting > 0:
                data = ser.readline().decode("utf-8").rstrip()
                message = Message(str(data))
                # print("appending to shared list")
                shared_list.append(message.process())

    def plotter_updater(self, shared_list):
        """Function to read from the shared list only when changes occur."""

        plotter = Plotter(self.color_keys, self.custom_analyses)

        previous_state = None
        while True:
            if len(shared_list) > 50:  # TODO:
                shared_list[:] = []
                previous_state = None

            current_state = list(
                shared_list
            )  # Take a snapshot of the current list state
            if current_state != previous_state:
                if previous_state == None:
                    plotter.update(current_state)
                else:
                    diff = [
                        item for item in current_state if item not in previous_state
                    ]
                    plotter.update(diff)
                previous_state = current_state  # Update the previous state

            # time.sleep(0.01)


def average(xarr, yarr):
    return float(np.mean(yarr))


if __name__ == "__main__":
    custom_one = CustomAnalysis(
        "mean", CustomAnalysis.kind.SERIES_SCALAR, average, "pink", "."
    )

    colors = {"P1": "red", "P2": "blue", "P3": "green"}
    serial_plotter = SmartSerialPloter(colors)
    serial_plotter.add_customAnalysis(custom_one)
    serial_plotter.begin()

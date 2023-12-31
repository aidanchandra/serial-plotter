import serial
from serial.tools.list_ports import comports
import json
import logging
import os
import sys
import threading
import time
import numpy as np
import random
import queue
from typing import List
import multiprocessing
from pick import pick
from datetime import datetime, timedelta
from pprint import pprint
import logging
from rich.console import Console
from rich.logging import RichHandler
from logging import Handler
from rich.console import Console
from rich.live import Live
from rich.table import Table
import time

from src.message_classes import TXMessage, RXMessage, Message, MessageProcessException

console = Console()


class SerialPort:
    def __init__(self, port, desc, hwid) -> None:
        self.port = port
        self.desc = desc
        self.hwid = hwid

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, SerialPort) and __value.port == __value.port

    def __str__(self) -> str:
        return str(self.port)

    def __repr__(self) -> str:
        return str(self.port) + " (" + str(self.desc) + ")"


class SerialClass:
    def __init__(self, cachesize, enable_logging=True, verbose=False) -> None:
        self.cachesize = cachesize
        self.ser = None

        # Below for hz measurements
        self.last_rx_time = 0
        self.last_rx_n = 0

        manager = multiprocessing.Manager()
        self.rx_messages = multiprocessing.Queue()
        self.tx_messages = multiprocessing.Queue()
        self.config = manager.dict()
        self.all_messages = manager.list()

        if verbose:
            logging.basicConfig(
                format="Serial Class: %(message)s",
                level=logging.DEBUG,
            )

    def get_ports(self) -> List[SerialPort]:
        """Get a list of available serial ports as SerialPort objects

        Returns:
            list(SerialPort): List of SerialPort objects
        """
        ports = serial.tools.list_ports.comports()
        ports_list = []
        for port, desc, hwid in sorted(ports):
            ports_list.append(SerialPort(port, desc, hwid))

        return ports_list

    def _log(self, header: dict = None, data: dict = None, verbose=False):
        """Log either a header or data to the current logfile associated with this file

        Args:
            header (dict, optional): header dict data. Defaults to None.
            data (dict, optional): data to log. Defaults to None.
        """
        if header == None and data == None:
            return

        if not self.log_enabled:
            return

        # Check if the file exists
        if os.path.exists("logging/" + self.log_instance_name + ".json"):
            # Read existing data
            try:
                with open("logging/" + self.log_instance_name + ".json", "r") as file:
                    # Read existing data, expecting it to be a dictionary
                    existing_data = json.load(file)
                    # Ensure the existing data is a dictionary
                    if not isinstance(existing_data, dict):
                        existing_data = {"header": {}, "data": []}
            except json.JSONDecodeError:
                # In case of a decoding error, start with an empty dictionary
                existing_data = {"header": {}, "data": []}
        else:
            existing_data = {"header": {}, "data": []}

        if header != None:
            existing_data["header"].update(header)

        if data != None:
            existing_data_list = existing_data["data"]
            new_data_list = existing_data_list.copy()
            for item in data:
                new_data_list.append(str(item.json_friendly_object()))
            existing_data["data"] = new_data_list

        # Write data back to file
        with open("logging/" + self.log_instance_name + ".json", "w") as file:
            json.dump(existing_data, file, indent=4)

        if verbose:
            logging.debug("Logged to " + str(self.log_instance_name))

    def _log_helper(self):
        logging.basicConfig(
            format="Log Thread: %(message)s",
            level=logging.DEBUG,
        )
        logging.info("Log thread started")
        while self.logging_thread_enabled:
            time.sleep(5)
            logging.info("Logging heartbeat recieved")
            self._log(data=self.all_messages)
            self.all_messages = self.all_messages[:]

    def _handle_tx(self):
        while not self.tx_messages.empty():
            message_to_send: TXMessage
            message_to_send = self.tx_messages.get_nowait()
            try:
                logging.debug(
                    "Sending following message: " + str(message_to_send.sendable())
                )
                self.ser.write(message_to_send.sendable())
                self.all_messages.append(message_to_send)
            except Exception as e:
                logging.error(f"Error sending message: {e}")

    def _handle_rx(self, latch_timeout: int):
        data = self.ser.readline().decode("utf-8").rstrip()
        try:
            message = RXMessage(str(data))
            message.process()
            if self.first_message == None:
                self.last_rx_time = time.perf_counter_ns()
                self.time_of_first_message = datetime.now()
                self.first_message = message
                logging.debug("Latched first successful message")
                logging.debug("First message time: " + str(self.time_of_first_message))

            message.apply_offset(self.time_of_first_message)
            self.all_messages.append(message)
            self.rx_messages.put_nowait(message)

        except MessageProcessException:
            self.latch_attempts += 1
            logging.info("Error in proccessing message: " + str(message))
            if self.latch_attempts > latch_timeout:
                raise Exception("Failed too many latch attempts")

    def get_n_total_messages_read(self):
        return len(self.all_messages)

    def get_hz_rx_messages(self):
        try:
            messsage_1: RXMessage
            messsage_1 = self.all_messages[-2]
            messsage_2: RXMessage
            messsage_2 = self.all_messages[-1]
            delta = messsage_2.dut_offset - messsage_1.dut_offset
            return 1 / delta.total_seconds()
        except IndexError:
            return 0

    def start(self):
        self.log_enabled = self.config["log_enabled"]
        self.log_instance_name = self.config["log_name"]

        self.process = multiprocessing.Process(target=self.handler)
        self.process.start()

    def end(self):
        self.process.terminate()
        self.process.join()
        self.logging_thread_enabled = False
        self.first_message = None

        try:
            self.ser.close()
        except:
            pass
        logging.debug("Serial port safely closed")
        if self.log_enabled:
            self._log(data=self.all_messages)
            logging.debug("Logged remaining data")
        self.all_messages[:] = []

    def handler(self):
        logging.basicConfig(
            format="Serial Thread: %(message)s",
            level=logging.DEBUG,
        )
        # Needed variables from self.config:
        self.port = self.config["port"]
        self.port: SerialPort
        self.baud = self.config["baud"]
        self.latch_timeout = self.config["latch_timeout"]

        logging.info("Connecting to: " + str(self.port.port))
        self.ser = serial.Serial(str(self.port.port), self.baud)
        self.cur_start_time = str(time.time())
        logging.info("Connected successfully")

        self._log(
            header={
                "port": str(self.port.port),
                "desc": str(self.port.desc),
                "hwid": str(self.port.hwid),
                "baud": str(self.baud),
                "local_t_connect": self.cur_start_time,
            }
        )

        logging.debug("Finished initial log")

        self.latch_attempts = 0
        self.first_message = None
        self.logging_thread_enabled = True

        log_thread = threading.Thread(
            target=self._log_helper,
            args=(),
        )
        if self.log_enabled:
            log_thread.start()

        logging.debug("Beginning main loop")
        self.ser.flush()
        while True:
            self._handle_tx()
            if self.ser.in_waiting > 0:
                self._handle_rx(self.latch_timeout)


if __name__ == "__main__":
    s = SerialClass(5000, verbose=True)
    print("______________________________________")
    option, index = pick(["Enable Log", "Disable Log"], "Logging?")
    enable_logging = index == 0

    ports = s.get_ports()
    option, index = pick(ports, "Available Serial Ports")
    chosen_port = ports[index]

    manager = multiprocessing.Manager()
    current_time = datetime.now()
    current_time = datetime.now()
    s.config["log_name"] = current_time.strftime("%Y-%m-%d_%H-%M-%S")
    s.config["on"] = True
    s.config["log_enabled"] = enable_logging
    s.config["port"] = chosen_port
    s.config["baud"] = 115200
    s.config["latch_timeout"] = 50

    table = Table()
    table.add_column("Column 1")
    table.add_column("Column 2")
    table.add_row("Row 1 Data 1", "Row 1 Data 2")
    table.add_row("Row 2 Data 1", "Row 2 Data 2")
    # Start the process

    s.start()

    input()
    s.end()

import serial
from serial.tools.list_ports import comports
import json
import logging
import os
import sys
import threading
import time


class RecievedMessage:
    def __init__(self, raw_string: str) -> None:
        self.raw_string = raw_string
        self.timestamp = None
        self.statuses = None
        self.datas = None
        self.offset = False
        self.local_t = str(time.time())

    def process(self):
        self.timestamp = self.raw_string[0 : int(self.raw_string.find("::"))]
        data_string_subst = self.raw_string[int(self.raw_string.find("::")) + 2 :]
        pairs = data_string_subst.split(",")
        self.datas = []
        self.statuses = []
        for pair in pairs:
            # Split each pair by colon
            name, data = pair.split(":")

            # Convert data to float and append the tuple to the result list
            if "!" in name:
                self.statuses.append((name, str(data)))
            else:
                self.datas.append((name, float(data)))
            self.data = {
                "timestamp": self.timestamp,
                "local_t": self.local_t,
                "statuses": self.statuses,
                "datas": self.datas,
                "is_offset": self.offset,
            }

    def apply_offset(self, dut_starttime):
        self.offset = True
        dut_offset = int(self.timestamp) - int(dut_starttime)
        self.data.update({"timestamp": dut_offset})

    def get(self):
        return self.data

    def get_timestamp(self):
        return self.timestamp

    def json_friendly_object(self) -> list:
        return ["RX", self.data]


class SendMessage:
    def __init__(self, message: str, line_ending: str) -> None:
        self.message = message
        self.line_ending = line_ending

    def sendable(self):
        # Append the line ending if specified
        if self.line_ending == "LF":
            self.message += "\n"
        elif self.line_ending == "CR":
            self.message += "\r"
        elif self.line_ending == "CRLF":
            self.message += "\r\n"

        return self.message.encode("utf-8")

    def json_friendly_object(self) -> list:
        return [
            "TX",
            {
                "local_t": str(time.time()),
                "line_ending": self.line_ending,
                "message": self.message,
            },
        ]


class SerialReader:
    def __init__(self, cachesize, enable_logging=True) -> None:
        self.logging_flag = enable_logging
        self.messages = []
        self.cachesize = cachesize
        self.ser = None
        self.on = False

    def get_ports(self):
        # initialize the serial monitor
        ports = serial.tools.list_ports.comports()
        ports_list = []
        for port, desc, hwid in sorted(ports):
            ports_list.append([port, desc, hwid])

        return ports_list

    def _log(self, header=None, data=None):
        """
        Logs a dictionary to a JSON file. If the file does not exist, it creates a new file.
        If it does exist, it appends data to the existing file.

        :param data: Dictionary to be logged.
        """
        if header == None and data == None:
            return

        # Check if the file exists
        if os.path.exists("logging/" + self.log_instance + ".json"):
            # Read existing data
            try:
                with open("logging/" + self.log_instance + ".json", "r") as file:
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
            new_data_list.append(data)
            existing_data["data"] = new_data_list

        # Write data back to file
        with open("logging/" + self.log_instance + ".json", "w") as file:
            json.dump(existing_data, file, indent=4)

        logging.debug("Logged to " + str(self.log_instance))

    def handler(
        self,
        read_messages,
        send_messages,
        misc_data,
        port,
        baud=115200,
        latch_timeout=50,
    ):
        logging.basicConfig(
            format="READER: %(asctime)s - %(levelname)s - %(message)s",
            level=logging.DEBUG,
        )
        logging.debug("_______________________________________________________")

        self.log_instance = misc_data["log_name"]
        self.cur_start_time = str(time.time())

        self.log_enabled = misc_data["log_enabled"]

        if self.log_enabled:
            self._log(
                header={
                    "port": str(port[0]),
                    "desc": str(port[1]),
                    "hwid": str(port[2]),
                    "baud": str(baud),
                    "local_t_connect": self.cur_start_time,
                    "data": [],
                }
            )

        logging.info("Connecting to: " + str(port[0]))
        logging.info("Baudrate: " + str(baud))

        self.ser = serial.Serial(str(port[0]), baud, timeout=1)

        latch_attempts = 0
        first_message = False
        dut_time_of_first_message = -1

        logging.debug("Began read function")
        start_time = time.perf_counter()
        while misc_data["on"]:
            # Messsages to send
            if len(send_messages) > 0:
                message_to_send: SendMessage
                for message_to_send in send_messages:
                    try:
                        logging.debug(
                            "Sending following message: "
                            + str(message_to_send.sendable())
                        )
                        self.ser.write(message_to_send.sendable())
                        self.messages.append(
                            message_to_send.json_friendly_object()
                        )  # TX messages will have current system time.time associated with them
                    except Exception as e:
                        logging.error(f"Error sending message: {e}")
                send_messages[:] = []
            # Messages to recieve
            if self.ser.in_waiting > 0:
                data = self.ser.readline().decode("utf-8").rstrip()
                try:
                    # Process the message
                    message = RecievedMessage(str(data))
                    message.process()

                    # If it is the first succesful one
                    if first_message == False:
                        dut_time_of_first_message = message.get_timestamp()
                        try:
                            int(dut_time_of_first_message)
                            logging.info(
                                "DUT Starttime: " + str(dut_time_of_first_message)
                            )
                            first_message = True
                        except ValueError:
                            logging.debug(
                                "Correctly handled malformed attempted offeset message"
                            )

                    # Append to shared list the now offset-message
                    message.apply_offset(dut_time_of_first_message)
                    read_messages.append(message.get())
                    self.messages.append(message.json_friendly_object())

                except (
                    Exception
                ) as e:  # Exception from processing message will be caught here - ie a latch error
                    logging.info("Failed %d latch attempts", latch_attempts)
                    logging.debug("Failed on message: %s", str(data))
                    logging.debug("Exception message: %s ", str(e))

                    self.ser.flush()
                    latch_attempts += 1
                    time.sleep(0.01)
                    if latch_attempts > latch_timeout:
                        logging.critical(
                            "Timeout in latching full-messages in from serial monitor"
                        )
                        raise e
                        # sys.exit(0)

            cur_time = time.perf_counter()
            ellapsed_time = cur_time - start_time
            if ellapsed_time > 5:
                if self.log_enabled:
                    log_start_time = time.perf_counter_ns()
                    logging.debug("Log-to-file heartbeat received")
                    # Start a new thread to run the _log function
                    log_thread = threading.Thread(
                        target=self._log,
                        args=(
                            None,
                            self.messages.copy(),
                        ),
                    )
                    log_thread.start()

                log_time_ellapsed = time.perf_counter_ns() - log_start_time
                logging.debug("Logging started in " + str(log_time_ellapsed) + "nS")

                start_time = time.perf_counter()
                self.messages = []

        self.ser.close()
        logging.debug("Serial port safely closed")
        if self.log_enabled:
            self._log(data=self.messages)
            logging.debug("Logged remaining data")
        self.messages = []
        logging.debug("_______________________________________________________")

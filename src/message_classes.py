import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class Message(ABC):
    @abstractmethod
    def json_friendly_object(self) -> list:
        pass

    @abstractmethod
    def __str__(self):
        pass


class MessageProcessException(Exception):
    def __init__(self, message="Exception in processing message"):
        self.message = message
        super().__init__(self.message)


class RXMessage(Message):
    def __init__(self, raw_string: str) -> None:
        self.raw_string = raw_string
        self.device_timestamp = None
        self.statuses = None
        self.datas = None
        self.unit = None
        self.offset = False
        current_time_ns = time.time_ns()

        self.local_t = str(time.time())

    def process(self):
        try:
            self.unit_str = self.raw_string[0:1]
            self.device_timestamp = self.raw_string[1 : int(self.raw_string.find("::"))]
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

            self.local_t = datetime.now()
        except:
            raise MessageProcessException()

    def get_statuses(self):
        return self.statuses

    def as_curve_keys(self):
        returnable = []
        for data in self.datas:
            returnable.append(data[0])
        # TODO:
        return returnable

    def as_plottable_list(self):
        """
        Returns one list
            datas = [(x1,y1), (x2,y2)]
        """
        returnable = []
        for data in self.datas:
            returnable.append((self.dut_offset.timestamp(), data[1]))
        return returnable

    def apply_offset(self, dut_starttime: datetime):
        try:
            self.offset = True
            if self.unit_str == "m":
                dut_offset = dut_starttime + timedelta(
                    milliseconds=int(self.device_timestamp)
                )
            if self.unit_str == "u":
                dut_offset = dut_starttime + timedelta(
                    microseconds=int(self.device_timestamp)
                )
            self.dut_offset = dut_offset
        except:
            raise MessageProcessException()
        # self.data.update({"timestamp": dut_offset})

    def get_timestamp(self):
        return self.timestamp

    def json_friendly_object(self) -> list:
        return [
            "RX",
            {"dut_offset": self.dut_offset.timestamp(), "message": self.raw_string},
        ]

    def __str__(self):
        return self.raw_string

    def __repr__(self) -> str:
        return self.__str__()


class TXMessage(Message):
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

    def __str__(self):
        return self.message

    def __repr__(self) -> str:
        return self.__str__()

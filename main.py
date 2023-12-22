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

    def __init__(self, name:str, type:kind, function_reader, color, dasher) -> None:
        self.type = type
        self.name = name
        self.function_reader = function_reader
        self.color = color
        self.dasher = dasher
        if(self.type == CustomAnalysis.kind.POINT_SCALAR):
            try:
                a = function_reader(1,2)
                assert(isinstance(a,float) or isinstance(a,int))
            except Exception as e:
                print("Malformed function for POINT_SCALAR")
                raise e
        if(self.type == CustomAnalysis.kind.SERIES_SCALAR):
            try:
                a = function_reader([1,2,3],[4,5,6]) # x_array, y_array
                assert(isinstance(a,float) or isinstance(a,int))
            except Exception as e:
                print("Malformed function for POINT_SCALAR")
                raise e
    def process(self):
        pass

class Message:
    def __init__(self, raw_string:str) -> None:
        self.raw_string = raw_string

    def process(self) -> dict:
        returnable = {}
        self.timestamp = self.raw_string[0:int(self.raw_string.find("::"))]
        returnable["timestamp"] = (int(self.timestamp))

        data_string_subst = self.raw_string[int(self.raw_string.find("::"))+2:]
        pairs = data_string_subst.split(',')
        datas = []
        statuses = []
        for pair in pairs:
            # Split each pair by colon
            name, data = pair.split(':')
            
            # Convert data to float and append the tuple to the result list
            if("!" in name):
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
        logging.basicConfig(format='PLOTTER: %(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)

        while(True):
            if(len(shared_list) > 0):
                self.data.append(shared_list.pop())

            if (len(self.data) >= self.cachesize):
                self.data = self.data[-self.cachesize:]



class SerialReader:
    def __init__(self, cachesize, enable_logging=True) -> None:
        self.logging_flag = enable_logging
        self.messages = []
        self.cachesize = cachesize
        self.ser = None
        

    def get_ports(self):
        #initialize the serial monitor
        ports = serial.tools.list_ports.comports()
        ports_list = []
        for port, desc, hwid in sorted(ports):
            # print(f"{port}: {desc} [{hwid}]")
            ports_list.append([port,desc,hwid])

        return ports_list

    def _log(self, data):
        """
        Logs a dictionary to a JSON file. If the file does not exist, it creates a new file. 
        If it does exist, it appends data to the existing file.

        :param data: Dictionary to be logged.
        """

        # Check if the file exists
        if os.path.exists('logging/'+self.log_instance+'.json'):
            # Read existing data
            try:
                with open('logging/'+self.log_instance+'.json', 'r') as file:
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
        with open('logging/'+self.log_instance+'.json', 'w') as file:
            json.dump(existing_data, file, indent=4)

    def begin_read(self, shared_list, port, baud=115200, latch_timeout=10):  
        logging.basicConfig(format='READER: %(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)



        self.log_instance = str(time.time()).replace('.','-')
        self._log({
            "port":str(port[0]),
            "desc":str(port[1]),
            "hwid":str(port[2]),
            "baud":str(baud),
            "t_connect":str(time.time()),
            "data":[]
        })


        logging.info("Connecting to:"+str(port[0]))
        self.ser = serial.Serial(str(port[0]), baud)

        latch_attempts = 0
        logging.debug("Began read function")
        start_time = time.perf_counter()
        while(True):
            if self.ser.in_waiting > 0:
                data = self.ser.readline().decode('utf-8').rstrip()
                try:
                    message = Message(str(data))
                    shared_list.append(message.process())
                    self.messages.append(str(data))
                except Exception as e:
                    logging.info("Failed %d latch attempts",latch_attempts)
                    latch_attempts+=1
                    if latch_attempts > latch_timeout:
                        logging.critical("Timeout in latching full-messages in from serial monitor")
                        raise e
                    
            cur_time = time.perf_counter()
            ellapsed_time = cur_time-start_time
            if ellapsed_time > 5:
                logging.debug("Log-to-file heartbeat recieved")
                self._log({
                    "data":self.messages
                })
                start_time = time.perf_counter()
                self.messages = []





class SmartSerialPloter:
    def __init__(self, cachesize=500) -> None:
        self.custom_analyses = []
        self.cachesize = cachesize
        self.plotter = Plotter(self.cachesize)
        self.reader = SerialReader(self.cachesize)


    def begin(self):
        logging.debug("Creating theads")
        manager = multiprocessing.Manager()
        shared_list = manager.list()
        # Creating processes
        serial_process = multiprocessing.Process(target=self.reader.begin_read, args=(shared_list, self.reader.get_ports()[1], ))
        plot_process = multiprocessing.Process(target=self.plotter.update, args=(shared_list,))

        logging.debug("Starting theads")
        # Starting processes
        serial_process.start()
        plot_process.start()

        logging.debug("Joining theads")
        # Joining processes
        serial_process.join()
        plot_process.join()

    def add_customAnalysis(self, obj:CustomAnalysis):
        self.custom_analyses.append(obj)
        

def average(xarr,yarr):
    return float(np.mean(yarr))

if __name__ == "__main__":
    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.DEBUG)
    a = SmartSerialPloter(cachesize = 5000)
    a.begin()
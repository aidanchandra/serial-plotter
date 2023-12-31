import multiprocessing


class ProcessHandler:
    def __init__(self):
        manager = multiprocessing.Manager()
        self.queue1 = multiprocessing.Queue()
        self.queue2 = multiprocessing.Queue()
        self.shared_dict = manager.dict()

    def process_function(self):
        while True:
            if not self.queue1.empty():
                item = self.queue1.get()
                print(f"Received from queue1: {item}")

            if not self.queue2.empty():
                item = self.queue2.get()
                print(f"Received from queue2: {item}")

            if "key" in self.shared_dict:
                print(f"Shared value: {self.shared_dict['key']}")

            # Add more logic here as needed

    def start_process(self):
        self.process = multiprocessing.Process(target=self.process_function)
        self.process.start()

    def stop_process(self):
        self.process.terminate()
        self.process.join()


# Usage of the ProcessHandler class
if __name__ == "__main__":
    handler = ProcessHandler()

    # Start the process
    handler.start_process()

    # Example of using the queues and dictionary
    handler.queue1.put("Item 1")
    handler.queue2.put("Item 2")
    handler.shared_dict["key"] = "Shared Value"

    # Perform other actions as needed...

    # Stop the process when done
    handler.stop_process()

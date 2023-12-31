import logging
from rich.console import Console
from rich.logging import RichHandler
from logging import Handler
from rich.console import Console
from rich.live import Live
from rich.table import Table
import time


class CustomRichHandler(RichHandler):
    def __init__(self, console: Console, use_rich: bool = True, *args, **kwargs):
        super().__init__(console=console, *args, **kwargs)
        self.use_rich = use_rich
        self.console = console

    def emit(self, record: logging.LogRecord):
        if self.use_rich:
            super().emit(record)
        else:
            # Print directly to standard output or error
            log_entry = self.format(record)
            if record.levelno >= logging.ERROR:
                print(log_entry, file=sys.stderr)
            else:
                print(log_entry, file=sys.stdout)


# Create a console object
console = Console()

# Set up logging with the custom handler
logging.basicConfig(
    level="DEBUG",
    handlers=[
        CustomRichHandler(console, use_rich=True)
    ],  # Change use_rich to False to switch to standard logging
)

# Example usage
logger = logging.getLogger(__name__)

logger.info("This is an info message.")
logger.error("This is an error message.")


def generate_table():
    table = Table()
    table.add_column("Column 1")
    table.add_column("Column 2")
    table.add_row("Row 1 Data 1", "Row 1 Data 2")
    table.add_row("Row 2 Data 1", "Row 2 Data 2")
    return table


# The live updating section using 'Live'
with Live(generate_table(), console=console, refresh_per_second=4) as live:
    for _ in range(10):  # Loop to update the live section
        # Update the table here (modify this as needed)
        new_table = generate_table()
        live.update(new_table)

        # Print log messages (will not disrupt the live updating)
        logger.info("Updating data...")

        time.sleep(1)  # Sleep to simulate data processing

console.log("Finished updating.")

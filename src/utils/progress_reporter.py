"""
Progress Reporting Utilities

Provides consistent progress logging across the application
for long-running operations like ETL, ML training, etc.
"""

import logging
from typing import Optional, Callable
from datetime import datetime, timedelta
import sys


class ProgressReporter:
    """
    Utility class for reporting progress of long-running operations.
    
    Provides consistent formatting and timing information.
    
    Example:
        reporter = ProgressReporter("Processing games", total=1000)
        
        for i, game in enumerate(games):
            process_game(game)
            reporter.update(i + 1)
        
        reporter.complete()
    """
    
    def __init__(
        self,
        task_name: str,
        total: Optional[int] = None,
        logger: Optional[logging.Logger] = None,
        report_interval: int = 10
    ):
        """
        Initialize progress reporter.
        
        Args:
            task_name: Name of the task being reported
            total: Total number of items (None if unknown)
            logger: Logger instance (creates new if None)
            report_interval: Report every N items
        """
        self.task_name = task_name
        self.total = total
        self.logger = logger or logging.getLogger(__name__)
        self.report_interval = report_interval
        
        self.current = 0
        self.start_time = datetime.now()
        self.last_report_time = self.start_time
    
    def update(self, current: Optional[int] = None, message: str = ""):
        """
        Update progress.
        
        Args:
            current: Current item number (if None, increments by 1)
            message: Optional additional message
        """
        if current is not None:
            self.current = current
        else:
            self.current += 1
        
        # Report at intervals
        if self.current % self.report_interval == 0 or self.current == self.total:
            self._report(message)
    
    def _report(self, message: str = ""):
        """Generate and log progress report."""
        elapsed = datetime.now() - self.start_time
        
        # Build progress string
        if self.total:
            percentage = (self.current / self.total) * 100
            progress_str = f"{self.current}/{self.total} ({percentage:.1f}%)"
            
            # Estimate time remaining
            if self.current > 0:
                items_per_second = self.current / elapsed.total_seconds()
                remaining_items = self.total - self.current
                eta_seconds = remaining_items / items_per_second if items_per_second > 0 else 0
                eta = timedelta(seconds=int(eta_seconds))
                time_info = f" | Elapsed: {self._format_timedelta(elapsed)} | ETA: {self._format_timedelta(eta)}"
            else:
                time_info = f" | Elapsed: {self._format_timedelta(elapsed)}"
        else:
            progress_str = str(self.current)
            time_info = f" | Elapsed: {self._format_timedelta(elapsed)}"
        
        # Build full message
        full_message = f"  Progress [{self.task_name}]: {progress_str}{time_info}"
        if message:
            full_message += f" | {message}"
        
        self.logger.info(full_message)
    
    def complete(self, final_message: str = ""):
        """
        Report task completion.
        
        Args:
            final_message: Optional completion message
        """
        elapsed = datetime.now() - self.start_time
        
        if self.total and self.current != self.total:
            self.logger.warning(
                f"Task '{self.task_name}' completed with {self.current}/{self.total} items processed"
            )
        
        completion_msg = f"✓ {self.task_name} completed: {self.current} items in {self._format_timedelta(elapsed)}"
        if final_message:
            completion_msg += f" | {final_message}"
        
        self.logger.info(completion_msg)
    
    def error(self, error_message: str):
        """
        Report task error.
        
        Args:
            error_message: Error description
        """
        elapsed = datetime.now() - self.start_time
        self.logger.error(
            f"✗ {self.task_name} failed after {self._format_timedelta(elapsed)}: {error_message}"
        )
    
    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """Format timedelta for display."""
        total_seconds = int(td.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


def report_section(title: str, logger: Optional[logging.Logger] = None):
    """
    Log a section header for organized output.
    
    Args:
        title: Section title
        logger: Logger instance
        
    Example:
        report_section("STARTING ETL PROCESS")
        # Logs formatted section header
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(title.center(70))
    logger.info("=" * 70)


def report_subsection(title: str, logger: Optional[logging.Logger] = None):
    """
    Log a subsection header.
    
    Args:
        title: Subsection title
        logger: Logger instance
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    logger.info("")
    logger.info("-" * 70)
    logger.info(title)
    logger.info("-" * 70)


def report_stats(stats: dict, logger: Optional[logging.Logger] = None):
    """
    Log statistics in a formatted way.
    
    Args:
        stats: Dictionary of stat name -> value
        logger: Logger instance
        
    Example:
        report_stats({
            'Games processed': 500,
            'Players found': 150,
            'Errors': 3
        })
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    max_key_length = max(len(str(k)) for k in stats.keys())
    
    logger.info("")
    for key, value in stats.items():
        logger.info(f"  {str(key).ljust(max_key_length)} : {value}")


class BatchProgressReporter:
    """
    Progress reporter for batch operations with commit intervals.
    
    Useful for database operations where you want to commit periodically.
    
    Example:
        reporter = BatchProgressReporter(
            "Loading games",
            total=1000,
            batch_size=100,
            on_batch=lambda: conn.commit()
        )
        
        for i, game in enumerate(games):
            load_game(game)
            reporter.update(i + 1)
    """
    
    def __init__(
        self,
        task_name: str,
        total: Optional[int] = None,
        batch_size: int = 100,
        on_batch: Optional[Callable] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize batch progress reporter.
        
        Args:
            task_name: Name of the task
            total: Total number of items
            batch_size: Items per batch
            on_batch: Callback function to call after each batch
            logger: Logger instance
        """
        self.reporter = ProgressReporter(task_name, total, logger, batch_size)
        self.batch_size = batch_size
        self.on_batch = on_batch
        self.batch_count = 0
    
    def update(self, current: Optional[int] = None, message: str = ""):
        """Update progress and execute batch callback if needed."""
        prev_current = self.reporter.current
        self.reporter.update(current, message)
        
        # Check if we crossed a batch boundary
        prev_batch = prev_current // self.batch_size
        new_batch = self.reporter.current // self.batch_size
        
        if new_batch > prev_batch:
            self.batch_count += 1
            if self.on_batch:
                self.on_batch()
    
    def complete(self, final_message: str = ""):
        """Complete task and execute final batch callback."""
        if self.on_batch:
            self.on_batch()
        self.reporter.complete(final_message)
    
    def error(self, error_message: str):
        """Report error."""
        self.reporter.error(error_message)

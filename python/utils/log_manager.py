#!/usr/bin/env python3
"""
Log Manager for archiving logs by date range
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def parse_datetime(date_str: str, time_str: str) -> datetime:
    """
    Parse date and time strings into a datetime object.
    
    Args:
        date_str: Date string in format YYYY-MM-DD
        time_str: Time string in format HH:MM:SS
    
    Returns:
        datetime object
    """
    datetime_str = f"{date_str} {time_str}"
    return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")


def extract_timestamp_from_log_line(line: str) -> Optional[datetime]:
    """
    Extract timestamp from a log line.
    Log format: YYYY-MM-DD HH:MM:SS [LEVEL] logger_name: message
    
    Args:
        line: Log line string
    
    Returns:
        datetime object if timestamp found, None otherwise
    """
    # Pattern: YYYY-MM-DD HH:MM:SS
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})'
    match = re.match(pattern, line.strip())
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    return None


def extract_timestamp_from_patch_filename(filename: str) -> Optional[datetime]:
    """
    Extract timestamp from a patch filename.
    Patch filename format: YYYYMMDD_HHMMSS_microseconds_filename_status.patch
    
    Args:
        filename: Patch filename string
    
    Returns:
        datetime object if timestamp found, None otherwise
    """
    # Pattern: YYYYMMDD_HHMMSS at the beginning of filename
    pattern = r'^(\d{8})_(\d{6})_'
    match = re.match(pattern, filename)
    if match:
        try:
            date_str = match.group(1)  # YYYYMMDD
            time_str = match.group(2)   # HHMMSS
            # Convert to datetime format
            datetime_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
            return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, IndexError):
            return None
    return None


def archive_logs_by_date_range(
    start_date: str,
    start_time: str,
    end_date: str,
    end_time: str,
    logs_dir: Optional[str] = None,
    remove_records: bool = False,
    comment: Optional[str] = None
) -> str:
    """
    Archive logs from logs/logs directory based on date and time range.
    
    Args:
        start_date: Start date in format YYYY-MM-DD
        start_time: Start time in format HH:MM:SS
        end_date: End date in format YYYY-MM-DD
        end_time: End time in format HH:MM:SS
        logs_dir: Base logs directory (default: logs/logs relative to project root)
        remove_records: If True, remove archived records from original log files
        comment: Optional comment to append to archive directory name
    
    Returns:
        Path to the archive directory
    
    Raises:
        ValueError: If date/time format is invalid or start > end
    """
    # Parse datetime objects
    try:
        start_dt = parse_datetime(start_date, start_time)
        end_dt = parse_datetime(end_date, end_time)
    except ValueError as e:
        raise ValueError(f"Invalid date/time format: {e}")
    
    if start_dt > end_dt:
        raise ValueError("Start datetime must be before end datetime")
    
    # Determine logs directory
    if logs_dir is None:
        # Default to logs/logs relative to project root
        project_root = Path(__file__).parent.parent.parent
        logs_dir = project_root / "logs" / "logs"
    else:
        logs_dir = Path(logs_dir)
    
    if not logs_dir.exists():
        raise ValueError(f"Logs directory does not exist: {logs_dir}")
    
    # Create archive directory name
    # Format: from_YYYYMMDD_HHMMSS_to_YYYYMMDD_HHMMSS[_comment]
    start_str = start_dt.strftime("%Y%m%d_%H%M%S")
    end_str = end_dt.strftime("%Y%m%d_%H%M%S")
    archive_dir_name = f"from_{start_str}_to_{end_str}"
    
    # Add comment if provided (sanitize for filesystem safety)
    if comment:
        # Replace unsafe characters with underscores
        safe_comment = re.sub(r'[<>:"/\\|?*]', '_', comment.strip())
        # Replace spaces with underscores and remove leading/trailing underscores
        safe_comment = re.sub(r'\s+', '_', safe_comment).strip('_')
        if safe_comment:
            archive_dir_name = f"{archive_dir_name}_{safe_comment}"
    
    archive_dir = logs_dir / "archived" / archive_dir_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Process all .log files in logs/logs directory
    log_files = list(logs_dir.glob("*.log"))
    
    archived_count = 0
    total_lines_archived = 0
    
    for log_file in log_files:
        if not log_file.is_file():
            continue
        
        archived_lines = []
        remaining_lines = []
        
        # Read log file and filter lines by date range
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            for line in all_lines:
                timestamp = extract_timestamp_from_log_line(line)
                if timestamp is None:
                    # If no timestamp found, keep the line in original file
                    remaining_lines.append(line)
                    continue
                
                # Check if timestamp is within range (inclusive)
                if start_dt <= timestamp <= end_dt:
                    archived_lines.append(line)
                    # Don't add to remaining_lines if we're removing records
                    if not remove_records:
                        remaining_lines.append(line)
                else:
                    remaining_lines.append(line)
        except Exception as e:
            print(f"Warning: Failed to read {log_file}: {e}")
            continue
        
        # Write archived lines to archive file
        if archived_lines:
            archive_file = archive_dir / log_file.name
            try:
                with open(archive_file, 'w', encoding='utf-8') as f:
                    f.writelines(archived_lines)
                archived_count += 1
                total_lines_archived += len(archived_lines)
                print(f"Archived {len(archived_lines)} lines from {log_file.name} to {archive_file}")
                
                # Remove archived lines from original file if requested
                if remove_records:
                    try:
                        with open(log_file, 'w', encoding='utf-8') as f:
                            f.writelines(remaining_lines)
                        print(f"  Removed {len(archived_lines)} lines from {log_file.name}")
                    except Exception as e:
                        print(f"Warning: Failed to update {log_file.name}: {e}")
            except Exception as e:
                print(f"Warning: Failed to write archive file {archive_file}: {e}")
    
    # Archive patch files
    print("\nArchiving patch files...")
    patches_dir = logs_dir.parent / "patches"
    patches_archived_count = 0
    
    if patches_dir.exists() and patches_dir.is_dir():
        # Create patches subdirectory in archive
        patches_archive_dir = archive_dir / "patches"
        patches_archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Process all .patch files in logs/patches directory
        patch_files = list(patches_dir.glob("*.patch"))
        
        for patch_file in patch_files:
            if not patch_file.is_file():
                continue
            
            # Extract timestamp from patch filename
            patch_timestamp = extract_timestamp_from_patch_filename(patch_file.name)
            if patch_timestamp is None:
                # Skip files without valid timestamp
                continue
            
            # Check if timestamp is within range (inclusive)
            if start_dt <= patch_timestamp <= end_dt:
                try:
                    # Copy patch file to archive
                    dest_patch_file = patches_archive_dir / patch_file.name
                    shutil.copy2(patch_file, dest_patch_file)
                    patches_archived_count += 1
                    
                    # Remove patch file from original location if requested
                    if remove_records:
                        try:
                            patch_file.unlink()
                            print(f"  Removed patch file: {patch_file.name}")
                        except Exception as e:
                            print(f"Warning: Failed to remove patch file {patch_file.name}: {e}")
                except Exception as e:
                    print(f"Warning: Failed to copy patch file {patch_file.name}: {e}")
    else:
        print(f"Warning: Patches directory does not exist: {patches_dir}")
    
    print(f"\nArchive completed:")
    print(f"  Archive directory: {archive_dir}")
    print(f"  Log files archived: {archived_count}")
    print(f"  Total log lines archived: {total_lines_archived}")
    print(f"  Patch files archived: {patches_archived_count}")
    if remove_records:
        print(f"  Records removed from original files: Yes")
    print(f"  Date range: {start_dt} to {end_dt}")
    
    return str(archive_dir)


def remove_logs_by_date_range(
    start_date: str,
    start_time: str,
    end_date: str,
    end_time: str,
    logs_dir: Optional[str] = None
) -> None:
    """
    Remove log records and patch files from logs/logs and logs/patches directories
    based on date and time range (without archiving).
    
    Args:
        start_date: Start date in format YYYY-MM-DD
        start_time: Start time in format HH:MM:SS
        end_date: End date in format YYYY-MM-DD
        end_time: End time in format HH:MM:SS
        logs_dir: Base logs directory (default: logs/logs relative to project root)
    
    Raises:
        ValueError: If date/time format is invalid or start > end
    """
    # Parse datetime objects
    try:
        start_dt = parse_datetime(start_date, start_time)
        end_dt = parse_datetime(end_date, end_time)
    except ValueError as e:
        raise ValueError(f"Invalid date/time format: {e}")
    
    if start_dt > end_dt:
        raise ValueError("Start datetime must be before end datetime")
    
    # Determine logs directory
    if logs_dir is None:
        project_root = Path(__file__).parent.parent.parent
        logs_dir = project_root / "logs" / "logs"
    else:
        logs_dir = Path(logs_dir)
    
    if not logs_dir.exists():
        raise ValueError(f"Logs directory does not exist: {logs_dir}")
    
    # Process all .log files in logs/logs directory
    log_files = list(logs_dir.glob("*.log"))
    
    removed_count = 0
    total_lines_removed = 0
    
    print("Removing log records...")
    for log_file in log_files:
        if not log_file.is_file():
            continue
        
        remaining_lines = []
        removed_lines_count = 0
        
        # Read log file and filter lines by date range
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
            
            for line in all_lines:
                timestamp = extract_timestamp_from_log_line(line)
                if timestamp is None:
                    # If no timestamp found, keep the line
                    remaining_lines.append(line)
                    continue
                
                # Check if timestamp is within range (inclusive)
                if start_dt <= timestamp <= end_dt:
                    removed_lines_count += 1
                else:
                    remaining_lines.append(line)
        except Exception as e:
            print(f"Warning: Failed to read {log_file}: {e}")
            continue
        
        # Write remaining lines back to file
        if removed_lines_count > 0:
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.writelines(remaining_lines)
                removed_count += 1
                total_lines_removed += removed_lines_count
                print(f"Removed {removed_lines_count} lines from {log_file.name}")
            except Exception as e:
                print(f"Warning: Failed to update {log_file.name}: {e}")
    
    # Remove patch files
    print("\nRemoving patch files...")
    patches_dir = logs_dir.parent / "patches"
    patches_removed_count = 0
    
    if patches_dir.exists() and patches_dir.is_dir():
        patch_files = list(patches_dir.glob("*.patch"))
        
        for patch_file in patch_files:
            if not patch_file.is_file():
                continue
            
            # Extract timestamp from patch filename
            patch_timestamp = extract_timestamp_from_patch_filename(patch_file.name)
            if patch_timestamp is None:
                continue
            
            # Check if timestamp is within range (inclusive)
            if start_dt <= patch_timestamp <= end_dt:
                try:
                    patch_file.unlink()
                    patches_removed_count += 1
                    print(f"Removed patch file: {patch_file.name}")
                except Exception as e:
                    print(f"Warning: Failed to remove patch file {patch_file.name}: {e}")
    else:
        print(f"Warning: Patches directory does not exist: {patches_dir}")
    
    print(f"\nRemoval completed:")
    print(f"  Log files modified: {removed_count}")
    print(f"  Total log lines removed: {total_lines_removed}")
    print(f"  Patch files removed: {patches_removed_count}")
    print(f"  Date range: {start_dt} to {end_dt}")


def validate_date(date_str: str) -> bool:
    """
    Validate date string format (YYYY-MM-DD).
    
    Args:
        date_str: Date string to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_time(time_str: str) -> bool:
    """
    Validate time string format (HH:MM:SS).
    
    Args:
        time_str: Time string to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        datetime.strptime(time_str, "%H:%M:%S")
        return True
    except ValueError:
        return False


def validate_year(year_str: str) -> bool:
    """Validate year (should be a positive integer)."""
    try:
        year = int(year_str)
        return 1900 <= year <= 9999
    except ValueError:
        return False


def validate_month(month_str: str) -> bool:
    """Validate month (1-12)."""
    try:
        month = int(month_str)
        return 1 <= month <= 12
    except ValueError:
        return False


def validate_day(day_str: str, year: int, month: int) -> bool:
    """Validate day based on year and month."""
    try:
        day = int(day_str)
        # Check if the date is valid
        datetime(year, month, day)
        return True
    except ValueError:
        return False


def validate_hour(hour_str: str) -> bool:
    """Validate hour (0-23)."""
    try:
        hour = int(hour_str)
        return 0 <= hour <= 23
    except ValueError:
        return False


def validate_minute(minute_str: str) -> bool:
    """Validate minute (0-59)."""
    try:
        minute = int(minute_str)
        return 0 <= minute <= 59
    except ValueError:
        return False


def validate_second(second_str: str) -> bool:
    """Validate second (0-59)."""
    try:
        second = int(second_str)
        return 0 <= second <= 59
    except ValueError:
        return False


def find_earliest_log_timestamp(logs_dir: Optional[str] = None) -> Optional[datetime]:
    """
    Scan all log files and find the earliest timestamp.
    
    Args:
        logs_dir: Base logs directory (default: logs/logs relative to project root)
    
    Returns:
        Earliest datetime found, or None if no valid timestamps found
    """
    # Determine logs directory
    if logs_dir is None:
        project_root = Path(__file__).parent.parent.parent
        logs_dir = project_root / "logs" / "logs"
    else:
        logs_dir = Path(logs_dir)
    
    if not logs_dir.exists():
        return None
    
    earliest_timestamp = None
    
    # Process all .log files in logs/logs directory
    log_files = list(logs_dir.glob("*.log"))
    
    for log_file in log_files:
        if not log_file.is_file():
            continue
        
        # Read log file and find earliest timestamp
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    timestamp = extract_timestamp_from_log_line(line)
                    if timestamp is not None:
                        if earliest_timestamp is None or timestamp < earliest_timestamp:
                            earliest_timestamp = timestamp
        except Exception:
            # Skip files that can't be read
            continue
    
    return earliest_timestamp


def prompt_date(prompt_text: str, default_dt: Optional[datetime] = None) -> str:
    """
    Prompt user for a date by asking for year, month, and day separately.
    
    Args:
        prompt_text: Prompt message to display
        default_dt: Default datetime to use if user presses Enter
    
    Returns:
        Valid date string in format YYYY-MM-DD
    """
    print(f"{prompt_text}:")
    
    # Set default values if provided
    default_year = default_dt.year if default_dt else None
    default_month = default_dt.month if default_dt else None
    default_day = default_dt.day if default_dt else None
    
    # Prompt for year
    while True:
        default_hint = f" (default: {default_year})" if default_year else ""
        year_input = input(f"  Year (YYYY, e.g., 2025){default_hint}: ").strip()
        if not year_input and default_year:
            year = default_year
            break
        elif validate_year(year_input):
            year = int(year_input)
            break
        else:
            print("  Error: Invalid year format. Please enter a 4-digit number, e.g., 2025")
    
    # Prompt for month
    while True:
        default_hint = f" (default: {default_month})" if default_month else ""
        month_input = input(f"  Month (MM, 1-12, e.g., 12){default_hint}: ").strip()
        if not month_input and default_month:
            month = default_month
            break
        elif validate_month(month_input):
            month = int(month_input)
            break
        else:
            print("  Error: Invalid month format. Please enter a number between 1-12, e.g., 12")
    
    # Prompt for day
    while True:
        default_hint = f" (default: {default_day})" if default_day else ""
        day_input = input(f"  Day (DD, e.g., 10){default_hint}: ").strip()
        if not day_input and default_day:
            # Validate that default day is still valid for the selected year/month
            if validate_day(str(default_day), year, month):
                day = default_day
                break
            else:
                # Default day is invalid for selected year/month, ask for input
                print(f"  Note: Default day {default_day} is invalid for {year}-{month:02d}, please enter a valid day")
                continue
        if validate_day(day_input, year, month):
            day = int(day_input)
            break
        else:
            print(f"  Error: Invalid day format or value. Please check valid day range for {year}-{month:02d}")
    
    return f"{year}-{month:02d}-{day:02d}"


def prompt_time(prompt_text: str, default_dt: Optional[datetime] = None) -> str:
    """
    Prompt user for a time by asking for hour, minute, and second separately.
    
    Args:
        prompt_text: Prompt message to display
        default_dt: Default datetime to use if user presses Enter
    
    Returns:
        Valid time string in format HH:MM:SS
    """
    print(f"{prompt_text}:")
    
    # Set default values if provided
    default_hour = default_dt.hour if default_dt else None
    default_minute = default_dt.minute if default_dt else None
    default_second = default_dt.second if default_dt else None
    
    # Prompt for hour
    while True:
        default_hint = f" (default: {default_hour})" if default_hour is not None else ""
        hour_input = input(f"  Hour (HH, 0-23, e.g., 23){default_hint}: ").strip()
        if not hour_input and default_hour is not None:
            hour = default_hour
            break
        elif validate_hour(hour_input):
            hour = int(hour_input)
            break
        else:
            print("  Error: Invalid hour format. Please enter a number between 0-23, e.g., 23")
    
    # Prompt for minute
    while True:
        default_hint = f" (default: {default_minute})" if default_minute is not None else ""
        minute_input = input(f"  Minute (MM, 0-59, e.g., 50){default_hint}: ").strip()
        if not minute_input and default_minute is not None:
            minute = default_minute
            break
        elif validate_minute(minute_input):
            minute = int(minute_input)
            break
        else:
            print("  Error: Invalid minute format. Please enter a number between 0-59, e.g., 50")
    
    # Prompt for second
    while True:
        default_hint = f" (default: {default_second})" if default_second is not None else ""
        second_input = input(f"  Second (SS, 0-59, e.g., 00){default_hint}: ").strip()
        if not second_input and default_second is not None:
            second = default_second
            break
        elif validate_second(second_input):
            second = int(second_input)
            break
        else:
            print("  Error: Invalid second format. Please enter a number between 0-59, e.g., 00")
    
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def main():
    """
    Interactive command-line interface for archiving and removing logs.
    Prompts user for operation mode and start/end date/time ranges.
    """
    import sys
    
    print("=" * 60)
    print("Log Archive Tool")
    print("=" * 60)
    print()
    print("Select operation:")
    print("  1. Archive and remove records")
    print("  2. Archive without removing records")
    print("  3. Remove records only (no archive)")
    print()
    
    # Prompt for operation mode
    while True:
        mode_input = input("Enter operation number (1-3): ").strip()
        if mode_input in ['1', '2', '3']:
            mode = int(mode_input)
            break
        else:
            print("Error: Please enter 1, 2, or 3")
    
    print()
    
    # Find earliest log timestamp to use as default
    print("Scanning log files to find the earliest timestamp...")
    earliest_dt = find_earliest_log_timestamp()
    
    if earliest_dt:
        print(f"Earliest log timestamp detected: {earliest_dt}")
        print("(Press Enter to use this as the default value)")
    else:
        print("Warning: No valid log timestamps found")
    print()
    
    # Prompt for start date and time
    print("Enter start date and time:")
    start_date = prompt_date("Start date", earliest_dt)
    start_time = prompt_time("Start time", earliest_dt)
    
    print()
    # Use current datetime as default for end date and time
    current_dt = datetime.now()
    print("Enter end date and time:")
    print(f"(Press Enter to use current time as default: {current_dt.strftime('%Y-%m-%d %H:%M:%S')})")
    end_date = prompt_date("End date", current_dt)
    end_time = prompt_time("End time", current_dt)
    
    # Validate that start datetime is before end datetime
    try:
        start_dt = parse_datetime(start_date, start_time)
        end_dt = parse_datetime(end_date, end_time)
        
        if start_dt > end_dt:
            print(f"\nError: Start time ({start_dt}) must be before end time ({end_dt})")
            print("Please rerun the program and enter a valid time range.")
            sys.exit(1)
        
        print()
        print(f"Time range: {start_dt} to {end_dt}")
        
        # Prompt for optional comment
        print()
        comment_input = input("Enter optional comment for archive directory name (press Enter to skip): ").strip()
        comment = comment_input if comment_input else None
        
        # Execute selected operation
        if mode == 1:
            print("Starting archive and removal...")
            print()
            archive_dir = archive_logs_by_date_range(start_date, start_time, end_date, end_time, remove_records=True, comment=comment)
            print(f"\nSuccess! Logs archived and removed. Archive location: {archive_dir}")
        elif mode == 2:
            print("Starting archive (without removal)...")
            print()
            archive_dir = archive_logs_by_date_range(start_date, start_time, end_date, end_time, remove_records=False, comment=comment)
            print(f"\nSuccess! Logs archived. Archive location: {archive_dir}")
        elif mode == 3:
            print("Starting removal only...")
            print()
            remove_logs_by_date_range(start_date, start_time, end_date, end_time)
            print(f"\nSuccess! Records removed.")
        
    except ValueError as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

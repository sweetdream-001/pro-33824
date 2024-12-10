"""Check if a file is a valid JSON file.

Usage:
python json_check.py [JSON file path]

Example:
python json_check.py multi_lang.json
"""
import argparse
import json
import sys
import os

def check_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            json.load(file)
            return True
    except FileNotFoundError:
        print(file_path, "is not found.")
        return False
    except json.JSONDecodeError:
        print(file_path, "is not a valid JSON file.")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Check if a file is a valid JSON file.")
    parser.add_argument("file_path", help="JSON file path")
    args = parser.parse_args()
    script_name = os.path.basename(__file__)
    file_name = os.path.basename(args.file_path)

    if not check_json_file(args.file_path):
        print(args.file_path, script_name, "FAIL")
        sys.exit(1)

    print(script_name, file_name, "PASS")

if __name__ == "__main__":
    main()

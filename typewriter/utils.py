import os
from pathlib import Path
from typing import List, Optional, Union

from bs4 import BeautifulSoup


def parse_directory_and_append_to_file(directory_path: Union[str, Path], output_file_path: Optional[str]) -> None:
    """
    Parses HTML files in a directory and its subdirectories, appending the cleaned text to a large text file.

    Args:
    directory_path (str): The path to the directory containing HTML files.
    output_file_path (str): The path to the output text file where the cleaned text will be appended.
    """
    directory_path = directory_path if isinstance(directory_path, Path) else Path(directory_path)
    output_file_path = output_file_path if output_file_path else 'output.txt'
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as html_file:
                        soup = BeautifulSoup(html_file, 'html.parser')
                        text = soup.get_text(separator=' ', strip=True)
                        with open(output_file_path, 'a', encoding='utf-8') as output_file:
                            output_file.write(text + '\n\n')
                except Exception as e:
                    print(f"An error occurred while processing {file_path}: {e}")

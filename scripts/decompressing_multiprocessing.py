#!/usr/bin/env python
#modified from https://github.com/Watchful1/PushshiftDumps/blob/master/scripts/to_csv.py
from multiprocessing import Process
import zstandard
import os
import json
import csv
import logging.handlers
from natsort import natsorted
from tqdm import tqdm
import threading
lock = threading.Lock()
# Configure logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

def read_and_decode(reader, chunk_size, max_window_size, previous_chunk=None, bytes_read=0):
    chunk = reader.read(chunk_size)
    bytes_read += chunk_size
    if previous_chunk is not None:
        chunk = previous_chunk + chunk
    try:
        return chunk.decode()
    except UnicodeDecodeError:
        if bytes_read > max_window_size:
            raise UnicodeError(f"Unable to decode frame after reading {bytes_read:,} bytes")
        return read_and_decode(reader, chunk_size, max_window_size, chunk, bytes_read)

def read_lines_zst(file_name):
    with open(file_name, 'rb') as file_handle:
        buffer = ''
        reader = zstandard.ZstdDecompressor(max_window_size=2**31).stream_reader(file_handle)
        while True:
            chunk = read_and_decode(reader, 2**27, (2**29) * 2)
            if not chunk:
                break
            lines = (buffer + chunk).split("\n")
            for line in lines[:-1]:
                yield line, file_handle.tell()
            buffer = lines[-1]
        reader.close()

def run(input_file_path):

        output_file_path = f"./RC/{os.path.basename(input_file_path)}_test_again_multi.csv"
        fields = ['created_utc', 'author', 'subreddit', 'body', 'parent_id', 'subreddit_id', 'id']
        file_size = os.stat(input_file_path).st_size
        file_lines, bad_lines = 0, 0
        created = None
      
        with open(output_file_path, "w", encoding='utf-8', newline="") as output_file:
            
            writer = csv.writer(output_file)
            writer.writerow(fields)
            
            for line, file_bytes_processed in read_lines_zst(input_file_path):
                try:
                    obj = json.loads(line)
                    output_obj = []
                    for field in fields:
                        if field == "created_utc":
                            value = datetime.fromtimestamp(int(obj['created_utc'])).strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            value = obj.get(field, "")
                        output_obj.append(str(value).encode("utf-8", errors='replace').decode())
                    writer.writerow(output_obj)
                    created = datetime.utcfromtimestamp(int(obj['created_utc']))
                except json.JSONDecodeError as err:
                    bad_lines += 1
                    log.error(f"Error decoding JSON: {err}")
                    log.error(line)
                    continue
                except KeyError as err:
                    log.error(f"Object has no key: {err}")
                    log.error(line)
                    continue
                except Exception as err:
                    log.error(f"Error processing line: {err}")
                    log.error(line)
                    continue
    
                file_lines += 1
                if file_lines % 100000 == 0:
                    log.info(f"{created.strftime('%Y-%m-%d %H:%M:%S')} : {file_lines:,} : {bad_lines:,} : {(file_bytes_processed / file_size) * 100:.0f}%")
    
        log.info(f"Complete : {file_lines:,} : {bad_lines:,}")

# protect the entry point
if __name__ == '__main__':
   
    path = '/mnt/data/reddit/reddit/comments/'
    files = natsorted(os.listdir(path))
    year = 2020
    files = [file for file in files if int(file.replace('RC', '').replace('-', '').replace('_', '')[:4]) == year]
    print(files)

    processes = [Process(target=run, args=(os.path.join(path, file),)) for file in tqdm(files)]
    
    # start all processes
    for process in processes:
        process.start()
    
    # wait for all processes to complete
    for process in processes:
        process.join()

    print('Decompress finished!', flush=True)
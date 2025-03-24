import socket
import sys
import os
import argparse
import re
import time

BUFFER_SIZE = 1000000

def get_cache_age(headers):
    for line in headers:
        if line.lower().startswith("cache-control"):
            match = re.search(r'max-age=(\d+)', line)
            if match:
                return int(match.group(1))
    return None

def is_cache_valid(cache_location, max_age):
    if not os.path.exists(cache_location):
        return False
    file_age = time.time() - os.path.getmtime(cache_location)
    return file_age <= max_age

parser = argparse.ArgumentParser()
parser.add_argument('hostname', help='IP Address Of Proxy Server')
parser.add_argument('port', type=int, help='Port number of the proxy server')
args = parser.parse_args()
proxyHost = args.hostname
proxyPort = args.port

try:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((proxyHost, proxyPort))
    server_socket.listen(5)
    print('Proxy server started and listening on {}:{}'.format(proxyHost, proxyPort))
except Exception as e:
    print(f'Failed to start server: {e}')
    sys.exit()

while True:
    print('Waiting for connection...')
    try:
        client_socket, client_addr = server_socket.accept()
        print('Connected to Proxy server')
    except:
        continue

    try:
        request_bytes = client_socket.recv(BUFFER_SIZE)
        request = request_bytes.decode('utf-8')
    except:
        client_socket.close()
        continue

    request_parts = request.split('\r\n')
    request_line = request_parts[0].split()
    method, URI, version = request_line

    URI = re.sub('^(/?)http(s?)://', '', URI, count=1)
    URI = URI.replace('/..', '')
    resource_parts = URI.split('/', 1)
    hostname = resource_parts[0]
    resource = '/' + resource_parts[1] if len(resource_parts) > 1 else '/'

    cache_location = f'./cache/{hostname}{resource.replace("/", "_")}'
    if cache_location.endswith('/'):
        cache_location += 'default'

    print(f'Checking cache for {cache_location}')

    try:
        with open(cache_location, "rb") as cache_file:
            headers = cache_file.readline().decode().split('\r\n')
            max_age = get_cache_age(headers)
            if max_age and is_cache_valid(cache_location, max_age):
                print('Cache hit! Serving from cache')
                client_socket.sendall(cache_file.read())
                client_socket.close()
                continue
    except:
        pass

    print(f'Cache miss. Connecting to {hostname}')
    try:
        origin_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = socket.gethostbyname(hostname)
        origin_socket.connect((address, 80))
        print('Connected to Origin Server')
    except:
        client_socket.close()
        continue

    request_to_origin = f"{method} {resource} {version}\r\nHost: {hostname}\r\nConnection: close\r\n\r\n"
    origin_socket.sendall(request_to_origin.encode())
    
    response = b""
    while True:
        data = origin_socket.recv(BUFFER_SIZE)
        if not data:
            break
        response += data

    response_str = response.decode(errors='ignore')
    if "301 Moved Permanently" in response_str or "302 Found" in response_str:
        location_match = re.search(r'Location: (.+?)\r\n', response_str)
        if location_match:
            new_location = location_match.group(1)
            print(f'Redirected to {new_location}')
            client_socket.sendall(f"HTTP/1.1 302 Found\r\nLocation: {new_location}\r\n\r\n".encode())
            client_socket.close()
            continue

    client_socket.sendall(response)
    os.makedirs(os.path.dirname(cache_location), exist_ok=True)
    with open(cache_location, 'wb') as cache_file:
        cache_file.write(response)

    print('Saved to cache and sent to client')
    origin_socket.close()
    client_socket.close()

# Include the libraries for socket and system calls
import socket
import sys
import os
import argparse
import re
import time

# 1MB buffer size
BUFFER_SIZE = 1000000

# Get the IP address and Port number to use for this web proxy server
parser = argparse.ArgumentParser()
parser.add_argument('hostname', help='the IP Address Of Proxy Server')
parser.add_argument('port', help='the port number of the proxy server')
args = parser.parse_args()
proxyHost = args.hostname
proxyPort = int(args.port)

# Create a server socket, bind it to a port and start listening
try:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print('Created socket')
except:
    print('Failed to create socket')
    sys.exit()

try:
    server_socket.bind((proxyHost, proxyPort))
    print('Port is bound')
except:
    print('Port is already in use')
    sys.exit()

try:
    server_socket.listen(5)
    print('Listening to socket')
except:
    print('Failed to listen')
    sys.exit()

# Cache expiration handling
def is_cache_valid(cache_location):
    try:
        with open(cache_location, 'r') as cacheFile:
            headers = cacheFile.readline()
            match = re.search(r'max-age=(\d+)', headers)
            if match:
                max_age = int(match.group(1))
                timestamp = float(cacheFile.readline().strip())
                if time.time() - timestamp > max_age:
                    return False
            return True
    except:
        return False

# continuously accept connections
while True:
    print('Waiting for connection...')
    clientSocket = None
    try:
        clientSocket, clientAddr = server_socket.accept()
        print('Received a connection')
    except:
        print('Failed to accept connection')
        sys.exit()

    try:
        message_bytes = clientSocket.recv(BUFFER_SIZE)
    except:
        print('Failed to receive data from client')
        clientSocket.close()
        continue

    message = message_bytes.decode('utf-8')
    print('Received request:\n< ' + message)
    
    requestParts = message.split() 
    method, URI, version = requestParts[:3]

    print(f'Method: {method}\nURI: {URI}\nVersion: {version}\n')

    URI = re.sub('^(/?)http(s?)://', '', URI, count=1).replace('/..', '')
    resourceParts = URI.split('/', 1)
    hostname, resource = resourceParts[0], '/' + resourceParts[1] if len(resourceParts) == 2 else '/'

    print(f'Requested Resource: {resource}')

    cacheLocation = f'./{hostname}{resource.replace("/", "_")}'
    print(f'Cache location: {cacheLocation}')

    if os.path.isfile(cacheLocation) and is_cache_valid(cacheLocation):
        try:
            with open(cacheLocation, 'rb') as cacheFile:
                cacheData = cacheFile.read()
                clientSocket.sendall(cacheData)
                print(f'Sent from cache: {cacheLocation}')
        except:
            print('Failed to read from cache')
    else:
        try:
            originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            address = socket.gethostbyname(hostname)
            originServerSocket.connect((address, 80))
            print(f'Connected to origin server: {hostname}')
            
            request = f"{method} {resource} {version}\r\nHost: {hostname}\r\nConnection: close\r\n\r\n"
            originServerSocket.sendall(request.encode())
            print(f'Forwarded request to origin server')
            
            originResponse = b""
            while True:
                data = originServerSocket.recv(BUFFER_SIZE)
                if not data:
                    break
                originResponse += data
            
            clientSocket.sendall(originResponse)
            print('Sent origin response to client')
            
            if b'301 Moved Permanently' in originResponse or b'302 Found' in originResponse:
                print('Handling redirect, not caching')
            else:
                cacheDir = os.path.dirname(cacheLocation)
                os.makedirs(cacheDir, exist_ok=True)
                with open(cacheLocation, 'wb') as cacheFile:
                    cacheFile.write(originResponse)
                print('Cached response')
            
            originServerSocket.close()
        except Exception as e:
            print(f'Error contacting origin server: {e}')
    
    try:
        clientSocket.close()
    except:
        print('Failed to close client socket')
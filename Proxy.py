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
parser.add_argument('port', type=int, help='the port number of the proxy server')
args = parser.parse_args()
proxyHost = args.hostname
proxyPort = args.port

# Create a server socket, bind it to a port and start listening
try:
    # Create a server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  
    print ('Created socket')
except:
    print ('Failed to create socket')
    sys.exit()

try:
    # Bind the the server socket to a host and port
    server_socket.bind((proxyHost, proxyPort))
    print ('Port is bound')
except:
    print('Port is already in use')
    sys.exit()

try:
    # Listen on the server socket
    server_socket.listen(5) 
    print ('Listening to socket')
except:
    print ('Failed to listen')
    sys.exit()

# continuously accept connections
while True:
    print ('Waiting for connection...')
    clientSocket = None

    # Accept connection from client and store in the clientSocket
    try:
        clientSocket, clientAddr = server_socket.accept()
        print ('Received a connection')
    except:
        print ('Failed to accept connection')
        sys.exit()

    # Get HTTP request from client
    # and store it in the variable: message_bytes
    try:
        message_bytes = clientSocket.recv(BUFFER_SIZE)
    except:
        print ('Failed to receive data from client')
        clientSocket.close()
        continue

    message = message_bytes.decode('utf-8')
    print ('Received request:')
    print ('< ' + message)

    # Extract the method, URI and version of the HTTP client request 
    requestParts = message.split()
    method = requestParts[0]
    URI = requestParts[1]
    version = requestParts[2]

    print ('Method:\t\t' + method)
    print ('URI:\t\t' + URI)
    print ('Version:\t' + version)
    print ('')

    # Get the requested resource from URI
    # Remove http protocol from the URI
    URI = re.sub('^(/?)http(s?)://', '', URI, count=1)

    # Remove parent directory changes - security
    URI = URI.replace('/..', '')

    # Split hostname from resource name
    resourceParts = URI.split('/', 1)
    hostname = resourceParts[0]
    resource = '/'

    if len(resourceParts) == 2:
        # Resource is absolute URI with hostname and resource
        resource = resource + resourceParts[1]

    print ('Requested Resource:\t' + resource)

    # Check if resource is in cache
    try:
        cacheLocation = './' + hostname + resource
        if cacheLocation.endswith('/'):
            cacheLocation = cacheLocation + 'default'

        print ('Cache location:\t\t' + cacheLocation)

        fileExists = os.path.isfile(cacheLocation)

        # If file exists in the cache, serve it directly
        if fileExists:
            cacheFile = open(cacheLocation, "rb")
            cacheData = cacheFile.read()
            print ('Cache hit! Loading from cache file: ' + cacheLocation)
            clientSocket.sendall(cacheData)
            cacheFile.close()
            print ('Sent to the client from cache')
        else:
            print('Cache miss. Requesting from origin server...')
            # Proceed to Step 7 for fetching from the origin server
    except Exception as e:
        print(f"Error: {e}")
        print('Error accessing cache or processing request')
        # You can either proceed to Step 7 here or handle errors accordingly

    # Cache miss – Fetch resource from origin server
    originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    address = socket.gethostbyname(hostname)
    originServerSocket.connect((address, 80))

    # Create HTTP request to origin server
    originServerRequest = f'{method} {resource} {version}\r\n'
    originServerRequestHeader = f'Host: {hostname}\r\nConnection: close\r\n'

    # Construct the request to send to the origin server
    request = originServerRequest + originServerRequestHeader + '\r\n'

    # Send the request to the origin server
    originServerSocket.sendall(request.encode())

    # Receive the response from the origin server
    originResponse = b""
    while True:
        data = originServerSocket.recv(BUFFER_SIZE)
        if not data:
            break
        originResponse += data

    # Send the response back to the client
    clientSocket.sendall(originResponse)

    # Check for Redirect (301 or 302) and follow Location header if needed
    if b"301 Moved Permanently" in originResponse or b"302 Found" in originResponse:
        location = re.search(r"Location: (http[s]?://[^\r\n]+)", originResponse.decode('utf-8'))
        if location:
            new_url = location.group(1)
            print(f"Redirected to: {new_url}")
            # Follow the redirect (Recursive request for new URL)

    # Handle Cache-Control: max-age for caching the response
    max_age_match = re.search(r"Cache-Control: max-age=(\d+)", originResponse.decode('utf-8'))
    if max_age_match:
        max_age = int(max_age_match.group(1))
        print(f"Cache max-age found: {max_age} seconds")
        # Cache the file with expiration time

    # Cache the response if needed
    cacheDir, file = os.path.split(cacheLocation)
    if not os.path.exists(cacheDir):
        os.makedirs(cacheDir)

    with open(cacheLocation, 'wb') as cacheFile:
        cacheFile.write(originResponse)
    print ('cache file closed')

    # finished communicating with origin server - shutdown socket writes
    print ('origin response received. Closing sockets')
    originServerSocket.close()

    clientSocket.shutdown(socket.SHUT_WR)
    print ('client socket shutdown for writing')

    try:
        clientSocket.close()
    except:
        print ('Failed to close client socket')

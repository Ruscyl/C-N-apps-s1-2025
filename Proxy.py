import socket
import os
import re
import time

def get_cache_location(url):
    filename = url.replace('http://', '').replace('/', '_')
    return os.path.join("cache", filename)

def fetch_from_origin(server_address, port, request):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as originSocket:
        originSocket.connect((server_address, port))
        originSocket.sendall(request)
        response = b""
        while True:
            data = originSocket.recv(4096)
            if not data:
                break
            response += data
    return response

def handle_client(clientSocket):
    request = clientSocket.recv(4096)
    first_line = request.split(b'\r\n')[0].decode()
    url = first_line.split()[1]
    cacheLocation = get_cache_location(url)
    
    if os.path.exists(cacheLocation):
        print("Cache hit: Serving from cache.")
        with open(cacheLocation, 'rb') as file:
            cachedResponse = file.read()
        clientSocket.sendall(cachedResponse)
    else:
        print("Cache miss: Fetching from origin server.")
        server_address = url.split('/')[2]  # Extract host
        port = 80
        originResponse = fetch_from_origin(server_address, port, request)
        
        status_line = originResponse.split(b'\r\n')[0]
        if b"404 Not Found" in status_line:
            print("Received 404 from origin server.")
            clientSocket.sendall(originResponse)
        elif b"301 Moved Permanently" in status_line or b"302 Found" in status_line:
            headers = originResponse.split(b'\r\n\r\n')[0].decode()
            location_match = re.search(r'Location: (.+)', headers)
            if location_match:
                new_url = location_match.group(1).strip()
                print(f"Redirecting to: {new_url}")
                clientSocket.sendall(f"HTTP/1.1 302 Found\r\nLocation: {new_url}\r\n\r\n".encode())
        else:
            headers = originResponse.split(b'\r\n\r\n')[0].decode()
            cache_control_match = re.search(r'Cache-Control: max-age=(\d+)', headers)
            if cache_control_match:
                max_age = int(cache_control_match.group(1))
                if max_age == 0:
                    print("Cache expired, fetching from origin server again.")
                    os.remove(cacheLocation)  # Delete the cached file if expired
            
            with open(cacheLocation, 'wb') as cacheFile:
                cacheFile.write(originResponse)
            print("Response cached.")
            clientSocket.sendall(originResponse)
    
    clientSocket.close()

def start_proxy(port):
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.bind(('0.0.0.0', port))
    serverSocket.listen(5)
    print(f"Proxy server running on port {port}...")
    
    while True:
        clientSocket, addr = serverSocket.accept()
        print(f"Connection received from {addr}")
        handle_client(clientSocket)

if __name__ == "__main__":
    start_proxy(8080)

import socket
import threading

# Store all connected peer sockets
peer_sockets = []
# A lock for synchronizing access to peer_sockets list
# This is important because multiple threads (handle_peer, send_messages) might modify it
sockets_lock = threading.Lock()

# --------- Server: Listen for incoming connections ---------
def listen_for_peers(port):
    # print(f"DEBUG: listen_for_peers thread started for port {port}")
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow address reuse immediately, helpful for quick restarts during testing
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('localhost', port))
        server.listen(5) # Allow up to 5 queued connections
        print(f"✅ Listening for peers on port {port}...")

        while True:
            # print(f"DEBUG: listen_for_peers on port {port} waiting for accept()")
            try:
                client_socket, client_address = server.accept()
                print(f"📥 Connection from {client_address}")

                with sockets_lock: # Safely add to the list
                    if client_socket not in peer_sockets:
                        peer_sockets.append(client_socket)

                # Start a new thread to handle messages from this specific client
                # daemon=True means these threads will close when the main program exits
                threading.Thread(target=handle_peer, args=(client_socket, client_address), daemon=True).start()
            except OSError as e: # Handle cases like server socket being closed
                print(f"INFO: Server socket on port {port} likely closed. Listener thread exiting. Error: {e}")
                break
            except Exception as e:
                print(f"ERROR in listen_for_peers accept loop for port {port}: {e}")
                # Decide if you want to break or continue listening after an error
                # For robustness, you might want to continue if it's a transient error with one connection attempt
    except Exception as e:
        print(f"CRITICAL ERROR setting up listener on port {port}: {e}")

# --------- Handle individual peer connections (runs in a thread per peer) ---------
def handle_peer(sock, address): # Added address for better logging
    # print(f"INFO: Thread started for handling peer: {address}")
    is_connected = True
    while is_connected:
        try:
            data = sock.recv(1024)  # Receive data (blocking call within this thread)
            if not data:
                print(f"INFO: Connection closed by {address}.")
                is_connected = False # Signal to exit loop
            else:
                print(f"\n📨 Received from {address}: {data.decode()}")
                # If you want to re-broadcast this message to other peers (like a chat room):
                # broadcast_message(data, sock) # You'd need to implement broadcast_message
        except ConnectionResetError:
            print(f"INFO: Connection reset by {address}.")
            is_connected = False
        except socket.timeout:
            print(f"INFO: Socket timeout for {address}. Still connected, but no data.")
            # You might want to implement a keep-alive or decide to close after too many timeouts
            continue # Continue waiting for data
        except socket.error as e: # Catch other socket specific errors
            print(f"SOCKET ERROR with {address}: {e}")
            is_connected = False
        except Exception as e:
            print(f"GENERAL ERROR with {address}: {e}")
            is_connected = False

    # print(f"INFO: Thread for {address} is ending.")
    with sockets_lock: # Safely remove from the list
        if sock in peer_sockets:
            peer_sockets.remove(sock)
            # print(f"INFO: Socket for {address} removed from peer_sockets.")
    try:
        sock.close()
    except Exception as e:
        print(f"ERROR closing socket for {address}: {e}")

# --------- Client: Connect to another peer's server ---------
def connect_to_peer(ip, port):
    try:
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.connect((ip, port))
        print(f"🔗 Connected to peer at {ip}:{port}")
        with sockets_lock: # Safely add to the list
            if peer_socket not in peer_sockets:
                peer_sockets.append(peer_socket)
        # Also start a handler thread for this outgoing connection to receive messages
        threading.Thread(target=handle_peer, args=(peer_socket, (ip, port)), daemon=True).start()
        return peer_socket
    except ConnectionRefusedError:
        print(f"❌ Connection refused by {ip}:{port}. Is the other peer listening?")
    except socket.timeout:
        print(f"❌ Connection to {ip}:{port} timed out.")
    except Exception as e:
        print(f"❌ Error connecting to {ip}:{port}: {e}")
    return None

# --------- Main thread: Send messages from user input ---------
def send_messages():
    # print("DEBUG: send_messages function called")
    try:
        while True:
            msg = input("💬 You: ")
            if msg.lower() == "exit":
                print("👋 Closing all connections...")
                with sockets_lock: # Get a consistent list of sockets to close
                    sockets_to_close = list(peer_sockets) # Iterate over a copy
                    peer_sockets.clear() # Clear the main list

                for s in sockets_to_close:
                    try:
                        # Optionally send a "bye" message before closing
                        # s.send("EXITING_CHAT".encode())
                        s.close()
                    except Exception as e_close:
                        print(f"Error while closing a socket: {e_close}")
                break # Exit the send_messages loop, and thus the program

            with sockets_lock: # Get a consistent list for sending
                current_connections = list(peer_sockets) # Iterate over a copy

            if not current_connections:
                print("INFO: No connected peers to send message to.")
                continue

            # print(f"DEBUG: Sending to sockets: {current_connections}")
            for s in current_connections:
                try:
                    s.send(msg.encode())
                except socket.error as se:
                    print(f"❌ Socket error sending to a peer: {se}")
                    # This socket might be broken, handle_peer should eventually remove it
                    # Or you can try to remove it here too, carefully with the lock
                except Exception as e_send:
                    print(f"❌ Failed to send to one of the peers: {e_send}")
        # print("DEBUG: Exiting send_messages function")
    except EOFError: # Happens if input stream is closed (e.g. piping input and it ends)
        print("\nINFO: Input stream closed. Exiting.")
    except KeyboardInterrupt: # Handle Ctrl+C gracefully in the input loop
        print("\n👋 Ctrl+C detected. Closing all connections...")
        # Similar closing logic as "exit" command
        with sockets_lock:
            sockets_to_close = list(peer_sockets)
            peer_sockets.clear()
        for s in sockets_to_close:
            try: s.close()
            except: pass
    except Exception as e:
        print(f"CRITICAL ERROR in send_messages: {e}")

# --------- Start the main application ---------
def start_peer():
    print("Peer-to-Peer Chat Application")
    peer_id = input("Which peer instance is this (e.g., 1 or 2, for port selection)? ")

    if peer_id == "1":
        listen_port = 8888
    elif peer_id == "2":
        listen_port = 8889
    # Add more peers or a more generic port input if needed
    # elif peer_id == "3":
    #    listen_port = 8890
    else:
        try:
            listen_port = int(peer_id) # Allow user to enter a port number directly
            if not (1024 <= listen_port <= 65535):
                raise ValueError("Port out of range")
        except ValueError:
            print("Invalid input. Please enter 1, 2, or a valid port number (1024-65535).")
            return

    # Start the listening thread
    listener_thread = threading.Thread(target=listen_for_peers, args=(listen_port,), daemon=True)
    listener_thread.start()

    # Allow some time for the listener to start, though it's usually very fast
    # import time
    # time.sleep(0.1)

    while True:
        connect_choice = input("Do you want to (c)onnect to another peer, (s)end message, or (e)xit? ").lower()
        if connect_choice == 'c':
            address = input("Enter peer address (IP,Port) e.g., 127.0.0.1,8888: ")
            try:
                ip, port_str = address.strip().split(',')
                port_to_connect = int(port_str.strip())
                connect_to_peer(ip.strip(), port_to_connect)
            except ValueError:
                print("❌ Invalid address format. Use IP,Port (e.g., 127.0.0.1,8888)")
            except Exception as e:
                print(f"❌ Error parsing address or connecting: {e}")
        elif connect_choice == 's': # This will fall through to send_messages if no explicit send option
            print("Enter your message below. Type 'exit' on a new line to close the application.")
            send_messages() # This will now block until 'exit' or Ctrl+C
            break # Exit start_peer loop after send_messages finishes
        elif connect_choice == 'e':
            print("👋 Exiting application...")
            # Gracefully close existing connections from send_messages logic if it were running
            # For simplicity here, we just trigger the exit path of send_messages
            # A more robust way would be to signal all threads to stop.
            # For now, let send_messages handle cleanup if it's called.
            # If send_messages wasn't the last thing, ensure cleanup:
            with sockets_lock:
                sockets_to_close = list(peer_sockets)
                peer_sockets.clear()
            for s_sock in sockets_to_close:
                try: s_sock.close()
                except: pass
            break # Exit the start_peer loop
        else:
            # If not connecting or exiting, assume user wants to send messages
            # This makes the UX a bit simpler after initial setup.
            # Or, you could print an "Invalid choice" message and loop again.
            print("Enter your message below. Type 'exit' on a new line to close the application.")
            send_messages()
            break # Exit start_peer loop after send_messages finishes


if __name__ == "__main__":
    start_peer()
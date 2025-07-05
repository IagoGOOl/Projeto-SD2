import socket
import threading

# Armazena todos os arquivos compartilhados por IP
all_files = {}

# Porta usada pelo servidor
SERVER_PORT = 1234

def handle_client(client_socket, client_address):
    ip_address = None

    try:
        while True:
            data = client_socket.recv(1024).decode().strip()
            if not data:
                break

            print(f"Recebido de {client_address}: {data}")
            parts = data.split()

            if parts[0] == "JOIN":
                ip_address = parts[1]
                all_files[ip_address] = []
                client_socket.send(b"CONFIRMJOIN\n")

            elif parts[0] == "CREATEFILE":
                filename = parts[1]
                size = int(parts[2])
                file_info = {"filename": filename, "size": size}
                all_files[ip_address].append(file_info)
                response = f"CONFIRMCREATEFILE {filename}\n"
                client_socket.send(response.encode())

            elif parts[0] == "DELETEFILE":
                filename = parts[1]
                all_files[ip_address] = [
                    f for f in all_files[ip_address] if f["filename"] != filename
                ]
                response = f"CONFIRMDELETEFILE {filename}\n"
                client_socket.send(response.encode())

            elif parts[0] == "LEAVE":
                if ip_address in all_files:
                    del all_files[ip_address]
                client_socket.send(b"CONFIRMLEAVE\n")
                break

            elif parts[0] == "SEARCH":
                if len(parts) < 2:
                    client_socket.send(b"ERROR Missing search pattern\n")
                    return  # ou continue se estiver dentro de um loop

                pattern = parts[1]
                result = []
                for ip, files in all_files.items():
                    for file in files:
                        if pattern in file["filename"]:
                            result.append(
                                f"FILE {file['filename']} {ip} {file['size']}"
                            )
                
                if result:
                    response = '\n'.join(result) + '\n'
                    client_socket.send(response.encode())
                else:
                    client_socket.send(b"NORESULT\n")
    except ConnectionResetError:
        print(f"Conexão com {client_address} perdida.")
    finally:
        if ip_address and ip_address in all_files:
            del all_files[ip_address]
        client_socket.close()
        print(f"Conexão encerrada: {client_address}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', SERVER_PORT))
    server.listen(5)
    print(f"Servidor escutando na porta {SERVER_PORT}...")

    while True:
        client_socket, client_address = server.accept()
        print(f"Nova conexão de {client_address}")
        client_thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_thread.start()

if __name__ == "__main__":
    start_server()


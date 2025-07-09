import os
import socket
import threading
from pathlib import Path

class FileSharingClient:
    def __init__(self, server_host, server_port=1234, client_port=1235, public_dir='public'):
        self.server_host = server_host
        self.server_port = server_port
        self.client_port = client_port
        self.public_dir = public_dir
        self.server_socket = None
        self.client_socket = None
        self.listener_socket = None
        self.running = False
        self.ensure_public_dir()
        
    def ensure_public_dir(self):
        Path(self.public_dir).mkdir(exist_ok=True)
        
    def start(self):
        
        self.connect_to_server()
        
        
        self.start_listener()
        
        try:
            while self.running:
                command = input("Comando (SEARCH <pattern>, LIST, DOWNLOAD <num> <ip>, DELETE <filename>, LEAVE): ").strip()
                
                if command.lower() == 'leave':
                    self.send_command("LEAVE")
                    break
                elif command.lower() == 'list':
                    self.list_local_files()
                elif command.lower().startswith('search'):
                    self.send_command(command)
                elif command.lower().startswith('download'):
                    self.handle_download_command(command)
                elif command.lower().startswith('delete'):
                    self.handle_delete_command(command)
                else:
                    print("Comando inválido")
                    
        except KeyboardInterrupt:
            print("\nEncerrando cliente...")
        finally:
            self.cleanup()
            
    def connect_to_server(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((self.server_host, self.server_port))
            self.running = True
            
            
            local_ip = socket.gethostbyname(socket.gethostname())
            
            
            self.send_command(f"JOIN {local_ip}")
            
            self.send_file_list()
            
        except Exception as e:
            print(f"Erro ao conectar ao servidor: {e}")
            self.running = False
            
    def send_command(self, command):
        try:
            self.server_socket.send(command.encode())
            response = self.server_socket.recv(1024).decode().strip()
            self.handle_server_response(response)
        except Exception as e:
            print(f"Erro ao enviar comando: {e}")
            
    def handle_server_response(self, response):
        if response.startswith("FILE"):
            files = response.split('\n')
            print("\nResultados da busca:")
            for i, file_info in enumerate(files, 1):
                parts = file_info.split()
                if len(parts) >= 4:
                    print(f"{i}. {parts[1]} (Tamanho: {parts[3]} bytes) - IP: {parts[2]}")
        else:
            print(f"Resposta do servidor: {response}")
            
    def send_file_list(self):
        try:
            for file in Path(self.public_dir).iterdir():
                if file.is_file():
                    self.send_command(f"CREATEFILE {file.name} {file.stat().st_size}")
        except Exception as e:
            print(f"Erro ao enviar lista de arquivos: {e}")
            
    def list_local_files(self):
        print("\nArquivos locais na pasta public:")
        for i, file in enumerate(Path(self.public_dir).iterdir(), 1):
            if file.is_file():
                print(f"{i}. {file.name} (Tamanho: {file.stat().st_size} bytes)")
                
    def start_listener(self):
        def listener():
            self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener_socket.bind(('0.0.0.0', self.client_port))
            self.listener_socket.listen(5)
            
            while self.running:
                try:
                    conn, addr = self.listener_socket.accept()
                    threading.Thread(
                        target=self.handle_download_request,
                        args=(conn, addr),
                        daemon=True
                    ).start()
                except:
                    break
                    
        threading.Thread(target=listener, daemon=True).start()
        print(f"Ouvindo conexões de download na porta {self.client_port}")
        
    def handle_download_request(self, conn, addr):
        try:
            data = conn.recv(1024).decode().strip()
            if data.startswith("GET"):
                parts = data.split()
                if len(parts) >= 2:
                    filename = parts[1]
                    file_path = Path(self.public_dir) / filename

                    start = 0
                    end = None  # até o fim do arquivo

                    if len(parts) >= 3:
                        try:
                            start = int(parts[2])
                        except ValueError:
                            start = 0

                    if len(parts) == 4 and parts[3].isdigit():
                        end = int(parts[3])

                    if file_path.is_file():
                        with open(file_path, 'rb') as f:
                            f.seek(start)
                            remaining = end - start if end is not None else None
                            chunk_size = 4096

                            while True:
                                if remaining is not None and remaining <= 0:
                                    break
                                to_read = min(chunk_size, remaining) if remaining else chunk_size
                                data = f.read(to_read)
                                if not data:
                                    break
                                conn.sendall(data)
                                if remaining:
                                    remaining -= len(data)

                        print(f"Arquivo {filename} (offset {start} até {end}) enviado para {addr[0]}")
                    else:
                        conn.send(b"ERROR File not found")
        except Exception as e:
            print(f"Erro ao lidar com download: {e}")
        finally:
            conn.close()
            
    def handle_download_command(self, command):
        parts = command.split()
        if len(parts) < 3:
            print("Uso: download <número do arquivo> <ip> [start] [end]")
            return

        try:
            file_num = int(parts[1])
            ip_address = parts[2]
            start = int(parts[3]) if len(parts) >= 4 else 0
            end = int(parts[4]) if len(parts) >= 5 else None

            self.server_socket.send(b"SEARCH .")
            response = ""
            while True:
                chunk = self.server_socket.recv(4096).decode()
                response += chunk
                if not chunk or chunk.endswith("\n"):
                    break

            files = [line for line in response.split('\n') if line.startswith("FILE")]

            if 1 <= file_num <= len(files):
                selected_file = files[file_num - 1].split()
                filename = selected_file[1]

                save_path = Path(self.public_dir) / filename

                # Detecta tamanho atual (caso exista)
                if save_path.exists():
                    existing_size = save_path.stat().st_size
                    # Se o usuário não forneceu 'start', continua de onde parou
                    if len(parts) < 4:
                        start = existing_size
                    elif start < existing_size:
                        print(f"Parte do arquivo já baixada até o byte {existing_size}.")
                        print("Remova o arquivo se quiser reiniciar o download.")
                        return
                else:
                    existing_size = 0

                # Estabelece a conexão com o outro cliente
                download_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                download_socket.connect((ip_address, self.client_port))

                # Monta comando GET
                if end is not None:
                    get_command = f"GET {filename} {start} {end}"
                else:
                    get_command = f"GET {filename} {start}"

                download_socket.send(get_command.encode())

                # Abre arquivo em modo append binário para continuar o download
                with open(save_path, 'ab') as f:
                    while True:
                        data = download_socket.recv(4096)
                        if not data:
                            break
                        f.write(data)

                print(f"Download de {filename} (offset {start} até {end or 'EOF'}) concluído!")

                # Registra no servidor caso o download tenha sido completo
                file_size = save_path.stat().st_size
                self.send_command(f"CREATEFILE {filename} {file_size}")
            else:
                print("Número de arquivo inválido")

        except Exception as e:
            print(f"Erro ao baixar arquivo: {e}")

    def handle_delete_command(self, command):
        parts = command.split(maxsplit=1)
        if len(parts) != 2:
            print("Uso: delete <nome-do-arquivo>")
            return

        filename = parts[1]
        file_path = Path(self.public_dir) / filename

        if not file_path.is_file():
            print(f"Arquivo '{filename}' não encontrado na pasta '{self.public_dir}'")
            return

        try:
            # Envia comando DELETEFILE ao servidor
            self.send_command(f"DELETEFILE {filename}")

            # Remove o arquivo localmente
            file_path.unlink()
            print(f"Arquivo '{filename}' removido localmente e do servidor.")
        except Exception as e:
            print(f"Erro ao remover arquivo: {e}")
            
    def cleanup(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.listener_socket:
            self.listener_socket.close()
        print("Cliente encerrado")

if __name__ == "__main__":
    ip = input("Digite o IP do servidor: ").strip()
    client = FileSharingClient(server_host=ip)
    client.start()


import socket
import threading

def receive_messages(sock):
    while True:
        try:
            data = sock.recv(1024).decode('utf-8')
            if not data:
                print("Соединение с сервером разорвано.")
                break
            messages = data.split('\n')
            for msg in messages:
                if not msg:
                    continue
                print(f"{msg}")
        except:
            print("Произошла ошибка при получении данных.")
            break

def main():
    server_address = input("Введите адрес сервера: ").strip()
    server_port = int(input("Введите порт сервера: ")) 
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((server_address, server_port))
    except ConnectionRefusedError:
        print("Не удалось подключиться к серверу.")
        return
    except socket.gaierror:
        print("Неверный адрес сервера.")
        return

    threading.Thread(target=receive_messages, args=(sock,), daemon=True).start()

    print("Подключение установлено. Введите любое число для подтверждения участия, 'история' для просмотра ваших предположений или 'выход' для выхода.")

    while True:
        msg = input()
        if msg.lower() == 'выход':
            try:
                sock.sendall("выход\n".encode('utf-8'))
            except:
                pass
            print("Отключение от сервера.")
            break
        elif msg.lower() == 'история':
            try:
                sock.sendall("история\n".encode('utf-8'))
            except:
                print("Не удалось отправить запрос истории.")
        else:
            try:
                sock.sendall(f"{msg}\n".encode('utf-8'))
            except:
                print("Не удалось отправить сообщение.")

    sock.close()

if __name__ == '__main__':
    main()

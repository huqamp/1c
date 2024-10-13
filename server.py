import socket
import threading
import random
import time

HOST = '192.168.0.108'  
PORT = 12344      

clients = {}
clients_lock = threading.RLock()
leaderboard = {}
total_experiments = 0
experiment_started = False
target_number = None
waiting_for_confirmations = False  
CONFIRM_TIMEOUT = 30

def handle_client(conn, addr):
    global experiment_started, target_number, total_experiments, waiting_for_confirmations

    client_id = f"{addr[0]}:{addr[1]}"
    with clients_lock:
        clients[conn] = {
            'address': client_id,
            'confirmed': False,
            'attempts': 0,
            'guesses': [],
            'won': False
        }

    print(f"Клиент {client_id} подключился.")

    try:
        conn.sendall("Добро пожаловать! Ожидание начала эксперимента.\n".encode('utf-8'))
        while True:
            data = conn.recv(1024).decode('utf-8').strip()
            if not data:
                break  

            if data.lower() == 'выход':
                break  

            if data.lower() == 'история':
                with clients_lock:
                    guesses = clients[conn]['guesses']
                if guesses:
                    history = '\n'.join(f"{i+1}: {guess}" for i, guess in enumerate(guesses))
                    response = f"История ваших предположений:\n{history}\n"
                else:
                    response = "Вы ещё не сделали ни одного предположения.\n"
                conn.sendall(response.encode('utf-8'))
                continue

            if not experiment_started:
                if waiting_for_confirmations:
                    if not clients[conn]['confirmed']:
                        try:
                            
                            int(data)
                            with clients_lock:
                                clients[conn]['confirmed'] = True
                            conn.sendall("Вы подтвердили участие в эксперименте. Ожидание других участников...\n".encode('utf-8'))
                            print(f"Участник {client_id} подтвердил участие.")
                        except ValueError:
                            conn.sendall("Пожалуйста, введите число для подтверждения участия.\n".encode('utf-8'))
                    else:
                        conn.sendall("Ожидание других участников...\n".encode('utf-8'))
                else:
                    conn.sendall("Эксперимент ещё не начался. Ожидание команды 'старт'.\n".encode('utf-8'))
                continue

            if experiment_started:
                try:
                    guess = int(data)
                    with clients_lock:
                        if not clients[conn]['won']:
                            clients[conn]['attempts'] += 1
                            clients[conn]['guesses'].append(guess)
                            if guess == target_number:
                                clients[conn]['won'] = True
                                response = "Поздравляем! Вы угадали число!\n"
                               
                                if client_id not in leaderboard or clients[conn]['attempts'] < leaderboard[client_id]:
                                    leaderboard[client_id] = clients[conn]['attempts']
                        
                                all_won = all(data['won'] for data in clients.values())
                                if all_won:
                                   
                                    experiment_ended_message = "Все участники угадали число. Эксперимент завершён.\n"
                                    for c in clients.keys():
                                        try:
                                            c.sendall(experiment_ended_message.encode('utf-8'))
                                        except:
                                            print(f"Не удалось отправить сообщение клиенту {clients[c]['address']}")
                                  
                                    print("="*50)
                                    print("Эксперимент завершён автоматически. Все участники угадали число.")
                                    print(f"Загаданное число было: {target_number}")
                                    print("Статистика участников:")
                                    for data in clients.values():
                                        print(f"- {data['address']}: Попыток: {data['attempts']}")
                                    print("="*50)
                                    reset_experiment()
                            elif guess < target_number:
                                response = "Загаданное число больше.\n"
                            else:
                                response = "Загаданное число меньше.\n"
                        else:
                            response = "Вы уже угадали число в этом эксперименте.\n"
                    conn.sendall(response.encode('utf-8'))
                except ValueError:
                    conn.sendall("Пожалуйста, введите корректное число.\n".encode('utf-8'))
            else:
                conn.sendall("Эксперимент ещё не начался. Ожидание команды 'старт'.\n".encode('utf-8'))

    except Exception as e:
        print(f"Ошибка с клиентом {client_id}: {e}")
    finally:
        with clients_lock:
            del clients[conn]
        conn.close()
        print(f"Клиент {client_id} отключился.")

def accept_clients(sock):
    while True:
        conn, addr = sock.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

def start_experiment():
    global experiment_started, target_number, total_experiments, waiting_for_confirmations

    with clients_lock:
        if not clients:
            print("Нет подключённых клиентов для запуска эксперимента.")
            return False

        print("Отправка сообщения о начале эксперимента всем клиентам...")
        for conn, data in clients.items():
            try:
                conn.sendall("Старт эксперимента! Подтвердите участие, отправив любое число.\n".encode('utf-8'))
                data['confirmed'] = False 
            except:
                print(f"Не удалось отправить сообщение клиенту {data['address']}")

    waiting_for_confirmations = True  

    
    start_time = time.time()
    while True:
        with clients_lock:
            pending_conns = [conn for conn, data in clients.items() if not data['confirmed']]

        if not pending_conns:
            break  

        if time.time() - start_time > CONFIRM_TIMEOUT:
            with clients_lock:
                pending_addresses = [clients[conn]['address'] for conn in pending_conns]
            print(f"Таймаут ожидания подтверждений. Не подтвердили участие: {', '.join(pending_addresses)}")
           
            with clients_lock:
                for conn, data in clients.items():
                    try:
                        if data['confirmed']:
                            conn.sendall("Не все игроки подтвердили своё участие, и из-за этого эксперимент не начался.\n".encode('utf-8'))
                        else:
                            conn.sendall("Вы не подтвердили своё участие, и поэтому эксперимент не начался.\n".encode('utf-8'))
                    except:
                        print(f"Не удалось отправить сообщение клиенту {data['address']}")
               
                for data in clients.values():
                    data['confirmed'] = False
            waiting_for_confirmations = False  
            return False

        time.sleep(1)  

    waiting_for_confirmations = False  

    
    with clients_lock:
        pending = [data['address'] for data in clients.values() if not data['confirmed']]
        if pending:
            print("Не все участники подтвердили участие. Эксперимент не начался.")
            return False
        else:
           
            experiment_started = True
            target_number = random.randint(1, 100)
            total_experiments += 1
           
            for data in clients.values():
                data['won'] = False
                data['attempts'] = 0
                data['guesses'] = []
            print(f"Эксперимент начался. Загаданное число: {target_number}")
           
            for conn, data in clients.items():
                try:
                    conn.sendall("Эксперимент начался! Начинайте угадывать число.\n".encode('utf-8'))
                except:
                    print(f"Не удалось отправить сообщение клиенту {data['address']}")
            return True

def reset_experiment():

    global experiment_started, target_number
    experiment_started = False
    target_number = None
    with clients_lock:
        for data in clients.values():
            data['confirmed'] = False
            data['attempts'] = 0
            data['guesses'] = []
            data['won'] = False

def main():
    global experiment_started, target_number, total_experiments, waiting_for_confirmations

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()
    print(f"Сервер запущен и слушает порт {PORT}.")

    threading.Thread(target=accept_clients, args=(sock,), daemon=True).start()

    try:
        while True:
            cmd = input("Введите команду (старт/завершить/участники/лидерборд/выход): ").strip().lower()
            if cmd == 'старт':
                if experiment_started:
                    print("Эксперимент уже запущен.")
                    continue
                confirmed = start_experiment()
                if confirmed:
                    print("Эксперимент начат.")
                else:
                    print("Эксперимент не начался.")
            elif cmd == 'завершить':
                if not experiment_started:
                    print("Эксперимент не запущен.")
                    continue
                print(f"Эксперимент завершён. Загаданное число было: {target_number}")
                with clients_lock:
                    for conn, data in clients.items():
                        try:
                            conn.sendall("Эксперимент завершён. Спасибо за участие!\n".encode('utf-8'))
                        except:
                            print(f"Не удалось отправить сообщение клиенту {data['address']}")
                reset_experiment()
            elif cmd == 'участники':
                with clients_lock:
                    if not clients:
                        print("Нет подключённых участников.")
                    else:
                        print("Участники и их статус подтверждения:")
                        for data in clients.values():
                            status = "Подтвердил" if data['confirmed'] else "Не подтвердил"
                            print(f"{data['address']}: Статус подтверждения: {status}, Попыток: {data['attempts']}, Угадал: {'Да' if data['won'] else 'Нет'}")
            elif cmd == 'лидерборд':
                print("Таблица лидеров по всем экспериментам:")
                with clients_lock:
                    if not leaderboard:
                        print("Лидеров пока нет.")
                    else:
                        sorted_leaderboard = sorted(leaderboard.items(), key=lambda x: x[1])
                        for idx, (addr, attempts) in enumerate(sorted_leaderboard, start=1):
                            print(f"{idx}. {addr}: Минимум попыток: {attempts}")
            elif cmd == 'выход':
                print("Уведомление всех участников о завершении работы сервера.")
                with clients_lock:
                    for conn, data in clients.items():
                        try:
                            conn.sendall("Сервер остановлен. До свидания!\n".encode('utf-8'))
                        except:
                            print(f"Не удалось отправить сообщение клиенту {data['address']}")
                print("Сервер остановлен.")
                break
            else:
                print("Неизвестная команда.")
    except KeyboardInterrupt:
        print("\nОстановка сервера по сигналу прерывания.")
        with clients_lock:
            for conn, data in clients.items():
                try:
                    conn.sendall("Сервер остановлен по сигналу прерывания. До свидания!\n".encode('utf-8'))
                except:
                    print(f"Не удалось отправить сообщение клиенту {data['address']}")
    finally:
        sock.close()

if __name__ == '__main__':
    main()

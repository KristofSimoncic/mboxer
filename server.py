# Importovanie potrebných modulov
import socket
import os
import hashlib


# Funkcia na zápis správy do súboru
def write(client_socket, message_dictionary):
    # Kontrola, či sú správne zadané potrebné položky
    if not ("Mailbox" in message_dictionary and "Content-length" in message_dictionary):
        client_socket.sendall("200 Bad request".encode())

    # Vytvorenie cesty k mailboxu, ak mailbox neexistuje, posiela sa chybová hláška
    mailbox_path = os.path.dirname(os.path.abspath(__file__)) + "/" + message_dictionary["Mailbox"]

    if not os.path.exists(mailbox_path):
        client_socket.sendall("203 No such mailbox".encode())

    # Ak vsetko prebehno v poriadku sprava sa zapise
    else:
        # Poslanie potvrdenia o prijatí požiadavky
        client_socket.sendall("100 OK".encode())

        # Vytvorenie názvu súboru z unikátneho hexadecimálneho reťazca a uloženie do súboru
        file_name = hashlib.md5()
        file_name.update(message_dictionary["content"].encode())
        file_name = file_name.hexdigest()

        file_path = mailbox_path + "/" + file_name + ".txt"

        # Zoberie sa iba zadany pocet bytov obsahu
        content = message_dictionary["content"]
        content_length = int(message_dictionary["Content-length"])

        content = content.encode()
        content = content[:content_length]
        content = content.decode()

        # Zapis do suboru
        with open(file_path, "w") as f:
            f.write(content)


# Funkcia na čítanie správy zo súboru a jej odoslanie klientovi
def read(client_socket, message_dictionary):
    # Ak nie sú v správe uvedené Mailbox a Message, klientovi sa pošle chybová správa
    if not ("Mailbox" in message_dictionary and "Message" in message_dictionary):
        client_socket.sendall("200 Bad request".encode())

    # Adresa mailboxu a správy
    mailbox_path = os.path.dirname(os.path.abspath(__file__)) + "/" + message_dictionary["Mailbox"]
    message_path = mailbox_path + "/" + message_dictionary["Message"] + ".txt"

    # Ak mailbox alebo správa neexistuje, klientovi sa pošle chybová správa
    if not (os.path.exists(mailbox_path) and os.path.exists(message_path)):
        client_socket.sendall("203 No such mailbox".encode())

    # Ak nemáme prístup k súboru so správou, klientovi sa pošle chybová správa
    elif not os.access(message_path, os.R_OK):
        client_socket.sendall("202 Read error".encode())

    # Ak všetko prebehne v poriadku, správa sa prečíta a pošle klientovi
    else:
        with open(message_path, "r") as f:
            status = "100 OK"
            content = f.read()
            content_length = len(content.encode())

            # Hlavička s dlzkou obsahu
            header = "Content-length: " + str(content_length)

            # Spojenie statusu, hlavičky a obsahu správy do jednej správy
            message = (status + "\n" + header + "\n" + "\n" + content).encode()

            # Odoslanie správy klientovi
            client_socket.sendall(message)


# Funkcia na vypis sprav v priecinku
def ls(client_socket, message_dictionary):
    # Ak priecinok nie je zadany, posiela sa chybova hlaska
    if not ("Mailbox" in message_dictionary):
        client_socket.sendall("200 Bad request".encode())

    # Vytvorenie adresy priecinku
    mailbox_path = os.path.dirname(os.path.abspath(__file__)) + "/" + message_dictionary["Mailbox"]

    # Ak adresa nie je v dosahu posiela sa chybova hlaska
    if not os.path.exists(mailbox_path):
        client_socket.sendall("203 No such mailbox".encode())

    # Ak vsetko prebehne v poriadku zisti sa pocet a nazvy suborov v priecinku, a odoslu sa klientovi
    else:
        status = "100 OK"

        # Nazvy suborov sa vlozia do zoznamu, ich pocet je jeho dlzka
        messages = os.listdir(mailbox_path)
        number_of_messages = len(messages)

        # Hlavicka s poctom sprav
        header = "Number-of-messages: " + str(number_of_messages)

        # Spravy sa spoja spolu so statusom a hlavickou a odoslu sa
        content = ""
        for mes in messages:
            content += mes + "\n"

        message = (status + "\n" + header + "\n" + "\n" + content).encode()
        client_socket.sendall(message)


# Funkcia na obsluhu klienta
def handle_client(client_socket, message_dictionary):
    # Zisti sa metoda, podla nej sa spusti prislusna funkcia
    if message_dictionary["method"] == "WRITE":
        write(client_socket, message_dictionary)
    elif message_dictionary["method"] == "READ":
        read(client_socket, message_dictionary)
    elif message_dictionary["method"] == "LS":
        ls(client_socket, message_dictionary)
    # Ak metoda chyba alebo je nepodporovana odosle sa chybova hlaska
    else:
        client_socket.sendall("204 Unknown method".encode())


# Data su ulozene do slovnika, toto je funkcia na jeho vytvorenie
def message_to_dictionary(message):
    message_lines = message.splitlines()
    message_dictionary = dict()

    # ako metoda sa ulozi prvy riadok spravy
    message_dictionary["method"] = message_lines[0]

    # Zisti sa index vynechaneho riadku
    space_index = message_lines.index("")

    # Od druheho riadku az po vynechany riadok su hlavicky
    for i in range(1, space_index):
        [identificator, value] = message_lines[i].split(":")
        message_dictionary[identificator] = value

    # Za obsahu sa bud vlozi prazdny retazec ak chyba
    if space_index+1 >= len(message_lines):
        content = ""
    # Alebo sa riadky s obsahom zase spoja a ulozia do slovnika
    else:
        content = '\n'.join(message_lines[space_index+1:])
    message_dictionary["content"] = content

    return message_dictionary

# Vytvori sa socket z danou ip adresou a portovacim cislom a pocuva
HOST = '127.0.0.1'
PORT = 9999

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = (HOST, PORT)
server_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
server_socket.bind(server_address)
server_socket.listen(5)


try:
    # Cyklus pre naviazanie spojenia s klientmi a ich obsluhu
    while True:
        # Naviazanie spojenia
        print('Waiting for a client connection...')
        client_socket, client_address = server_socket.accept()
        print('Client connected:', client_address)

        try:
            # Ak sa naviaze forkuje sa na detsky a rodicovsky proces
            pid = os.fork()

            if pid == 0:
                # Detsky proces obsluhuje klienta
                # Tu prijme spravu
                message = client_socket.recv(1024).decode()
                print("PRIJAL SOM")

                # Tu je vlozi do slovniku
                message_dictionary = message_to_dictionary(message)

                print('Received message:')
                print(message_dictionary)

                # Obsluha klienta
                handle_client(client_socket, message_dictionary)

                # Uzavre sa spojenie
                client_socket.close()

                # os._exit(0)
            else:
                # Rodicovky proces uzavrie spojenie a pokracuje na novu iteraciu kde pocuva na dalsieho klienta
                client_socket.close()

        except Exception as e:
            # V pripade poruchy sa spusti
            print(f'Error while handling client connection: {e}')
            client_socket.sendall("500 Internal server error\n".encode())
            client_socket.close()

except KeyboardInterrupt:
    # V pripade prerusenia
    pass

finally:
    # Uzavretie serverovskeho socketu
    server_socket.close()

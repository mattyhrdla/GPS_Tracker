import time
import machine
import random
import ujson
import BG77

# Globální proměnné
DEFAULT_INTERVAL = 1800  # Čas základního intervalu
FAST_INTERVAL = 60       # Rychlý interval při krádeži
MAX_ATTEMPTS = 5

# IP adresa a port serveru
SERVER_IP = "62.245.74.185"
SERVER_PORT = 26901

# Funkce pro náhodné souřadnice v ČR (cca hranice ČR)
def get_random_location():
    lat = round(random.uniform(48.5, 50.6), 6)
    lon = round(random.uniform(12.0, 18.9), 6)
    return lat, lon

# Inicializace modemu
def init_modem():
    uart = machine.UART(0, baudrate=115200, tx=machine.Pin(0), rx=machine.Pin(1))
    modem = BG77.BG77(uart, verbose=False, radio=True)
    
    while modem.isRegistered():
        modem.setOperator(BG77.COPS_DEREGISTER)
        time.sleep(2)
        
    while not modem.isRegistered():
        modem.setEcho(False)
        modem.setRATType(BG77.RAT_NB_IOT_ONLY, 1)
        modem.setAPN("lpwa.vodafone.iot")
        modem.setOperator(BG77.COPS_MANUAL, BG77.Operator.CZ_VODAFONE)

        for i in range(MAX_ATTEMPTS):
            if modem.isRegistered():
                print("Registrován k síti.")
                break
            print("Čekám na registraci...")
            time.sleep(5)
        else:
            print("Modem se nepodařilo zaregistrovat.")
            print("Pokus o opětovné připojení do sítě")
    
    if not modem.attachToNetwork():
        print("Nepodařilo se připojit k síti.")
    
    return modem

# Vytváření UDP socketu
def create_udp_socket(modem):
    for attempt in range(MAX_ATTEMPTS):
        try:
            success, sock = modem.socket(BG77.AF_INET, BG77.SOCK_DGRAM)
            
            if not success:
                raise RuntimeError("Nepodařilo se vytvořit socket.")
            
            sock.settimeout(10)
            if not sock.connect(SERVER_IP, SERVER_PORT):
                raise RuntimeError("Chyba při připojení socketu.")

            print("Socket úspěšně vytvořen a připojen.")
            return sock

        except Exception as e:
            print(f"Chyba při vytváření socketu, pokus {attempt + 1}/{MAX_ATTEMPTS}")
            time.sleep(2)

    # Pokud žádný pokus nevyšel
    print("Socket se nepodařilo vytvořit ani po opakovaných pokusech.")
    return None


# Odesílání UDP zprávy
def send_udp_message(sock, message):
    if not sock.send(message, 2):
        raise RuntimeError("Odeslání zprávy selhalo.")
    
# Čtení odpovědi ze serveru
def receive_response(sock):
    length, response = sock.recv(1460)
    
    if length > 0 and response:
        return response
    else:
        return None

# Zpracování odpovědi
def process_response(response, interval):      
    if "tru" in response.lower():
        print(f"Změna intervalu na {FAST_INTERVAL} sekund.")
        return FAST_INTERVAL
    elif "fals" in response.lower():
        print(f"Změna intervalu na {DEFAULT_INTERVAL / 60} minut")
        return DEFAULT_INTERVAL
    elif "o" in response.lower():
        print("Interval zůstává bez změny")
        return interval
    else:
        print("Neznámá odpověď, ponechávám aktuální interval.")
        return interval   
    
# Funkce hlavní smyčky
def main():
    print("Zahájení inicializace modemu")
    interval = DEFAULT_INTERVAL
    modem = init_modem()
    
    while True:
        try:                           
            lat, lon = get_random_location()
            payload = ujson.dumps({"latitude": lat, "longitude": lon})
            print("Generovaná data:", payload)
            sock = create_udp_socket(modem)
            
            if not sock:
                print(f"Přeskakuji odesílání, další pokus za {interval} sekund.")
                time.sleep(interval)
                modem = init_modem()
                continue
            
            for attempt in range(MAX_ATTEMPTS):
                try:
                    send_udp_message(sock, payload)
                    response = receive_response(sock)
                    sock.close()
                    
                    if response:
                        print("Zprávu se podařilo úspěšně odeslat")
                        print("Odpověď od serveru:", response)
                        interval = process_response(response, interval)
                        break
                    else:
                        print("Nepodařilo se odeslat zprávu")
                        print("Počet zbývajících pokusů:", MAX_ATTEMPTS - (attempt + 1))
                        
                except Exception as e:
                    raise(e)
                finally:
                    if sock:
                        sock.close()
                        modem.sendCommand('AT+QICLOSE=1\r\n', timeout=1)

        except Exception as e:
            print("Chyba:", e)
            interval = DEFAULT_INTERVAL
        
        if interval == DEFAULT_INTERVAL:
            print(f"Další odesílání proběhne za {DEFAULT_INTERVAL/60} minut")    
        else:
            print(f"Další odesílání proběhne za {FAST_INTERVAL} sekund")
        
        print("---------------------------------------------------\n\n")
        time.sleep(interval)
        print("---------------------------------------------------")

# Spuštění hlavní smyčky
main()
import time
from multiprocessing import Process, Manager
from operator import itemgetter

class Orquestrador:
    def __init__(self, lista_desordenada, lista_ordenada, estados_servidores, config):
        self.lista_desordenada = lista_desordenada # Gerador irá por as tarefas aqui.
        self.lista_ordenada = lista_ordenada# Servidores leem daqui
        self.estados_servidores = estados_servidores 
        self.config = config 
        self.rr_index = 0 

    def escolher_servidor(self):
        """Define o servidor inicial baseado em Round Robin simples para distribuição"""
        num_servers = self.config.get('num_servidores', 3)
        servidor_id = (self.rr_index % num_servers) + 1
        self.rr_index += 1
        return servidor_id

    def aplicar_politica(self):
        """Ordena a lista compartilhada baseada na política escolhida"""
        politica = self.config.get('politica', 'RR')
        
        buffer_tarefas = list(self.lista_ordenada)
        
        if not buffer_tarefas:
            return

        if politica == 'SJF':
            buffer_tarefas.sort(key=itemgetter('tempo_exec'))

        elif politica == 'Prioridade':
            buffer_tarefas.sort(key=itemgetter('prioridade'))

        self.lista_ordenada[:] = []
        self.lista_ordenada.extend(buffer_tarefas)

    def balancear_carga(self):
        """Verifica sobrecarga e migra tarefas se necessário"""

        cargas = {i: 0 for i in range(1, self.config['num_servidores'] + 1)}

        tarefas_pendentes = [t for t in self.lista_ordenada if t['tempo_ja_executado'] == 0]
        
        for t in tarefas_pendentes:
            sid = t.get('servidor_de_trabalho')
            if sid in cargas:
                cargas[sid] += 1
        
        # Identifica servidor mais cheio e mais vazio
        max_load_server = max(cargas, key=cargas.get)
        min_load_server = min(cargas, key=cargas.get)
        
        # Se a diferença for maior que 2, migra uma tarefa
        if cargas[max_load_server] - cargas[min_load_server] > 1:
            for i, task in enumerate(self.lista_ordenada):
                if task['servidor_de_trabalho'] == max_load_server and task['tempo_ja_executado'] == 0:
                    task['servidor_de_trabalho'] = min_load_server
                    self.lista_ordenada[i] = task 
                    print(f"[ORCHESTRADOR] Migrando tarefa {task['id']} do Servidor {max_load_server} para {min_load_server}")
                    break

    def processar(self):
        print(f"[ORCHESTRADOR] Iniciado. Política: {self.config['politica']}")
        
        while True:
            if self.lista_desordenada:
                req = self.lista_desordenada.pop(0)
                
                req['tipo_escalonador'] = self.config['politica']
                req['servidor_de_trabalho'] = self.escolher_servidor()
                req['id_ordem_processamento'] = 0 
                req['tempo_ja_executado'] = 0
                req['tempo_chegada'] = time.time()
                req['momento_finalizada'] = None
                req['primeira_resposta_preempcao'] = None
                
                self.lista_ordenada.append(req)
                print(f"[ORCHESTRADOR] Nova tarefa {req['id']} atribuída ao Servidor {req['servidor_de_trabalho']}")

            self.aplicar_politica()

            self.balancear_carga()

            time.sleep(0.1) # Para não sobrecarregar CPU

def run_orquestrador(lista_des, lista_ord, estados, config):
    orq = Orquestrador(lista_des, lista_ord, estados, config)
    orq.processar()

#if __name__ == "__main__":
    
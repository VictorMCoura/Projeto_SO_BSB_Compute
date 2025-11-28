import time
import random
from multiprocessing import Process, Manager
import os

CONFIG = {
    'num_servidores': 3,
    'politica': 'RR',       # Pode trocar pra 'SJF' ou 'Prioridade'
    'quantum': 2.0,         # Tempo limite (só pro RR)
    'total_requisicoes': 15
}

class GeradorDeCargas:
    def __init__(self, lista_desordenada, qtd_gerar):
        self.lista_desordenada = lista_desordenada
        self.qtd_gerar = qtd_gerar

    def executar(self):
        print(f"[GERADOR] Criando {self.qtd_gerar} tarefas...")
        for i in range(1, self.qtd_gerar + 1):
            tempo_total = round(random.uniform(1.0, 6.0), 2)
            prioridade = random.randint(1, 3)
            tipo = random.choice(['visao_computacional', 'nlp', 'voz'])
            
            requisicao = {
                'id': i,
                'tipo': tipo,
                'prioridade': prioridade,
                'tempo_total': tempo_total,
                'tempo_restante': tempo_total,
                'tempo_ja_executado': 0.0,
                'servidor_trabalho': None
            }
            
            self.lista_desordenada.append(requisicao)
            time.sleep(random.uniform(0.3, 0.8)) 
        print("[GERADOR] Acabou.")

def run_gerador(lista, qtd):
    GeradorDeCargas(lista, qtd).executar()


class Orquestrador:
    def __init__(self, lista_desordenada, lista_ordenada, config, mutex):
        self.lista_desordenada = lista_desordenada
        self.lista_ordenada = lista_ordenada
        self.config = config
        self.mutex = mutex 
        self.rr_index = 0

    # Escolhe servidor girando (1 -> 2 -> 3 -> 1...)
    def escolher_servidor_rr(self):
        s_id = (self.rr_index % self.config['num_servidores']) + 1
        self.rr_index += 1
        return s_id

    # Ordena na lista local 
    def inserir_ordenado(self, buffer, tarefa):
        politica = self.config['politica']
        pos = len(buffer)
        
        if politica == 'SJF':
            for i, t in enumerate(buffer):
                if tarefa['tempo_restante'] < t['tempo_restante']:
                    pos = i
                    break
        elif politica == 'Prioridade':
            for i, t in enumerate(buffer):
                if tarefa['prioridade'] < t['prioridade']:
                    pos = i
                    break
        
        buffer.insert(pos, tarefa)

    # Tira da entrada, processa e joga na saída ordenada
    def processar_entrada(self):
        if not self.lista_desordenada:
            return

        req = self.lista_desordenada.pop(0)
        req['servidor_trabalho'] = self.escolher_servidor_rr()
        
        # Bloqueia a lista compartilhada pra escrever sem dar erro
        with self.mutex:
            buffer = list(self.lista_ordenada) 
            self.inserir_ordenado(buffer, req) 
            
            # Atualiza a lista oficial de uma vez
            self.lista_ordenada[:] = []
            self.lista_ordenada.extend(buffer)
            
        print(f"[ORQUESTRADOR] Tarefa {req['id']} -> S{req['servidor_trabalho']}")

    # Move tarefas de servidores cheios pra vazios
    def balancear_carga(self):
        # Bloqueia tudo porque vai ler E alterar
        with self.mutex:
            cargas = {i: 0 for i in range(1, self.config['num_servidores'] + 1)}
            pendentes = [t for t in self.lista_ordenada if t['tempo_ja_executado'] == 0]
            
            for t in pendentes:
                if t['servidor_trabalho'] in cargas:
                    cargas[t['servidor_trabalho']] += 1
            
            if not cargas: return
            
            max_s = max(cargas, key=cargas.get)
            min_s = min(cargas, key=cargas.get)
            
            # Se a diferença for grande, move uma tarefa
            if cargas[max_s] - cargas[min_s] > 1:
                for i in range(len(self.lista_ordenada)):
                    t = self.lista_ordenada[i]
                    if t['servidor_trabalho'] == max_s and t['tempo_ja_executado'] == 0:
                        t['servidor_trabalho'] = min_s
                        self.lista_ordenada[i] = t 
                        print(f"   >>> [BALANCEAMENTO] Moveu Tarefa {t['id']}: S{max_s} -> S{min_s}")
                        break

    def iniciar(self):
        print(f"[ORQUESTRADOR] Rodando ({self.config['politica']})")
        while True:
            self.processar_entrada()
            self.balancear_carga()
            time.sleep(0.1)

def run_orquestrador(l_des, l_ord, cfg, mut):
    Orquestrador(l_des, l_ord, cfg, mut).iniciar()

# Pega tarefa, executa e devolve se não acabar 
def run_worker(id_worker, lista_ordenada, config, mutex):
    print(f"[WORKER {id_worker}] Online.")
    while True:
        tarefa_encontrada = None
        
        # Bloqueia pra procurar e pegar a tarefa (Atomicidade)
        with mutex:
            for i, tarefa in enumerate(lista_ordenada):
                if tarefa['servidor_trabalho'] == id_worker:
                    tarefa_encontrada = lista_ordenada.pop(i) # Tira da fila
                    break
        
        if tarefa_encontrada:
            # Processa fora do lock pra não travar os outros
            tempo_restante = tarefa_encontrada['tempo_restante']
            
            # Se for RR, limita pelo Quantum. Se não, vai até o fim.
            if config['politica'] == 'RR':
                tempo_executar = min(tempo_restante, config['quantum'])
            else:
                tempo_executar = tempo_restante

            print(f"   [WORKER {id_worker}] Rodando Req {tarefa_encontrada['id']} ({tempo_executar:.1f}s)...")
            time.sleep(tempo_executar)
            
            # Atualiza quanto falta
            tarefa_encontrada['tempo_restante'] -= tempo_executar
            tarefa_encontrada['tempo_ja_executado'] += tempo_executar
            
            if tarefa_encontrada['tempo_restante'] <= 0.05:
                print(f"   ✅ [WORKER {id_worker}] Req {tarefa_encontrada['id']} FINALIZADA.")
            else:
                print(f"   🔄 [WORKER {id_worker}] Quantum acabou pra Req {tarefa_encontrada['id']}.")
                
                # Bloqueia pra devolver pro fim da fila
                with mutex:
                    lista_ordenada.append(tarefa_encontrada)
        else:
            time.sleep(0.5) # Espera ativa se não tiver trabalho

if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=== BSB COMPUTE: INICIANDO ===")
    
    with Manager() as manager:
        # Cria o cadeado global
        mutex_global = manager.Lock()
        
        lista_entrada = manager.list()
        lista_saida = manager.list()
        
        p_ger = Process(target=run_gerador, args=(lista_entrada, CONFIG['total_requisicoes']))
        p_orq = Process(target=run_orquestrador, args=(lista_entrada, lista_saida, CONFIG, mutex_global))
        
        workers = []
        for i in range(1, CONFIG['num_servidores'] + 1):
            w = Process(target=run_worker, args=(i, lista_saida, CONFIG, mutex_global))
            workers.append(w)
            
        p_ger.start()
        p_orq.start()
        for w in workers: w.start()
        
        p_ger.join()
        
        # Deixa rodar um tempo pra ver o resultado
        time.sleep(25) 
        
        print("\n=== Encerrando ===")
        p_orq.terminate()
        for w in workers: w.terminate()
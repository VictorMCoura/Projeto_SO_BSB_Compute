import time
import random
import logging
from multiprocessing import Process, Manager
import os

# Configuração dos logs (pra ficar organizado no terminal)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='[%H:%M:%S]' 
)
logger = logging.getLogger()

# Configs do teste
CONFIG = {
    'num_servidores': 3,
    'politica': 'Prioridade',   # Pode trocar pra 'RR' ou 'SJF'
    'quantum': 2.0,             # Tempo limite (só pro RR)
    'total_requisicoes': 15
}

# Gerador de Cargas
# Cria tarefas aleatórias e joga na fila
class GeradorDeCargas:
    def __init__(self, lista_entrada, qtd_gerar):
        self.lista_entrada = lista_entrada
        self.qtd_gerar = qtd_gerar

    def executar(self): 
        logger.info(f"GERADOR: Criando {self.qtd_gerar} tarefas...")
        for i in range(1, self.qtd_gerar + 1):
            tempo_total = round(random.uniform(1.0, 5.0), 2)
            prioridade = random.randint(1, 3) 
            tipo = random.choice(['Visão', 'NLP', 'Voz'])
            
            req = {
                'id': i,
                'tipo': tipo,
                'prioridade': prioridade,
                'tempo_total': tempo_total,
                'tempo_restante': tempo_total,
                'tempo_chegada': time.time(),
                'tempo_primeira_execucao': None,
                'tempo_fim': None,
                'servidor_trabalho': None
            }
            
            self.lista_entrada.append(req)
            time.sleep(random.uniform(0.2, 0.6)) # Pausa pra não criar tudo instantâneo
            
        logger.info("GERADOR: Acabou.")

def run_gerador(lista, qtd):
    GeradorDeCargas(lista, qtd).executar()

# Orquestrador 
class Orquestrador:
    def __init__(self, lista_entrada, lista_saida, config, mutex):
        self.lista_entrada = lista_entrada
        self.lista_saida = lista_saida 
        self.config = config
        self.mutex = mutex 
        self.rr_index = 0

    # Escolhe servidor girando (1 -> 2 -> 3 -> 1...)
    def escolher_servidor(self):
        s_id = (self.rr_index % self.config['num_servidores']) + 1
        self.rr_index += 1
        return s_id
    
    # Ordena na lista local 
    def inserir_inteligente(self, buffer, tarefa):
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

    # Tira da entrada e joga pra fila de processamento
    def processar_entrada(self):
        if not self.lista_entrada: return

        req = self.lista_entrada.pop(0)
        req['servidor_trabalho'] = self.escolher_servidor()
        
        # Bloqueia pra escrever na lista 
        with self.mutex:
            buffer = list(self.lista_saida) 
            self.inserir_inteligente(buffer, req) 
            
            # Atualiza a lista
            self.lista_saida[:] = []
            self.lista_saida.extend(buffer)
            
        logger.info(f"ORQUESTRADOR: Req {req['id']} -> Servidor {req['servidor_trabalho']}")

    # Move tarefas de quem tá cheio pra quem tá livre
    def balancear_carga(self):
        # Bloqueia tudo pra ler e alterar
        with self.mutex:
            buffer = list(self.lista_saida) 
            
            # Conta tarefas de cada um
            cargas = {i: 0 for i in range(1, self.config['num_servidores'] + 1)}
            for t in buffer:
                if t['servidor_trabalho'] in cargas:
                    cargas[t['servidor_trabalho']] += 1
            
            if not cargas: return
            
            max_s = max(cargas, key=cargas.get)
            min_s = min(cargas, key=cargas.get)
            
            # Se a diferença for grande, move uma tarefa
            if cargas[max_s] - cargas[min_s] > 1:
                alterou = False
                for i in range(len(buffer)):
                    t = buffer[i]
                    if t['servidor_trabalho'] == max_s:
                        t['servidor_trabalho'] = min_s
                        buffer[i] = t 
                        logger.info(f"BALANCEAMENTO: Req {t['id']} de S{max_s} pra S{min_s}")
                        alterou = True
                        break
                
                # Só gasta tempo salvando se mudou algo
                if alterou:
                    self.lista_saida[:] = []
                    self.lista_saida.extend(buffer)

    def iniciar(self):
        logger.info(f"ORQUESTRADOR: Rodando ({self.config['politica']})")
        while True:
            self.processar_entrada()
            self.balancear_carga()
            time.sleep(0.05) 

def run_orquestrador(l_in, l_out, cfg, mut):
    Orquestrador(l_in, l_out, cfg, mut).iniciar()

# Worker
def run_worker(id, lista_saida, lista_concluidas, stats_cpu, config, mutex):
    logger.info(f"WORKER {id}: Pronto.")
    tempo_trabalhado = 0.0 
    
    while True:
        tarefa = None
        
        # Bloqueia pra pegar tarefa 
        with mutex:
            buffer = list(lista_saida)
            idx_encontrado = -1
            for i, t in enumerate(buffer):
                if t['servidor_trabalho'] == id:
                    idx_encontrado = i
                    break
            
            # Se achou, remove da lista
            if idx_encontrado != -1:
                tarefa = lista_saida.pop(idx_encontrado)
        
        if tarefa:
            # Marca a primeira vez que rodou 
            if tarefa['tempo_primeira_execucao'] is None:
                tarefa['tempo_primeira_execucao'] = time.time()

            restante = tarefa['tempo_restante']
            
            # Se for RR, limita pelo Quantum. Se não, vai até o fim.
            if config['politica'] == 'RR':
                tempo_turno = min(restante, config['quantum']) 
            else:
                tempo_turno = restante 

            logger.info(f"WORKER {id}: Rodando Req {tarefa['id']} ({tempo_turno:.1f}s)...")
            time.sleep(tempo_turno) # Simula trabalho
            
            tempo_trabalhado += tempo_turno
            tarefa['tempo_restante'] -= tempo_turno
            

            if tarefa['tempo_restante'] <= 0.05:
                tarefa['tempo_fim'] = time.time()
                lista_concluidas.append(tarefa) 
                logger.info(f"WORKER {id}: Req {tarefa['id']} ACABOU.")
                
                stats_cpu[id] = tempo_trabalhado
            else:
                logger.info(f"WORKER {id}: Req {tarefa['id']} voltando pra fila.")
                # Bloqueia pra devolver pro fim da fila
                with mutex:
                    lista_saida.append(tarefa)
        else:
            time.sleep(0.1)

# Main
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear') 
    print(">>> BSB COMPUTE <<<")
    
    tempo_inicio_simulacao = time.time()

    with Manager() as manager:
        # Cria as coisas compartilhadas
        mutex = manager.Lock()
        fila_entrada = manager.list()
        fila_trabalho = manager.list()
        lista_concluidas = manager.list() 
        stats_cpu = manager.dict() 
        
        # Cria os Processos
        p_gerador = Process(target=run_gerador, args=(fila_entrada, CONFIG['total_requisicoes']))
        p_orquestrador = Process(target=run_orquestrador, args=(fila_entrada, fila_trabalho, CONFIG, mutex))
        
        workers = []
        for i in range(1, CONFIG['num_servidores'] + 1):
            w = Process(target=run_worker, args=(i, fila_trabalho, lista_concluidas, stats_cpu, CONFIG, mutex))
            workers.append(w)
            
        # Inicia tudo
        p_gerador.start()
        p_orquestrador.start()
        for w in workers: w.start()
        
        # Espera o gerador terminar
        p_gerador.join()
        
        # Espera limpar a fila de tarefas
        while len(lista_concluidas) < CONFIG['total_requisicoes']:
            time.sleep(1)
            
        print("\n" + "="*50)
        print("RELATÓRIO FINAL")
        print("="*50)
        
        tempo_total_sim = time.time() - tempo_inicio_simulacao
        total_tasks = len(lista_concluidas)
        
        soma_retorno = 0   
        soma_resposta = 0  
        soma_espera = 0
        max_espera = 0
        
        for t in lista_concluidas:
            # 1. Turnaround (Chegada até Fim)
            t_retorno = t['tempo_fim'] - t['tempo_chegada']
            soma_retorno += t_retorno
            
            # 2. Response (Chegada até 1ª vez na CPU)
            if t['tempo_primeira_execucao']:
                t_resp_real = t['tempo_primeira_execucao'] - t['tempo_chegada']
                soma_resposta += t_resp_real
            
            # 3. Espera (Tempo na fila sem fazer nada)
            t_espera = t_retorno - t['tempo_total']
            if t_espera < 0: t_espera = 0
            
            soma_espera += t_espera
            if t_espera > max_espera: max_espera = t_espera
            
        total_cpu_time = sum(stats_cpu.values())
        capacidade_total = CONFIG['num_servidores'] * tempo_total_sim
        cpu_util = (total_cpu_time / capacidade_total) * 100 if capacidade_total > 0 else 0
        
        print(f"Política: {CONFIG['politica']}")
        print(f"Total Tarefas: {total_tasks}")
        print(f"Tempo Simulação: {tempo_total_sim:.2f}s")
        print("-" * 30)
        print(f"1. Throughput:        {total_tasks / tempo_total_sim:.2f} tarefas/seg")
        print(f"2. T. Médio Retorno:  {soma_retorno / total_tasks:.2f}s (Turnaround)")
        print(f"3. T. Médio Resposta: {soma_resposta / total_tasks:.2f}s (Response)")
        print(f"4. Max Espera:        {max_espera:.2f}s")
        print(f"5. Uso da CPU:        {cpu_util:.1f}%")
        print("="*50)

        # Mata os processos
        p_orquestrador.terminate()
        for w in workers: w.terminate()
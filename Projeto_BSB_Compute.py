import time
import random
import logging
from multiprocessing import Process, Manager
import os

# Configuração dos logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='[%H:%M:%S]' 
)
logger = logging.getLogger()


# CONFIGURAÇÕES DA SIMULAÇÃO
CONFIG = {
    'num_servidores': 3,
    'politica': 'Prioridade',       # 'RR', 'SJF' ou 'Prioridade'
    'quantum': 2.0,         # Tempo máximo na CPU
    'total_requisicoes': 15 # Total de tarefas pra rodar no teste
}


# Classe - GERADOR DE REQUISIÇÕES
class GeradorDeCargas:
    def __init__(self, lista_entrada, qtd_gerar):
        self.lista_entrada = lista_entrada
        self.qtd_gerar = qtd_gerar

    def executar(self): #Criando tarefas aleatórias
        logger.info(f"GERADOR: Iniciando. Meta: {self.qtd_gerar} tarefas.")
        for i in range(1, self.qtd_gerar + 1):
            tempo_total = round(random.uniform(1.0, 5.0), 2)
            prioridade = random.randint(1, 3) # 1 é Alta, 3 é Baixa
            tipo = random.choice(['Visão', 'NLP', 'Voz'])
            
            req = {
                'id': i,
                'tipo': tipo,
                'prioridade': prioridade,
                'tempo_total': tempo_total,
                'tempo_restante': tempo_total,
                'tempo_chegada': time.time(),
                'servidor_trabalho': None
            }
            
            self.lista_entrada.append(req)
            # logger.info(f"GERADOR: Criou Req {i} (Pri: {prioridade}, Tempo: {tempo_total}s)")
            
            # Pausa pra não chegar tudo de uma vez
            time.sleep(random.uniform(0.2, 0.6))
            
        logger.info("GERADOR: Acabou o serviço.")

def run_gerador(lista, qtd):
    GeradorDeCargas(lista, qtd).executar()


# Classe - ORQUESTRADOR 
class Orquestrador:
    def __init__(self, lista_entrada, lista_saida, config, mutex):
        self.lista_entrada = lista_entrada
        self.lista_saida = lista_saida # Fila ordenada pros workers
        self.config = config
        self.mutex = mutex # Lock
        self.rr_index = 0

    def escolher_servidor_rr(self):
        s_id = (self.rr_index % self.config['num_servidores']) + 1
        self.rr_index += 1
        return s_id

    
    def inserir_inteligente(self, buffer, tarefa):
        politica = self.config['politica']
        pos = len(buffer) # Por padrão vai pro final (RR)
        if politica == 'SJF':
            # Fura fila se for mais rápido que os outros
            for i, t in enumerate(buffer):
                if tarefa['tempo_restante'] < t['tempo_restante']:
                    pos = i
                    break
        elif politica == 'Prioridade':
            # Fura fila se for mais urgente (número menor)
            for i, t in enumerate(buffer):
                if tarefa['prioridade'] < t['prioridade']:
                    pos = i
                    break
        
        buffer.insert(pos, tarefa)

    # Pega da entrada e joga pra fila de processamento
    def processar_entrada(self):
        if not self.lista_entrada: return

        req = self.lista_entrada.pop(0)
        req['servidor_trabalho'] = self.escolher_servidor_rr()
        
        # Bloqueia pra escrever na lista compartilhada
        with self.mutex:
            buffer = list(self.lista_saida)
            self.inserir_inteligente(buffer, req)
            
            # Atualiza a lista oficial de uma tacada só
            self.lista_saida[:] = []
            self.lista_saida.extend(buffer)
            
        logger.info(f"ORQUESTRADOR: Req {req['id']} -> Servidor {req['servidor_trabalho']}")

    # Tira trabalho de quem tá cheio e manda pra quem tá livre
    def balancear_carga(self):
        # Bloqueia tudo para possivel alteração
        with self.mutex:
            # Conta quantas tarefas cada um tem
            cargas = {i: 0 for i in range(1, self.config['num_servidores'] + 1)}
            for t in self.lista_saida:
                # Só conta se o worker ainda não pegou a tarefa
                if t['servidor_trabalho'] in cargas:
                    cargas[t['servidor_trabalho']] += 1
            
            if not cargas: return
            
            # Acha o mais cheio e o mais vazio
            max_s = max(cargas, key=cargas.get)
            min_s = min(cargas, key=cargas.get)
            
            # Se a diferença for grande (>1), move a tarefa
            if cargas[max_s] - cargas[min_s] > 1:
                for i in range(len(self.lista_saida)):
                    t = self.lista_saida[i]
                    if t['servidor_trabalho'] == max_s:
                        t['servidor_trabalho'] = min_s # Troca o dono
                        self.lista_saida[i] = t # Salva
                        logger.info(f"BALANCEAMENTO: Req {t['id']} movida de S{max_s} para S{min_s}")
                        break

    def iniciar(self):
        logger.info(f"ORQUESTRADOR: Online (Política: {self.config['politica']})")
        while True:
            self.processar_entrada()
            self.balancear_carga()
            time.sleep(0.05) # Respira pra não travar a CPU

def run_orquestrador(l_in, l_out, cfg, mut):
    Orquestrador(l_in, l_out, cfg, mut).iniciar()

# Classe - WORKER 
def run_worker(id, lista_saida, lista_concluidas, stats_cpu, config, mutex):
    logger.info(f"WORKER {id}: Pronto pro trabalho.")
    tempo_trabalhado = 0.0 
    
    while True:
        tarefa = None
        
        # Novamente bloqueia e pega uma tarefa da fila
        with mutex:
            for i, t in enumerate(lista_saida):
                if t['servidor_trabalho'] == id:
                    tarefa = lista_saida.pop(i) # Pega pra mim
                    break
        
        if tarefa:
            # Decide quanto tempo vai rodar agora
            restante = tarefa['tempo_restante']
            
            if config['politica'] == 'RR':
                tempo_turno = min(restante, config['quantum']) 
            else:
                tempo_turno = restante # Vai até o fim para algoritmos não preemptivos

            logger.info(f"WORKER {id}: Rodando Req {tarefa['id']} ({tempo_turno:.1f}s)...")
            time.sleep(tempo_turno) # Simula o trabalho pesado
            

            tempo_trabalhado += tempo_turno
            tarefa['tempo_restante'] -= tempo_turno
            
            # Acabou ou volta pra fila?
            if tarefa['tempo_restante'] <= 0.05:
                tarefa['tempo_fim'] = time.time()
                lista_concluidas.append(tarefa) 
                logger.info(f"WORKER {id}: Req {tarefa['id']} FINALIZADA.")
                
                # Atualiza uso de CPU na memória compartilhada
                stats_cpu[id] = tempo_trabalhado
            else:
                # Ainda esta rodando, quantum acabou
                logger.info(f"WORKER {id}: Req {tarefa['id']} voltando pra fila.")
                with mutex:
                    lista_saida.append(tarefa)
        else:
            time.sleep(0.1) # Descansa se não tiver nada

# Main
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear') 
    print(">>> BSB COMPUTE <<<")
    
    tempo_inicio_simulacao = time.time()

    with Manager() as manager:
        # Cria as estruturas compartilhadas
        mutex = manager.Lock()
        fila_entrada = manager.list()
        fila_trabalho = manager.list()
        lista_concluidas = manager.list() # Histórico
        stats_cpu = manager.dict() # Pra saber quem trabalhou mais
        
        # Cria os Processos
        p_gerador = Process(target=run_gerador, args=(fila_entrada, CONFIG['total_requisicoes']))
        p_orquestrador = Process(target=run_orquestrador, args=(fila_entrada, fila_trabalho, CONFIG, mutex))
        
        workers = []
        for i in range(1, CONFIG['num_servidores'] + 1):
            w = Process(target=run_worker, args=(i, fila_trabalho, lista_concluidas, stats_cpu, CONFIG, mutex))
            workers.append(w)
            
        # Inicia a bagunça
        p_gerador.start()
        p_orquestrador.start()
        for w in workers: w.start()
        
        # Espera o gerador terminar de criar as tarefas
        p_gerador.join()
        
        # Espera até todas as tarefas serem concluídas
        while len(lista_concluidas) < CONFIG['total_requisicoes']:
            time.sleep(1)
            
        print("\n" + "="*50)
        print("Logs de Desempenho: ")
        print("="*50)
        
        tempo_total_sim = time.time() - tempo_inicio_simulacao
        total_tasks = len(lista_concluidas)
        
        soma_resposta = 0
        soma_espera = 0
        max_espera = 0
        
        for t in lista_concluidas:
            # Tempo de Resposta 
            t_resposta = t['tempo_fim'] - t['tempo_chegada']
            soma_resposta += t_resposta
            
            # Tempo de Espera = Resposta - Execução Real
            t_espera = t_resposta - t['tempo_total']
            soma_espera += t_espera
            if t_espera > max_espera: max_espera = t_espera
            
        # Cálculo de CPU
        total_cpu_time = sum(stats_cpu.values())
        capacidade_total = CONFIG['num_servidores'] * tempo_total_sim
        cpu_util = (total_cpu_time / capacidade_total) * 100
        
        print(f"Política Usada: {CONFIG['politica']}")
        print(f"Tarefas Executadas: {total_tasks}")
        print(f"Tempo Total Simulação: {tempo_total_sim:.2f}s")
        print("-" * 30)
        print(f"1. Throughput: {total_tasks / tempo_total_sim:.2f} tarefas/seg")
        print(f"2. Tempo Médio de Resposta: {soma_resposta / total_tasks:.2f}s")
        print(f"3. Taxa de Espera Máxima: {max_espera:.2f}s")
        print(f"4. Utilização Média da CPU: {cpu_util:.1f}%")
        print("="*50)

        # Mata os processos 
        p_orquestrador.terminate()
        for w in workers: w.terminate()
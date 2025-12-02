# ☁️ BSB Compute: Sistema de Orquestração de Tarefas

**Instituição:** CEUB - Centro Universitário de Brasília  
**Curso:** Ciência da Computação
**Disciplina:** Sistemas Operacionais (2025.2)  
**Professor:** Me. Michel Junio Ferreira Rosa  

---

## 📖 Sobre o Projeto
O **BSB Compute** é um simulador de um cluster de inferência distribuído, projetado para gerenciar o agendamento e execução de requisições de Inteligência Artificial (como Visão Computacional, NLP e Processamento de Voz).

O sistema foi desenvolvido para resolver o problema clássico de **sistemas operacionais**: como distribuir recursos finitos (CPU/Tempo) entre múltiplos processos concorrentes de forma justa e eficiente, evitando sobrecarga e condições de corrida (*Race Conditions*).

### 🎯 Objetivos Atendidos
1.  **Simulação de Paralelismo Real:** Uso de `multiprocessing` para criar processos independentes e isolados.
2.  **Comunicação entre Processos (IPC):** Uso de memória compartilhada (`Manager`) e primitivas de sincronização.
3.  **Políticas de Escalonamento:** Implementação de algoritmos clássicos (RR, SJF e Prioridade).
4.  **Robustez:** Prevenção de conflitos de acesso à memória.

---

## ⚙️ Arquitetura do Sistema

O sistema opera no modelo **Produtor-Consumidor** com um orquestrador intermediário, dividido em três módulos principais:

### 1. Gerador de Cargas 
* Simula a chegada aleatória de requisições.
* Define atributos como `Prioridade` (1-3), `Tempo de Execução` estimado e `Tipo` da tarefa.
* Deposita as tarefas na **Fila de Entrada** (Shared Memory).

### 2. Orquestrador 
Responsável pela gestão centralizada do cluster. Executa dois papéis fundamentais:
* **Escalonador (Dispatcher):** Retira tarefas da entrada e as atribui aos servidores seguindo a política configurada.
* **Balanceador de Carga (Load Balancer):** Monitora em tempo real o tamanho da fila de cada Worker. Se detecta desequilíbrio (diferença > 1 tarefa), migra processos pendentes do servidor sobrecarregado para o ocioso.

### 3. Workers (Servidores)
Processos que simulam a CPU.
* Consomem tarefas da sua fila dedicada.
* Respeitam regras de **Preempção** (se a política for Round Robin).
* Registram estatísticas de uso e tempo de resposta.

---

## 🧠 Funcionalidades Técnicas 

### 🚦 Políticas de Escalonamento
O comportamento do sistema é definido pela variável `CONFIG` no código:

* **Round Robin (RR) com Quantum:**
    * Distribui tarefas ciclicamente (1 → 2 → 3 → 1).
    * Aplica um **Quantum** (fatia de tempo, ex: 2.0s).
    * Se a tarefa não termina no tempo limite, ela sofre preempção e volta para o fim da fila.
* **SJF (Shortest Job First):**
    * O Orquestrador insere tarefas na fila de forma ordenada.
    * Tarefas mais curtas "furam a fila" e são executadas antes, minimizando o tempo médio de espera.
* **Prioridade:**
    * Tarefas de alta prioridade (Valor 1) são inseridas à frente das de baixa prioridade (Valor 3).

### 🔒 Sincronização e Robustez (Mutex)
Para garantir a integridade dos dados em um ambiente concorrente, foi implementado um **Mutex (Lock Global)**.
* **Problema Resolvido:** Evita *Race Conditions* (Condição de Corrida) onde dois Workers poderiam tentar retirar a mesma tarefa da fila simultaneamente, ou o Orquestrador tentar reordenar uma lista enquanto ela está sendo lida.
* **Implementação:** Regiões críticas (acesso a filas compartilhadas) são protegidas pelo bloco `with mutex:`.

---

## 📊 Métricas e Relatório
Ao final da execução, o sistema gera um relatório detalhado contendo:

1.  **Throughput:** Capacidade de processamento (Tarefas/segundo).
2.  **Tempo Médio de Resposta (Turnaround):** Tempo total desde a chegada até a conclusão.
3.  **Taxa de Espera Máxima:** Pior caso de espera na fila.
4.  **Utilização de CPU:** Porcentagem de tempo que os servidores passaram processando vs. ociosos.

---

## 🚀 Como Executar

### Pré-requisitos
* Python 3.8+
* Git

### Passo a Passo

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/SEU_USUARIO/Projeto_SO_BSB_Compute.git](https://github.com/SEU_USUARIO/Projeto_SO_BSB_Compute.git)
    cd Projeto_SO_BSB_Compute
    ```

2.  **Configure a Simulação (Opcional):**
    Abra o arquivo `main.py` e edite o dicionário `CONFIG`:
    ```python
    CONFIG = {
        'num_servidores': 3,    # Quantidade de Workers
        'politica': 'RR',       # 'RR', 'SJF' ou 'Prioridade'
        'quantum': 2.0,         # Tempo limite (apenas para RR)
        'total_requisicoes': 15 # Duração do teste
    }
    ```

3.  **Rode o projeto:**
    ```bash
    python main.py
    ```
---
*Projeto desenvolvido para a disciplina de Sistemas Operacionais - 2025.2*
